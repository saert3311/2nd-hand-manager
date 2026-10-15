from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from inventory.models import AIPromptConfiguration, Product
from inventory.services.ai_service import (
    AIServiceError,
    IntakePreflightSchema,
    ProductListingSchema,
    generate_product_listing,
    identify_intake_product,
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

    @override_settings(GEMINI_API_KEY="valid-api-key")
    @patch("inventory.services.ai_service.genai.Client")
    def test_dynamic_configuration_from_database(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.parsed = ProductListingSchema(
            title="Sudadera Exclusiva",
            description="Detalles de lujo"
        )
        mock_client.models.generate_content.return_value = mock_response

        # Create custom active configuration for Spanish
        AIPromptConfiguration.objects.create(
            language="es",
            model_name="gemini-2.5-pro",
            temperature=0.7,
            system_instruction="Instrucciones exclusivas para Wallapop y coleccionistas.",
            is_active=True,
        )

        result = generate_product_listing(self.product, language="es")
        self.assertEqual(result["title"], "Sudadera Exclusiva")

        call_args = mock_client.models.generate_content.call_args
        # Verify custom model was passed
        self.assertEqual(call_args.kwargs.get("model"), "gemini-2.5-pro")
        # Verify custom temperature was passed to config
        config_arg = call_args.kwargs.get("config")
        self.assertEqual(config_arg.temperature, 0.7)
        # Verify custom system instruction was used
        contents = call_args.kwargs.get("contents")
        prompt_text = contents[0]
        self.assertIn("Instrucciones exclusivas para Wallapop y coleccionistas.", prompt_text)
        self.assertIn("NOTAS DE CAMPO DE LA ENTRADA", prompt_text)

    @override_settings(GEMINI_API_KEY="valid-api-key")
    @patch("inventory.services.ai_service.genai.Client")
    def test_explicit_model_name_override(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.parsed = ProductListingSchema(title="Custom Title", description="Custom Desc")
        mock_client.models.generate_content.return_value = mock_response

        # Active configuration has model 'gemini-2.5-flash'
        # Call with explicit override
        generate_product_listing(self.product, model_name="gemini-exp-custom", language="en")
        call_args = mock_client.models.generate_content.call_args
        self.assertEqual(call_args.kwargs.get("model"), "gemini-exp-custom")

    @override_settings(GEMINI_API_KEY="valid-api-key")
    @patch("inventory.services.ai_service.genai.Client")
    def test_fallback_when_no_active_database_configuration(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.parsed = ProductListingSchema(title="Fallback Title", description="Fallback Desc")
        mock_client.models.generate_content.return_value = mock_response

        # Deactivate all configurations
        AIPromptConfiguration.objects.all().update(is_active=False)

        generate_product_listing(self.product, language="es")
        call_args = mock_client.models.generate_content.call_args
        self.assertEqual(call_args.kwargs.get("model"), "gemini-2.5-flash")
        config_arg = call_args.kwargs.get("config")
        self.assertEqual(config_arg.temperature, 0.3)
        contents = call_args.kwargs.get("contents")
        prompt_text = contents[0]
        self.assertIn("Eres un experto en reventa", prompt_text)

    @override_settings(GEMINI_API_KEY="valid-api-key")
    @patch("inventory.services.ai_service.genai.Client")
    def test_resilient_fallback_on_database_query_error(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.parsed = ProductListingSchema(title="Resilient Title", description="Resilient Desc")
        mock_client.models.generate_content.return_value = mock_response

        with patch("inventory.models.AIPromptConfiguration.objects.filter", side_effect=RuntimeError("DB Lock")):
            result = generate_product_listing(self.product, language="en")
            self.assertEqual(result["title"], "Resilient Title")

        call_args = mock_client.models.generate_content.call_args
        self.assertEqual(call_args.kwargs.get("model"), "gemini-2.5-flash")
        config_arg = call_args.kwargs.get("config")
        self.assertEqual(config_arg.temperature, 0.3)


class IntakePreflightServiceTests(TestCase):
    @override_settings(GEMINI_API_KEY="")
    def test_missing_api_key_returns_failure(self):
        result = identify_intake_product([b"\xff\xd8\xfffakeimage"])
        self.assertFalse(result["success"])
        self.assertIn("GEMINI_API_KEY is not configured", result["error"])

    @override_settings(GEMINI_API_KEY="test-key")
    def test_empty_input_returns_failure_spanish(self):
        result = identify_intake_product([], raw_note="", language="es")
        self.assertFalse(result["success"])
        self.assertIn("No se han proporcionado fotos ni notas", result["error"])

    @override_settings(GEMINI_API_KEY="test-key")
    def test_empty_input_returns_failure_english(self):
        result = identify_intake_product([], raw_note="", language="en")
        self.assertFalse(result["success"])
        self.assertIn("No photos or notes provided", result["error"])

    @override_settings(GEMINI_API_KEY="test-key")
    @patch("inventory.services.ai_service.genai.Client")
    def test_successful_identification_with_parsed_response(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.parsed = IntakePreflightSchema(
            identified_title="Nike Air Max 90 Infrared",
            category="Calzado / Zapatillas",
            detected_attributes=["Colorway blanco/gris/infrarrojo", "Cámara Air visible"],
            missing_or_recommended_info=["Etiqueta de talla no visible", "Comprobar desgaste en suela"],
            suggested_note="Nike Air Max 90 Infrared. Buen estado. Revisar etiqueta de lengüeta.",
        )
        mock_client.models.generate_content.return_value = mock_response

        sample_img = b"\xff\xd8\xfffakejpg"
        result = identify_intake_product([sample_img], raw_note="Zapatillas vintage", language="es")

        self.assertTrue(result["success"])
        self.assertEqual(result["identified_title"], "Nike Air Max 90 Infrared")
        self.assertEqual(result["category"], "Calzado / Zapatillas")
        self.assertEqual(len(result["detected_attributes"]), 2)
        self.assertIn("Etiqueta de talla no visible", result["missing_or_recommended_info"])
        self.assertEqual(result["suggested_note"], "Nike Air Max 90 Infrared. Buen estado. Revisar etiqueta de lengüeta.")

    @override_settings(GEMINI_API_KEY="test-key")
    @patch("inventory.services.ai_service.genai.Client")
    def test_successful_identification_with_json_fallback(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.parsed = None
        mock_response.text = (
            '{"identified_title": "Levi\'s 501 Made in USA", "category": "Pantalones",'
            ' "detected_attributes": ["Denim rígido", "Botones plateados"],'
            ' "missing_or_recommended_info": ["Revisar etiqueta interior W/L"],'
            ' "suggested_note": "Levi\'s 501 Made in USA vintage."}'
        )
        mock_client.models.generate_content.return_value = mock_response

        result = identify_intake_product([b"\x89PNG\r\n\x1a\nfakepng"])
        self.assertTrue(result["success"])
        self.assertEqual(result["identified_title"], "Levi's 501 Made in USA")
        self.assertEqual(result["category"], "Pantalones")
        self.assertIn("Denim rígido", result["detected_attributes"])

    @override_settings(GEMINI_API_KEY="test-key")
    @patch("inventory.services.ai_service.genai.Client")
    def test_image_truncation_to_three_images(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.parsed = IntakePreflightSchema(
            identified_title="Item",
            category="Cat",
            detected_attributes=[],
            missing_or_recommended_info=[],
            suggested_note="Note",
        )
        mock_client.models.generate_content.return_value = mock_response

        five_images = [
            b"\xff\xd8\xff-1",
            b"\xff\xd8\xff-2",
            b"\xff\xd8\xff-3",
            b"\xff\xd8\xff-4",
            b"\xff\xd8\xff-5",
        ]
        identify_intake_product(five_images, raw_note="Test note")

        call_args = mock_client.models.generate_content.call_args
        contents = call_args.kwargs.get("contents")
        # 1 text prompt + 3 images (capped) = 4 items
        self.assertEqual(len(contents), 4)

    @override_settings(GEMINI_API_KEY="test-key")
    @patch("inventory.services.ai_service.genai.Client")
    def test_api_network_failure_returns_failure_dict_without_exception(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.side_effect = RuntimeError("Connection timeout to Gemini")

        result = identify_intake_product([b"\xff\xd8\xfffake"])
        self.assertFalse(result["success"])
        self.assertIn("Connection timeout to Gemini", result["error"])

    @override_settings(GEMINI_API_KEY="test-key")
    @patch("inventory.services.ai_service.genai.Client")
    def test_language_prompts(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.parsed = IntakePreflightSchema(
            identified_title="Item",
            category="Cat",
            detected_attributes=[],
            missing_or_recommended_info=[],
            suggested_note="Note",
        )
        mock_client.models.generate_content.return_value = mock_response

        # Spanish
        identify_intake_product([b"fake"], language="es")
        call_args_es = mock_client.models.generate_content.call_args
        prompt_es = call_args_es.kwargs.get("contents")[0]
        self.assertIn("COMPLETAMENTE EN ESPAÑOL", prompt_es)
        self.assertIn("NOTAS PRELIMINARES DEL ASISTENTE", prompt_es)

        # English
        identify_intake_product([b"fake"], language="en")
        call_args_en = mock_client.models.generate_content.call_args
        prompt_en = call_args_en.kwargs.get("contents")[0]
        self.assertIn("COMPLETELY IN ENGLISH", prompt_en)
        self.assertIn("ASSISTANT PRELIMINARY NOTES", prompt_en)
