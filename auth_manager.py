"""
JWT Authentication Manager - Step 16
Handles login, token generation, and route protection
"""

import jwt
import logging
import os
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, redirect, url_for
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ── Config from .env ──────────────────────────
JWT_SECRET      = os.getenv("JWT_SECRET", "change-this-secret-in-production")
JWT_EXPIRY_HRS  = int(os.getenv("JWT_EXPIRY_HRS", 8))
ADMIN_USERNAME  = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD  = os.getenv("ADMIN_PASSWORD", "techzone2026")


class AuthManager:
    """Handles JWT token creation and validation"""

    def __init__(self):
        self.secret     = JWT_SECRET
        self.expiry_hrs = JWT_EXPIRY_HRS

    # ─────────────────────────────────────────────
    # TOKEN OPERATIONS
    # ─────────────────────────────────────────────

    def generate_token(self, username: str) -> str:
        """Generate a signed JWT token"""
        payload = {
            "sub":      username,
            "iat":      datetime.utcnow(),
            "exp":      datetime.utcnow() + timedelta(hours=self.expiry_hrs),
            "role":     "admin",
        }
        token = jwt.encode(payload, self.secret, algorithm="HS256")
        logger.info(f"JWT token generated for user: {username}")
        return token

    def verify_token(self, token: str) -> dict | None:
        """Verify token and return payload, or None if invalid"""
        try:
            payload = jwt.decode(token, self.secret, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"JWT token invalid: {e}")
            return None

    def validate_credentials(self, username: str, password: str) -> bool:
        """Check username and password against .env config"""
        return username == ADMIN_USERNAME and password == ADMIN_PASSWORD

    # ─────────────────────────────────────────────
    # TOKEN EXTRACTION HELPERS
    # ─────────────────────────────────────────────

    def get_token_from_request(self) -> str | None:
        """Extract JWT from Authorization header or cookie"""
        # Try Authorization: Bearer <token>
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]

        # Try cookie (for browser sessions)
        return request.cookies.get("access_token")

    def get_token_from_query(self) -> str | None:
        """Extract JWT from query param (for direct URL access)"""
        return request.args.get("token")


# ── Singleton ──
auth_manager = AuthManager()


# ─────────────────────────────────────────────
# DECORATORS
# ─────────────────────────────────────────────

def jwt_required(f):
    """
    Decorator for API routes -- returns 401 JSON if not authenticated.
    Checks Authorization header or cookie.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = auth_manager.get_token_from_request()
        if not token:
            return jsonify({"error": "Authentication required", "code": 401}), 401

        payload = auth_manager.verify_token(token)
        if not payload:
            return jsonify({"error": "Token expired or invalid", "code": 401}), 401

        request.current_user = payload.get("sub")
        return f(*args, **kwargs)
    return decorated


def dashboard_login_required(f):
    """
    Decorator for HTML dashboard routes -- redirects to /login if not authenticated.
    Checks cookie only (browser sessions).
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get("access_token")
        if not token:
            return redirect("/login")

        payload = auth_manager.verify_token(token)
        if not payload:
            return redirect("/login?expired=1")

        request.current_user = payload.get("sub")
        return f(*args, **kwargs)
    return decorated
