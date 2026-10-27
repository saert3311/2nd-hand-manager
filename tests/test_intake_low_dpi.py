import io
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import translation
from PIL import Image

from inventory.models import Product

User = get_user_model()


class IntakeLowDPITests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="scanner_assistant", password="password123")
        self.url = reverse("inventory:intake")

    def create_dummy_image(self, name="photo.jpg", format="JPEG"):
        buf = io.BytesIO()
        img = Image.new("RGB", (80, 80), color="green")
        img.save(buf, format=format)
        buf.seek(0)
        return SimpleUploadedFile(name, buf.getvalue(), content_type=f"image/{format.lower()}")

    def test_preview_grid_density_responsive_classes(self):
        """Verify the preview grid uses a comfortable 2-column layout on mobile viewports for easier button tapping."""
        self.client.login(username="scanner_assistant", password="password123")
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")

        # Must use 2-column layout on mobile devices for accessible touch controls
        self.assertIn('id="previewGrid"', html)
        self.assertIn("grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2.5 sm:gap-3", html)
        self.assertNotIn("grid-cols-3 sm:grid-cols-4 md:grid-cols-5", html)

    def test_streamlined_intake_header_and_identify_elements(self):
        """Verify the 'View Catalog' link, header subtitle, and identify help text are removed for streamlined mobile UX."""
        self.client.login(username="scanner_assistant", password="password123")
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")

        self.assertNotIn("Snap photos &amp; jot notes on the go", html)
        self.assertNotIn("Snap photos & jot notes on the go", html)
        self.assertNotIn("View Catalog", html)
        self.assertNotIn("Ver catálogo", html)
        self.assertNotIn('id="identifyHelpText"', html)

    def test_streamlined_ai_advisory_banner(self):
        """Verify AI advisory banner has reduced margins, full-width button without helper text, and overflow protection."""
        self.client.login(username="scanner_assistant", password="password123")
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")

        self.assertIn('id="aiAdvisoryBanner" class="hidden p-3 sm:p-3.5 rounded-xl border', html)
        self.assertNotIn("Quickly copy AI suggestion into field notes", html)
        self.assertNotIn("Copia rápidamente la sugerencia", html)
        self.assertIn("w-full sm:w-auto inline-flex items-center justify-center", html)
        self.assertIn("max-w-full", html)

    def test_delete_button_contrast_and_stroke_width(self):
        """Verify delete button 'X' visual badge uses high-contrast white ring and bold stroke-width=3 for 1x low-DPI clarity."""
        self.client.login(username="scanner_assistant", password="password123")
        resp = self.client.get(self.url)
        html = resp.content.decode("utf-8")

        # Visual badge with white isolation ring to pop against busy photo backgrounds
        self.assertIn("ring-1 ring-white/90", html)
        self.assertIn("bg-rose-600 hover:bg-rose-700 active:bg-rose-800", html)
        self.assertIn("w-6 h-6 rounded-full", html)

        # SVG cross icon with bold stroke-width=3 for crisp low-DPI rendering
        self.assertIn('stroke-width="3"', html)
        self.assertIn("photo-delete-btn", html)

    def test_top_badge_compact_styling(self):
        """Verify top-left Cover and sequence badges have compact dimensions preventing overlap with delete button."""
        self.client.login(username="scanner_assistant", password="password123")
        resp = self.client.get(self.url)
        html = resp.content.decode("utf-8")

        # Compact cover badge and sequence pill with contrast ring
        self.assertIn("ring-1 ring-black/20", html)
        self.assertIn("ring-1 ring-white/20", html)
        self.assertIn("⭐ #1", html)

    def test_thumbnail_card_and_image_cursor(self):
        """Verify miniature cards feature dark framing and images have cursor-pointer and click-to-inspect trigger."""
        self.client.login(username="scanner_assistant", password="password123")
        resp = self.client.get(self.url)
        html = resp.content.decode("utf-8")

        self.assertIn("bg-slate-900", html)
        self.assertIn("cursor-pointer", html)
        self.assertIn("openLightbox(idx)", html)

    def test_reorder_controls_compact_pill(self):
        """Verify bottom reorder controls are housed in a slim floating pill leaving over 70% of thumbnail visible."""
        self.client.login(username="scanner_assistant", password="password123")
        resp = self.client.get(self.url)
        html = resp.content.decode("utf-8")

        self.assertIn("bg-slate-900/80 backdrop-blur-xs p-0.5 rounded-lg", html)
        self.assertIn("photo-reorder-btn w-6 h-6", html)

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
