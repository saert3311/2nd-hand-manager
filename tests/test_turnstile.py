import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, TestCase, override_settings

from inventory.context_processors import turnstile as turnstile_context_processor
from inventory.services.turnstile_service import (
    DUMMY_SECRET_ALWAYS_FAIL,
    DUMMY_SECRET_ALWAYS_PASS,
    verify_turnstile_token,
)


class TurnstileServiceTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_empty_or_whitespace_token_returns_false(self):
        self.assertFalse(verify_turnstile_token(""))
        self.assertFalse(verify_turnstile_token("   "))
        self.assertFalse(verify_turnstile_token(None))

    @override_settings(TURNSTILE_SECRET_KEY="")
    def test_missing_secret_key_returns_false(self):
        self.assertFalse(verify_turnstile_token("valid-looking-token"))

    @override_settings(TURNSTILE_SECRET_KEY=DUMMY_SECRET_ALWAYS_PASS)
    def test_cloudflare_dummy_always_pass_key(self):
        self.assertTrue(verify_turnstile_token("dummy-token"))

    @override_settings(TURNSTILE_SECRET_KEY=DUMMY_SECRET_ALWAYS_FAIL)
    def test_cloudflare_dummy_always_fail_key(self):
        self.assertFalse(verify_turnstile_token("dummy-token"))

    @override_settings(TURNSTILE_SECRET_KEY="test-secret-key-12345", TURNSTILE_TIMEOUT=3.0)
    @patch("urllib.request.urlopen")
    def test_successful_verification_with_mocked_http(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({"success": True}).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        result = verify_turnstile_token("client-token-abc", remote_ip="192.168.1.50")
        self.assertTrue(result)

        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.full_url, "https://challenges.cloudflare.com/turnstile/v0/siteverify")
        self.assertEqual(req.get_method(), "POST")

    @override_settings(TURNSTILE_SECRET_KEY="test-secret-key-12345")
    @patch("urllib.request.urlopen")
    def test_failed_verification_returns_false(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({
            "success": False,
            "error-codes": ["invalid-input-response"],
        }).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        result = verify_turnstile_token("invalid-client-token")
        self.assertFalse(result)

    @override_settings(TURNSTILE_SECRET_KEY="test-secret-key-12345")
    @patch("urllib.request.urlopen")
    def test_timeout_error_fails_closed(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError("Connection timed out")
        result = verify_turnstile_token("token-under-timeout")
        self.assertFalse(result)

    @override_settings(TURNSTILE_SECRET_KEY="test-secret-key-12345")
    @patch("urllib.request.urlopen")
    def test_http_error_fails_closed(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://challenges.cloudflare.com/turnstile/v0/siteverify",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=io.BytesIO(b"error"),
        )
        result = verify_turnstile_token("token-under-500")
        self.assertFalse(result)

    @override_settings(TURNSTILE_SECRET_KEY="test-secret-key-12345")
    @patch("urllib.request.urlopen")
    def test_url_error_fails_closed(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("DNS resolution failed")
        result = verify_turnstile_token("token-dns-failure")
        self.assertFalse(result)

    @override_settings(TURNSTILE_SECRET_KEY="test-secret-key-12345")
    @patch("urllib.request.urlopen")
    def test_invalid_json_fails_closed(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b"<html>Cloudflare Gateway Error</html>"
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        result = verify_turnstile_token("token-bad-json")
        self.assertFalse(result)

    @override_settings(TURNSTILE_SITE_KEY="site-key-xyz", TURNSTILE_ENABLED=True)
    def test_turnstile_context_processor_enabled(self):
        request = self.factory.get("/login/")
        context = turnstile_context_processor(request)
        self.assertEqual(context["TURNSTILE_SITE_KEY"], "site-key-xyz")
        self.assertTrue(context["TURNSTILE_ENABLED"])

    @override_settings(TURNSTILE_SITE_KEY="", TURNSTILE_ENABLED=False)
    def test_turnstile_context_processor_disabled(self):
        request = self.factory.get("/login/")
        context = turnstile_context_processor(request)
        self.assertEqual(context["TURNSTILE_SITE_KEY"], "")
        self.assertFalse(context["TURNSTILE_ENABLED"])


class PublicLoginTurnstileTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user = User.objects.create_user(username="turnstile_user", password="secretpassword")

    @override_settings(
        TURNSTILE_ENABLED=True,
        TURNSTILE_SITE_KEY="1x00000000000000000000AA",
        TURNSTILE_SECRET_KEY="1x0000000000000000000000000000000AA",
    )
    def test_login_page_renders_turnstile_widget_when_enabled(self):
        response = self.client.get("/login/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "challenges.cloudflare.com/turnstile/v0/api.js")
        self.assertContains(response, 'class="cf-turnstile"')
        self.assertContains(response, 'data-sitekey="1x00000000000000000000AA"')
        self.assertContains(response, 'data-theme="light"')

    @override_settings(
        TURNSTILE_ENABLED=False,
        TURNSTILE_SITE_KEY="",
        TURNSTILE_SECRET_KEY="",
    )
    def test_login_page_omits_turnstile_widget_when_disabled(self):
        response = self.client.get("/login/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "challenges.cloudflare.com/turnstile/v0/api.js")
        self.assertNotContains(response, 'class="cf-turnstile"')

    @override_settings(
        TURNSTILE_ENABLED=True,
        TURNSTILE_SITE_KEY="test-site-key",
        TURNSTILE_SECRET_KEY="test-secret-key",
    )
    def test_login_post_missing_token_fails_validation(self):
        response = self.client.post("/login/", {
            "username": "turnstile_user",
            "password": "secretpassword",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["user"].is_authenticated)
        self.assertContains(response, "Please complete the security challenge.")

    @override_settings(
        TURNSTILE_ENABLED=True,
        TURNSTILE_SITE_KEY="test-site-key",
        TURNSTILE_SECRET_KEY="test-secret-key",
    )
    @patch("inventory.forms.verify_turnstile_token", return_value=False)
    def test_login_post_invalid_token_fails_validation(self, mock_verify):
        response = self.client.post("/login/", {
            "username": "turnstile_user",
            "password": "secretpassword",
            "cf-turnstile-response": "invalid-token",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Security verification failed. Please try again.")
        mock_verify.assert_called_once()

    @override_settings(
        TURNSTILE_ENABLED=True,
        TURNSTILE_SITE_KEY="test-site-key",
        TURNSTILE_SECRET_KEY="test-secret-key",
    )
    def test_turnstile_error_messages_in_spanish(self):
        from django.utils import translation
        with translation.override("es"):
            response = self.client.post("/login/", {
                "username": "turnstile_user",
                "password": "secretpassword",
            }, HTTP_ACCEPT_LANGUAGE="es")
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Por favor, completa la verificación de seguridad.")


    @override_settings(
        TURNSTILE_ENABLED=True,
        TURNSTILE_SITE_KEY="test-site-key",
        TURNSTILE_SECRET_KEY="test-secret-key",
    )
    @patch("inventory.forms.verify_turnstile_token", return_value=True)
    def test_login_post_valid_token_succeeds(self, mock_verify):
        response = self.client.post("/login/", {
            "username": "turnstile_user",
            "password": "secretpassword",
            "cf-turnstile-response": "valid-token-123",
        })
        # Should redirect to intake or dashboard
        self.assertEqual(response.status_code, 302)
        mock_verify.assert_called_once()

    @override_settings(
        TURNSTILE_ENABLED=False,
        TURNSTILE_SITE_KEY="",
        TURNSTILE_SECRET_KEY="",
    )
    def test_login_post_without_token_succeeds_when_disabled(self):
        response = self.client.post("/login/", {
            "username": "turnstile_user",
            "password": "secretpassword",
        })
        self.assertEqual(response.status_code, 302)


class AdminLoginTurnstileTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.manager = User.objects.create_user(
            username="turnstile_manager",
            password="managersecret",
            is_staff=True,
        )

    @override_settings(
        TURNSTILE_ENABLED=True,
        TURNSTILE_SITE_KEY="1x00000000000000000000AA",
        TURNSTILE_SECRET_KEY="1x0000000000000000000000000000000AA",
    )
    def test_admin_login_page_renders_turnstile_widget_when_enabled(self):
        response = self.client.get("/admin/login/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "challenges.cloudflare.com/turnstile/v0/api.js")
        self.assertContains(response, 'class="cf-turnstile"')
        self.assertContains(response, 'data-sitekey="1x00000000000000000000AA"')
        self.assertContains(response, 'data-theme="light"')

    @override_settings(
        TURNSTILE_ENABLED=False,
        TURNSTILE_SITE_KEY="",
        TURNSTILE_SECRET_KEY="",
    )
    def test_admin_login_page_omits_turnstile_widget_when_disabled(self):
        response = self.client.get("/admin/login/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "challenges.cloudflare.com/turnstile/v0/api.js")
        self.assertNotContains(response, 'class="cf-turnstile"')

    @override_settings(
        TURNSTILE_ENABLED=True,
        TURNSTILE_SITE_KEY="test-site-key",
        TURNSTILE_SECRET_KEY="test-secret-key",
    )
    def test_admin_login_post_missing_token_fails_validation(self):
        response = self.client.post("/admin/login/", {
            "username": "turnstile_manager",
            "password": "managersecret",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["user"].is_authenticated)
        self.assertContains(response, "Please complete the security challenge.")

    @override_settings(
        TURNSTILE_ENABLED=True,
        TURNSTILE_SITE_KEY="test-site-key",
        TURNSTILE_SECRET_KEY="test-secret-key",
    )
    @patch("inventory.forms.verify_turnstile_token", return_value=False)
    def test_admin_login_post_invalid_token_fails_validation(self, mock_verify):
        response = self.client.post("/admin/login/", {
            "username": "turnstile_manager",
            "password": "managersecret",
            "cf-turnstile-response": "bad-admin-token",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["user"].is_authenticated)
        self.assertContains(response, "Security verification failed. Please try again.")
        mock_verify.assert_called_once()

    @override_settings(
        TURNSTILE_ENABLED=True,
        TURNSTILE_SITE_KEY="test-site-key",
        TURNSTILE_SECRET_KEY="test-secret-key",
    )
    @patch("inventory.forms.verify_turnstile_token", return_value=True)
    def test_admin_login_post_valid_token_succeeds(self, mock_verify):
        response = self.client.post("/admin/login/", {
            "username": "turnstile_manager",
            "password": "managersecret",
            "cf-turnstile-response": "good-admin-token",
        })
        self.assertEqual(response.status_code, 302)
        mock_verify.assert_called_once()

    @override_settings(
        TURNSTILE_ENABLED=False,
        TURNSTILE_SITE_KEY="",
        TURNSTILE_SECRET_KEY="",
    )
    def test_admin_login_post_without_token_succeeds_when_disabled(self):
        response = self.client.post("/admin/login/", {
            "username": "turnstile_manager",
            "password": "managersecret",
        })
        self.assertEqual(response.status_code, 302)


