import json

from django.test import TestCase
from django.urls import reverse
from django.utils import translation

from inventory.models import Product, ProductImage
from tests.helpers import create_role_users, create_user_with_group, make_test_image_file


class PhotoReorderingBackendTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager, cls.assistant = create_role_users(prefix="reord_api")

    def setUp(self):
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
        file = make_test_image_file(
            name=name, size=(60, 60), color="blue", image_format="WEBP", content_type="image/webp"
        )
        return ProductImage.objects.create(product=product, image=file, order=order)

    def test_unauthenticated_reorder_redirects(self):
        resp = self.client.post(self.reorder_url, json.dumps({"image_ids": [self.img1.id]}), content_type="application/json")
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("inventory:login"), resp.url)

    def test_assistant_reorder_forbidden(self):
        self.client.force_login(self.assistant)
        resp = self.client.post(
            self.reorder_url,
            json.dumps({"image_ids": [self.img2.id, self.img1.id, self.img3.id]}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_get_method_not_allowed(self):
        self.client.force_login(self.manager)
        resp = self.client.get(self.reorder_url)
        self.assertEqual(resp.status_code, 405)

    def test_manager_reorder_success_json(self):
        self.client.force_login(self.manager)
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
        self.client.force_login(self.manager)
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
        self.client.force_login(self.manager)
        resp = self.client.post(
            self.reorder_url,
            "NOT_JSON",
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()["success"])

    def test_empty_image_ids_returns_bad_request(self):
        self.client.force_login(self.manager)
        resp = self.client.post(
            self.reorder_url,
            json.dumps({"image_ids": []}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_non_integer_image_ids_returns_bad_request(self):
        self.client.force_login(self.manager)
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

        self.client.force_login(self.manager)
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
        self.client.force_login(self.manager)
        # Only 2 out of 3 IDs sent
        resp = self.client.post(
            self.reorder_url,
            json.dumps({"image_ids": [self.img1.id, self.img2.id]}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)


class PhotoReorderingIntakeUITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = create_user_with_group("assistant_ui", group_name="assistants")
        cls.url = reverse("inventory:intake")

    def setUp(self):
        self.client.force_login(self.user)

    def test_intake_template_renders_reordering_guidance_and_controls(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")

        # Semantic reordering guidance and controls
        self.assertIn("Drag or tap arrows to reorder", html)
        self.assertIn("photo-reorder-btn", html)
        self.assertIn("photo-make-cover-btn", html)
        self.assertIn("draggable", html)

    def test_intake_reorder_spanish_localization(self):
        with translation.override("es"):
            resp = self.client.get(self.url, headers={"Accept-Language": "es"})
            self.assertEqual(resp.status_code, 200)
            html = resp.content.decode("utf-8")

            self.assertIn("Arrastra o toca las flechas para reordenar", html)
            self.assertIn("Portada", html)
            self.assertIn("Mover a la izquierda", html)
            self.assertIn("Mover a la derecha", html)
            self.assertIn("Establecer como foto de portada", html)

    def test_intake_submission_preserves_image_order(self):
        imgA = make_test_image_file("A_cover.jpg", size=(60, 60), color="green")
        imgB = make_test_image_file("B_second.jpg", size=(60, 60), color="green")
        imgC = make_test_image_file("C_third.jpg", size=(60, 60), color="green")

        resp = self.client.post(
            self.url,
            {
                "raw_note": "Three photos in specific order",
                "images": [imgA, imgB, imgC],
            },
        )
        self.assertRedirects(resp, self.url)
        self.assertEqual(Product.objects.count(), 1)
        product = Product.objects.first()

        images = list(product.images.order_by("order"))
        self.assertEqual(len(images), 3)
        self.assertEqual(images[0].order, 0)
        self.assertEqual(images[1].order, 1)
        self.assertEqual(images[2].order, 2)
        self.assertEqual(product.primary_image.id, images[0].id)


class PhotoReorderingDetailUITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager, cls.assistant = create_role_users(prefix="reord_det")

    def setUp(self):
        self.product = Product.objects.create(
            raw_note="Product for detail UI test",
            created_by=self.assistant,
        )

        # 3 images
        for i in range(3):
            file = make_test_image_file(
                f"det_{i}.webp", size=(60, 60), color="red", image_format="WEBP", content_type="image/webp"
            )
            ProductImage.objects.create(product=self.product, image=file, order=i)

        self.detail_url = reverse("inventory:product_detail", kwargs={"pk": self.product.pk})

    def test_manager_detail_view_renders_reorder_controls(self):
        self.client.force_login(self.manager)
        resp = self.client.get(self.detail_url)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")

        self.assertIn('id="toggleReorderModeBtn"', html)
        self.assertIn('id="galleryThumbnailsGrid"', html)
        self.assertIn('id="reorderFeedbackBanner"', html)
        self.assertIn("thumb-reorder-controls", html)
        self.assertIn("btn-thumb-move-left", html)
        self.assertIn("btn-thumb-make-cover", html)
        self.assertIn("btn-thumb-move-right", html)
        self.assertIn("persistImageOrder", html)

    def test_assistant_detail_view_hides_reorder_controls(self):
        self.client.force_login(self.assistant)
        resp = self.client.get(self.detail_url)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")

        # Assistant should NOT see the reorder button or reorder controls
        self.assertNotIn('id="toggleReorderModeBtn"', html)
        self.assertNotIn("thumb-reorder-controls", html)
        self.assertNotIn("btn-thumb-move-left", html)
        self.assertNotIn("btn-thumb-make-cover", html)

    def test_single_image_detail_view_hides_reorder_button(self):
        # Product with only 1 image
        single_prod = Product.objects.create(raw_note="Single photo", created_by=self.assistant)
        file = make_test_image_file(
            "single.webp", size=(60, 60), color="yellow", image_format="WEBP", content_type="image/webp"
        )
        ProductImage.objects.create(product=single_prod, image=file, order=0)

        self.client.force_login(self.manager)
        resp = self.client.get(reverse("inventory:product_detail", kwargs={"pk": single_prod.pk}))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")

        self.assertNotIn('id="toggleReorderModeBtn"', html)

    def test_detail_reorder_spanish_localization(self):
        self.client.force_login(self.manager)
        with translation.override("es"):
            resp = self.client.get(self.detail_url, headers={"Accept-Language": "es"})
            self.assertEqual(resp.status_code, 200)
            html = resp.content.decode("utf-8")

            self.assertIn("Reordenar", html)
            self.assertIn("Listo", html)
            self.assertIn("Foto de portada", html)
            self.assertIn("¡Orden de fotos guardado correctamente!", html)
