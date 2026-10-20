import io
import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from PIL import Image

from inventory.forms import ProductIntakeForm
from inventory.models import Product
from inventory.permissions import ROLE_ASSISTANT, ROLE_MANAGER
from inventory.services.ai_service import (
    IntakePreflightSchema,
    _clean_price,
    identify_intake_product,
)

User = get_user_model()


class IntakePreflightSchemaTests(TestCase):
    """Unit tests for IntakePreflightSchema Pydantic model with valuation fields."""

    def test_schema_with_valid_valuation_fields(self):
        data = {
            "identified_title": "Nike Air Max 90",
            "category": "Calzado",
            "detected_attributes": ["White/Infrared", "Leather/Mesh"],
            "missing_or_recommended_info": ["Etiqueta de talla"],
            "suggested_note": "Zapatillas Nike Air Max 90 en buen estado",
            "estimated_retail_price": 149.99,
            "estimated_resale_price": 65.50,
        }
        schema = IntakePreflightSchema(**data)
        self.assertEqual(schema.estimated_retail_price, 149.99)
        self.assertEqual(schema.estimated_resale_price, 65.50)

    def test_schema_with_none_valuation_fields(self):
        data = {
            "identified_title": "Jarrón artesanal de cerámica",
            "category": "Decoración",
            "detected_attributes": ["Cerámica esmaltada"],
            "missing_or_recommended_info": [],
            "suggested_note": "Jarrón artesanal sin sellos visibles",
            "estimated_retail_price": None,
            "estimated_resale_price": None,
        }
        schema = IntakePreflightSchema(**data)
        self.assertIsNone(schema.estimated_retail_price)
        self.assertIsNone(schema.estimated_resale_price)

    def test_schema_defaults_to_none_when_omitted(self):
        data = {
            "identified_title": "Bolso vintage",
            "category": "Accesorios",
            "suggested_note": "Bolso de cuero marrón",
        }
        schema = IntakePreflightSchema(**data)
        self.assertIsNone(schema.estimated_retail_price)
        self.assertIsNone(schema.estimated_resale_price)

    def test_clean_price_sanitization(self):
        self.assertIsNone(_clean_price(None))
        self.assertIsNone(_clean_price(-15.00))
        self.assertIsNone(_clean_price("invalid"))
        self.assertIsNone(_clean_price(10000000.00))
        self.assertEqual(_clean_price(45), 45.0)
        self.assertEqual(_clean_price("59.99"), 59.99)
        self.assertEqual(_clean_price(12.3456), 12.35)


class IdentifyIntakeProductValuationTests(TestCase):
    """Unit tests for identify_intake_product parsing valuation estimates."""

    def setUp(self):
        buf = io.BytesIO()
        img = Image.new("RGB", (50, 50), color="blue")
        img.save(buf, format="JPEG")
        self.sample_bytes = [buf.getvalue()]

    @patch("inventory.services.ai_service.genai.Client")
    def test_identify_parses_valuation_from_parsed_response(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_parsed = MagicMock()
        mock_parsed.identified_title = "Sony WH-1000XM4"
        mock_parsed.category = "Electrónica"
        mock_parsed.detected_attributes = ["Negro", "Bluetooth"]
        mock_parsed.missing_or_recommended_info = ["Comprobar cable de carga"]
        mock_parsed.suggested_note = "Auriculares con cancelación de ruido"
        mock_parsed.estimated_retail_price = 379.0
        mock_parsed.estimated_resale_price = 185.0

        mock_response = MagicMock()
        mock_response.parsed = mock_parsed
        mock_client.models.generate_content.return_value = mock_response

        with patch("inventory.services.ai_service.settings.GEMINI_API_KEY", "dummy_key"):
            result = identify_intake_product(self.sample_bytes, raw_note="Auriculares Sony")

        self.assertTrue(result["success"])
        self.assertEqual(result["identified_title"], "Sony WH-1000XM4")
        self.assertEqual(result["estimated_retail_price"], 379.0)
        self.assertEqual(result["estimated_resale_price"], 185.0)

    @patch("inventory.services.ai_service.genai.Client")
    def test_identify_parses_valuation_from_json_fallback(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.parsed = None
        mock_response.text = json.dumps({
            "identified_title": "Chaqueta Barbour Beaufort",
            "category": "Ropa Vintage",
            "detected_attributes": ["Verde oliva", "Cera"],
            "missing_or_recommended_info": ["Revisar desgaste en puños"],
            "suggested_note": "Chaqueta encerada clásica Barbour",
            "estimated_retail_price": 425.0,
            "estimated_resale_price": 160.0,
        })
        mock_client.models.generate_content.return_value = mock_response

        with patch("inventory.services.ai_service.settings.GEMINI_API_KEY", "dummy_key"):
            result = identify_intake_product(self.sample_bytes, raw_note="Barbour")

        self.assertTrue(result["success"])
        self.assertEqual(result["identified_title"], "Chaqueta Barbour Beaufort")
        self.assertEqual(result["estimated_retail_price"], 425.0)
        self.assertEqual(result["estimated_resale_price"], 160.0)

    @patch("inventory.services.ai_service.genai.Client")
    def test_identify_handles_null_valuations_gracefully(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_parsed = MagicMock()
        mock_parsed.identified_title = "Cuadro anónimo"
        mock_parsed.category = "Arte"
        mock_parsed.detected_attributes = ["Óleo"]
        mock_parsed.missing_or_recommended_info = []
        mock_parsed.suggested_note = "Pintura al óleo sobre lienzo"
        mock_parsed.estimated_retail_price = None
        mock_parsed.estimated_resale_price = None

        mock_response = MagicMock()
        mock_response.parsed = mock_parsed
        mock_client.models.generate_content.return_value = mock_response

        with patch("inventory.services.ai_service.settings.GEMINI_API_KEY", "dummy_key"):
            result = identify_intake_product(self.sample_bytes)

        self.assertTrue(result["success"])
        self.assertIsNone(result["estimated_retail_price"])
        self.assertIsNone(result["estimated_resale_price"])


class ProductModelAndFormValuationTests(TestCase):
    """Tests for Product model persistence and ProductIntakeForm binding of valuation fields."""

    def test_product_model_stores_estimated_prices(self):
        product = Product.objects.create(
            raw_note="Vintage watch",
            estimated_retail_price=Decimal("250.00"),
            estimated_resale_price=Decimal("89.95"),
            sale_price=Decimal("85.00"),
        )
        product.refresh_from_db()
        self.assertEqual(product.estimated_retail_price, Decimal("250.00"))
        self.assertEqual(product.estimated_resale_price, Decimal("89.95"))
        self.assertEqual(product.sale_price, Decimal("85.00"))

    def test_product_model_negative_price_raises_validation_error(self):
        product = Product(
            raw_note="Invalid item",
            estimated_retail_price=Decimal("-10.00"),
        )
        with self.assertRaises(ValidationError):
            product.full_clean()

    def test_product_intake_form_saves_valuation_fields(self):
        form_data = {
            "raw_note": "Fender Stratocaster Made in Mexico",
            "sale_price": "450.00",
            "ai_title": "Guitarra Fender Stratocaster MIM",
            "estimated_retail_price": "849.00",
            "estimated_resale_price": "495.00",
        }
        form = ProductIntakeForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)
        product = form.save()

        self.assertEqual(product.ai_title, "Guitarra Fender Stratocaster MIM")
        self.assertEqual(product.estimated_retail_price, Decimal("849.00"))
        self.assertEqual(product.estimated_resale_price, Decimal("495.00"))
        self.assertEqual(product.sale_price, Decimal("450.00"))


class IntakeAndDetailValuationViewTests(TestCase):
    """Integration tests for intake and detail template rendering and identify endpoint."""

    def setUp(self):
        self.client = Client()
        self.assistant_group, _ = Group.objects.get_or_create(name=ROLE_ASSISTANT)
        self.manager_group, _ = Group.objects.get_or_create(name=ROLE_MANAGER)

        self.assistant = User.objects.create_user(username="assistant_val", password="password123")
        self.assistant.groups.add(self.assistant_group)

        self.manager = User.objects.create_user(username="manager_val", password="password123")
        self.manager.groups.add(self.manager_group)

    def create_dummy_image(self, name="item.jpg"):
        buf = io.BytesIO()
        img = Image.new("RGB", (40, 40), color="green")
        img.save(buf, format="JPEG")
        buf.seek(0)
        return SimpleUploadedFile(name, buf.getvalue(), content_type="image/jpeg")

    def test_intake_page_renders_valuation_containers(self):
        self.client.login(username="assistant_val", password="password123")
        resp = self.client.get(reverse("inventory:intake"))
        self.assertEqual(resp.status_code, 200)

        # Check advisory valuation elements
        self.assertContains(resp, 'id="advisoryValuationContainer"')
        self.assertContains(resp, 'id="advisoryRetailPrice"')
        self.assertContains(resp, 'id="advisoryResalePrice"')

        # Check sale price benchmark pills and button
        self.assertContains(resp, 'id="intakePriceBenchmarks"')
        self.assertContains(resp, 'id="badgeRefRetail"')
        self.assertContains(resp, 'id="badgeRefResale"')
        self.assertContains(resp, 'id="btnUseEstimatedResale"')

        # Check hidden inputs
        self.assertContains(resp, 'id="id_estimated_retail_price"')
        self.assertContains(resp, 'id="id_estimated_resale_price"')

    @patch("inventory.views.identify_intake_product")
    def test_intake_identify_view_returns_valuation_json(self, mock_identify):
        mock_identify.return_value = {
            "success": True,
            "identified_title": "Ray-Ban Wayfarer",
            "category": "Accesorios",
            "detected_attributes": ["Black", "G-15 Lens"],
            "missing_or_recommended_info": [],
            "suggested_note": "Gafas de sol clásicas Ray-Ban",
            "estimated_retail_price": 165.0,
            "estimated_resale_price": 75.0,
        }
        self.client.login(username="assistant_val", password="password123")
        img = self.create_dummy_image()

        resp = self.client.post(
            reverse("inventory:intake_identify"),
            {"images": [img], "raw_note": "Gafas Rayban"}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["estimated_retail_price"], 165.0)
        self.assertEqual(data["estimated_resale_price"], 75.0)

    def test_product_detail_view_renders_valuation_benchmarks_and_apply_button(self):
        product = Product.objects.create(
            raw_note="Casio G-Shock",
            ai_title="Reloj Casio G-Shock DW-5600",
            sale_price=Decimal("60.00"),
            estimated_retail_price=Decimal("110.00"),
            estimated_resale_price=Decimal("55.00"),
            created_by=self.manager,
        )

        self.client.login(username="manager_val", password="password123")
        resp = self.client.get(reverse("inventory:product_detail", kwargs={"pk": product.pk}))
        self.assertEqual(resp.status_code, 200)

        # Check benchmark badges render
        self.assertContains(resp, 'id="detail-valuation-benchmarks"')
        self.assertContains(resp, 'id="ref-retail-price"')
        self.assertContains(resp, "110.00")
        self.assertContains(resp, 'id="ref-resale-price"')
        self.assertContains(resp, "55.00")

        # Check quick apply button renders for manager
        self.assertContains(resp, 'id="btnApplyResalePrice"')
        self.assertContains(resp, 'data-resale="55.00"')

    def test_product_detail_view_without_valuation_omits_benchmarks(self):
        product = Product.objects.create(
            raw_note="Generic mug",
            ai_title="Taza de café",
            sale_price=Decimal("5.00"),
            estimated_retail_price=None,
            estimated_resale_price=None,
            created_by=self.manager,
        )

        self.client.login(username="manager_val", password="password123")
        resp = self.client.get(reverse("inventory:product_detail", kwargs={"pk": product.pk}))
        self.assertEqual(resp.status_code, 200)

        self.assertNotContains(resp, 'id="detail-valuation-benchmarks"')
        self.assertNotContains(resp, 'id="btnApplyResalePrice"')
