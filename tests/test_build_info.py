import os
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from inventory.context_processors import build_info
from inventory.permissions import ROLE_ASSISTANT, ROLE_MANAGER
from inventory.services.version_service import clear_build_info_cache, get_build_info


class VersionServiceTestCase(TestCase):
    def setUp(self):
        clear_build_info_cache()

    def tearDown(self):
        clear_build_info_cache()

    def test_build_info_from_environment_variables(self):
        with patch.dict(
            os.environ,
            {
                "APP_BUILD_TIME": "2026-10-19 18:30 UTC",
                "APP_BUILD_COMMIT": "abc1234567890",
                "APP_VERSION": "2.4.0",
                "APP_ENV": "production",
            },
        ):
            clear_build_info_cache()
            info = get_build_info()
            self.assertEqual(info["build_time"], "2026-10-19 18:30 UTC")
            self.assertEqual(info["commit_short"], "abc1234")
            self.assertEqual(info["version"], "2.4.0")
            self.assertEqual(info["environment"], "production")
            self.assertEqual(info["environment_badge"], "PROD")
            self.assertIn("bg-emerald-100", info["badge_css"])
            self.assertEqual(info["formatted_display"], "2026-10-19 18:30 UTC (abc1234)")

    def test_build_info_from_file_fallback(self, tmp_path=None):
        test_dir = Path("tmp_test_build_info")
        test_dir.mkdir(exist_ok=True)
        date_file = test_dir / "build_date.txt"
        commit_file = test_dir / "build_commit.txt"
        date_file.write_text("2026-10-19 15:00 UTC\n", encoding="utf-8")
        commit_file.write_text("fedcba987654\n", encoding="utf-8")

        try:
            with patch.dict(os.environ, {"APP_BUILD_TIME": "", "APP_BUILD_COMMIT": ""}, clear=True):
                with override_settings(BASE_DIR=test_dir, APP_BUILD_TIME="", APP_BUILD_COMMIT=""):
                    clear_build_info_cache()
                    info = get_build_info()
                    self.assertEqual(info["build_time"], "2026-10-19 15:00 UTC")
                    self.assertEqual(info["commit_short"], "fedcba9")
                    self.assertTrue(info["is_docker"])
        finally:
            if date_file.exists():
                date_file.unlink()
            if commit_file.exists():
                commit_file.unlink()
            if test_dir.exists():
                test_dir.rmdir()

    def test_build_info_git_fallback(self):
        # In this repository, .git exists
        with patch.dict(os.environ, {"APP_BUILD_TIME": "", "APP_BUILD_COMMIT": ""}):
            with override_settings(APP_BUILD_TIME="", APP_BUILD_COMMIT=""):
                clear_build_info_cache()
                info = get_build_info()
                # Should resolve either from git or local fallback without crashing
                self.assertTrue(bool(info["build_time"]))
                self.assertTrue(bool(info["commit_short"]))
                self.assertIn(info["environment_badge"], ["DEV", "STAGING", "PROD"])

    def test_build_info_staging_environment(self):
        with patch.dict(os.environ, {"APP_ENV": "staging"}):
            clear_build_info_cache()
            info = get_build_info()
            self.assertEqual(info["environment"], "staging")
            self.assertEqual(info["environment_badge"], "STAGING")
            self.assertIn("bg-amber-100", info["badge_css"])

    def test_build_info_graceful_missing_fallback(self):
        with patch.dict(os.environ, {"APP_BUILD_TIME": "", "APP_BUILD_COMMIT": "", "APP_ENV": ""}):
            with override_settings(
                BASE_DIR=Path("non_existent_dir_for_test"),
                DEBUG=True,
                APP_BUILD_TIME="",
                APP_BUILD_COMMIT="",
                APP_ENV="",
            ):
                with patch("inventory.services.version_service._get_git_output", return_value=None):
                    clear_build_info_cache()
                    info = get_build_info()
                    self.assertEqual(info["build_time"], "Local Dev")
                    self.assertIsNone(info["commit_short"])
                    self.assertEqual(info["environment_badge"], "DEV")

    def test_context_processor(self):
        client = Client()
        response = client.get(reverse("inventory:login"))
        self.assertIn("build_info", response.context)
        info = response.context["build_info"]
        self.assertIn("build_time", info)
        self.assertIn("environment_badge", info)
        direct_result = build_info(response.wsgi_request)
        self.assertIn("build_info", direct_result)



class FooterTemplateRenderingTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        manager_group, _ = Group.objects.get_or_create(name=ROLE_MANAGER)
        Group.objects.get_or_create(name=ROLE_ASSISTANT)

        cls.manager = User.objects.create_user(
            username="manager_build_test",
            password="TestPassword123!",
            is_staff=True,
        )
        cls.manager.groups.add(manager_group)

    def setUp(self):
        clear_build_info_cache()

    def tearDown(self):
        clear_build_info_cache()

    def test_footer_renders_build_info_on_login_screen(self):
        with patch.dict(
            os.environ,
            {
                "APP_BUILD_TIME": "2026-10-19 18:30 UTC",
                "APP_BUILD_COMMIT": "9d931b9",
                "APP_ENV": "production",
            },
        ):
            clear_build_info_cache()
            response = self.client.get(reverse("inventory:login"))
            self.assertEqual(response.status_code, 200)
            content = response.content.decode("utf-8")
            self.assertIn('id="footer-build-time"', content)
            self.assertIn("2026-10-19 18:30 UTC", content)
            self.assertIn('id="footer-build-sha"', content)
            self.assertIn("9d931b9", content)
            self.assertIn('id="footer-build-env"', content)
            self.assertIn("PROD", content)

    def test_footer_renders_build_info_on_dashboard(self):
        self.client.force_login(self.manager)
        with patch.dict(
            os.environ,
            {
                "APP_BUILD_TIME": "2026-10-19 18:30 UTC",
                "APP_BUILD_COMMIT": "f78d80c",
                "APP_ENV": "staging",
            },
        ):
            clear_build_info_cache()
            response = self.client.get(reverse("inventory:dashboard"))
            self.assertEqual(response.status_code, 200)
            content = response.content.decode("utf-8")
            self.assertIn('id="footer-build-time"', content)
            self.assertIn("2026-10-19 18:30 UTC", content)
            self.assertIn('id="footer-build-sha"', content)
            self.assertIn("f78d80c", content)
            self.assertIn("STAGING", content)

    def test_footer_spanish_localization(self):
        self.client.force_login(self.manager)
        with patch.dict(
            os.environ,
            {
                "APP_BUILD_TIME": "2026-10-19 18:30 UTC",
                "APP_BUILD_COMMIT": "f78d80c",
                "APP_ENV": "production",
            },
        ):
            clear_build_info_cache()
            response = self.client.get(
                reverse("inventory:dashboard"),
                HTTP_ACCEPT_LANGUAGE="es",
            )
            self.assertEqual(response.status_code, 200)
            content = response.content.decode("utf-8")
            self.assertIn("Compilación:", content)
            self.assertIn("Commit:", content)
