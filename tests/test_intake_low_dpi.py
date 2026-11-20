from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import translation

from inventory.models import Product
from tests.helpers import make_test_image_file

User = get_user_model()


class IntakeLowDPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="scanner_assistant", password="password123")
        cls.url = reverse("inventory:intake")

    def setUp(self):
        self.client.force_login(self.user)

    def create_dummy_image(self, name="photo.jpg", format="JPEG"):
        return make_test_image_file(
            name=name, size=(80, 80), color="green", image_format=format, content_type=f"image/{format.lower()}"
        )

    def test_preview_grid_and_advisory_banner_structure(self):
        """Verify semantic preview grid, streamlined header, advisory banner, and photo action controls."""
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")

        self.assertIn('id="previewGrid"', html)
        self.assertIn("grid-cols-2", html)
        self.assertNotIn("Snap photos &amp; jot notes on the go", html)
        self.assertNotIn("View Catalog", html)
        self.assertNotIn('id="identifyHelpText"', html)

        self.assertIn('id="aiAdvisoryBanner"', html)
        self.assertIn('id="applySuggestionBtn"', html)
        self.assertIn("photo-delete-btn", html)
        self.assertIn("photo-reorder-btn", html)
        self.assertIn("⭐ #1", html)

    def test_image_inspection_lightbox_modal_presence(self):
        """Verify full-size image inspection lightbox modal exists with proper accessibility roles and controls."""
        self.client.login(username="scanner_assistant", password="password123")
        resp = self.client.get(self.url)
        html = resp.content.decode("utf-8")

        self.assertIn('id="imagePreviewModal"', html)
        self.assertIn('role="dialog"', html)
        self.assertIn('aria-modal="true"', html)
        self.assertIn('aria-labelledby="modalPhotoTitle"', html)
        self.assertIn('id="modalPreviewImg"', html)
        self.assertIn('id="modalPhotoTitle"', html)
        self.assertIn('id="modalPhotoCounter"', html)
        self.assertIn('id="closeImageModalBtn"', html)
        self.assertIn('id="modalPrevBtn"', html)
        self.assertIn('id="modalNextBtn"', html)
        self.assertIn('id="rotateLeftBtn"', html)
        self.assertIn('id="rotateRightBtn"', html)
        self.assertIn('id="applyCropBtn"', html)
        self.assertIn("inventory/vendor/cropper.min.css", html)
        self.assertIn("inventory/vendor/cropper.min.js", html)
        self.assertIn("photo-edit-btn", html)

    def test_lightbox_modal_spanish_localization(self):
        """Verify Spanish translations for photo inspection, navigation, and preview helper text."""
        self.client.login(username="scanner_assistant", password="password123")
        with translation.override("es"):
            resp = self.client.get(self.url, HTTP_ACCEPT_LANGUAGE="es")
            self.assertEqual(resp.status_code, 200)
            html = resp.content.decode("utf-8")

            self.assertIn("Inspección de foto", html)
            self.assertIn("Cerrar vista previa", html)
            self.assertIn("Arrastra o toca las flechas para reordenar", html)
            self.assertIn("Toca para ampliar foto", html)
            self.assertIn("Foto anterior", html)
            self.assertIn("Foto siguiente", html)
            self.assertIn("Cerrar", html)
            self.assertIn("Girar 90° a la izquierda", html)
            self.assertIn("Girar 90° a la derecha", html)
            self.assertIn("Aplicar recorte y giro", html)
            self.assertIn("Recortar o girar foto", html)

    def test_lightbox_modal_english_localization(self):
        """Verify English text for photo inspection, navigation, and preview helper text."""
        self.client.login(username="scanner_assistant", password="password123")
        with translation.override("en"):
            resp = self.client.get(self.url, HTTP_ACCEPT_LANGUAGE="en")
            self.assertEqual(resp.status_code, 200)
            html = resp.content.decode("utf-8")

            self.assertIn("Photo Inspection", html)
            self.assertIn("Close preview", html)
            self.assertIn("Drag or tap arrows to reorder", html)
            self.assertIn("Tap to enlarge photo", html)
            self.assertIn("Previous photo", html)
            self.assertIn("Next photo", html)
            self.assertIn("Close", html)
            self.assertIn("Rotate left 90°", html)
            self.assertIn("Rotate right 90°", html)
            self.assertIn("Apply crop & rotate", html)
            self.assertIn("Crop or rotate photo", html)

    def test_intake_submission_preserves_post_workflow(self):
        """Ensure form POST and image persistence continue working without regressions with the new miniature markup."""
        self.client.login(username="scanner_assistant", password="password123")
        img = self.create_dummy_image("compact_test.jpg")
        data = {
            "images": [img],
            "raw_note": "Scanner intake test note for compact UI",
            "sale_price": "29.99",
            "ai_title": "Identified Item Title",
        }
        resp = self.client.post(self.url, data, follow=True)
        self.assertEqual(resp.status_code, 200)

        product = Product.objects.filter(raw_note__contains="Scanner intake test").first()
        self.assertIsNotNone(product)
        self.assertEqual(product.images.count(), 1)
        self.assertEqual(product.sale_price, Decimal("29.99"))

    def test_notes_field_positioned_directly_below_uploaded_photos(self):
        """Field Notes / Short Description sits right below uploaded photo previews and above AI Identify & Origin."""
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")

        self.assertIn('aria-describedby="rawNoteHelp"', html)
        self.assertIn('id="rawNoteHelp"', html)

        pos_preview = html.index('id="previewContainer"')
        pos_notes = html.index('id="id_raw_note"')
        pos_identify = html.index('id="identifyBtn"')
        pos_origin = html.index('id="id_origin"')
        self.assertLess(pos_preview, pos_notes)
        self.assertLess(pos_notes, pos_identify)
        self.assertLess(pos_identify, pos_origin)
