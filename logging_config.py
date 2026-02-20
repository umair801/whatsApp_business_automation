"""
Structured JSON logging configuration for enterprise monitoring
"""

import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        if hasattr(record, "intent"):
            log_data["intent"] = record.intent
        if hasattr(record, "language"):
            log_data["language"] = record.language
        if hasattr(record, "response_time"):
            log_data["response_time_ms"] = record.response_time
        return json.dumps(log_data)


def setup_logging(log_level: str = "INFO"):
    import os
    os.makedirs("logs", exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(JsonFormatter())
    root_logger.addHandler(console_handler)

    file_handler = logging.FileHandler("logs/app.log")
    file_handler.setFormatter(JsonFormatter())
    root_logger.addHandler(file_handler)

    return root_logger
