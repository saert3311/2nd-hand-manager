from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import translation

from inventory.models import Product
from tests.helpers import make_test_image_file

User = get_user_model()


class IntakeIdentificationGateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="assistant_gate", password="password123")
        cls.url = reverse("inventory:intake")
        cls.identify_url = reverse("inventory:intake_identify")

    def setUp(self):
        self.client.force_login(self.user)

    def create_dummy_image(self, name="photo.jpg", format="JPEG"):
        return make_test_image_file(name=name, size=(60, 60), color="blue", image_format=format, content_type=f"image/{format.lower()}")

    def test_submit_button_initially_disabled_in_html(self):
        """Verify the Save button renders with disabled attribute and accessibility attributes on initial page load."""
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

        # Check button attributes
        html = resp.content.decode("utf-8")
        self.assertIn('id="submitBtn"', html)
        self.assertIn("disabled", html)
        self.assertIn('aria-disabled="true"', html)
        self.assertIn('aria-describedby="submitHelpText"', html)

        # Check helper text element
        self.assertIn('id="submitHelpText"', html)
        self.assertIn("Identify product with AI first to enable saving", html)

    def test_submit_button_spanish_localization(self):
        """Verify localized Spanish text for the mandatory identification helper text."""
        with translation.override("es"):
            resp = self.client.get(self.url, HTTP_ACCEPT_LANGUAGE="es")
            self.assertEqual(resp.status_code, 200)
            html = resp.content.decode("utf-8")
            self.assertIn("Identifica primero el producto con IA para habilitar el guardado", html)
            self.assertIn("Producto identificado — listo para guardar", html)
            self.assertIn("Por favor, identifica el producto con IA antes de guardar.", html)

    def test_template_contains_identification_gate_controls(self):
        """Verify presence of intake form, AI identify trigger, guarded submit button, and live help text."""
        resp = self.client.get(self.url)
        html = resp.content.decode("utf-8")

        self.assertIn('id="intakeForm"', html)
        self.assertIn('id="identifyBtn"', html)
        self.assertIn('id="submitBtn"', html)
        self.assertIn('id="submitHelpText"', html)
        self.assertIn('aria-disabled="true"', html)

    @patch("inventory.views.identify_intake_product")
    def test_identify_preflight_endpoint_success_enables_gate(self, mock_identify):
        """Verify identify endpoint returns JSON success for assistant."""
        self.client.login(username="assistant_gate", password="password123")
        mock_identify.return_value = {
            "success": True,
            "identified_title": "Sony Walkman WM-D6C",
            "category": "Electronics",
            "detected_attributes": ["Vintage", "Cassette Player"],
            "suggested_note": "Includes original carry case and manual.",
            "missing_or_recommended_info": ["Check battery compartment for corrosion."],
            "estimated_retail_price": 350.00,
            "estimated_resale_price": 180.00,
        }

        img = self.create_dummy_image("walkman.jpg")
        resp = self.client.post(self.identify_url, {"images": [img], "raw_note": "Vintage walkman"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["identified_title"], "Sony Walkman WM-D6C")
        self.assertEqual(data["estimated_retail_price"], 350.00)
        self.assertEqual(data["estimated_resale_price"], 180.00)

    @patch("inventory.views.identify_intake_product")
    def test_identify_preflight_endpoint_failure_fallback_response(self, mock_identify):
        """Verify identify endpoint handles error safely (returning JSON error) without breaking the flow."""
        self.client.login(username="assistant_gate", password="password123")
        mock_identify.return_value = {
            "success": False,
            "error": "Could not identify product from photos.",
            "identified_title": None,
            "category": None,
            "detected_attributes": [],
            "suggested_note": None,
            "missing_or_recommended_info": [],
            "estimated_retail_price": None,
            "estimated_resale_price": None,
        }

        img = self.create_dummy_image("unclear.jpg")
        resp = self.client.post(self.identify_url, {"images": [img]})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["success"])
        self.assertIn("Could not identify product", data["error"])

    def test_backend_submission_persists_valid_product(self):
        """Verify that the backend intake view persists valid submissions successfully."""
        self.client.login(username="assistant_gate", password="password123")
        img = self.create_dummy_image("item.jpg")

        resp = self.client.post(
            self.url,
            {
                "raw_note": "Handmade wooden chair",
                "images": [img],
                "ai_title": "Vintage Oak Dining Chair",
                "estimated_retail_price": "120.00",
                "estimated_resale_price": "60.00",
                "sale_price": "55.00",
            },
        )
        self.assertRedirects(resp, self.url)
        self.assertEqual(Product.objects.count(), 1)
        prod = Product.objects.first()
        self.assertEqual(prod.raw_note, "Handmade wooden chair")
        self.assertEqual(prod.ai_title, "Vintage Oak Dining Chair")
        self.assertEqual(prod.estimated_retail_price, Decimal("120.00"))
        self.assertEqual(prod.estimated_resale_price, Decimal("60.00"))
        self.assertEqual(prod.sale_price, Decimal("55.00"))
