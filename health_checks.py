"""
Health check and monitoring endpoints for enterprise deployment
"""

from flask import Blueprint, jsonify
from datetime import datetime
import psutil
import os

health_bp = Blueprint('health', __name__)


@health_bp.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "service": "techzone-whatsapp-bot"
    }), 200


@health_bp.route("/health/ready", methods=["GET"])
def readiness_check():
    checks = {
        "database": check_database(),
        "openai": check_openai(),
        "twilio": check_twilio()
    }
    all_ready = all(checks.values())
    return jsonify({
        "ready": all_ready,
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }), 200 if all_ready else 503


@health_bp.route("/health/live", methods=["GET"])
def liveness_check():
    return jsonify({
        "alive": True,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }), 200


@health_bp.route("/metrics", methods=["GET"])
def metrics():
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    return jsonify({
        "system": {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_available_mb": memory.available / (1024 * 1024),
            "disk_percent": disk.percent,
            "disk_free_gb": disk.free / (1024 ** 3)
        },
        "process": {
            "pid": os.getpid(),
            "threads": psutil.Process().num_threads(),
            "open_files": len(psutil.Process().open_files())
        },
        "timestamp": datetime.utcnow().isoformat() + "Z"
    })


def check_database():
    try:
        from supabase import create_client
        client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
        client.table('conversations').select('id').limit(1).execute()
        return True
    except Exception:
        return False


def check_openai():
    try:
        from openai import OpenAI
        OpenAI(api_key=os.getenv("OPENAI_API_KEY")).models.list()
        return True
    except Exception:
        return False


def check_twilio():
    return bool(os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN"))
