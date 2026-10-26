import os
import shutil
from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from PIL import Image

from inventory.models import MarketplaceSite, Product, ProductImage, ProductListingLink, ProductStatus
from inventory.permissions import ROLE_ASSISTANT, ROLE_MANAGER

User = get_user_model()


class DetailPhotoUploadComponentTests(TestCase):
    """
    Automated test suite for Phase 34: Detail View Photo Upload Component System.
    Verifies component visibility, role gating, DOM attributes, dynamic slot counting,
    form submission, published sync integration, and bilingual localization.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        os.makedirs("tmp_test_detail_images", exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        if os.path.exists("tmp_test_detail_images"):
            shutil.rmtree("tmp_test_detail_images", ignore_errors=True)

    def setUp(self):
        self.mgr_group, _ = Group.objects.get_or_create(name=ROLE_MANAGER)
        self.asst_group, _ = Group.objects.get_or_create(name=ROLE_ASSISTANT)

        self.manager = User.objects.create_user(
            username="manager_upload",
            password="password123",
            is_staff=True,
        )
        self.manager.groups.add(self.mgr_group)

        self.assistant = User.objects.create_user(
            username="assistant_upload",
            password="password123",
            is_staff=False,
        )
        self.assistant.groups.add(self.asst_group)

        self.product = Product.objects.create(
            ai_title="Cazadora Vintage Barbour",
            ai_description="Auténtica cazadora encerada.",
            sale_price=120.00,
            status=ProductStatus.READY,
            created_by=self.manager,
        )
        # Attach 2 initial photos
        self.img1 = self._create_product_image(self.product, order=0)
        self.img2 = self._create_product_image(self.product, order=1)

        self.client_manager = Client()
        self.client_manager.login(username="manager_upload", password="password123")

        self.client_asst = Client()
        self.client_asst.login(username="assistant_upload", password="password123")

    def _create_dummy_image_file(self, filename="sample.jpg", color=(40, 90, 160)):
        stream = BytesIO()
        img = Image.new("RGB", (300, 300), color=color)
        img.save(stream, format="JPEG")
        return SimpleUploadedFile(
            filename,
            stream.getvalue(),
            content_type="image/jpeg",
        )

    def _create_product_image(self, product, order=0):
        img_file = self._create_dummy_image_file(f"prod_{product.pk}_{order}.jpg")
        return ProductImage.objects.create(
            product=product,
            image=img_file,
            order=order,
        )

    # =========================================================================
    # 1. Component Visibility & Role Gating
    # =========================================================================
    def test_manager_sees_upload_component_when_under_capacity(self):
        """Manager should see the enhanced photo upload component when product has < 10 photos."""
        url = reverse("inventory:product_detail", kwargs={"pk": self.product.pk})
        resp = self.client_manager.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="detailPhotoUploadContainer"')
        self.assertContains(resp, 'id="detailDropZone"')
        self.assertContains(resp, 'id="btnTriggerDetailCamera"')
        self.assertContains(resp, 'id="btnTriggerDetailGallery"')
        self.assertContains(resp, 'id="detailUploadSlotCount"')
        self.assertEqual(resp.context["available_slots"], 8)

    def test_assistant_cannot_see_upload_component(self):
        """Assistants do not have manager permissions and should never see the upload component."""
        url = reverse("inventory:product_detail", kwargs={"pk": self.product.pk})
        resp = self.client_asst.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'id="detailPhotoUploadContainer"')
        self.assertNotContains(resp, 'id="detailDropZone"')
        self.assertNotContains(resp, 'id="btnUploadDetailPhotos"')

    def test_upload_component_hidden_when_product_has_10_photos(self):
        """When product reaches maximum 10 photos, upload component should not render."""
        # Add 8 more photos to reach 10 total
        for i in range(2, 10):
            self._create_product_image(self.product, order=i)

        self.assertEqual(self.product.images.count(), 10)

        url = reverse("inventory:product_detail", kwargs={"pk": self.product.pk})
        resp = self.client_manager.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'id="detailPhotoUploadContainer"')
        self.assertNotContains(resp, 'id="detailDropZone"')
        self.assertEqual(resp.context["available_slots"], 0)

    # =========================================================================
    # 2. DOM Attributes & Accessibility Standards
    # =========================================================================
    def test_dom_attributes_for_mobile_camera_and_gallery(self):
        """Verify DOM attributes support direct camera capture and multi-photo gallery."""
        url = reverse("inventory:product_detail", kwargs={"pk": self.product.pk})
        resp = self.client_manager.get(url)
        content = resp.content.decode("utf-8")

        # Camera input has capture="environment" and accept="image/*"
        self.assertIn('id="detailCameraInput"', content)
        self.assertIn('capture="environment"', content)
        self.assertIn('accept="image/*"', content)

        # Gallery input has multiple and accept="image/*"
        self.assertIn('id="detailImageInput"', content)
        self.assertIn('multiple', content)

        # Dropzone and indicator
        self.assertIn('id="detailDropZone"', content)
        self.assertIn('id="detailCompressionIndicator"', content)
        self.assertIn('role="status"', content)
        self.assertIn('aria-live="polite"', content)

        # Pending queue
        self.assertIn('id="detailPendingContainer"', content)
        self.assertIn('id="detailPendingGrid"', content)
        self.assertIn('id="btnUploadDetailPhotos"', content)

    # =========================================================================
    # 3. Dynamic Capacity & Slot Counter
    # =========================================================================
    def test_slot_count_displays_correctly(self):
        """Verify data attributes and available slot calculations in context."""
        url = reverse("inventory:product_detail", kwargs={"pk": self.product.pk})
        resp = self.client_manager.get(url)
        content = resp.content.decode("utf-8")

        # Product has 2 images -> 8 available
        self.assertIn('data-existing="2"', content)
        self.assertIn('data-max="10"', content)
        self.assertEqual(resp.context["available_slots"], 8)

    # =========================================================================
    # 4. Form Submission & Published Sync Integration
    # =========================================================================
    def test_upload_additional_photos_via_form_endpoint(self):
        """Posting photos to product_upload_images adds photos and preserves order."""
        upload_url = reverse("inventory:product_upload_images", kwargs={"pk": self.product.pk})
        f1 = self._create_dummy_image_file("extra1.jpg")
        f2 = self._create_dummy_image_file("extra2.jpg")

        resp = self.client_manager.post(upload_url, {"images": [f1, f2]})
        self.assertEqual(resp.status_code, 302)

        self.product.refresh_from_db()
        self.assertEqual(self.product.images.count(), 4)

    def test_uploading_photo_to_published_product_triggers_platform_sync(self):
        """Uploading photos to an already published product automatically sets needs_platform_sync = True."""
        site, _ = MarketplaceSite.objects.get_or_create(slug="wallapop", defaults={"name": "Wallapop", "order": 1})
        ProductListingLink.objects.create(
            product=self.product,
            site=site,
            url="https://es.wallapop.com/item/barbour-jacket",
            is_active=True,
        )
        self.product.status = ProductStatus.PUBLISHED
        self.product.needs_platform_sync = False
        self.product.save()

        upload_url = reverse("inventory:product_upload_images", kwargs={"pk": self.product.pk})
        f1 = self._create_dummy_image_file("tag_photo.jpg")

        resp = self.client_manager.post(upload_url, {"images": [f1]})
        self.assertEqual(resp.status_code, 302)

        self.product.refresh_from_db()
        self.assertTrue(self.product.needs_platform_sync)

    def test_upload_exceeding_capacity_rejected_with_error(self):
        """Uploading more photos than remaining slots is rejected with a validation error."""
        # Add 7 photos so product has 9 total (1 slot remaining)
        for i in range(2, 9):
            self._create_product_image(self.product, order=i)

        self.assertEqual(self.product.images.count(), 9)

        upload_url = reverse("inventory:product_upload_images", kwargs={"pk": self.product.pk})
        f1 = self._create_dummy_image_file("f1.jpg")
        f2 = self._create_dummy_image_file("f2.jpg")

        resp = self.client_manager.post(upload_url, {"images": [f1, f2]})
        self.assertEqual(resp.status_code, 302)

        self.product.refresh_from_db()
        # Count should remain 9
        self.assertEqual(self.product.images.count(), 9)

    # =========================================================================
    # 5. Localization (Spanish & English)
    # =========================================================================
    def test_spanish_localization(self):
        """Verify Spanish translations render on the product detail page."""
        url = reverse("inventory:product_detail", kwargs={"pk": self.product.pk})
        resp = self.client_manager.get(url, HTTP_ACCEPT_LANGUAGE="es")
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")

        self.assertIn("Añadir más fotos", content)
        self.assertIn("Tomar foto", content)
        self.assertIn("Elegir de la galería", content)
        self.assertIn("Subir fotos seleccionadas", content)

    def test_english_localization(self):
        """Verify English translations render when English is requested."""
        url = reverse("inventory:product_detail", kwargs={"pk": self.product.pk})
        resp = self.client_manager.get(url, HTTP_ACCEPT_LANGUAGE="en")
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")

        self.assertIn("Add More Photos", content)
        self.assertIn("Take Photo", content)
        self.assertIn("Choose from Gallery", content)
        self.assertIn("Upload Selected Photos", content)
