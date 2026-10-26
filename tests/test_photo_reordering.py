import io
import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from PIL import Image

from inventory.models import Product, ProductImage
from inventory.permissions import ROLE_ASSISTANT, ROLE_MANAGER

User = get_user_model()


class PhotoReorderingBackendTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Groups (created by migrations)
        self.manager_group, _ = Group.objects.get_or_create(name=ROLE_MANAGER)
        self.assistant_group, _ = Group.objects.get_or_create(name=ROLE_ASSISTANT)

        # Users
        self.manager = User.objects.create_user(username="manager1", password="password123")
        self.manager.groups.add(self.manager_group)

        self.assistant = User.objects.create_user(username="assistant1", password="password123")
        self.assistant.groups.add(self.assistant_group)

        # Products
        self.product = Product.objects.create(
            raw_note="Product with multiple photos",
            created_by=self.assistant,
        )

        # Create 3 images for self.product
        self.img1 = self._create_product_image(self.product, "img1.webp", order=0)
        self.img2 = self._create_product_image(self.product, "img2.webp", order=1)
        self.img3 = self._create_product_image(self.product, "img3.webp", order=2)

        self.reorder_url = reverse("inventory:product_reorder_images", kwargs={"pk": self.product.pk})

    def _create_product_image(self, product, name, order=0):
        buf = io.BytesIO()
        img = Image.new("RGB", (60, 60), color="blue")
        img.save(buf, format="WEBP")
        buf.seek(0)
        file = SimpleUploadedFile(name, buf.getvalue(), content_type="image/webp")
        return ProductImage.objects.create(product=product, image=file, order=order)

    def test_unauthenticated_reorder_redirects(self):
        resp = self.client.post(self.reorder_url, json.dumps({"image_ids": [self.img1.id]}), content_type="application/json")
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("inventory:login"), resp.url)

    def test_assistant_reorder_forbidden(self):
        self.client.login(username="assistant1", password="password123")
        resp = self.client.post(
            self.reorder_url,
            json.dumps({"image_ids": [self.img2.id, self.img1.id, self.img3.id]}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_get_method_not_allowed(self):
        self.client.login(username="manager1", password="password123")
        resp = self.client.get(self.reorder_url)
        self.assertEqual(resp.status_code, 405)

    def test_manager_reorder_success_json(self):
        self.client.login(username="manager1", password="password123")
        new_order = [self.img3.id, self.img1.id, self.img2.id]
        resp = self.client.post(
            self.reorder_url,
            json.dumps({"image_ids": new_order}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["reordered_ids"], new_order)
        self.assertTrue(data["primary_image_url"].endswith(self.img3.image.name))

        # Check DB state
        self.img1.refresh_from_db()
        self.img2.refresh_from_db()
        self.img3.refresh_from_db()

        self.assertEqual(self.img3.order, 0)
        self.assertEqual(self.img1.order, 1)
        self.assertEqual(self.img2.order, 2)

        # Check Product.primary_image
        self.assertEqual(self.product.primary_image.id, self.img3.id)

    def test_manager_reorder_success_form_data(self):
        self.client.login(username="manager1", password="password123")
        new_order = [str(self.img2.id), str(self.img3.id), str(self.img1.id)]
        resp = self.client.post(
            self.reorder_url,
            {"image_ids": new_order},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])

        self.img1.refresh_from_db()
        self.img2.refresh_from_db()
        self.img3.refresh_from_db()

        self.assertEqual(self.img2.order, 0)
        self.assertEqual(self.img3.order, 1)
        self.assertEqual(self.img1.order, 2)
        self.assertEqual(self.product.primary_image.id, self.img2.id)

    def test_malformed_json_returns_bad_request(self):
        self.client.login(username="manager1", password="password123")
        resp = self.client.post(
            self.reorder_url,
            "NOT_JSON",
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()["success"])

    def test_empty_image_ids_returns_bad_request(self):
        self.client.login(username="manager1", password="password123")
        resp = self.client.post(
            self.reorder_url,
            json.dumps({"image_ids": []}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_non_integer_image_ids_returns_bad_request(self):
        self.client.login(username="manager1", password="password123")
        resp = self.client.post(
            self.reorder_url,
            json.dumps({"image_ids": ["abc", "def", "ghi"]}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_cross_product_image_id_injection_rejected(self):
        # Create second product with its own image
        product2 = Product.objects.create(raw_note="Second product", created_by=self.assistant)
        foreign_img = self._create_product_image(product2, "foreign.webp", order=0)

        self.client.login(username="manager1", password="password123")
        # Attempt to insert foreign_img into self.product
        invalid_ids = [self.img1.id, self.img2.id, foreign_img.id]
        resp = self.client.post(
            self.reorder_url,
            json.dumps({"image_ids": invalid_ids}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data["success"])
        self.assertIn("do not match", data["error"])

    def test_incomplete_image_ids_rejected(self):
        self.client.login(username="manager1", password="password123")
        # Only 2 out of 3 IDs sent
        resp = self.client.post(
            self.reorder_url,
            json.dumps({"image_ids": [self.img1.id, self.img2.id]}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
