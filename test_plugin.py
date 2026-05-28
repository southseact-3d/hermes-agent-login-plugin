"""
Unit tests for the jlcpcb-auth plugin.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from credentials import (
    PASSWORD_KEY,
    USERNAME_KEY,
    clear_credentials,
    credentials_available,
    get_credentials,
    set_credentials,
    username_hint,
)
from hooks import post_tool_call
from schemas import JLCPCB_AUTH_STATUS, JLCPCB_LOGIN, JLCPCB_LOGOUT
from tools import (
    _extract_error_text,
    _find_ref,
    _is_tab_active,
    _sanitise_error,
    _session,
    jlcpcb_auth_status,
    jlcpcb_login,
)

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


def _load_dashboard_api_module():
    path = Path(__file__).parent / "dashboard" / "plugin_api.py"
    spec = importlib.util.spec_from_file_location("jlcpcb_dashboard_api", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TempEnvFileMixin:
    def setUp(self):
        super().setUp()
        self._temp_dir = tempfile.TemporaryDirectory()
        self._env_path = Path(self._temp_dir.name) / ".env"
        os.environ["HERMES_ENV_FILE"] = str(self._env_path)
        os.environ.pop(USERNAME_KEY, None)
        os.environ.pop(PASSWORD_KEY, None)
        _session["logged_in"] = False
        _session["logged_in_at"] = None
        _session["username_hint"] = None

    def tearDown(self):
        clear_credentials()
        os.environ.pop("HERMES_ENV_FILE", None)
        self._temp_dir.cleanup()
        super().tearDown()


class TestPluginMetadata(unittest.TestCase):
    def test_plugin_yaml_no_requires_env(self):
        content = (Path(__file__).parent / "plugin.yaml").read_text()
        self.assertNotIn("requires_env:", content)

    def test_dashboard_manifest_has_api_and_tab_path(self):
        manifest = json.loads((Path(__file__).parent / "dashboard" / "manifest.json").read_text())
        self.assertEqual(manifest["name"], "jlcpcb-auth")
        self.assertIn("api", manifest)
        self.assertIn("entry", manifest)
        self.assertEqual(manifest["tab"]["path"], "/jlcpcb-auth")

    def test_dashboard_registration_name_matches_manifest(self):
        manifest = json.loads((Path(__file__).parent / "dashboard" / "manifest.json").read_text())
        js = (Path(__file__).parent / "dashboard" / "dist" / "index.js").read_text()
        match = re.search(r'const\s+pluginName\s*=\s*"([^"]+)"', js)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), manifest["name"])


class TestSchemas(unittest.TestCase):
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
        self.assertIn("no credentials", desc)


class TestCredentialService(TempEnvFileMixin, unittest.TestCase):
    def test_set_get_and_hint(self):
        set_credentials("testuser@example.com", "SuperSecret123!")
        username, password = get_credentials()
        self.assertEqual(username, "testuser@example.com")
        self.assertEqual(password, "SuperSecret123!")
        self.assertTrue(credentials_available())
        self.assertEqual(username_hint(), "tes***")

    def test_clear_credentials(self):
        set_credentials("u@example.com", "password")
        clear_credentials()
        username, password = get_credentials()
        self.assertIsNone(username)
        self.assertIsNone(password)
        self.assertFalse(credentials_available())

    def test_preserves_unrelated_env_entries(self):
        self._env_path.write_text("# existing\nOTHER_TOKEN=abc\n")
        set_credentials("user@example.com", "pw")
        data = self._env_path.read_text()
        self.assertIn("OTHER_TOKEN=abc", data)

    def test_handles_special_characters(self):
        complex_password = "line1\nline2=with spaces"
        set_credentials("special@example.com", complex_password)
        username, password = get_credentials()
        self.assertEqual(username, "special@example.com")
        self.assertEqual(password, complex_password)


class TestCredentialRedaction(TempEnvFileMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        set_credentials("testuser@example.com", "SuperSecret123!")

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


class TestAccessibilityTreeParser(unittest.TestCase):
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


class TestAuthStatusTool(TempEnvFileMixin, unittest.TestCase):
    def test_status_when_no_credentials(self):
        result = json.loads(jlcpcb_auth_status({}))
        self.assertFalse(result["logged_in"])
        self.assertIn("error", result)

    def test_status_when_not_logged_in(self):
        set_credentials("user@test.com", "pass")
        result = json.loads(jlcpcb_auth_status({}))
        self.assertFalse(result["logged_in"])

    def test_login_fails_without_credentials(self):
        result = json.loads(jlcpcb_login({}))
        self.assertEqual(result["status"], "error")
        self.assertIn("JLCPCB_USERNAME", result["message"])

    def test_login_result_never_contains_password(self):
        set_credentials("u@test.com", "HunterTwo99!")
        result_str = jlcpcb_login({}, ctx=None)
        self.assertNotIn("HunterTwo99!", result_str)


class TestDashboardApi(TempEnvFileMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.api = _load_dashboard_api_module()

    def _decode(self, response):
        return json.loads(response.body.decode())

    def test_status_endpoint(self):
        response = asyncio.run(self.api.get_status())
        payload = self._decode(response)
        self.assertIn("credentials", payload)
        self.assertFalse(payload["credentials"]["username_set"])

    def test_save_and_clear_credentials_endpoints(self):
        payload = self.api.CredentialsPayload(username="dash@example.com", password="pw123")
        save_response = asyncio.run(self.api.save_credentials(payload))
        save_body = self._decode(save_response)
        self.assertTrue(save_body["success"])

        status_response = asyncio.run(self.api.get_status())
        status_body = self._decode(status_response)
        self.assertTrue(status_body["credentials"]["username_set"])
        self.assertTrue(status_body["credentials"]["password_set"])

        clear_response = asyncio.run(self.api.clear_stored_credentials())
        clear_body = self._decode(clear_response)
        self.assertTrue(clear_body["success"])

    def test_save_credentials_keeps_password_whitespace(self):
        payload = self.api.CredentialsPayload(
            username="whitespace@example.com",
            password="  Secret With Spaces  ",
        )
        save_response = asyncio.run(self.api.save_credentials(payload))
        save_body = self._decode(save_response)
        self.assertTrue(save_body["success"])

        username, password = get_credentials()
        self.assertEqual(username, "whitespace@example.com")
        self.assertEqual(password, "  Secret With Spaces  ")


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
