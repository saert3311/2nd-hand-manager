from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from inventory.models import Product, ProductImage

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
