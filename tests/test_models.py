from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from inventory.models import AIPromptConfiguration, Product, ProductImage

User = get_user_model()


class ProductModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password123")

    def test_product_creation_and_defaults(self):
        product = Product.objects.create(
            raw_note="Vintage blue jacket in good condition",
            created_by=self.user
        )
        self.assertEqual(product.raw_note, "Vintage blue jacket in good condition")
        self.assertEqual(product.ai_title, "")
        self.assertFalse(product.is_sold)
        self.assertIsNone(product.sold_at)
        self.assertIsNone(product.sale_price)
        self.assertEqual(product.created_by, self.user)
        self.assertEqual(product.display_title, "Vintage blue jacket in good condition")

    def test_display_title_with_ai_title(self):
        product = Product.objects.create(
            raw_note="Raw notes",
            ai_title="Men's Vintage Denim Jacket - Size M"
        )
        self.assertEqual(product.display_title, "Men's Vintage Denim Jacket - Size M")

    def test_display_title_fallback_when_empty(self):
        product = Product.objects.create()
        self.assertEqual(product.display_title, f"Product #{product.pk}")

    def test_mark_as_sold_and_unsold(self):
        product = Product.objects.create(raw_note="Item")
        self.assertFalse(product.is_sold)
        self.assertIsNone(product.sold_at)

        product.mark_as_sold(price=Decimal("45.50"))
        product.refresh_from_db()
        self.assertTrue(product.is_sold)
        self.assertIsNotNone(product.sold_at)
        self.assertEqual(product.sale_price, Decimal("45.50"))

        product.mark_as_unsold()
        product.refresh_from_db()
        self.assertFalse(product.is_sold)
        self.assertIsNone(product.sold_at)
        self.assertEqual(product.sale_price, Decimal("45.50"))

    def test_product_images_ordering_and_primary_image(self):
        product = Product.objects.create(raw_note="Item with images")
        img_file1 = SimpleUploadedFile("test1.webp", b"dummy_content", content_type="image/webp")
        img_file2 = SimpleUploadedFile("test2.webp", b"dummy_content", content_type="image/webp")

        img2 = ProductImage.objects.create(product=product, image=img_file2, order=1)
        img1 = ProductImage.objects.create(product=product, image=img_file1, order=0)

        self.assertEqual(product.primary_image, img1)
        self.assertEqual(list(product.images.all()), [img1, img2])


class AIPromptConfigurationModelTests(TestCase):
    def test_default_seeded_configurations_exist(self):
        es_config = AIPromptConfiguration.objects.filter(language="es", is_active=True).first()
        en_config = AIPromptConfiguration.objects.filter(language="en", is_active=True).first()

        self.assertIsNotNone(es_config)
        self.assertIsNotNone(en_config)
        self.assertEqual(es_config.model_name, "gemini-2.5-flash")
        self.assertEqual(en_config.model_name, "gemini-2.5-flash")
        self.assertEqual(es_config.temperature, 0.3)
        self.assertEqual(en_config.temperature, 0.3)
        self.assertIn("ESPAÑOL", es_config.system_instruction)
        self.assertIn("ENGLISH", en_config.system_instruction)

    def test_str_representation(self):
        config = AIPromptConfiguration(
            language="es",
            model_name="gemini-2.5-pro",
            temperature=0.4,
            system_instruction="Instrucciones",
            is_active=True,
        )
        self.assertIn("gemini-2.5-pro", str(config))
        self.assertIn("Active", str(config))

    def test_temperature_validation(self):
        from django.core.exceptions import ValidationError

        config_invalid_high = AIPromptConfiguration(
            language="es",
            model_name="gemini-2.5-flash",
            temperature=1.5,
            system_instruction="Test",
            is_active=False,
        )
        with self.assertRaises(ValidationError):
            config_invalid_high.save()

        config_invalid_low = AIPromptConfiguration(
            language="es",
            model_name="gemini-2.5-flash",
            temperature=-0.2,
            system_instruction="Test",
            is_active=False,
        )
        with self.assertRaises(ValidationError):
            config_invalid_low.save()

    def test_option_a_automatic_demotion_of_previous_active_configuration(self):
        # Initial active config for 'es' exists from seed
        initial_es = AIPromptConfiguration.objects.get(language="es", is_active=True)

        # Create a new active config for 'es'
        new_es = AIPromptConfiguration.objects.create(
            language="es",
            model_name="gemini-2.5-pro",
            temperature=0.2,
            system_instruction="Nuevas instrucciones optimizadas para Wallapop",
            is_active=True,
        )

        initial_es.refresh_from_db()
        new_es.refresh_from_db()

        self.assertFalse(initial_es.is_active)
        self.assertTrue(new_es.is_active)

        # English active config should remain completely unaffected
        en_config = AIPromptConfiguration.objects.get(language="en", is_active=True)
        self.assertTrue(en_config.is_active)
