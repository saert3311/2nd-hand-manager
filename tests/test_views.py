from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from inventory.models import Product
from tests.helpers import create_role_users, make_test_image_file


class GenerateAIViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager, cls.assistant = create_role_users(prefix="views_ai")
        cls.manager.is_staff = True
        cls.manager.save(update_fields=["is_staff"])

    def setUp(self):
        self.product = Product.objects.create(
            raw_note="Vintage 90s Carhartt jacket dark brown",
            created_by=self.assistant,
        )
        self.ai_url = reverse("inventory:generate_ai", kwargs={"pk": self.product.pk})

    @patch("inventory.services.ai_service.generate_product_listing")
    def test_manager_can_trigger_ai_generation(self, mock_generate):
        mock_generate.return_value = {
            "title": "Vintage 1990s Carhartt Detroit Jacket - Dark Brown",
            "description": "• Heavyweight canvas\n• Authentic workwear patina\n• Clean lining",
        }

        self.client.force_login(self.manager)
        resp = self.client.post(self.ai_url)

        self.assertRedirects(resp, reverse("inventory:product_detail", kwargs={"pk": self.product.pk}))
        self.product.refresh_from_db()
        self.assertEqual(self.product.ai_title, "Vintage 1990s Carhartt Detroit Jacket - Dark Brown")
        self.assertEqual(self.product.ai_description, "• Heavyweight canvas\n• Authentic workwear patina\n• Clean lining")
        # Ensure raw_note is strictly preserved!
        self.assertEqual(self.product.raw_note, "Vintage 90s Carhartt jacket dark brown")

    def test_assistant_cannot_trigger_ai(self):
        self.client.force_login(self.assistant)
        resp = self.client.post(self.ai_url)
        self.assertEqual(resp.status_code, 403)

    def test_get_request_redirects_to_detail(self):
        self.client.force_login(self.manager)
        resp = self.client.get(self.ai_url)
        self.assertRedirects(resp, reverse("inventory:product_detail", kwargs={"pk": self.product.pk}))


class IntakeIdentifyViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.url = reverse("inventory:intake_identify")
        cls.manager, cls.assistant = create_role_users(prefix="preflight")
        cls.manager.is_staff = True
        cls.manager.save(update_fields=["is_staff"])

    def test_anonymous_user_redirected_to_login(self):
        resp = self.client.post(self.url)
        self.assertRedirects(resp, f"{reverse('inventory:login')}?next={self.url}")

    def test_get_method_not_allowed(self):
        self.client.force_login(self.assistant)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 405)
        data = resp.json()
        self.assertFalse(data["success"])
        self.assertIn("Method not allowed", data["error"])

    def test_post_without_files_returns_400(self):
        self.client.force_login(self.assistant)
        resp = self.client.post(self.url, {"raw_note": "Some notes"})
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data["success"])
        self.assertIn("at least one photo", data["error"])

    def test_post_with_invalid_file_extension_returns_400(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.force_login(self.assistant)
        invalid_file = SimpleUploadedFile("document.txt", b"plain text content", content_type="text/plain")
        resp = self.client.post(self.url, {"images": [invalid_file]})
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data["success"])

    def test_post_with_exceeded_image_count_returns_400(self):
        self.client.force_login(self.assistant)
        images = [make_test_image_file(name=f"photo_{i}.jpg", size=(60, 60), color="blue") for i in range(11)]
        resp = self.client.post(self.url, {"images": images})
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data["success"])

    @patch("inventory.views.identify_intake_product")
    def test_assistant_successful_identification(self, mock_identify):
        mock_identify.return_value = {
            "success": True,
            "identified_title": "Nike Air Max 90",
            "category": "Sneakers",
            "detected_attributes": ["White leather", "Red accents"],
            "missing_or_recommended_info": ["Check insole logo wear"],
            "suggested_note": "Nike Air Max 90. Leather good condition.",
        }

        self.client.force_login(self.assistant)
        img = make_test_image_file(name="shoe.jpg", size=(60, 60), color="blue")
        resp = self.client.post(self.url, {"images": [img], "raw_note": "Sneaker from garage"})

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["identified_title"], "Nike Air Max 90")
        self.assertEqual(data["category"], "Sneakers")
        self.assertIn("Check insole logo wear", data["missing_or_recommended_info"])
        self.assertEqual(data["suggested_note"], "Nike Air Max 90. Leather good condition.")

        mock_identify.assert_called_once()
        call_kwargs = mock_identify.call_args.kwargs
        self.assertEqual(len(call_kwargs["images_bytes"]), 1)
        self.assertEqual(call_kwargs["raw_note"], "Sneaker from garage")

    @patch("inventory.views.identify_intake_product")
    def test_manager_can_also_call_identify(self, mock_identify):
        mock_identify.return_value = {
            "success": True,
            "identified_title": "Vintage Rolex",
            "category": "Watches",
            "detected_attributes": ["Steel bezel"],
            "missing_or_recommended_info": [],
            "suggested_note": "Rolex watch.",
        }

        self.client.force_login(self.manager)
        img = make_test_image_file(name="watch.jpg", size=(60, 60), color="blue")
        resp = self.client.post(self.url, {"images": [img]})

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["identified_title"], "Vintage Rolex")

    @patch("inventory.views.identify_intake_product")
    def test_identify_ai_failure_returns_200_with_success_false(self, mock_identify):
        mock_identify.return_value = {
            "success": False,
            "error": "Gemini API unavailable",
        }

        self.client.force_login(self.assistant)
        img = make_test_image_file(name="item.jpg", size=(60, 60), color="blue")
        resp = self.client.post(self.url, {"images": [img]})

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "Gemini API unavailable")


class MobileNavigationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager, cls.assistant = create_role_users(prefix="nav")
        cls.manager.is_staff = True
        cls.manager.save(update_fields=["is_staff"])

    def test_unauthenticated_header_shows_logo_and_no_mobile_toggle(self):
        resp = self.client.get(reverse("inventory:login"))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self.assertIn("2ndHand", content)
        self.assertIn("Staging", content)
        self.assertNotIn('id="mobile-menu-button"', content)
        self.assertNotIn('id="mobile-menu"', content)
        self.assertIn('name="language" value="en"', content)

    def test_authenticated_assistant_renders_mobile_toggle_and_drawer(self):
        self.client.force_login(self.assistant)
        resp = self.client.get(reverse("inventory:intake"))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")

        self.assertIn('id="mobile-menu-button"', content)
        self.assertIn('aria-controls="mobile-menu"', content)
        self.assertIn('aria-expanded="false"', content)
        self.assertIn('id="hamburger-icon"', content)
        self.assertIn('id="close-icon"', content)

        self.assertIn('id="mobile-menu"', content)
        self.assertIn("nav_assistant", content)
        self.assertIn("Assistant", content)

        self.assertIn(reverse("inventory:intake"), content)
        self.assertIn(reverse("inventory:dashboard"), content)
        self.assertNotIn(reverse("admin:index"), content)

    def test_authenticated_manager_renders_admin_link_in_mobile_drawer(self):
        self.client.force_login(self.manager)
        resp = self.client.get(reverse("inventory:dashboard"))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")

        self.assertIn('id="mobile-menu-button"', content)
        self.assertIn("nav_manager", content)
        self.assertIn("Manager", content)
        self.assertIn(reverse("admin:index"), content)

    def test_mobile_header_renders_doubts_badge_when_pending(self):
        from inventory.models import ClarificationCategory, ProductClarification

        product = Product.objects.create(raw_note="Leather boots", created_by=self.assistant)
        ProductClarification.objects.create(
            product=product,
            category=ClarificationCategory.MEASUREMENTS,
            question="What is the heel height?",
            asked_by=self.manager,
        )

        self.client.force_login(self.assistant)
        resp = self.client.get(reverse("inventory:intake"))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")

        self.assertIn("badge-pending-clarifications", content)
        self.assertIn("status=awaiting_info", content)

    def test_spanish_translations_in_mobile_navigation(self):
        self.client.force_login(self.assistant)
        self.client.cookies["django_language"] = "es"
        resp = self.client.get(reverse("inventory:intake"))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")

        self.assertIn("Abrir menú", content)
        self.assertIn("Navegación móvil", content)
        self.assertIn("Nueva Entrada", content)
        self.assertIn("Panel de Control", content)
        self.assertIn("Asistente", content)
        self.assertIn("Cerrar Sesión", content)

