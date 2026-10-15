import io
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from PIL import Image

from inventory.models import Product
from inventory.permissions import ROLE_ASSISTANT

User = get_user_model()


class GenerateAIViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.manager = User.objects.create_user(username="manager_ai", password="password123", is_staff=True)
        self.assistant = User.objects.create_user(username="asst_ai", password="password123")
        asst_group = Group.objects.create(name=ROLE_ASSISTANT)
        self.assistant.groups.add(asst_group)

        self.product = Product.objects.create(
            raw_note="Vintage 90s Carhartt jacket dark brown",
            created_by=self.assistant
        )
        self.ai_url = reverse("inventory:generate_ai", kwargs={"pk": self.product.pk})

    @patch("inventory.services.ai_service.generate_product_listing")
    def test_manager_can_trigger_ai_generation(self, mock_generate):
        mock_generate.return_value = {
            "title": "Vintage 1990s Carhartt Detroit Jacket - Dark Brown",
            "description": "• Heavyweight canvas\n• Authentic workwear patina\n• Clean lining"
        }

        self.client.login(username="manager_ai", password="password123")
        resp = self.client.post(self.ai_url)

        self.assertRedirects(resp, reverse("inventory:product_detail", kwargs={"pk": self.product.pk}))
        self.product.refresh_from_db()
        self.assertEqual(self.product.ai_title, "Vintage 1990s Carhartt Detroit Jacket - Dark Brown")
        self.assertEqual(self.product.ai_description, "• Heavyweight canvas\n• Authentic workwear patina\n• Clean lining")
        # Ensure raw_note is strictly preserved!
        self.assertEqual(self.product.raw_note, "Vintage 90s Carhartt jacket dark brown")

    def test_assistant_cannot_trigger_ai(self):
        self.client.login(username="asst_ai", password="password123")
        # Expect permission denied (HTTP 403)
        resp = self.client.post(self.ai_url)
        self.assertEqual(resp.status_code, 403)

    def test_get_request_redirects_to_detail(self):
        self.client.login(username="manager_ai", password="password123")
        resp = self.client.get(self.ai_url)
        self.assertRedirects(resp, reverse("inventory:product_detail", kwargs={"pk": self.product.pk}))


class IntakeIdentifyViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("inventory:intake_identify")
        self.assistant = User.objects.create_user(username="asst_preflight", password="password123")
        asst_group, _ = Group.objects.get_or_create(name=ROLE_ASSISTANT)
        self.assistant.groups.add(asst_group)

        self.manager = User.objects.create_user(username="mgr_preflight", password="password123", is_staff=True)

    def create_dummy_image(self, name="photo.jpg", format="JPEG"):
        buf = io.BytesIO()
        img = Image.new("RGB", (60, 60), color="blue")
        img.save(buf, format=format)
        buf.seek(0)
        return SimpleUploadedFile(name, buf.getvalue(), content_type=f"image/{format.lower()}")

    def test_anonymous_user_redirected_to_login(self):
        resp = self.client.post(self.url)
        self.assertRedirects(resp, f"{reverse('inventory:login')}?next={self.url}")

    def test_get_method_not_allowed(self):
        self.client.login(username="asst_preflight", password="password123")
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 405)
        data = resp.json()
        self.assertFalse(data["success"])
        self.assertIn("Method not allowed", data["error"])

    def test_post_without_files_returns_400(self):
        self.client.login(username="asst_preflight", password="password123")
        resp = self.client.post(self.url, {"raw_note": "Some notes"})
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data["success"])
        self.assertIn("at least one photo", data["error"])

    def test_post_with_invalid_file_extension_returns_400(self):
        self.client.login(username="asst_preflight", password="password123")
        invalid_file = SimpleUploadedFile("document.txt", b"plain text content", content_type="text/plain")
        resp = self.client.post(self.url, {"images": [invalid_file]})
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data["success"])

    def test_post_with_exceeded_image_count_returns_400(self):
        self.client.login(username="asst_preflight", password="password123")
        images = [self.create_dummy_image(f"photo_{i}.jpg") for i in range(11)]
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

        self.client.login(username="asst_preflight", password="password123")
        img = self.create_dummy_image("shoe.jpg")
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

        self.client.login(username="mgr_preflight", password="password123")
        img = self.create_dummy_image("watch.jpg")
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

        self.client.login(username="asst_preflight", password="password123")
        img = self.create_dummy_image("item.jpg")
        resp = self.client.post(self.url, {"images": [img]})

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "Gemini API unavailable")
