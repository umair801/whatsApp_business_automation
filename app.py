"""
app.py
Enterprise WhatsApp Business Automation System
TechZone - Production-Ready AI Agent
"""

import os
import logging
import json
import re
import time
from flask import Flask, request
from dotenv import load_dotenv
from openai import OpenAI
from twilio.twiml.messaging_response import MessagingResponse
from supabase import create_client, Client
from datetime import datetime

# Import custom modules
from logging_config import setup_logging
from health_checks import health_bp
from redis_cache import RedisCache
from product_knowledge import ProductKnowledgeBase
from order_manager import OrderManager, FUNCTION_TOOLS

from sentiment_analyzer import analyze_sentiment
from escalation_handler import handle_escalation

from flask import render_template, make_response, jsonify, redirect
from analytics import AnalyticsEngine
from export_manager import ExportManager

from auth_manager import auth_manager, jwt_required, dashboard_login_required

from websocket_manager import socketio, ws_manager

# Startup validation
from startup_check import check_environment, ensure_knowledge_base

load_dotenv()

# Setup structured logging
logger = setup_logging(log_level=os.getenv("LOG_LEVEL", "INFO"))

# Validate environment on boot
check_environment()

# Initialize clients
try:
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    logger.info("OpenAI client initialized")
except Exception as e:
    logger.error(f"Failed to initialize OpenAI client: {e}")
    raise

try:
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    supabase: Client = create_client(supabase_url, supabase_key)
    logger.info("Supabase client initialized")
except Exception as e:
    logger.error(f"Failed to initialize Supabase client: {e}")
    raise

# Initialize Redis cache (Railway-safe: graceful fallback if unavailable)
redis_cache = RedisCache(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379))
)

# Initialize Product Knowledge Base and Order Manager
product_kb = ProductKnowledgeBase(openai_client, supabase)
order_manager = OrderManager(supabase, product_kb)
logger.info("Product Knowledge Base and Order Manager initialized")

# Ensure ChromaDB is populated (handles Railway cold starts)
ensure_knowledge_base(product_kb)

# Flask app
app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False
app.config['SECRET_KEY'] = os.getenv('JWT_SECRET', 'change-this-secret')

# Register health check blueprint
app.register_blueprint(health_bp)

# Attach SocketIO to Flask app
socketio.init_app(app)


# ============================================
# DATABASE MEMORY MANAGER
# ============================================

class DatabaseMemoryManager:
    """Stores conversation history in Supabase with Redis caching"""

    def __init__(self, supabase_client, redis_cache):
        self.supabase = supabase_client
        self.cache = redis_cache
        self.logger = logging.getLogger(__name__)

    def get_history(self, user_id: str, limit: int = 10) -> list:
        cached_history = self.cache.get_conversation_history(user_id)
        if cached_history:
            return cached_history[:limit]

        try:
            response = self.supabase.table('conversations') \
                .select('*') \
                .eq('user_id', user_id) \
                .order('created_at', desc=True) \
                .limit(limit) \
                .execute()

            messages = response.data[::-1]
            history = []
            for msg in messages:
                history.append({
                    "role": msg['role'],
                    "content": msg['message']
                })

            self.cache.set_conversation_history(user_id, history)
            self.logger.info(
                "Retrieved conversation history from database",
                extra={"user_id": user_id, "message_count": len(history)}
            )
            return history

        except Exception as e:
            self.logger.error(f"Error getting history: {e}", extra={"user_id": user_id}, exc_info=True)
            return []

    def add_message(self, user_id: str, role: str, content: str) -> bool:
        try:
            self.supabase.table('conversations').insert({
                "user_id": user_id,
                "message": content,
                "role": role,
                "created_at": datetime.now().isoformat()
            }).execute()

            self.cache.invalidate_conversation(user_id)
            self.logger.info("Message saved to database", extra={"user_id": user_id, "role": role})
            return True

        except Exception as e:
            self.logger.error(f"Error saving message: {e}", extra={"user_id": user_id}, exc_info=True)
            return False


# ============================================
# AGENT CLASSES
# ============================================

class LanguageAgent:
    """Detects language with logging"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def detect(self, text: str) -> str:
        start_time = time.time()

        for char in text:
            if '\u0600' <= char <= '\u06FF':
                language = "urdu"
                self._log_detection(text, language, start_time)
                return language

        roman_urdu_words = [
            'kya', 'hai', 'nahi', 'aap', 'mujhe', 'kitna',
            'kahan', 'kab', 'kyun', 'kaise', 'haan', 'jee',
            'ki', 'ka', 'ke', 'mein', 'se', 'ko', 'chahiye',
            'bhai', 'yaar', 'theek', 'acha', 'batao', 'dikhao',
            'lena', 'chahta', 'chahti', 'order'
        ]

        words = text.lower().split()
        if not words:
            return "english"

        urdu_count = sum(1 for word in words if word in roman_urdu_words)
        language = "roman_urdu" if urdu_count / len(words) > 0.25 else "english"

        self._log_detection(text, language, start_time)
        return language

    def _log_detection(self, text: str, language: str, start_time: float):
        response_time = (time.time() - start_time) * 1000
        self.logger.info(
            "Language detected",
            extra={"language": language, "text_length": len(text), "response_time": round(response_time, 2)}
        )


class IntentAgent:
    """Classifies intent with logging"""

    def __init__(self, client):
        self.client = client
        self.logger = logging.getLogger(__name__)

    def classify(self, text: str) -> str:
        start_time = time.time()

        prompt = f"""Classify into ONE intent:
            - greeting
            - product_inquiry (asking about specific products)
            - product_search (searching for products by criteria)
            - place_order (user wants to buy/order something)
            - check_stock (asking if product is available)
            - order_status (asking about their order)
            - price_inquiry
            - business_hours
            - complaint
            - human_request
            - personal_question

            Message: "{text}"

            Reply with ONLY the intent name."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )
            intent = response.choices[0].message.content.strip()

            response_time = (time.time() - start_time) * 1000
            self.logger.info(
                "Intent classified",
                extra={"intent": intent, "response_time": round(response_time, 2)}
            )
            return intent

        except Exception as e:
            self.logger.error(f"Intent classification failed: {e}", exc_info=True)
            return "greeting"


class ResponseAgent:
    """Generates responses with RAG and function calling"""

    def __init__(self, client, memory_manager, product_kb, order_manager):
        self.client = client
        self.memory = memory_manager
        self.product_kb = product_kb
        self.order_manager = order_manager
        self.logger = logging.getLogger(__name__)

    def generate(self, intent: str, language: str, user_message: str, user_id: str) -> str:
        start_time = time.time()

        if intent in ["product_inquiry", "product_search", "price_inquiry"]:
            response = self._handle_product_query(user_message, language)
        elif intent in ["place_order", "check_stock", "order_status"]:
            response = self._handle_order_intent(intent, user_message, language, user_id)
        elif intent in ["personal_question", "complaint"]:
            response = self._generate_with_context(language, user_message, user_id)
        else:
            response = self._get_template_response(intent, language)

        response_time = (time.time() - start_time) * 1000
        self.logger.info(
            "Response generated",
            extra={
                "intent": intent,
                "language": language,
                "response_time": round(response_time, 2),
                "response_length": len(response)
            }
        )
        return response

    def _handle_order_intent(self, intent: str, query: str, language: str, user_id: str) -> str:
        id_match = re.search(r'ID:?\s*(\d+)', query, re.IGNORECASE)

        if id_match and intent == "place_order":
            product_id = int(id_match.group(1))
            result = self.order_manager.place_order(user_id=user_id, product_id=product_id, quantity=1)
            return self.order_manager.format_order_confirmation(result, language)

        try:
            messages = [
                {"role": "system", "content": "You are an order assistant. Extract order details from user messages."},
                {"role": "user", "content": query}
            ]

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=FUNCTION_TOOLS,
                tool_choice="auto"
            )

            message = response.choices[0].message

            if message.tool_calls:
                tool_call = message.tool_calls[0]
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)

                if function_name == "place_order":
                    result = self.order_manager.place_order(
                        user_id=user_id,
                        product_id=function_args['product_id'],
                        quantity=function_args.get('quantity', 1)
                    )
                    return self.order_manager.format_order_confirmation(result, language)

                elif function_name == "check_stock":
                    result = self.order_manager.check_stock(function_args['product_id'])
                    if result['success']:
                        in_stock = "✅ In Stock" if result['in_stock'] else "❌ Out of Stock"
                        return f"{result['product_name']}\n{in_stock}\nQuantity: {result['stock_quantity']}\nPrice: Rs. {result['price']:,.0f}"
                    return result['error']

                elif function_name == "get_order_status":
                    result = self.order_manager.get_order_status(function_args['order_number'])
                    return self.order_manager.format_order_status(result, language)

            if intent == "order_status":
                status_messages = {
                    "english": "📦 To check your order status, please share your order number (e.g. ORD-12345). You would have received it after placing your order.",
                    "urdu": "📦 آرڈر کی تفصیل کے لیے اپنا آرڈر نمبر شیئر کریں (مثلاً ORD-12345)۔",
                    "roman_urdu": "📦 Order check karne ke liye apna order number batain (e.g. ORD-12345). Yeh aapko order ke baad mila hoga."
                }
                return status_messages.get(language, status_messages["english"])

            help_messages = {
                "english": "Please tell me the product name or show me products first, then I can help you order!",
                "roman_urdu": "Pehle product ka naam batain ya products dikhain, phir order kar saktay hain!"
            }
            return help_messages.get(language, help_messages["english"])

        except Exception as e:
            self.logger.error(f"Order intent error: {e}", exc_info=True)
            return "Sorry, I encountered an error processing your request."

    def _handle_product_query(self, query: str, language: str) -> str:
        try:
            category = self._extract_category(query)
            max_price = self._extract_price(query)

            products = self.product_kb.search_products(query, category=category, max_price=max_price, limit=5)
            response = self.product_kb.format_product_response(products, language)

            if products:
                order_hints = {
                    "english": "\n\n💡 To order, say: 'I want product number X'",
                    "roman_urdu": "\n\n💡 Order karne ke liye: 'Mujhe number X chahiye'"
                }
                response += order_hints.get(language, "")

            return response

        except Exception as e:
            self.logger.error(f"Product query error: {e}")
            return "Sorry, I encountered an error searching products."

    def _extract_category(self, query: str) -> str:
        query_lower = query.lower()
        accessory_keywords = ['headphone', 'earphone', 'earbud', 'airpod', 'mouse', 'keyboard', 'ssd', 'accessory']
        if any(word in query_lower for word in accessory_keywords):
            return "accessory"
        if any(word in query_lower for word in ['laptop', 'notebook']):
            return "laptop"
        if any(word in query_lower for word in ['phone', 'mobile', 'smartphone', 'iphone', 'galaxy', 'redmi']):
            return "phone"
        return None

    def _extract_price(self, query: str) -> float:
        patterns = [r'under (\d+)k', r'below (\d+)k', r'less than (\d+)k', r'under (\d+)', r'below (\d+)']
        for pattern in patterns:
            match = re.search(pattern, query.lower())
            if match:
                price = int(match.group(1))
                if 'k' in pattern:
                    price *= 1000
                return float(price)
        return None

    def _get_template_response(self, intent: str, language: str) -> str:
        responses = {
            "greeting": {
                "english": "Hello! 👋 Welcome to TechZone!\n\n💻 Browse laptops\n📱 Check phones\n🎧 See accessories\n🛒 Place orders",
                "urdu": "السلام علیکم! 👋 ٹیک زون میں خوش آمدید!",
                "roman_urdu": "Salam! 👋 TechZone mein khush aamdeed!\n\n💻 Laptops\n📱 Phones\n🎧 Accessories\n🛒 Order karein"
            },
            "business_hours": {
                "english": "⏰ Mon-Sat: 10 AM - 10 PM\nSun: 2 PM - 9 PM\n📍 Mall Road, Lahore",
                "urdu": "⏰ پیر-ہفتہ: صبح 10 سے رات 10\nاتوار: دوپہر 2 سے رات 9",
                "roman_urdu": "⏰ Peer-Haftah: 10 AM - 10 PM\nItwaar: 2 PM - 9 PM"
            },
            "complaint": {
                "english": "Sorry! 😔 Connecting with support.",
                "urdu": "معذرت! 😔 سپورٹ سے رابطہ کر رہے ہیں۔",
                "roman_urdu": "Maazrat! 😔 Support se contact kar rahay hain."
            },
            "human_request": {
                "english": "Sure! 👤 Team will respond in 2-3 minutes.",
                "urdu": "بالکل! 👤 ٹیم 2-3 منٹ میں جواب دے گی۔",
                "roman_urdu": "Bilkul! 👤 Team 2-3 minute mein reply degi."
            }
        }

        intent_responses = responses.get(intent, responses["greeting"])
        return intent_responses.get(language, intent_responses["english"])

    def _generate_with_context(self, language: str, user_message: str, user_id: str) -> str:
        history = self.memory.get_history(user_id, limit=10)

        system_prompts = {
            "english": "You are Ayesha from TechZone Pakistan. Be friendly and remember past conversation.",
            "urdu": "آپ ٹیک زون کی آئشہ ہیں۔ پچھلی بات چیت یاد رکھیں۔",
            "roman_urdu": "Aap TechZone ki Ayesha ho. Pichli conversation yaad rakho."
        }

        messages = [{"role": "system", "content": system_prompts.get(language, system_prompts["english"])}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        try:
            response = self.client.chat.completions.create(model="gpt-4o-mini", messages=messages)
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"Response generation failed: {e}", exc_info=True)
            return "Sorry, I encountered an error. Please try again!"


# ============================================
# ORCHESTRATOR
# ============================================

class AgentOrchestrator:
    """Coordinates all agents including sentiment analysis and escalation"""

    def __init__(self, client, supabase_client, redis_cache, product_kb, order_manager):
        self.client = client
        self.supabase = supabase_client
        self.memory = DatabaseMemoryManager(supabase_client, redis_cache)
        self.language_agent = LanguageAgent()
        self.intent_agent = IntentAgent(client)
        self.response_agent = ResponseAgent(client, self.memory, product_kb, order_manager)
        self.logger = logging.getLogger(__name__)

    def process_message(self, user_message: str, user_id: str) -> str:
        start_time = time.time()

        self.logger.info(
            "Processing message",
            extra={"user_id": user_id, "message_length": len(user_message)}
        )

        try:
            language = self.language_agent.detect(user_message)
            conversation_history = self.memory.get_history(user_id, limit=10)

            sentiment = analyze_sentiment(
                client=self.client,
                message=user_message,
                conversation_history=conversation_history,
                phone_number=user_id
            )

            self.logger.info(
                "Sentiment analyzed",
                extra={
                    "user_id": user_id,
                    "score": sentiment.score,
                    "label": sentiment.label,
                    "should_escalate": sentiment.should_escalate
                }
            )

            if sentiment.should_escalate:
                self.logger.warning(
                    "ESCALATION TRIGGERED",
                    extra={
                        "user_id": user_id,
                        "reason": sentiment.escalation_reason,
                        "score": sentiment.score
                    }
                )

                escalation_response = handle_escalation(
                    client=self.client,
                    phone_number=user_id,
                    sentiment_result=sentiment,
                    conversation_history=conversation_history,
                    language=language,
                    supabase_client=self.supabase
                )

                self.memory.add_message(user_id, "user", user_message)
                self.memory.add_message(user_id, "assistant", escalation_response)

                try:
                    ws_manager.broadcast_escalation(
                        case_id=f"ESC-{datetime.now().strftime('%Y%m%d%H%M')}",
                        phone_number=user_id,
                        reason=sentiment.escalation_reason,
                        score=sentiment.score
                    )
                    ws_manager.broadcast_kpi_update(analytics_engine)
                except Exception as ws_err:
                    self.logger.warning(f"WebSocket broadcast error: {ws_err}")

                return escalation_response

            intent = self.intent_agent.classify(user_message)
            response = self.response_agent.generate(intent, language, user_message, user_id)

            self.memory.add_message(user_id, "user", user_message)
            self.memory.add_message(user_id, "assistant", response)

            try:
                ws_manager.broadcast_new_message(
                    user_id=user_id,
                    language=language,
                    intent=intent,
                    sentiment_label=sentiment.label
                )
                ws_manager.broadcast_kpi_update(analytics_engine)
            except Exception as ws_err:
                self.logger.warning(f"WebSocket broadcast error: {ws_err}")

            total_time = (time.time() - start_time) * 1000
            self.logger.info(
                "Message processed successfully",
                extra={
                    "user_id": user_id,
                    "language": language,
                    "intent": intent,
                    "sentiment_label": sentiment.label,
                    "response_time": round(total_time, 2)
                }
            )

            return response

        except Exception as e:
            self.logger.error(f"Error processing message: {e}", extra={"user_id": user_id}, exc_info=True)
            return "Sorry, I encountered an error. Please try again!"


# Initialize orchestrator
orchestrator = AgentOrchestrator(openai_client, supabase, redis_cache, product_kb, order_manager)

# Initialize analytics engine
analytics_engine = AnalyticsEngine(supabase)

# Initialize export manager
export_manager = ExportManager(analytics_engine)


# ============================================
# WEBHOOK ROUTES
# ============================================

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    """Receive WhatsApp messages from Twilio"""

    if request.method == "GET":
        return "Webhook is ready!", 200

    request_start = time.time()

    try:
        incoming_msg = request.values.get('Body', '').strip()
        from_number = request.values.get('From', '')

        logger.info(
            "Webhook request received",
            extra={"from_number": from_number, "message_length": len(incoming_msg)}
        )

        response_text = orchestrator.process_message(incoming_msg, from_number)

        resp = MessagingResponse()
        resp.message(response_text)

        request_time = (time.time() - request_start) * 1000
        logger.info(
            "Webhook request completed",
            extra={"from_number": from_number, "response_time": round(request_time, 2)}
        )

        return str(resp)

    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        resp = MessagingResponse()
        resp.message("Sorry, I encountered an error. Please try again!")
        return str(resp)


@app.route("/")
def home():
    return {
        "service": "TechZone WhatsApp Business Automation",
        "version": "1.0.0",
        "status": "online",
        "features": [
            "Multi-agent architecture",
            "Persistent memory (Supabase)",
            "Bilingual support (English, Urdu, Roman Urdu)",
            "Production monitoring",
            "Redis caching",
            "RAG product knowledge base",
            "Function calling for orders",
            "Sentiment analysis",
            "Complaint escalation",
            "JWT authentication",
            "Real-time WebSocket dashboard",
            "CSV and PDF export"
        ],
        "endpoints": {
            "webhook": "/webhook",
            "health": "/health",
            "ready": "/health/ready",
            "live": "/health/live",
            "metrics": "/metrics",
            "cache_stats": "/cache/stats",
            "dashboard": "/dashboard",
            "login": "/login"
        }
    }


@app.route("/cache/stats", methods=["GET"])
def cache_stats():
    return redis_cache.get_stats()


# ============================================
# DASHBOARD ROUTES
# ============================================

@app.route("/login", methods=["GET"])
def login_page():
    return render_template("login.html")


@app.route("/api/login", methods=["POST"])
def api_login():
    data     = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not auth_manager.validate_credentials(username, password):
        logger.warning(f"Failed login attempt for user: {username}")
        return jsonify({"error": "Invalid credentials"}), 401

    token = auth_manager.generate_token(username)

    response = make_response(jsonify({
        "token":    token,
        "username": username,
        "expires":  f"{auth_manager.expiry_hrs}h"
    }))
    response.set_cookie(
        "access_token", token,
        httponly=True,
        samesite="Lax",
        max_age=auth_manager.expiry_hrs * 3600
    )
    logger.info(f"Successful login: {username}")
    return response


@app.route("/logout")
def logout():
    response = make_response(redirect("/login"))
    response.delete_cookie("access_token")
    return response


@app.route("/dashboard")
@dashboard_login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/api/dashboard")
@jwt_required
def api_dashboard():
    try:
        data = analytics_engine.get_dashboard_data()
        return data
    except Exception as e:
        logger.error(f"Dashboard API error: {e}")
        return {"error": str(e)}, 500


# ============================================
# EXPORT ROUTES
# ============================================

@app.route("/export/csv/overview")
@dashboard_login_required
def export_csv_overview():
    output = export_manager.export_overview_csv()
    filename = f"techzone_overview_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return app.response_class(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.route("/export/csv/orders")
@dashboard_login_required
def export_csv_orders():
    output = export_manager.export_orders_csv()
    filename = f"techzone_orders_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return app.response_class(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.route("/export/csv/escalations")
@dashboard_login_required
def export_csv_escalations():
    output = export_manager.export_escalations_csv()
    filename = f"techzone_escalations_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return app.response_class(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.route("/export/csv/trends")
@dashboard_login_required
def export_csv_trends():
    output = export_manager.export_trends_csv()
    filename = f"techzone_trends_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return app.response_class(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.route("/export/pdf")
@dashboard_login_required
def export_pdf():
    try:
        buffer = export_manager.export_full_pdf()
        filename = f"techzone_report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        return app.response_class(
            buffer.getvalue(),
            mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"PDF export error: {e}")
        return {"error": str(e)}, 500


# ============================================
# WEBSOCKET EVENT HANDLERS
# ============================================

@socketio.on("connect")
def handle_connect():
    ws_manager.on_connect()


@socketio.on("disconnect")
def handle_disconnect():
    ws_manager.on_disconnect()


@socketio.on("request_kpi")
def handle_kpi_request():
    ws_manager.broadcast_kpi_update(analytics_engine)


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("TechZone Enterprise WhatsApp Automation System")
    logger.info(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    logger.info(f"Log level: {os.getenv('LOG_LEVEL', 'INFO')}")
    logger.info("=" * 60)

    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=False, allow_unsafe_werkzeug=True)
