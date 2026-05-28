"""
FastAPI routes for the JLCPCB Auth dashboard panel.

Mounted at: /api/plugins/jlcpcb-auth/
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from credentials import clear_credentials, env_file_path, get_credentials, set_credentials, username_hint

router = APIRouter()


class CredentialsPayload(BaseModel):
    username: str
    password: str


def _get_session_state() -> tuple[bool, int | None]:
    session = None
    max_age = None

    try:
        from tools import SESSION_MAX_AGE, _session

        session = _session
        max_age = SESSION_MAX_AGE
    except Exception:
        try:
            from hermes_agent.plugins.jlcpcb_auth.tools import SESSION_MAX_AGE, _session

            session = _session
            max_age = SESSION_MAX_AGE
        except Exception:
            return False, None

    if not session:
        return False, None

    logged_in = bool(session.get("logged_in"))
    logged_in_at = session.get("logged_in_at")
    age = int(time.time() - logged_in_at) if logged_in_at else None

    if age and max_age and age > max_age:
        session["logged_in"] = False
        session["logged_in_at"] = None
        return False, age

    return logged_in, age


def _reset_session_state() -> None:
    try:
        from tools import _session

        _session["logged_in"] = False
        _session["logged_in_at"] = None
        _session["username_hint"] = None
    except Exception:
        try:
            from hermes_agent.plugins.jlcpcb_auth.tools import _session

            _session["logged_in"] = False
            _session["logged_in_at"] = None
            _session["username_hint"] = None
        except Exception:
            return


@router.get("/status")
async def get_status():
    username, password = get_credentials()
    logged_in, session_age = _get_session_state()

    return JSONResponse(
        {
            "credentials": {
                "username_set": bool(username),
                "password_set": bool(password),
                "username_hint": username_hint(),
            },
            "session": {
                "logged_in": logged_in,
                "session_age_seconds": session_age,
            },
            "env_file": str(env_file_path()),
            "env_file_exists": env_file_path().exists(),
        }
    )


@router.post("/credentials")
async def save_credentials(payload: CredentialsPayload):
    username = payload.username.strip()
    password = payload.password

    if not username or not password or not password.strip():
        raise HTTPException(status_code=400, detail="Username and password are required.")

    if "@" not in username:
        raise HTTPException(status_code=400, detail="Username should be an email address.")

    try:
        set_credentials(username, password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return JSONResponse(
        {
            "success": True,
            "message": "Credentials saved. They take effect immediately.",
            "username_hint": username_hint(),
        }
    )


@router.post("/test")
async def test_login():
    username, password = get_credentials()
    if not username or not password:
        return JSONResponse(
            {
                "success": False,
                "message": "No credentials stored. Please save credentials first.",
            }
        )

    return JSONResponse(
        {
            "success": True,
            "message": (
                "Credentials are configured. To perform a full browser login test, "
                "ask the agent: 'Test my JLCPCB login'."
            ),
            "username_hint": username_hint(),
        }
    )


@router.post("/clear")
async def clear_stored_credentials():
    clear_credentials()
    _reset_session_state()
    return JSONResponse(
        {
            "success": True,
            "message": "JLCPCB credentials cleared.",
        }
    )
