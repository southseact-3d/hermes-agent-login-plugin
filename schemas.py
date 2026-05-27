"""
schemas.py — Tool schemas for the JLCPCB auth plugin.

These are the ONLY descriptions the LLM model ever sees.
There are intentionally NO credential parameters in any schema.
The model calls jlcpcb_login() with no arguments; credentials are
read exclusively by the handler from environment variables.
"""

JLCPCB_LOGIN = {
    "name": "jlcpcb_login",
    "description": (
        "Log in to JLCPCB using securely stored credentials. "
        "Call this before placing orders, uploading Gerber files, "
        "checking order status, or accessing any authenticated JLCPCB page. "
        "No credentials are required as parameters — they are managed "
        "securely by the system and are never visible to you. "
        "Returns: {status: 'logged_in'} on success, or an error message. "
        "If already logged in, returns {status: 'already_logged_in'} immediately."
    ),
    "parameters": {
        "type": "object",
        "properties": {},   # ← intentionally empty — no credentials exposed
        "required": [],
    },
}

JLCPCB_LOGOUT = {
    "name": "jlcpcb_logout",
    "description": (
        "Log out of JLCPCB and clear the browser session. "
        "Call this when finished with JLCPCB tasks if you want to "
        "ensure a clean session state."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

JLCPCB_AUTH_STATUS = {
    "name": "jlcpcb_auth_status",
    "description": (
        "Check whether the current browser session is authenticated with JLCPCB. "
        "Returns {logged_in: true/false} and a session age if available. "
        "Use this to avoid unnecessary re-logins."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}
