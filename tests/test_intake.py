import io

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
