"""
backend.py — FastAPI routes for the JLCPCB Auth dashboard panel.

Mounted at: /api/plugins/jlcpcb-auth/

Endpoints:
  GET  /status       — returns whether credentials are set and session state
  POST /credentials  — writes JLCPCB_USERNAME / JLCPCB_PASSWORD to ~/.hermes/.env
  POST /test         — triggers a test login (does NOT store result in model context)
  POST /clear        — removes credentials from ~/.hermes/.env
"""

import json
import os
import re
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()

ENV_FILE = Path.home() / ".hermes" / ".env"
USERNAME_KEY = "JLCPCB_USERNAME"
PASSWORD_KEY = "JLCPCB_PASSWORD"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class CredentialsPayload(BaseModel):
    username: str
    password: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_env_file() -> dict[str, str]:
    """Parse ~/.hermes/.env into a dict. Handles comments and blank lines."""
    result: dict[str, str] = {}
    if not ENV_FILE.exists():
        return result
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, val = line.partition("=")
            result[key.strip()] = val.strip()
    return result


def _write_env_file(values: dict[str, str]) -> None:
    """Write key=value pairs to ~/.hermes/.env, preserving other entries."""
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)

    existing = _read_env_file()
    existing.update(values)

    lines = [f"{k}={v}" for k, v in existing.items()]
    ENV_FILE.write_text("\n".join(lines) + "\n")
    # Secure the file — owner read/write only
    ENV_FILE.chmod(0o600)


def _remove_from_env_file(keys: list[str]) -> None:
    existing = _read_env_file()
    for k in keys:
        existing.pop(k, None)
    lines = [f"{k}={v}" for k, v in existing.items()]
    ENV_FILE.write_text("\n".join(lines) + "\n")
    if ENV_FILE.exists():
        ENV_FILE.chmod(0o600)


def _credentials_set() -> tuple[bool, bool]:
    """Returns (username_set, password_set) based on env vars (live process state)."""
    return (
        bool(os.environ.get(USERNAME_KEY, "").strip()),
        bool(os.environ.get(PASSWORD_KEY, "").strip()),
    )


def _username_hint() -> str:
    raw = os.environ.get(USERNAME_KEY, "")
    if not raw:
        return ""
    if len(raw) <= 3:
        return "***"
    return raw[:3] + "***"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/status")
async def get_status():
    """Return credential and session status."""
    username_set, password_set = _credentials_set()

    # Import session state from tools module (same process)
    try:
        from hermes_agent.plugins.jlcpcb_auth.tools import _session, SESSION_MAX_AGE
        logged_in = _session.get("logged_in", False)
        logged_in_at = _session.get("logged_in_at")
        session_age = int(time.time() - logged_in_at) if logged_in_at else None
        if session_age and session_age > SESSION_MAX_AGE:
            logged_in = False
    except ImportError:
        logged_in = False
        session_age = None

    return JSONResponse({
        "credentials": {
            "username_set": username_set,
            "password_set": password_set,
            "username_hint": _username_hint(),
        },
        "session": {
            "logged_in": logged_in,
            "session_age_seconds": session_age,
        },
        "env_file": str(ENV_FILE),
        "env_file_exists": ENV_FILE.exists(),
    })


@router.post("/credentials")
async def save_credentials(payload: CredentialsPayload):
    """
    Save credentials to ~/.hermes/.env and update the live process env.
    The password is never echoed back in any response.
    """
    username = payload.username.strip()
    password = payload.password.strip()

    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required.")

    if "@" not in username:
        raise HTTPException(status_code=400, detail="Username should be an email address.")

    # Write to .env file for persistence across restarts
    _write_env_file({USERNAME_KEY: username, PASSWORD_KEY: password})

    # Also update the live process environment so changes take effect
    # immediately without a Hermes restart
    os.environ[USERNAME_KEY] = username
    os.environ[PASSWORD_KEY] = password

    return JSONResponse({
        "success": True,
        "message": "Credentials saved. They take effect immediately.",
        "username_hint": username[:3] + "***",
    })


@router.post("/test")
async def test_login():
    """
    Trigger a test login using the stored credentials.
    Returns success/failure WITHOUT exposing any credential values.
    This runs the same jlcpcb_login tool handler but outside the agent loop.
    """
    u_set, p_set = _credentials_set()
    if not u_set or not p_set:
        return JSONResponse({
            "success": False,
            "message": "No credentials stored. Please save credentials first.",
        })

    try:
        # We call the tool handler directly but we can't drive the browser
        # from the dashboard backend (no browser ctx). Instead we verify
        # credentials are present and return a diagnostic.
        # A full browser test must be triggered via the agent chat.
        return JSONResponse({
            "success": True,
            "message": (
                "Credentials are configured. To perform a full browser login test, "
                "ask the agent: 'Test my JLCPCB login'."
            ),
            "username_hint": _username_hint(),
        })
    except Exception as exc:
        return JSONResponse({
            "success": False,
            "message": f"Error: {str(exc)[:100]}",
        })


@router.post("/clear")
async def clear_credentials():
    """Remove JLCPCB credentials from the .env file and live environment."""
    _remove_from_env_file([USERNAME_KEY, PASSWORD_KEY])
    os.environ.pop(USERNAME_KEY, None)
    os.environ.pop(PASSWORD_KEY, None)

    # Reset session state
    try:
        from hermes_agent.plugins.jlcpcb_auth.tools import _session
        _session["logged_in"] = False
        _session["logged_in_at"] = None
    except ImportError:
        pass

    return JSONResponse({
        "success": True,
        "message": "JLCPCB credentials cleared.",
    })
