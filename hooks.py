"""
hooks.py — Plugin lifecycle hooks for the JLCPCB auth plugin.

post_tool_call: Belt-and-braces credential redaction.
  Scans every tool result before it is returned to the model's context.
  If a credential value has somehow leaked into the output (e.g. from
  an unexpected browser error trace), it is replaced with ***.
  This is a safety net — the primary defence is that credentials are
  never passed as parameters or returned in results by design.
"""

try:
    from .credentials import get_credentials
except ImportError:
    from credentials import get_credentials


def post_tool_call(tool_name: str, result: str, ctx=None, **kwargs) -> str:
    """
    Intercept every tool result and redact any credential values.
    Called by Hermes after every tool execution, for every tool
    (not just our own — belt-and-braces).
    """
    username, password = get_credentials()
    username = username or ""
    password = password or ""

    if not result:
        return result

    # Redact password first (more sensitive), then username
    if password and len(password) > 2 and password in result:
        result = result.replace(password, "[REDACTED]")

    if username and len(username) > 3 and username in result:
        result = result.replace(username, "[REDACTED]")

    return result
