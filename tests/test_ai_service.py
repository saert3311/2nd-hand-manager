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
from tests.helpers import configure_gemini_mock


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
        configure_gemini_mock(
            mock_client_cls,
            parsed=ProductListingSchema(
                title="Vintage 1994 Pink Floyd Band T-Shirt XL",
                description="• Authentic 1994 tour tee\n• Black vintage wash with slight distress\n• Size XL",
            ),
        )

        result = generate_product_listing(self.product)
        self.assertEqual(result["title"], "Vintage 1994 Pink Floyd Band T-Shirt XL")
        self.assertIn("Authentic 1994 tour tee", result["description"])

    @override_settings(GEMINI_API_KEY="valid-api-key")
    @patch("inventory.services.ai_service.genai.Client")
    def test_successful_ai_listing_generation_with_json_fallback(self, mock_client_cls):
        configure_gemini_mock(
            mock_client_cls,
            parsed=None,
            text='{"title": "Sony Walkman Retro Cassette", "description": "Works perfectly."}',
        )

        result = generate_product_listing(self.product)
        self.assertEqual(result["title"], "Sony Walkman Retro Cassette")
        self.assertEqual(result["description"], "Works perfectly.")

    @override_settings(GEMINI_API_KEY="valid-api-key")
    @patch("inventory.services.ai_service.genai.Client")
    def test_api_network_failure_raises_ai_service_error(self, mock_client_cls):
        configure_gemini_mock(
            mock_client_cls,
            side_effect=RuntimeError("Connection timeout to Gemini"),
        )

        with self.assertRaises(AIServiceError) as ctx:
            generate_product_listing(self.product)
        self.assertIn("AI generation failed", str(ctx.exception))

    @override_settings(GEMINI_API_KEY="valid-api-key")
    @patch("inventory.services.ai_service.genai.Client")
    def test_prompt_in_spanish_when_language_is_es(self, mock_client_cls):
        mock_client, _ = configure_gemini_mock(
            mock_client_cls,
            parsed=ProductListingSchema(
                title="Camiseta Vintage Pink Floyd 1994 XL",
                description="• Camiseta de gira oficial\n• Talla XL\n• Buen estado vintage",
            ),
        )

        result = generate_product_listing(self.product, language="es")
        self.assertEqual(result["title"], "Camiseta Vintage Pink Floyd 1994 XL")

        call_args = mock_client.models.generate_content.call_args
        config_arg = call_args.kwargs.get("config")
        contents = call_args.kwargs.get("contents") or call_args[1].get("contents")
        prompt_text = contents[0]
        self.assertIn("COMPLETAMENTE EN ESPAÑOL", config_arg.system_instruction)
        self.assertIn("NOTAS DE CAMPO DE LA ENTRADA", prompt_text)

    @override_settings(GEMINI_API_KEY="valid-api-key")
    @patch("inventory.services.ai_service.genai.Client")
    def test_prompt_in_english_by_default(self, mock_client_cls):
        mock_client, _ = configure_gemini_mock(
            mock_client_cls,
            parsed=ProductListingSchema(
                title="Vintage Pink Floyd Shirt",
                description="Tour shirt",
            ),
        )

        generate_product_listing(self.product, language="en")
        call_args = mock_client.models.generate_content.call_args
        config_arg = call_args.kwargs.get("config")
        contents = call_args.kwargs.get("contents") or call_args[1].get("contents")
        prompt_text = contents[0]
        self.assertIn("COMPLETELY IN ENGLISH", config_arg.system_instruction)
        self.assertIn("FIELD NOTES FROM INTAKE", prompt_text)

    @override_settings(GEMINI_API_KEY="valid-api-key")
    @patch("inventory.services.ai_service.genai.Client")
    def test_dynamic_configuration_from_database(self, mock_client_cls):
        mock_client, _ = configure_gemini_mock(
            mock_client_cls,
            parsed=ProductListingSchema(
                title="Sudadera Exclusiva",
                description="Detalles de lujo",
            ),
        )

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
        # Verify custom temperature & native system_instruction were passed to config
        config_arg = call_args.kwargs.get("config")
        self.assertEqual(config_arg.temperature, 0.7)
        self.assertIn("Instrucciones exclusivas para Wallapop y coleccionistas.", config_arg.system_instruction)
        self.assertIsInstance(config_arg.seed, int)
        contents = call_args.kwargs.get("contents")
        prompt_text = contents[0]
        self.assertIn("NOTAS DE CAMPO DE LA ENTRADA", prompt_text)

    @override_settings(GEMINI_API_KEY="valid-api-key")
    @patch("inventory.services.ai_service.genai.Client")
    def test_explicit_model_name_override(self, mock_client_cls):
        mock_client, _ = configure_gemini_mock(
            mock_client_cls,
            parsed=ProductListingSchema(title="Custom Title", description="Custom Desc"),
        )

        # Active configuration has model 'gemini-2.5-flash'
        # Call with explicit override
        generate_product_listing(self.product, model_name="gemini-exp-custom", language="en")
        call_args = mock_client.models.generate_content.call_args
        self.assertEqual(call_args.kwargs.get("model"), "gemini-exp-custom")

    @override_settings(GEMINI_API_KEY="valid-api-key")
    @patch("inventory.services.ai_service.genai.Client")
    def test_fallback_when_no_active_database_configuration(self, mock_client_cls):
        mock_client, _ = configure_gemini_mock(
            mock_client_cls,
            parsed=ProductListingSchema(title="Fallback Title", description="Fallback Desc"),
        )

        # Deactivate all configurations
        AIPromptConfiguration.objects.all().update(is_active=False)

        generate_product_listing(self.product, language="es")
        call_args = mock_client.models.generate_content.call_args
        self.assertEqual(call_args.kwargs.get("model"), "gemini-4-hydrogen")
        config_arg = call_args.kwargs.get("config")
        self.assertEqual(config_arg.temperature, 0.1)
        self.assertEqual(config_arg.thinking_config.thinking_level, "LOW")
        self.assertIn("Eres un experto en reventa", config_arg.system_instruction)

    @override_settings(GEMINI_API_KEY="valid-api-key")
    @patch("inventory.services.ai_service.genai.Client")
    def test_resilient_fallback_on_database_query_error(self, mock_client_cls):
        mock_client, _ = configure_gemini_mock(
            mock_client_cls,
            parsed=ProductListingSchema(title="Resilient Title", description="Resilient Desc"),
        )

        with patch("inventory.models.AIPromptConfiguration.objects.filter", side_effect=RuntimeError("DB Lock")):
            result = generate_product_listing(self.product, language="en")
            self.assertEqual(result["title"], "Resilient Title")

        call_args = mock_client.models.generate_content.call_args
        self.assertEqual(call_args.kwargs.get("model"), "gemini-4-hydrogen")
        config_arg = call_args.kwargs.get("config")
        self.assertEqual(config_arg.temperature, 0.1)
        self.assertEqual(config_arg.thinking_config.thinking_level, "LOW")


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
        configure_gemini_mock(
            mock_client_cls,
            parsed=IntakePreflightSchema(
                identified_title="Nike Air Max 90 Infrared",
                category="Calzado / Zapatillas",
                detected_attributes=["Colorway blanco/gris/infrarrojo", "Cámara Air visible"],
                missing_or_recommended_info=["Etiqueta de talla no visible", "Comprobar desgaste en suela"],
                suggested_note="Nike Air Max 90 Infrared. Buen estado. Revisar etiqueta de lengüeta.",
            ),
        )

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
        configure_gemini_mock(
            mock_client_cls,
            parsed=None,
            text=(
                '{"identified_title": "Levi\'s 501 Made in USA", "category": "Pantalones",'
                ' "detected_attributes": ["Denim rígido", "Botones plateados"],'
                ' "missing_or_recommended_info": ["Revisar etiqueta interior W/L"],'
                ' "suggested_note": "Levi\'s 501 Made in USA vintage."}'
            ),
        )

        result = identify_intake_product([b"\x89PNG\r\n\x1a\nfakepng"])
        self.assertTrue(result["success"])
        self.assertEqual(result["identified_title"], "Levi's 501 Made in USA")
        self.assertEqual(result["category"], "Pantalones")
        self.assertIn("Denim rígido", result["detected_attributes"])

    @override_settings(GEMINI_API_KEY="test-key")
    @patch("inventory.services.ai_service.genai.Client")
    def test_image_truncation_to_three_images(self, mock_client_cls):
        mock_client, _ = configure_gemini_mock(
            mock_client_cls,
            parsed=IntakePreflightSchema(
                identified_title="Item",
                category="Cat",
                detected_attributes=[],
                missing_or_recommended_info=[],
                suggested_note="Note",
            ),
        )

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
        configure_gemini_mock(
            mock_client_cls,
            side_effect=RuntimeError("Connection timeout to Gemini"),
        )

        result = identify_intake_product([b"\xff\xd8\xfffake"])
        self.assertFalse(result["success"])
        self.assertIn("Connection timeout to Gemini", result["error"])

    @override_settings(GEMINI_API_KEY="test-key")
    @patch("inventory.services.ai_service.genai.Client")
    def test_language_prompts(self, mock_client_cls):
        mock_client, _ = configure_gemini_mock(
            mock_client_cls,
            parsed=IntakePreflightSchema(
                identified_title="Item",
                category="Cat",
                detected_attributes=[],
                missing_or_recommended_info=[],
                suggested_note="Note",
            ),
        )

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

    @override_settings(GEMINI_API_KEY="test-key")
    @patch("inventory.services.ai_service.genai.Client")
    def test_intake_identification_uses_gemini_flash_latest_model(self, mock_client_cls):
        mock_client, _ = configure_gemini_mock(
            mock_client_cls,
            parsed=IntakePreflightSchema(
                identified_title="Vintage Denim Jacket",
                category="Ropa",
                detected_attributes=[],
                missing_or_recommended_info=[],
                suggested_note="",
            ),
        )

        identify_intake_product([b"\xff\xd8\xffsample"])
        client_kwargs = mock_client_cls.call_args.kwargs
        self.assertEqual(client_kwargs["http_options"].api_version, "v1beta")
        call_args = mock_client.models.generate_content.call_args
        self.assertEqual(call_args.kwargs.get("model"), "gemini-4-hydrogen")
        self.assertEqual(call_args.kwargs.get("config").thinking_config.thinking_level, "LOW")

    @override_settings(GEMINI_API_KEY="test-key")
    @patch("inventory.services.ai_service.genai.Client")
    def test_generate_listing_pins_v1beta_api_version(self, mock_client_cls):
        configure_gemini_mock(
            mock_client_cls,
            parsed=ProductListingSchema(
                title="Pink Floyd 1994 Tee",
                description="Vintage tee",
            ),
        )

        product = Product.objects.create(raw_note="Vintage tee")
        generate_product_listing(product)
        client_kwargs = mock_client_cls.call_args.kwargs
        self.assertEqual(client_kwargs["http_options"].api_version, "v1beta")

    @override_settings(GEMINI_API_KEY="test-key")
    @patch("inventory.services.ai_service.genai.Client")
    def test_self_healing_fallback_on_404_not_found(self, mock_client_cls):
        mock_ok = MagicMock()
        mock_ok.parsed = IntakePreflightSchema(
            identified_title="Recovered Levi's Jacket",
            category="Ropa",
            detected_attributes=[],
            missing_or_recommended_info=[],
            suggested_note="",
        )
        # First model fails with 404 NOT_FOUND; second model in chain (gemini-3.8-flash) succeeds
        mock_client, _ = configure_gemini_mock(
            mock_client_cls,
            side_effect=[
                RuntimeError("404 NOT_FOUND. {'error': {'code': 404, 'message': 'Model is not found', 'status': 'NOT_FOUND'}}"),
                mock_ok,
            ],
        )

        res = identify_intake_product([b"\xff\xd8\xffsample"])
        self.assertTrue(res["success"])
        self.assertEqual(res["identified_title"], "Recovered Levi's Jacket")
        self.assertEqual(mock_client.models.generate_content.call_count, 2)
        first_call = mock_client.models.generate_content.call_args_list[0].kwargs["model"]
        second_call = mock_client.models.generate_content.call_args_list[1].kwargs["model"]
        self.assertEqual(first_call, "gemini-4-hydrogen")
        self.assertEqual(second_call, "gemini-3.8-flash")

    def test_resolve_thinking_config_clamps_minimal_on_unsupported_models(self):
        from inventory.services.compliance_service import resolve_thinking_config

        # Gemini 4 Hydrogen & 3.8 Flash do not support MINIMAL -> clamped to LOW
        self.assertEqual(resolve_thinking_config("gemini-4-hydrogen", "minimal").thinking_level, "LOW")
        self.assertEqual(resolve_thinking_config("gemini-3.8-flash", "minimal").thinking_level, "LOW")
        # Gemini 3.5 Flash-Lite & 3.6 Flash support MINIMAL -> kept as MINIMAL
        self.assertEqual(resolve_thinking_config("gemini-3.5-flash-lite", "minimal").thinking_level, "MINIMAL")
        self.assertEqual(resolve_thinking_config("gemini-3.6-flash", "minimal").thinking_level, "MINIMAL")
        # Explicit medium/high preserved
        self.assertEqual(resolve_thinking_config("gemini-4-hydrogen", "medium").thinking_level, "MEDIUM")
        self.assertEqual(resolve_thinking_config("gemini-4-hydrogen", "high").thinking_level, "HIGH")

    @override_settings(GEMINI_API_KEY="test-key")
    def test_fetch_available_gemini_models_filters_incompatible_models(self):
        from django.core.cache import cache

        from inventory.services.compliance_service import (
            GEMINI_MODELS_CACHE_KEY,
            fetch_available_gemini_models,
        )

        cache.delete(GEMINI_MODELS_CACHE_KEY)
        self.addCleanup(cache.delete, GEMINI_MODELS_CACHE_KEY)

        def _make_model(name, display, actions=None):
            m = MagicMock()
            m.name = name
            m.display_name = display
            m.supported_actions = actions if actions is not None else ["generateContent"]
            return m

        fake_client_cls = MagicMock()
        fake_client = MagicMock()
        fake_client_cls.return_value = fake_client
        fake_client.models.list.return_value = [
            _make_model("models/gemini-4-hydrogen", "Gemini 4 Hydrogen"),
            _make_model("models/gemini-3.8-flash", "Gemini 3.8 Flash"),
            _make_model("models/gemini-3.8-flash-tts", "Gemini 3.8 Flash TTS"),
            _make_model("models/gemini-3.1-flash-image", "Nano Banana 2"),
            _make_model("models/lyria-3.5", "Lyria 3.5"),
            _make_model("models/gemma-4-31b-it", "Gemma 4 31B IT"),
            _make_model("models/gemini-embedding-001", "Gemini Embedding", actions=["embedContent"]),
        ]

        choices = fetch_available_gemini_models(force_refresh=True, client_cls=fake_client_cls)
        model_ids = [m_id for m_id, _ in choices]
        self.assertIn("gemini-4-hydrogen", model_ids)
        self.assertIn("gemini-3.8-flash", model_ids)
        self.assertNotIn("gemini-3.8-flash-tts", model_ids)
        self.assertNotIn("gemini-3.1-flash-image", model_ids)
        self.assertNotIn("lyria-3.5", model_ids)
        self.assertNotIn("gemma-4-31b-it", model_ids)
        self.assertNotIn("gemini-embedding-001", model_ids)

    @patch(
        "inventory.admin.fetch_available_gemini_models",
        return_value=[
            ("gemini-4-hydrogen", "Gemini 4 Hydrogen"),
            ("gemini-3.8-flash", "Gemini 3.8 Flash"),
            ("gemini-3.5-flash-lite", "Gemini 3.5 Flash-Lite"),
        ],
    )
    def test_admin_form_populates_dynamic_model_choices_and_preserves_custom(self, mock_fetch_models):
        from inventory.admin import AIPromptConfigurationAdminForm

        custom_cfg = AIPromptConfiguration.objects.create(
            language="es",
            model_name="gemini-custom-preview",
            intake_model_name="gemini-3.5-flash-lite",
            thinking_level="low",
            temperature=0.2,
            system_instruction="Test",
            is_active=False,
        )
        form = AIPromptConfigurationAdminForm(instance=custom_cfg)
        mock_fetch_models.assert_called_once_with(force_refresh=False)
        primary_values = [val for val, _ in form.fields["model_name"].widget.choices]
        intake_values = [val for val, _ in form.fields["intake_model_name"].widget.choices]
        self.assertIn("gemini-4-hydrogen", primary_values)
        self.assertIn("gemini-custom-preview", primary_values)
        self.assertIn("", intake_values)
        self.assertIn("gemini-3.5-flash-lite", intake_values)
