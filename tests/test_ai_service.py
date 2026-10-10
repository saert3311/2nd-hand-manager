from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from inventory.models import Product
from inventory.services.ai_service import (
    AIServiceError,
    ProductListingSchema,
    generate_product_listing,
)


class AIServiceTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            raw_note="Original 1994 Pink Floyd tour tee, black, size XL, light fade on collar"
        )

    @override_settings(GEMINI_API_KEY="")
    def test_missing_api_key_raises_error(self):
        with self.assertRaises(AIServiceError) as ctx:
            generate_product_listing(self.product)
        self.assertIn("GEMINI_API_KEY is not configured", str(ctx.exception))

    @override_settings(GEMINI_API_KEY="test-key")
    def test_empty_product_raises_error(self):
        empty_prod = Product.objects.create(raw_note="")
        with self.assertRaises(AIServiceError) as ctx:
            generate_product_listing(empty_prod)
        self.assertIn("Cannot generate listing", str(ctx.exception))

    @override_settings(GEMINI_API_KEY="valid-api-key")
    @patch("inventory.services.ai_service.genai.Client")
    def test_successful_ai_listing_generation_with_parsed_response(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.parsed = ProductListingSchema(
            title="Vintage 1994 Pink Floyd Band T-Shirt XL",
            description="• Authentic 1994 tour tee\n• Black vintage wash with slight distress\n• Size XL"
        )
        mock_client.models.generate_content.return_value = mock_response

        result = generate_product_listing(self.product)
        self.assertEqual(result["title"], "Vintage 1994 Pink Floyd Band T-Shirt XL")
        self.assertIn("Authentic 1994 tour tee", result["description"])

    @override_settings(GEMINI_API_KEY="valid-api-key")
    @patch("inventory.services.ai_service.genai.Client")
    def test_successful_ai_listing_generation_with_json_fallback(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.parsed = None
        mock_response.text = '{"title": "Sony Walkman Retro Cassette", "description": "Works perfectly."}'
        mock_client.models.generate_content.return_value = mock_response

        result = generate_product_listing(self.product)
        self.assertEqual(result["title"], "Sony Walkman Retro Cassette")
        self.assertEqual(result["description"], "Works perfectly.")

    @override_settings(GEMINI_API_KEY="valid-api-key")
    @patch("inventory.services.ai_service.genai.Client")
    def test_api_network_failure_raises_ai_service_error(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.side_effect = RuntimeError("Connection timeout to Gemini")

        with self.assertRaises(AIServiceError) as ctx:
            generate_product_listing(self.product)
        self.assertIn("AI generation failed", str(ctx.exception))

    @override_settings(GEMINI_API_KEY="valid-api-key")
    @patch("inventory.services.ai_service.genai.Client")
    def test_prompt_in_spanish_when_language_is_es(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.parsed = ProductListingSchema(
            title="Camiseta Vintage Pink Floyd 1994 XL",
            description="• Camiseta de gira oficial\n• Talla XL\n• Buen estado vintage"
        )
        mock_client.models.generate_content.return_value = mock_response

        result = generate_product_listing(self.product, language="es")
        self.assertEqual(result["title"], "Camiseta Vintage Pink Floyd 1994 XL")

        call_args = mock_client.models.generate_content.call_args
        contents = call_args.kwargs.get("contents") or call_args[1].get("contents")
        prompt_text = contents[0]
        self.assertIn("COMPLETAMENTE EN ESPAÑOL", prompt_text)
        self.assertIn("NOTAS DE CAMPO DE LA ENTRADA", prompt_text)

    @override_settings(GEMINI_API_KEY="valid-api-key")
    @patch("inventory.services.ai_service.genai.Client")
    def test_prompt_in_english_by_default(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.parsed = ProductListingSchema(
            title="Vintage Pink Floyd Shirt",
            description="Tour shirt"
        )
        mock_client.models.generate_content.return_value = mock_response

        generate_product_listing(self.product, language="en")
        call_args = mock_client.models.generate_content.call_args
        contents = call_args.kwargs.get("contents") or call_args[1].get("contents")
        prompt_text = contents[0]
        self.assertIn("COMPLETELY IN ENGLISH", prompt_text)
        self.assertIn("FIELD NOTES FROM INTAKE", prompt_text)
