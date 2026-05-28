"""
tools.py — Tool handlers for the JLCPCB auth plugin.

Security contract:
  - Credentials are accessed only via credentials.py.
  - Credentials are NEVER returned in any tool result.
  - Credentials are NEVER logged (the post_tool_call hook in hooks.py
    redacts any accidental leaks as a belt-and-braces measure).
  - The model's context window never contains username or password values.

JLCPCB login flow notes (as of 2025/2026):
  - Login URL: https://passport.jlcpcb.com/#/login
  - The page is a Vue.js SPA — fully JS-rendered, no static HTML form.
  - Hermes browser represents it as an accessibility tree with ref IDs.
  - The page has two top-level tabs: "Sign In" and "Create Account".
    The Sign In tab is active by default, but we explicitly check and
    click it to be resilient to A/B tests or layout changes.
  - Within Sign In, there are two sub-modes: email/password and phone/OTP.
    We target the email/password mode.
  - After submit, success is detected by navigation away from passport.jlcpcb.com
    OR by the appearance of a user avatar / account menu element.
  - "Already logged in" is detected by checking if jlcpcb.com shows an
    account avatar before attempting login.
"""

import json
import time
from typing import Any

try:
    from .credentials import credentials_available, get_credentials, username_hint
except ImportError:
    from credentials import credentials_available, get_credentials, username_hint

# ---------------------------------------------------------------------------
# Module-level session state
# Tracks whether we believe we are logged in, and when.
# This is process-scoped — it resets on Hermes restart (intentional).
# ---------------------------------------------------------------------------
_session: dict[str, Any] = {
    "logged_in": False,
    "logged_in_at": None,
    "username_hint": None,  # stored as first 3 chars + *** for diagnostic use only
}

# How long (seconds) before we consider a cached login stale and re-verify
SESSION_MAX_AGE = 3600  # 1 hour


# ---------------------------------------------------------------------------
# jlcpcb_auth_status
# ---------------------------------------------------------------------------

def jlcpcb_auth_status(args: dict, ctx=None, **kwargs) -> str:
    """Return the current auth state without touching the browser."""
    if not credentials_available():
        return json.dumps({
            "logged_in": False,
            "error": "Credentials not configured. Set JLCPCB_USERNAME and JLCPCB_PASSWORD.",
        })

    age = None
    if _session["logged_in"] and _session["logged_in_at"]:
        age = int(time.time() - _session["logged_in_at"])
        # Expire stale sessions
        if age > SESSION_MAX_AGE:
            _session["logged_in"] = False
            _session["logged_in_at"] = None

    return json.dumps({
        "logged_in": _session["logged_in"],
        "session_age_seconds": age,
        "account_hint": username_hint() if _session["logged_in"] else None,
    })


# ---------------------------------------------------------------------------
# jlcpcb_login  (the main tool)
# ---------------------------------------------------------------------------

def jlcpcb_login(args: dict, ctx=None, **kwargs) -> str:
    """
    Log in to JLCPCB.

    Uses ctx.run_browser_task() — the canonical Hermes plugin API for
    driving the built-in browser without exposing credentials to the model.

    The browser task receives credentials from the credential service;
    they are injected directly into browser_type() calls and never
    appear in the task description string that the model might see.
    """
    if not credentials_available():
        return json.dumps({
            "status": "error",
            "message": (
                "JLCPCB credentials are not configured. "
                "Set JLCPCB_USERNAME and JLCPCB_PASSWORD environment variables, "
                "or use the JLCPCB Auth panel in the Hermes dashboard."
            ),
        })

    # Fast path: already logged in and session is fresh
    if _session["logged_in"] and _session["logged_in_at"]:
        age = time.time() - _session["logged_in_at"]
        if age < SESSION_MAX_AGE:
            return json.dumps({
                "status": "already_logged_in",
                "session_age_seconds": int(age),
            })

    # Read credentials NOW into local variables — they exist only in this
    # stack frame and are passed directly to browser actions.
    # They are never serialised, returned, or logged.
    username, password = get_credentials()
    if not username or not password:
        return json.dumps({
            "status": "error",
            "message": "JLCPCB credentials are not configured.",
        })

    try:
        result = _do_login(ctx, username, password)
        # Wipe local references as soon as browser work is done
        del username, password
        return result
    except Exception as exc:
        del username, password
        # Ensure no credential values appear in the exception message
        safe_msg = _sanitise_error(str(exc))
        _session["logged_in"] = False
        return json.dumps({"status": "error", "message": safe_msg})


def _do_login(ctx, username: str, password: str) -> str:
    """
    Perform the actual browser login sequence.

    Uses ctx.browser_* helpers which map directly to Hermes built-in
    browser tools (browser_navigate, browser_snapshot, browser_click,
    browser_type) without going through the model's tool-call loop.
    These are synchronous from the plugin's perspective.
    """
    browser = ctx.browser  # Hermes PluginContext browser proxy

    # -----------------------------------------------------------------------
    # Step 1: Navigate to the JLCPCB passport login page
    # -----------------------------------------------------------------------
    browser.navigate("https://passport.jlcpcb.com/#/login")

    # Wait for the SPA to hydrate — the page is JS-rendered
    # browser.wait_for_element handles polling with timeout
    browser.wait_for_element(
        hint="Sign In tab or email input",
        timeout=15,
    )

    # -----------------------------------------------------------------------
    # Step 2: Get the accessibility tree snapshot to find element ref IDs
    # -----------------------------------------------------------------------
    snapshot = browser.snapshot(full=False)

    # -----------------------------------------------------------------------
    # Step 3: Ensure we are on the Sign In tab, not Create Account
    # The page has two tabs. Default is Sign In but we check explicitly.
    # We look for a tab/button whose label contains "Sign In" (case-insensitive)
    # and click it only if it is not already selected.
    # -----------------------------------------------------------------------
    sign_in_ref = _find_ref(snapshot, labels=["sign in", "login", "log in"], role_hints=["tab", "button"])
    create_ref = _find_ref(snapshot, labels=["create account", "register", "sign up"], role_hints=["tab", "button"])

    # If "Create Account" is the currently active/selected tab, click "Sign In"
    if sign_in_ref and _is_tab_active(snapshot, create_ref):
        browser.click(sign_in_ref)
        snapshot = browser.snapshot(full=False)

    elif sign_in_ref and not _is_tab_active(snapshot, sign_in_ref):
        # Sign In tab exists but not selected — click it
        browser.click(sign_in_ref)
        snapshot = browser.snapshot(full=False)

    # -----------------------------------------------------------------------
    # Step 4: Locate email/password inputs
    # The JLCPCB SPA uses two sub-modes within Sign In:
    #   - Email + password (what we want)
    #   - Phone + OTP
    # We click the email/password sub-tab if visible.
    # -----------------------------------------------------------------------
    email_mode_ref = _find_ref(snapshot, labels=["email", "email/password", "password login"])
    if email_mode_ref:
        browser.click(email_mode_ref)
        snapshot = browser.snapshot(full=False)

    # -----------------------------------------------------------------------
    # Step 5: Fill email field
    # -----------------------------------------------------------------------
    email_ref = _find_ref(
        snapshot,
        labels=["email", "username", "account", "email address"],
        input_types=["email", "text"],
    )
    if not email_ref:
        return json.dumps({
            "status": "error",
            "message": "Could not find email input on JLCPCB login page. The page layout may have changed.",
        })

    browser.click(email_ref)
    browser.clear(email_ref)
    browser.type(email_ref, username)   # ← credential injected here, never in model context

    # -----------------------------------------------------------------------
    # Step 6: Fill password field
    # -----------------------------------------------------------------------
    snapshot = browser.snapshot(full=False)
    password_ref = _find_ref(
        snapshot,
        labels=["password"],
        input_types=["password"],
    )
    if not password_ref:
        return json.dumps({
            "status": "error",
            "message": "Could not find password input on JLCPCB login page.",
        })

    browser.click(password_ref)
    browser.clear(password_ref)
    browser.type(password_ref, password)  # ← credential injected here

    # -----------------------------------------------------------------------
    # Step 7: Submit the form
    # Try: a Sign In / Login submit button, then fall back to Enter key
    # -----------------------------------------------------------------------
    snapshot = browser.snapshot(full=False)
    submit_ref = _find_ref(
        snapshot,
        labels=["sign in", "log in", "login", "submit"],
        role_hints=["button", "submit"],
    )
    if submit_ref:
        browser.click(submit_ref)
    else:
        browser.key(password_ref, "Enter")

    # -----------------------------------------------------------------------
    # Step 8: Detect success or failure
    # Success signals:
    #   a) URL changes away from passport.jlcpcb.com
    #   b) An account avatar / user menu appears
    #   c) Page title changes to JLCPCB (not Account)
    # Failure signals:
    #   a) Error message element appears on page
    #   b) Still on passport.jlcpcb.com after timeout
    # -----------------------------------------------------------------------
    success = browser.wait_for_condition(
        condition_fn=_login_success_condition,
        timeout=20,
    )

    if success:
        _session["logged_in"] = True
        _session["logged_in_at"] = time.time()
        _session["username_hint"] = username_hint()
        return json.dumps({"status": "logged_in"})

    # Check for an error message on the page
    snapshot = browser.snapshot(full=True)
    error_text = _extract_error_text(snapshot)
    _session["logged_in"] = False

    return json.dumps({
        "status": "error",
        "message": error_text or "Login did not complete. Check credentials or try again.",
    })


def _login_success_condition(browser) -> bool:
    """
    Returns True when login has completed successfully.
    Called repeatedly by wait_for_condition with timeout.
    """
    try:
        url = browser.current_url()
        # Success: navigated away from passport subdomain
        if "passport.jlcpcb.com" not in url:
            return True
        # Also check for account avatar/menu on the page
        snapshot = browser.snapshot(full=False)
        if _find_ref(snapshot, labels=["my account", "account", "avatar", "profile", "order"], role_hints=["link", "button", "img"]):
            return True
        return False
    except Exception:
        return False


# ---------------------------------------------------------------------------
# jlcpcb_logout
# ---------------------------------------------------------------------------

def jlcpcb_logout(args: dict, ctx=None, **kwargs) -> str:
    """Log out of JLCPCB and clear session state."""
    try:
        browser = ctx.browser
        browser.navigate("https://jlcpcb.com")
        snapshot = browser.snapshot(full=False)

        # Look for a logout / sign out link
        logout_ref = _find_ref(
            snapshot,
            labels=["sign out", "log out", "logout", "signout"],
            role_hints=["button", "link"],
        )
        if logout_ref:
            browser.click(logout_ref)

        _session["logged_in"] = False
        _session["logged_in_at"] = None
        return json.dumps({"status": "logged_out"})
    except Exception as exc:
        _session["logged_in"] = False
        return json.dumps({"status": "logged_out", "note": _sanitise_error(str(exc))})


# ---------------------------------------------------------------------------
# Accessibility tree helpers
# ---------------------------------------------------------------------------

def _find_ref(
    snapshot: str,
    labels: list[str],
    role_hints: list[str] | None = None,
    input_types: list[str] | None = None,
) -> str | None:
    """
    Search a Hermes accessibility-tree snapshot for an element matching
    any of the provided labels and optionally filtered by ARIA role or
    input type.

    Hermes snapshots use a compact text format like:
        @e12 [button] "Sign In"
        @e15 [textbox] "Email address" type=email
        @e18 [textbox] "Password" type=password

    Returns the ref ID string (e.g. "@e15") or None.
    """
    if not snapshot:
        return None

    lower_labels = [l.lower() for l in labels]
    lower_roles = [r.lower() for r in role_hints] if role_hints else None
    lower_types = [t.lower() for t in input_types] if input_types else None

    best_ref = None

    for line in snapshot.splitlines():
        line_lower = line.lower()

        # Extract ref ID — Hermes uses @eN format
        if not line_lower.strip().startswith("@e"):
            continue

        parts = line.split()
        if not parts:
            continue
        ref = parts[0]  # e.g. "@e15"

        # Role filter
        if lower_roles:
            role_match = any(f"[{r}]" in line_lower for r in lower_roles)
            if not role_match:
                continue

        # Input type filter
        if lower_types:
            type_match = any(f"type={t}" in line_lower for t in lower_types)
            if not type_match:
                continue

        # Label match
        if any(label in line_lower for label in lower_labels):
            # Prefer exact/full-word matches — take the first good one
            if best_ref is None:
                best_ref = ref

    return best_ref


def _is_tab_active(snapshot: str, ref: str | None) -> bool:
    """Return True if the given ref ID corresponds to an active/selected tab."""
    if not ref or not snapshot:
        return False
    for line in snapshot.splitlines():
        if line.startswith(ref):
            lower = line.lower()
            # Must be explicitly selected/active — not just containing the word
            # 'aria-selected="false"' must NOT count
            if 'aria-selected="false"' in lower:
                return False
            if 'aria-selected="true"' in lower:
                return True
            # Fallback: check for standalone "active" class marker
            if " active" in lower or "[active]" in lower:
                return True
            return False
    return False


def _extract_error_text(snapshot: str) -> str | None:
    """
    Look for error/alert text in the snapshot — e.g. "Incorrect password",
    "Account does not exist", "Too many attempts".
    Returns sanitised text (guaranteed not to contain credential values).
    """
    error_keywords = ["incorrect", "invalid", "does not exist", "wrong", "error",
                      "failed", "too many", "locked", "captcha", "verify"]
    for line in snapshot.splitlines():
        lower = line.lower()
        if any(kw in lower for kw in error_keywords):
            # Strip ref IDs and role brackets, return plain text
            text = " ".join(
                w for w in line.split()
                if not w.startswith("@e") and not (w.startswith("[") and w.endswith("]"))
            )
            return _sanitise_error(text[:200])
    return None


def _sanitise_error(msg: str) -> str:
    """Belt-and-braces: remove credential values from any error string."""
    username, password = get_credentials()
    if username and username in msg:
        msg = msg.replace(username, "***")
    if password and password in msg:
        msg = msg.replace(password, "***")
    return msg
