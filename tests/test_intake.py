import io
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from PIL import Image

from inventory.models import Product

User = get_user_model()


class ProductIntakeViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="assistant1", password="password123")
        self.url = reverse("inventory:intake")

    def create_dummy_image(self, name="photo.jpg", format="JPEG"):
        buf = io.BytesIO()
        img = Image.new("RGB", (80, 80), color="red")
        img.save(buf, format=format)
        buf.seek(0)
        return SimpleUploadedFile(name, buf.getvalue(), content_type=f"image/{format.lower()}")

    def test_intake_requires_login(self):
        resp = self.client.get(self.url)
        self.assertRedirects(resp, f"{reverse('inventory:login')}?next={self.url}")

    def test_intake_get_authenticated(self):
        self.client.login(username="assistant1", password="password123")
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "New Product Intake")
        self.assertContains(resp, 'id="identifyBtn"')
        self.assertContains(resp, 'id="aiAdvisoryBanner"')
        self.assertContains(resp, 'id="applySuggestionBtn"')
        self.assertContains(resp, 'id="id_sale_price"')

    def test_intake_post_without_images_fails(self):
        self.client.login(username="assistant1", password="password123")
        resp = self.client.post(self.url, {"raw_note": "A cool vintage watch"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Please attach at least one photo")
        self.assertEqual(Product.objects.count(), 0)

    def test_intake_post_with_valid_images_success(self):
        self.client.login(username="assistant1", password="password123")
        img1 = self.create_dummy_image("front.jpg")
        img2 = self.create_dummy_image("back.png", format="PNG")

        resp = self.client.post(
            self.url,
            {
                "raw_note": "Vintage Levi's denim jacket, size L",
                "images": [img1, img2],
            }
        )
        self.assertRedirects(resp, self.url)
        self.assertEqual(Product.objects.count(), 1)
        product = Product.objects.first()
        self.assertEqual(product.raw_note, "Vintage Levi's denim jacket, size L")
        self.assertEqual(product.created_by, self.user)
        self.assertEqual(product.images.count(), 2)

        # Verify all saved images have been converted to WebP
        for prod_img in product.images.all():
            self.assertTrue(prod_img.image.name.endswith(".webp"))

    def test_intake_post_exceeding_max_images_fails(self):
        self.client.login(username="assistant1", password="password123")
        images = [self.create_dummy_image(f"img_{i}.jpg") for i in range(11)]

        resp = self.client.post(
            self.url,
            {
                "raw_note": "Too many images",
                "images": images,
            }
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "maximum of 10 images")
        self.assertEqual(Product.objects.count(), 0)

    def test_intake_post_with_optional_sale_price_persists(self):
        self.client.login(username="assistant1", password="password123")
        img = self.create_dummy_image("item.jpg")

        resp = self.client.post(
            self.url,
            {
                "raw_note": "Vintage Nike windbreaker",
                "sale_price": "35.50",
                "images": [img],
            }
        )
        self.assertRedirects(resp, self.url)
        self.assertEqual(Product.objects.count(), 1)
        product = Product.objects.first()
        self.assertEqual(product.sale_price, Decimal("35.50"))
        self.assertEqual(product.raw_note, "Vintage Nike windbreaker")

    def test_intake_post_with_blank_sale_price_sets_none(self):
        self.client.login(username="assistant1", password="password123")
        img = self.create_dummy_image("item.jpg")

        resp = self.client.post(
            self.url,
            {
                "raw_note": "Unpriced item",
                "sale_price": "",
                "images": [img],
            }
        )
        self.assertRedirects(resp, self.url)
        self.assertEqual(Product.objects.count(), 1)
        product = Product.objects.first()
        self.assertIsNone(product.sale_price)

    def test_intake_post_with_negative_sale_price_fails(self):
        self.client.login(username="assistant1", password="password123")
        img = self.create_dummy_image("item.jpg")

        resp = self.client.post(
            self.url,
            {
                "raw_note": "Negative price item",
                "sale_price": "-15.00",
                "images": [img],
            }
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Product.objects.count(), 0)
        self.assertContains(resp, "greater than or equal to 0.00")

    def test_intake_get_renders_sale_price_field(self):
        self.client.login(username="assistant1", password="password123")
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'name="sale_price"')
        self.assertContains(resp, "Target Sale Price")
        self.assertContains(resp, "€")

    def test_intake_get_renders_validation_and_async_elements(self):
        self.client.login(username="assistant1", password="password123")
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="intakeClientAlert"')
        self.assertContains(resp, 'role="alert"')
        self.assertContains(resp, 'aria-live="polite"')
        self.assertContains(resp, 'id="submitBtnIcon"')
        self.assertContains(resp, 'id="submitBtnText"')
        self.assertContains(resp, 'id="intakeForm"')
        self.assertContains(resp, 'novalidate')
        self.assertContains(resp, "Saving product...")
        self.assertContains(resp, "Please wait for AI analysis to finish...")
        self.assertContains(resp, "Please attach at least one photo of the product before saving.")

    def test_intake_get_renders_photo_management_elements(self):
        self.client.login(username="assistant1", password="password123")
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="previewContainer"')
        self.assertContains(resp, 'id="previewGrid"')
        self.assertContains(resp, 'photo-delete-btn')
        self.assertContains(resp, 'selectedFiles')
        self.assertContains(resp, 'syncFileInput')
        self.assertContains(resp, 'renderPreviews')
        self.assertContains(resp, 'DataTransfer')
        self.assertContains(resp, "Remove photo")
        self.assertContains(resp, "Please select a maximum of 10 photos.")

    def test_intake_get_renders_spanish_translations(self):
        self.client.login(username="assistant1", password="password123")
        resp = self.client.get(self.url, HTTP_ACCEPT_LANGUAGE="es")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Guardando producto...")
        self.assertContains(resp, "Espera a que finalice el análisis con IA...")
        self.assertContains(resp, "Por favor, adjunta al menos una foto del producto antes de guardar.")
        self.assertContains(resp, "Eliminar foto")
        self.assertContains(resp, "Por favor, selecciona un máximo de 10 fotos.")


