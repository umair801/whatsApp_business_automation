"""
Analytics Data Layer
Aggregates conversation, sentiment, escalation, and performance metrics
from Supabase for dashboard consumption
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from supabase import Client

logger = logging.getLogger(__name__)


class AnalyticsEngine:
    """Queries Supabase and computes all dashboard metrics"""

    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client

    def get_overview(self) -> dict:
        try:
            customers = self.supabase.table("conversations").select("user_id, role").execute()
            unique_customers = len(set(r["user_id"] for r in customers.data))
            total_messages = sum(1 for r in customers.data if r.get("role") == "user")

            orders = self.supabase.table("orders").select("id, total_price, status").execute()
            total_orders = len(orders.data)
            total_revenue = sum(r.get("total_price", 0) or 0 for r in orders.data)
            pending_orders = sum(1 for r in orders.data if r.get("status") == "pending")

            try:
                escalations = self.supabase.table("escalation_events").select("id, status").execute()
                total_escalations = len(escalations.data)
                open_escalations = sum(1 for r in escalations.data if r.get("status") == "open")
            except Exception:
                total_escalations = 0
                open_escalations = 0

            today = datetime.utcnow().date().isoformat()
            today_msgs = self.supabase.table("conversations").select("id").gte("created_at", today).execute()

            return {
                "unique_customers": unique_customers,
                "total_messages": total_messages,
                "total_orders": total_orders,
                "total_revenue": total_revenue,
                "pending_orders": pending_orders,
                "total_escalations": total_escalations,
                "open_escalations": open_escalations,
                "messages_today": len(today_msgs.data)
            }
        except Exception as e:
            logger.error(f"Overview metrics error: {e}")
            return {}

    def get_conversation_trends(self, days: int = 7) -> list[dict]:
        try:
            since = (datetime.utcnow() - timedelta(days=days)).isoformat()
            result = self.supabase.table("conversations").select("created_at, role").gte("created_at", since).execute()

            counts: dict[str, int] = {}
            for row in result.data:
                if row.get("role") == "user":
                    date = row["created_at"][:10]
                    counts[date] = counts.get(date, 0) + 1

            trend = []
            for i in range(days):
                date = (datetime.utcnow() - timedelta(days=days - 1 - i)).date().isoformat()
                trend.append({"date": date, "messages": counts.get(date, 0)})
            return trend
        except Exception as e:
            logger.error(f"Conversation trends error: {e}")
            return []

    def get_language_breakdown(self) -> list[dict]:
        try:
            result = self.supabase.table("conversations").select("message, role").eq("role", "user").limit(500).execute()
            counts = {"English": 0, "Urdu": 0, "Roman Urdu": 0}
            roman_urdu_words = ['kya', 'hai', 'nahi', 'aap', 'mujhe', 'kitna',
                                'ki', 'ka', 'ke', 'mein', 'se', 'ko', 'bhai',
                                'theek', 'acha', 'batao', 'chahiye', 'haan']
            for row in result.data:
                msg = row.get("message", "")
                if any('\u0600' <= c <= '\u06FF' for c in msg):
                    counts["Urdu"] += 1
                else:
                    words = msg.lower().split()
                    urdu_count = sum(1 for w in words if w in roman_urdu_words)
                    if words and urdu_count / len(words) > 0.25:
                        counts["Roman Urdu"] += 1
                    else:
                        counts["English"] += 1
            return [{"language": k, "count": v} for k, v in counts.items() if v > 0]
        except Exception as e:
            logger.error(f"Language breakdown error: {e}")
            return []

    def get_order_metrics(self) -> dict:
        try:
            result = self.supabase.table("orders").select("*, products(name)").order("created_at", desc=True).limit(50).execute()
            status_counts: dict[str, int] = {}
            for row in result.data:
                status = row.get("status", "unknown")
                status_counts[status] = status_counts.get(status, 0) + 1
            recent = []
            for row in result.data[:10]:
                recent.append({
                    "order_number": row.get("order_number", ""),
                    "product_name": (row.get("products") or {}).get("name", "Unknown Product"),
                    "total_amount": row.get("total_price", 0),
                    "status": row.get("status", ""),
                    "created_at": row.get("created_at", ""),
                })
            return {
                "status_breakdown": [{"status": k, "count": v} for k, v in status_counts.items()],
                "recent_orders": recent
            }
        except Exception as e:
            logger.error(f"Order metrics error: {e}")
            return {"status_breakdown": [], "recent_orders": []}

    def get_escalation_metrics(self) -> dict:
        try:
            result = self.supabase.table("escalation_events").select("*").order("timestamp", desc=True).limit(20).execute()
            open_cases = [r for r in result.data if r.get("status") == "open"]
            resolved_cases = [r for r in result.data if r.get("status") == "resolved"]
            score_labels = {"angry": 0, "negative": 0, "neutral": 0}
            for row in result.data:
                label = row.get("sentiment_label", "neutral")
                if label in score_labels:
                    score_labels[label] += 1
            return {
                "recent_escalations": result.data,
                "open_count": len(open_cases),
                "resolved_count": len(resolved_cases),
                "sentiment_distribution": [{"label": k, "count": v} for k, v in score_labels.items()]
            }
        except Exception as e:
            logger.error(f"Escalation metrics error: {e}")
            return {"recent_escalations": [], "open_count": 0, "resolved_count": 0, "sentiment_distribution": []}

    def get_dashboard_data(self) -> dict:
        return {
            "generated_at": datetime.utcnow().isoformat(),
            "overview": self.get_overview(),
            "conversation_trends": self.get_conversation_trends(),
            "language_breakdown": self.get_language_breakdown(),
            "order_metrics": self.get_order_metrics(),
            "escalation_metrics": self.get_escalation_metrics()
        }
