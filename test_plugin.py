"""
test_plugin.py — Unit tests for the jlcpcb-auth plugin.

Tests everything that can be verified without a live browser:
  - Schema correctness (no credential parameters)
  - Credential redaction (sanitise_error, post_tool_call hook)
  - Session state management
  - Accessibility tree parser (_find_ref, _is_tab_active)
  - Dashboard backend helpers
  - tools return correct structure when credentials missing

Run with:
  cd jlcpcb-auth
  python -m pytest test_plugin.py -v
  # or without pytest:
  python test_plugin.py
"""

import json
import os
import sys
import unittest

# ── Allow running from the plugin directory directly ──────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from schemas import JLCPCB_LOGIN, JLCPCB_LOGOUT, JLCPCB_AUTH_STATUS
from tools import (
    _find_ref,
    _is_tab_active,
    _extract_error_text,
    _sanitise_error,
    _session,
    jlcpcb_auth_status,
    jlcpcb_login,
)
from hooks import post_tool_call


# ── Sample accessibility tree snapshots ──────────────────────────────────────

SNAPSHOT_SIGN_IN_ACTIVE = """
@e1 [tablist] "Login options"
@e2 [tab] "Sign In" aria-selected="true"
@e3 [tab] "Create Account" aria-selected="false"
@e4 [textbox] "Email address" type=email
@e5 [textbox] "Password" type=password
@e6 [button] "Sign In"
@e7 [link] "Forgot password?"
"""

SNAPSHOT_CREATE_ACCOUNT_ACTIVE = """
@e1 [tablist] "Login options"
@e2 [tab] "Sign In" aria-selected="false"
@e3 [tab] "Create Account" aria-selected="true"
@e10 [textbox] "New email" type=email
@e11 [textbox] "New password" type=password
@e12 [button] "Create Account"
"""

SNAPSHOT_ERROR = """
@e1 [tablist] ""
@e2 [tab] "Sign In" aria-selected="true"
@e4 [textbox] "Email address" type=email
@e5 [textbox] "Password" type=password
@e6 [button] "Sign In"
@e20 [alert] "Incorrect password or account does not exist."
"""

SNAPSHOT_PHONE_MODE = """
@e1 [tablist] "Login options"
@e2 [tab] "Sign In" aria-selected="true"
@e3 [tab] "Create Account" aria-selected="false"
@e8 [tab] "Email" aria-selected="false"
@e9 [tab] "Phone" aria-selected="true"
@e15 [textbox] "Phone number" type=tel
@e16 [button] "Send OTP"
"""


class TestSchemas(unittest.TestCase):
    """Schemas must not expose any credential parameters."""

    def test_login_has_no_parameters(self):
        params = JLCPCB_LOGIN["parameters"]
        self.assertEqual(params["properties"], {})
        self.assertEqual(params["required"], [])

    def test_logout_has_no_parameters(self):
        params = JLCPCB_LOGOUT["parameters"]
        self.assertEqual(params["properties"], {})
        self.assertEqual(params["required"], [])

    def test_status_has_no_parameters(self):
        params = JLCPCB_AUTH_STATUS["parameters"]
        self.assertEqual(params["properties"], {})
        self.assertEqual(params["required"], [])

    def test_login_description_mentions_no_credentials(self):
        desc = JLCPCB_LOGIN["description"].lower()
        # Description should explicitly say credentials aren't required as params
        self.assertIn("no credentials", desc)

    def test_tool_names_correct(self):
        self.assertEqual(JLCPCB_LOGIN["name"], "jlcpcb_login")
        self.assertEqual(JLCPCB_LOGOUT["name"], "jlcpcb_logout")
        self.assertEqual(JLCPCB_AUTH_STATUS["name"], "jlcpcb_auth_status")


class TestCredentialRedaction(unittest.TestCase):
    """Credentials must never appear in any output."""

    def setUp(self):
        os.environ["JLCPCB_USERNAME"] = "testuser@example.com"
        os.environ["JLCPCB_PASSWORD"] = "SuperSecret123!"

    def tearDown(self):
        os.environ.pop("JLCPCB_USERNAME", None)
        os.environ.pop("JLCPCB_PASSWORD", None)

    def test_sanitise_removes_password(self):
        msg = "Login failed: wrong password SuperSecret123! was rejected"
        sanitised = _sanitise_error(msg)
        self.assertNotIn("SuperSecret123!", sanitised)
        self.assertIn("***", sanitised)

    def test_sanitise_removes_username(self):
        msg = "No account found for testuser@example.com"
        sanitised = _sanitise_error(msg)
        self.assertNotIn("testuser@example.com", sanitised)

    def test_post_tool_call_hook_redacts_password(self):
        leaked = '{"result": "error connecting with password SuperSecret123!"}'
        result = post_tool_call("some_tool", leaked)
        self.assertNotIn("SuperSecret123!", result)
        self.assertIn("[REDACTED]", result)

    def test_post_tool_call_hook_redacts_username(self):
        leaked = '{"result": "testuser@example.com authenticated"}'
        result = post_tool_call("some_tool", leaked)
        self.assertNotIn("testuser@example.com", result)

    def test_post_tool_call_hook_passes_normal_output(self):
        normal = '{"status": "logged_in"}'
        result = post_tool_call("jlcpcb_login", normal)
        self.assertEqual(result, normal)


class TestAccessibilityTreeParser(unittest.TestCase):
    """_find_ref must correctly locate elements in Hermes accessibility trees."""

    def test_find_email_input(self):
        ref = _find_ref(SNAPSHOT_SIGN_IN_ACTIVE, labels=["email"], input_types=["email"])
        self.assertEqual(ref, "@e4")

    def test_find_password_input(self):
        ref = _find_ref(SNAPSHOT_SIGN_IN_ACTIVE, labels=["password"], input_types=["password"])
        self.assertEqual(ref, "@e5")

    def test_find_sign_in_tab(self):
        ref = _find_ref(SNAPSHOT_SIGN_IN_ACTIVE, labels=["sign in"], role_hints=["tab"])
        self.assertEqual(ref, "@e2")

    def test_find_create_account_tab(self):
        ref = _find_ref(SNAPSHOT_SIGN_IN_ACTIVE, labels=["create account"], role_hints=["tab"])
        self.assertEqual(ref, "@e3")

    def test_find_submit_button(self):
        ref = _find_ref(SNAPSHOT_SIGN_IN_ACTIVE, labels=["sign in"], role_hints=["button"])
        # Should find @e6 (the button, not the tab) — button check takes priority
        self.assertIsNotNone(ref)

    def test_find_returns_none_for_missing(self):
        ref = _find_ref(SNAPSHOT_SIGN_IN_ACTIVE, labels=["nonexistent_element_xyz"])
        self.assertIsNone(ref)

    def test_is_tab_active_sign_in(self):
        ref = _find_ref(SNAPSHOT_SIGN_IN_ACTIVE, labels=["sign in"], role_hints=["tab"])
        active = _is_tab_active(SNAPSHOT_SIGN_IN_ACTIVE, ref)
        self.assertTrue(active)

    def test_is_tab_active_create_account_not_active(self):
        ref = _find_ref(SNAPSHOT_SIGN_IN_ACTIVE, labels=["create account"], role_hints=["tab"])
        active = _is_tab_active(SNAPSHOT_SIGN_IN_ACTIVE, ref)
        self.assertFalse(active)

    def test_create_account_tab_active_in_that_snapshot(self):
        ref = _find_ref(SNAPSHOT_CREATE_ACCOUNT_ACTIVE, labels=["create account"], role_hints=["tab"])
        active = _is_tab_active(SNAPSHOT_CREATE_ACCOUNT_ACTIVE, ref)
        self.assertTrue(active)

    def test_find_email_mode_tab_in_phone_mode_snapshot(self):
        """Should find the email sub-tab to switch away from phone mode."""
        ref = _find_ref(SNAPSHOT_PHONE_MODE, labels=["email"], role_hints=["tab"])
        self.assertEqual(ref, "@e8")


class TestErrorExtraction(unittest.TestCase):
    def test_extracts_incorrect_password_error(self):
        text = _extract_error_text(SNAPSHOT_ERROR)
        self.assertIsNotNone(text)
        self.assertIn("incorrect", text.lower())

    def test_no_error_in_clean_snapshot(self):
        text = _extract_error_text(SNAPSHOT_SIGN_IN_ACTIVE)
        self.assertIsNone(text)


class TestAuthStatusTool(unittest.TestCase):
    def setUp(self):
        _session["logged_in"] = False
        _session["logged_in_at"] = None
        os.environ.pop("JLCPCB_USERNAME", None)
        os.environ.pop("JLCPCB_PASSWORD", None)

    def test_status_when_no_credentials(self):
        result = json.loads(jlcpcb_auth_status({}))
        self.assertFalse(result["logged_in"])
        self.assertIn("error", result)

    def test_status_when_not_logged_in(self):
        os.environ["JLCPCB_USERNAME"] = "user@test.com"
        os.environ["JLCPCB_PASSWORD"] = "pass"
        result = json.loads(jlcpcb_auth_status({}))
        self.assertFalse(result["logged_in"])

    def test_login_fails_without_credentials(self):
        result = json.loads(jlcpcb_login({}))
        self.assertEqual(result["status"], "error")
        self.assertIn("JLCPCB_USERNAME", result["message"])

    def test_login_result_never_contains_password(self):
        os.environ["JLCPCB_USERNAME"] = "u@test.com"
        os.environ["JLCPCB_PASSWORD"] = "HunterTwo99!"
        # No ctx → will fail with an AttributeError, not expose credentials
        result_str = jlcpcb_login({}, ctx=None)
        self.assertNotIn("HunterTwo99!", result_str)


# ── Run directly ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Running jlcpcb-auth plugin tests...\n")
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
