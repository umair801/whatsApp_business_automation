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
    """Basic health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "service": "whatsapp-bot"
    }), 200


@health_bp.route("/health/ready", methods=["GET"])
def readiness_check():
    """Readiness check - validates dependencies"""
    checks = {
        "database": check_database(),
        "openai": check_openai(),
        "twilio": check_twilio()
    }
    
    all_ready = all(checks.values())
    status_code = 200 if all_ready else 503
    
    return jsonify({
        "ready": all_ready,
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }), status_code


@health_bp.route("/health/live", methods=["GET"])
def liveness_check():
    """Liveness check - basic application responsiveness"""
    return jsonify({
        "alive": True,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }), 200


@health_bp.route("/metrics", methods=["GET"])
def metrics():
    """System metrics endpoint"""
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
    """Check database connectivity"""
    try:
        from supabase import create_client
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            return False
        
        client = create_client(supabase_url, supabase_key)
        # Simple query to test connection
        client.table('conversations').select('id').limit(1).execute()
        return True
    except Exception as e:
        print(f"Database check failed: {e}")
        return False


def check_openai():
    """Check OpenAI API connectivity"""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        # Simple API call
        client.models.list()
        return True
    except Exception as e:
        print(f"OpenAI check failed: {e}")
        return False


def check_twilio():
    """Check Twilio credentials"""
    try:
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        return bool(account_sid and auth_token)
    except Exception as e:
        print(f"Twilio check failed: {e}")
        return False
