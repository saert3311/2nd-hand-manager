import io
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import translation
from PIL import Image

from inventory.models import Product

User = get_user_model()


class IntakeIdentificationGateTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="assistant_gate", password="password123")
        self.url = reverse("inventory:intake")
        self.identify_url = reverse("inventory:intake_identify")

    def create_dummy_image(self, name="photo.jpg", format="JPEG"):
        buf = io.BytesIO()
        img = Image.new("RGB", (60, 60), color="blue")
        img.save(buf, format=format)
        buf.seek(0)
        return SimpleUploadedFile(name, buf.getvalue(), content_type=f"image/{format.lower()}")

    def test_submit_button_initially_disabled_in_html(self):
        """Verify the Save button renders with disabled attribute and accessibility attributes on initial page load."""
        self.client.login(username="assistant_gate", password="password123")
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
        self.client.login(username="assistant_gate", password="password123")
        with translation.override("es"):
            resp = self.client.get(self.url, HTTP_ACCEPT_LANGUAGE="es")
            self.assertEqual(resp.status_code, 200)
            html = resp.content.decode("utf-8")
            self.assertIn("Identifica primero el producto con IA para habilitar el guardado", html)
            self.assertIn("Producto identificado — listo para guardar", html)
            self.assertIn("Por favor, identifica el producto con IA antes de guardar.", html)

    def test_template_contains_state_machine_and_guards(self):
        """Verify presence of JS state machine variables, functions, and client submit guard."""
        self.client.login(username="assistant_gate", password="password123")
        resp = self.client.get(self.url)
        html = resp.content.decode("utf-8")

        # Check state variable
        self.assertIn("let hasIdentified = false;", html)

        # Check update function
        self.assertIn("function updateSubmitButtonState()", html)

        # Check identifyBtn click finally sets hasIdentified to true
        self.assertIn("hasIdentified = true;", html)

        # Check zero-files resets hasIdentified to false
        self.assertIn("hasIdentified = false;", html)

        # Check submit listener guard
        self.assertIn("if (!hasIdentified)", html)

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
