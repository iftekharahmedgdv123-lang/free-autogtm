"""Admin login: one admin user, PBKDF2 password hash, session cookies.

Credentials come from environment variables, so they are never committed:
    FREE_AUTOGTM_ADMIN_USER (default: admin)
    FREE_AUTOGTM_ADMIN_PASSWORD (default: changeme123 — change it!)

Sessions live in memory (token -> username + expiry, 12 hours). Restarting
the server logs everyone out, which is the safe default for a small tool.
"""
import hashlib
import hmac
import os
import secrets
import time

SESSIONS = {}
SESSION_TTL = 12 * 3600

def admin_user():
    return os.environ.get("FREE_AUTOGTM_ADMIN_USER", "admin")

def _password_hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000).hex()

def admin_password_hash():
    """Hash of the configured password, with a fixed salt derived from the
    password itself for this single-user tool (no user table to store a
    per-user salt in). Verification is a constant-time compare."""
    password = os.environ.get("FREE_AUTOGTM_ADMIN_PASSWORD", "changeme123")
    salt = hashlib.sha256(b"free-autogtm-admin").digest()
    return _password_hash(password, salt)

def is_default_password():
    return os.environ.get("FREE_AUTOGTM_ADMIN_PASSWORD", "changeme123") == "changeme123"

def check_login(username, password):
    if not username or not password:
        return False
    if not hmac.compare_digest(username, admin_user()):
        return False
    salt = hashlib.sha256(b"free-autogtm-admin").digest()
    return hmac.compare_digest(_password_hash(password, salt), admin_password_hash())

def create_session(username):
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = {"user": username, "expires": time.time() + SESSION_TTL}
    return token

def check_session(token):
    if not token:
        return None
    sess = SESSIONS.get(token)
    if not sess or sess["expires"] < time.time():
        SESSIONS.pop(token, None)
        return None
    return sess["user"]

def destroy_session(token):
    SESSIONS.pop(token, None)
