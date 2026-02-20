"""
Orders Management System with Function Calling
Handles order placement, tracking, and inventory updates
"""

import os
import logging
from typing import Dict, List, Optional
from datetime import datetime
from supabase import Client


class OrderManager:
    """Manages customer orders and inventory"""
    
    def __init__(self, supabase_client: Client, product_kb):
        self.supabase = supabase_client
        self.product_kb = product_kb
        self.logger = logging.getLogger(__name__)
    
    def place_order(self, user_id: str, product_id: int, quantity: int = 1,
                    customer_name: Optional[str] = None, customer_phone: Optional[str] = None,
                    delivery_address: Optional[str] = None) -> Dict:
        try:
            product = self.product_kb.get_product_by_id(product_id)
            if not product:
                return {"success": False, "error": "Product not found"}
            if product['stock_quantity'] < quantity:
                return {"success": False, "error": f"Insufficient stock. Available: {product['stock_quantity']}"}
            
            total_price = float(product['price']) * quantity
            order_number = self._generate_order_number()
            
            self.supabase.table('orders').insert({
                "order_number": order_number, "user_id": user_id, "product_id": product_id,
                "quantity": quantity, "total_price": total_price, "status": "pending",
                "customer_name": customer_name, "customer_phone": customer_phone,
                "delivery_address": delivery_address
            }).execute()
            
            self.product_kb.update_stock(product_id, product['stock_quantity'] - quantity)
            self.logger.info(f"Order placed: {order_number}", extra={"user_id": user_id})
            
            return {
                "success": True, "order_number": order_number,
                "product_name": product['name'], "quantity": quantity,
                "total_price": total_price, "status": "pending"
            }
        except Exception as e:
            self.logger.error(f"Order placement error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    def check_stock(self, product_id: int) -> Dict:
        try:
            product = self.product_kb.get_product_by_id(product_id)
            if not product:
                return {"success": False, "error": "Product not found"}
            return {
                "success": True, "product_name": product['name'],
                "stock_quantity": product['stock_quantity'],
                "in_stock": product['stock_quantity'] > 0,
                "price": float(product['price'])
            }
        except Exception as e:
            self.logger.error(f"Stock check error: {e}")
            return {"success": False, "error": str(e)}
    
    def get_order_status(self, order_number: str) -> Dict:
        try:
            order = self.supabase.table('orders').select('*, products(name, brand)') \
                .eq('order_number', order_number).single().execute().data
            return {
                "success": True, "order_number": order['order_number'],
                "product_name": order['products']['name'], "brand": order['products']['brand'],
                "quantity": order['quantity'], "total_price": float(order['total_price']),
                "status": order['status'], "created_at": order['created_at']
            }
        except Exception as e:
            self.logger.error(f"Order status error: {e}")
            return {"success": False, "error": "Order not found"}
    
    def get_user_orders(self, user_id: str, limit: int = 5) -> List[Dict]:
        try:
            return self.supabase.table('orders').select('*, products(name, brand)') \
                .eq('user_id', user_id).order('created_at', desc=True).limit(limit).execute().data
        except Exception as e:
            self.logger.error(f"Get user orders error: {e}")
            return []
    
    def update_order_status(self, order_number: str, status: str) -> bool:
        try:
            self.supabase.table('orders').update({
                "status": status, "updated_at": datetime.now().isoformat()
            }).eq('order_number', order_number).execute()
            return True
        except Exception as e:
            self.logger.error(f"Update order status error: {e}")
            return False
    
    def _generate_order_number(self) -> str:
        import random
        timestamp = datetime.now().strftime("%Y%m%d")
        random_part = ''.join([str(random.randint(0, 9)) for _ in range(5)])
        return f"ORD-{timestamp}-{random_part}"
    
    def format_order_confirmation(self, order: Dict, language: str = "english") -> str:
        if not order.get('success'):
            msgs = {
                "english": f"❌ Order failed: {order.get('error', 'Unknown error')}",
                "urdu": f"❌ آرڈر ناکام: {order.get('error', 'نامعلوم خرابی')}",
                "roman_urdu": f"❌ Order fail: {order.get('error', 'Unknown error')}"
            }
            return msgs.get(language, msgs["english"])
        
        templates = {
            "english": f"""✅ Order Placed Successfully!

📦 Order: {order['order_number']}
📱 Product: {order['product_name']}
🔢 Quantity: {order['quantity']}
💰 Total: Rs. {order['total_price']:,.0f}
📍 Status: {order['status'].title()}

We'll contact you soon for delivery!
Thank you for shopping with TechZone! 🎉""",
            "urdu": f"""✅ آرڈر کامیابی سے مکمل!

📦 آرڈر: {order['order_number']}
📱 پروڈکٹ: {order['product_name']}
🔢 مقدار: {order['quantity']}
💰 کل: روپے {order['total_price']:,.0f}
📍 حالت: {order['status']}

ہم جلد ڈیلیوری کے لیے رابطہ کریں گے!""",
            "roman_urdu": f"""✅ Order kamyabi se complete!

📦 Order: {order['order_number']}
📱 Product: {order['product_name']}
🔢 Quantity: {order['quantity']}
💰 Total: Rs. {order['total_price']:,.0f}
📍 Status: {order['status']}

Hum jald delivery ke liye rabta karein ge!
TechZone se shopping ke liye shukriya! 🎉"""
        }
        return templates.get(language, templates["english"])
    
    def format_order_status(self, order: Dict, language: str = "english") -> str:
        if not order.get('success'):
            msgs = {
                "english": "❌ Order not found. Please check your order number.",
                "urdu": "❌ آرڈر نہیں ملا۔ براہ کرم اپنا آرڈر نمبر چیک کریں۔",
                "roman_urdu": "❌ Order nahi mila. Order number check karein."
            }
            return msgs.get(language, msgs["english"])
        
        status_emoji = {"pending": "⏳", "confirmed": "✅", "processing": "📦",
                        "shipped": "🚚", "delivered": "✅", "cancelled": "❌"}
        emoji = status_emoji.get(order['status'], "📋")
        
        templates = {
            "english": f"""{emoji} Order Status

📦 Order: {order['order_number']}
📱 Product: {order['product_name']} ({order['brand']})
🔢 Quantity: {order['quantity']}
💰 Total: Rs. {order['total_price']:,.0f}
📍 Status: {order['status'].title()}
📅 Ordered: {order['created_at'][:10]}""",
            "roman_urdu": f"""{emoji} Order Status

📦 Order: {order['order_number']}
📱 Product: {order['product_name']}
🔢 Quantity: {order['quantity']}
💰 Total: Rs. {order['total_price']:,.0f}
📍 Status: {order['status']}"""
        }
        return templates.get(language, templates["english"])


FUNCTION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "place_order",
            "description": "Place an order for a product",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "integer", "description": "The ID of the product to order"},
                    "quantity": {"type": "integer", "description": "Quantity to order", "default": 1}
                },
                "required": ["product_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_stock",
            "description": "Check if a product is in stock",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "integer", "description": "The ID of the product to check"}
                },
                "required": ["product_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_order_status",
            "description": "Get the status of an order",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_number": {"type": "string", "description": "The order number to look up"}
                },
                "required": ["order_number"]
            }
        }
    }
]
