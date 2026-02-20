"""
WebSocket Manager
Handles real-time event broadcasting to connected dashboard clients
"""

import logging
from datetime import datetime
from flask_socketio import SocketIO, emit

logger = logging.getLogger(__name__)

socketio = SocketIO(cors_allowed_origins="*", async_mode="threading")


class WebSocketManager:
    def __init__(self, socketio_instance: SocketIO):
        self.sio = socketio_instance
        self.connected_clients = 0

    def on_connect(self):
        self.connected_clients += 1
        logger.info(f"Dashboard client connected | total={self.connected_clients}")
        emit("server_time", {"timestamp": datetime.utcnow().isoformat()})

    def on_disconnect(self):
        self.connected_clients = max(0, self.connected_clients - 1)
        logger.info(f"Dashboard client disconnected | total={self.connected_clients}")

    def broadcast_new_message(self, user_id: str, language: str, intent: str, sentiment_label: str):
        payload = {
            "type":            "new_message",
            "user_id":         user_id[-4:] + "****",
            "language":        language,
            "intent":          intent,
            "sentiment_label": sentiment_label,
            "timestamp":       datetime.utcnow().isoformat(),
        }
        self.sio.emit("new_message", payload)

    def broadcast_escalation(self, case_id: str, phone_number: str, reason: str, score: float):
        payload = {
            "type":      "escalation",
            "case_id":   case_id,
            "phone":     phone_number[-4:] + "****",
            "reason":    reason,
            "score":     score,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.sio.emit("escalation", payload)
        logger.warning(f"WebSocket: broadcast escalation | case_id={case_id}")

    def broadcast_new_order(self, order_number: str, product_name: str, amount: float, status: str):
        payload = {
            "type":         "new_order",
            "order_number": order_number,
            "product_name": product_name,
            "amount":       amount,
            "status":       status,
            "timestamp":    datetime.utcnow().isoformat(),
        }
        self.sio.emit("new_order", payload)

    def broadcast_kpi_update(self, analytics_engine):
        try:
            overview = analytics_engine.get_overview()
            self.sio.emit("kpi_update", {
                "type":      "kpi_update",
                "overview":  overview,
                "timestamp": datetime.utcnow().isoformat(),
            })
        except Exception as e:
            logger.error(f"WebSocket: KPI broadcast error: {e}")


ws_manager = WebSocketManager(socketio)
