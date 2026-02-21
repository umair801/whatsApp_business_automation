"""
Escalation Workflow Engine
Handles notification, DB flagging, and response generation for escalations
"""

import logging
from datetime import datetime
from typing import Optional
from openai import OpenAI
from sentiment_analyzer import SentimentResult

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Escalation Response Templates
# ─────────────────────────────────────────────

ESCALATION_RESPONSES = {
    "english": """I sincerely apologize for the frustration you're experiencing. 
        This is not the experience we want for our valued customers.

        I'm immediately escalating your case to our senior support team. 
        A human agent will contact you within **15 minutes**.

        Your case reference: **{case_id}**

        Is there anything specific you'd like me to note for our team?""",

    "urdu": """ہم آپ کی پریشانی کے لیے معذرت خواہ ہیں۔
        آپ کا معاملہ فوری طور پر ہمارے سینئر سپورٹ ٹیم کو بھیجا جا رہا ہے۔
        ایک ہیومن ایجنٹ 15 منٹ میں آپ سے رابطہ کرے گا۔
        آپ کا کیس نمبر: {case_id}""",

    "roman_urdu": """Hum aapki takleef ke liye maafi chahte hain.
        Aapka masla abhi hamare senior team ko bheja ja raha hai.
        Ek human agent 15 minute mein aapse contact karega.
        Aapka case number: {case_id}"""
}


def generate_case_id(phone_number: str) -> str:
    """Generate a unique case ID for tracking."""
    timestamp = datetime.now().strftime("%Y%m%d%H%M")
    suffix = phone_number[-4:]
    return f"ESC-{timestamp}-{suffix}"


def handle_escalation(
    client: OpenAI,
    phone_number: str,
    sentiment_result: SentimentResult,
    conversation_history: list[dict],
    language: str,
    supabase_client=None
) -> str:
    """
    Full escalation workflow:
    1. Generate case ID
    2. Log to database
    3. Send alert (simulated)
    4. Return empathetic response
    """

    case_id = generate_case_id(phone_number)

    # Log escalation event
    _log_escalation_event(
        phone_number=phone_number,
        case_id=case_id,
        sentiment_result=sentiment_result,
        supabase_client=supabase_client
    )

    # Simulate sending alert (replace with real Slack/email in production)
    _send_escalation_alert(
        phone_number=phone_number,
        case_id=case_id,
        reason=sentiment_result.escalation_reason,
        sentiment_score=sentiment_result.score
    )

    # Generate response in correct language
    lang_key = "english"
    if language == "urdu":
        lang_key = "urdu"
    elif language == "roman_urdu":
        lang_key = "roman_urdu"

    response = ESCALATION_RESPONSES[lang_key].format(case_id=case_id)

    logger.info(f"Escalation handled | case_id={case_id} | phone={phone_number[-4:]}****")
    return response


def _log_escalation_event(
    phone_number: str,
    case_id: str,
    sentiment_result: SentimentResult,
    supabase_client=None
) -> None:
    """Log escalation to Supabase (or local log if DB unavailable)."""

    escalation_data = {
        "case_id": case_id,
        "phone_number": phone_number,
        "sentiment_score": sentiment_result.score,
        "sentiment_label": sentiment_result.label,
        "escalation_reason": sentiment_result.escalation_reason,
        "triggers": sentiment_result.triggers,
        "timestamp": datetime.utcnow().isoformat()
    }

    if supabase_client:
        try:
            supabase_client.table("escalation_events").insert(escalation_data).execute()
            logger.info(f"Escalation logged to DB | case_id={case_id}")
        except Exception as e:
            logger.error(f"Failed to log escalation to DB: {e}")
            logger.info(f"Escalation data (local): {escalation_data}")
    else:
        # Fallback: structured log (still captured by your logging system)
        logger.warning(f"ESCALATION_EVENT | {escalation_data}")


def _send_escalation_alert(
    phone_number: str,
    case_id: str,
    reason: Optional[str],
    sentiment_score: float
) -> None:
    """
    Send escalation alert to support team.
    Production: integrate Slack webhook or SendGrid email here.
    """
    alert_message = (
        f"🚨 ESCALATION ALERT\n"
        f"Case ID: {case_id}\n"
        f"Customer: {phone_number[-4:]}****\n"
        f"Sentiment Score: {sentiment_score:.2f}\n"
        f"Reason: {reason}\n"
        f"Time: {datetime.utcnow().isoformat()}"
    )

    # Production: Replace this with actual Slack/email integration
    # Example Slack: requests.post(SLACK_WEBHOOK_URL, json={"text": alert_message})
    logger.warning(f"ALERT_NOTIFICATION | {alert_message}")
    print(f"\n{'='*50}\n{alert_message}\n{'='*50}\n")