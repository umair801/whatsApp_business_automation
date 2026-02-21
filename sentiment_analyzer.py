"""
Enterprise Sentiment Analysis & Complaint Escalation System
Detects customer frustration and triggers automated escalation workflows
"""

import re
import json
import logging
from datetime import datetime
from typing import Optional
from openai import OpenAI
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Data Models
# ─────────────────────────────────────────────

@dataclass
class SentimentResult:
    score: float          # -1.0 (very negative) to +1.0 (very positive)
    label: str            # angry | negative | neutral | positive | very_positive
    confidence: float     # 0.0 to 1.0
    triggers: list[str]   # specific phrases that triggered the score
    should_escalate: bool
    escalation_reason: Optional[str] = None

@dataclass
class ConversationSentimentTracker:
    phone_number: str
    scores: list[float] = field(default_factory=list)
    negative_streak: int = 0
    escalated: bool = False
    total_messages: int = 0

# ─────────────────────────────────────────────
# Escalation Configuration (tune per client)
# ─────────────────────────────────────────────

ESCALATION_CONFIG = {
    "single_message_threshold": -0.7,   # Escalate immediately if score below this
    "average_score_threshold": -0.5,    # Escalate if avg of last 3 messages below this
    "negative_streak_limit": 2,          # Escalate after N consecutive negative messages
    "urgent_keywords": [
        "fraud", "scam", "cheat", "lawsuit", "lawyer", "police", "refund now",
        "fraud kar rahe", "dhoka", "police ko bataunga", "court", "consumer court",
        "stolen", "thief", "worst", "terrible", "unacceptable", "disgusting",
        "fraud kar", "dhoka diya", "chor", "bakwas", "bekar", "ghatiya",
        "paisa wapas", "return karo", "refund karo", "complaint karunga",
        "tum log", "yeh sab fraud", "jhoot", "fake"
    ],
    "distress_keywords": [
        "emergency", "urgent", "immediately", "right now", "cant wait",
        "jaldi", "abhi", "zaroor", "please help", "desperate"
    ]
}

# ─────────────────────────────────────────────
# In-memory tracker (replace with Redis in production)
# ─────────────────────────────────────────────

_conversation_trackers: dict[str, ConversationSentimentTracker] = {}


def get_tracker(phone_number: str) -> ConversationSentimentTracker:
    if phone_number not in _conversation_trackers:
        _conversation_trackers[phone_number] = ConversationSentimentTracker(
            phone_number=phone_number
        )
    return _conversation_trackers[phone_number]


# ─────────────────────────────────────────────
# Rule-Based Pre-Check (fast, no API call)
# ─────────────────────────────────────────────

def check_urgent_keywords(message: str) -> tuple[bool, list[str]]:
    """Quick scan for urgent/abusive keywords before calling AI."""
    message_lower = message.lower()
    found_urgent = [kw for kw in ESCALATION_CONFIG["urgent_keywords"] if kw in message_lower]
    return len(found_urgent) > 0, found_urgent


# ─────────────────────────────────────────────
# AI Sentiment Analysis
# ─────────────────────────────────────────────

def analyze_sentiment(
    client: OpenAI,
    message: str,
    conversation_history: list[dict],
    phone_number: str
) -> SentimentResult:
    """
    Hybrid sentiment analysis:
    1. Rule-based keyword check (instant)
    2. AI analysis with conversation context
    3. Escalation decision based on history
    """

    # Step 1: Fast keyword check
    is_urgent, urgent_triggers = check_urgent_keywords(message)

    # Step 2: AI sentiment scoring
    history_summary = ""
    if len(conversation_history) > 2:
        last_3 = conversation_history[-4:-1]  # last 3 customer messages
        history_summary = f"Recent conversation context: {json.dumps(last_3[-3:])}"

    prompt = f"""Analyze the sentiment of this customer message in a business context.
        The customer may write in English, Urdu, or Roman Urdu (Pakistani dialect).

        Message: "{message}"
        {history_summary}

        Respond ONLY with valid JSON in this exact format:
        {{
        "score": <float between -1.0 and 1.0>,
        "label": "<angry|negative|neutral|positive|very_positive>",
        "confidence": <float between 0.0 and 1.0>,
        "key_phrases": ["phrase1", "phrase2"],
        "reasoning": "<one sentence>"
        }}

        Scoring guide:
        - angry (-1.0 to -0.7): threats, insults, extreme frustration, complaints about fraud
        - negative (-0.7 to -0.3): dissatisfied, complaining, frustrated
        - neutral (-0.3 to 0.3): informational, questions, normal requests
        - positive (0.3 to 0.7): satisfied, happy, thankful
        - very_positive (0.7 to 1.0): delighted, enthusiastic, praising"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=200
        )

        raw = response.choices[0].message.content.strip()
        # Clean potential markdown fences
        raw = re.sub(r"```json|```", "", raw).strip()
        data = json.loads(raw)

        score = float(data.get("score", 0.0))
        label = data.get("label", "neutral")
        confidence = float(data.get("confidence", 0.8))
        key_phrases = data.get("key_phrases", [])

        # Merge AI findings with keyword triggers
        all_triggers = list(set(key_phrases + urgent_triggers))

        # Override if urgent keywords found
        if is_urgent:
            score = min(score, -0.75)
            label = "angry"

    except Exception as e:
        logger.error(f"Sentiment AI call failed: {e}")
        # Fallback: use keyword-only detection
        score = -0.8 if is_urgent else 0.0
        label = "angry" if is_urgent else "neutral"
        confidence = 0.6
        all_triggers = urgent_triggers

    # Step 3: Update conversation tracker
    tracker = get_tracker(phone_number)
    tracker.scores.append(score)
    tracker.total_messages += 1

    if score < -0.3:
        tracker.negative_streak += 1
    else:
        tracker.negative_streak = 0

    # Step 4: Escalation decision
    should_escalate, escalation_reason = _evaluate_escalation(
        score, tracker, is_urgent
    )

    if should_escalate and not tracker.escalated:
        tracker.escalated = True

    logger.info(f"Sentiment analysis | phone={phone_number[-4:]}**** | "
                f"score={score:.2f} | label={label} | escalate={should_escalate}")

    return SentimentResult(
        score=score,
        label=label,
        confidence=confidence,
        triggers=all_triggers,
        should_escalate=should_escalate,
        escalation_reason=escalation_reason
    )


def _evaluate_escalation(
    current_score: float,
    tracker: ConversationSentimentTracker,
    is_urgent: bool
) -> tuple[bool, Optional[str]]:
    """Multi-factor escalation logic."""

    # Already escalated -- don't double-escalate
    if tracker.escalated:
        return False, None

    # Rule 1: Immediate escalation for very angry messages
    if current_score <= ESCALATION_CONFIG["single_message_threshold"]:
        return True, f"High-anger message detected (score: {current_score:.2f})"

    # Rule 2: Urgent keyword detected
    if is_urgent:
        return True, "Urgent/threatening keyword detected"

    # Rule 3: Sustained negativity (average of last 3)
    if len(tracker.scores) >= 3:
        recent_avg = sum(tracker.scores[-3:]) / 3
        if recent_avg <= ESCALATION_CONFIG["average_score_threshold"]:
            return True, f"Sustained negative sentiment (avg: {recent_avg:.2f})"

    # Rule 4: Negative streak
    if tracker.negative_streak >= ESCALATION_CONFIG["negative_streak_limit"]:
        return True, f"Consecutive negative messages ({tracker.negative_streak} in a row)"

    return False, None