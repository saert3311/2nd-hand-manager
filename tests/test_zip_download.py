import io
import zipfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from PIL import Image

from inventory.models import Product, ProductImage
from inventory.permissions import ROLE_ASSISTANT

User = get_user_model()


class ProductDetailAndZipDownloadTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.manager = User.objects.create_user(username="mgr", password="password123", is_staff=True)
        self.assistant = User.objects.create_user(username="asst", password="password123")

        asst_group = Group.objects.create(name=ROLE_ASSISTANT)
        self.assistant.groups.add(asst_group)

        # Create product with an image
        self.product = Product.objects.create(
            raw_note="Vintage brown leather belt",
            created_by=self.assistant
        )

        img_buf = io.BytesIO()
        test_img = Image.new("RGB", (50, 50), color="brown")
        test_img.save(img_buf, format="WEBP")
        img_buf.seek(0)
        uploaded = SimpleUploadedFile("belt.webp", img_buf.getvalue(), content_type="image/webp")
        self.product_image = ProductImage.objects.create(
            product=self.product,
            image=uploaded,
            order=0
        )

    def test_product_detail_requires_login(self):
        url = reverse("inventory:product_detail", kwargs={"pk": self.product.pk})
        resp = self.client.get(url)
        self.assertRedirects(resp, f"{reverse('inventory:login')}?next={url}")

    def test_product_detail_view_authenticated(self):
        self.client.login(username="mgr", password="password123")
        url = reverse("inventory:product_detail", kwargs={"pk": self.product.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Vintage brown leather belt")
        self.assertContains(resp, "Download All Photos (.ZIP)")

    def test_manager_can_update_product_price_and_sold(self):
        self.client.login(username="mgr", password="password123")
        url = reverse("inventory:product_detail", kwargs={"pk": self.product.pk})

        resp = self.client.post(
            url,
            {
                "ai_title": "Genuine Brown Leather Belt",
                "ai_description": "Clean vintage leather belt in great shape.",
                "sale_price": "29.99",
                "is_sold": "on",
            }
        )
        self.assertRedirects(resp, url)
        self.product.refresh_from_db()
        self.assertEqual(self.product.ai_title, "Genuine Brown Leather Belt")
        self.assertEqual(self.product.sale_price, Decimal("29.99"))
        self.assertTrue(self.product.is_sold)
        self.assertIsNotNone(self.product.sold_at)

    def test_assistant_cannot_update_product(self):
        self.client.login(username="asst", password="password123")
        url = reverse("inventory:product_detail", kwargs={"pk": self.product.pk})

        resp = self.client.post(
            url,
            {
                "ai_title": "Hacked Title",
                "sale_price": "5.00",
            }
        )
        self.assertRedirects(resp, url)
        self.product.refresh_from_db()
        self.assertNotEqual(self.product.ai_title, "Hacked Title")

    def test_zip_download_success(self):
        self.client.login(username="mgr", password="password123")
        url = reverse("inventory:download_zip", kwargs={"pk": self.product.pk})
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/zip")
        self.assertIn(f"product_{self.product.id}_photos.zip", resp["Content-Disposition"])

        # Validate that the downloaded response content is a real zip archive
        zip_file = zipfile.ZipFile(io.BytesIO(resp.content))
        file_list = zip_file.namelist()
        self.assertEqual(len(file_list), 1)
        self.assertTrue(file_list[0].endswith(".webp"))
        self.assertIn(f"product_{self.product.id}_img_1.webp", file_list[0])
