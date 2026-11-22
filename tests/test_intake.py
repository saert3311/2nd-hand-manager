from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import translation

from inventory.models import Product
from tests.helpers import create_user_with_group, make_test_image_file


class ProductIntakeViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = create_user_with_group("assistant1")
        cls.url = reverse("inventory:intake")

    def test_intake_requires_login(self):
        resp = self.client.get(self.url)
        self.assertRedirects(resp, f"{reverse('inventory:login')}?next={self.url}")

    def test_intake_get_authenticated(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "New Product Intake")
        self.assertContains(resp, 'id="cameraInput"')
        self.assertContains(resp, 'id="imageInput"')
        self.assertContains(resp, 'id="btnTriggerCamera"')
        self.assertContains(resp, 'id="btnTriggerGallery"')
        self.assertContains(resp, 'id="compressionIndicator"')
        self.assertContains(resp, 'id="identifyBtn"')
        self.assertContains(resp, 'id="aiAdvisoryBanner"')
        self.assertContains(resp, 'id="applySuggestionBtn"')
        self.assertContains(resp, 'id="id_sale_price"')

    def test_intake_post_without_images_fails(self):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {"raw_note": "A cool vintage watch"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Please attach at least one photo")
        self.assertEqual(Product.objects.count(), 0)

    def test_intake_post_with_valid_images_success(self):
        self.client.force_login(self.user)
        img1 = make_test_image_file(name="front.jpg", size=(80, 80), color="red")
        img2 = make_test_image_file(
            name="back.png", size=(80, 80), color="red", image_format="PNG", content_type="image/png"
        )

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
        self.client.force_login(self.user)
        images = [make_test_image_file(name=f"img_{i}.jpg", size=(80, 80), color="red") for i in range(11)]

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
        self.client.force_login(self.user)
        img = make_test_image_file(name="item.jpg", size=(80, 80), color="red")

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

    def test_intake_sale_price_displays_in_dashboard_and_product_detail(self):
        self.client.force_login(self.user)
        img = make_test_image_file(name="item.jpg", size=(80, 80), color="red")

        self.client.post(
            self.url,
            {
                "raw_note": "Vintage Nike windbreaker",
                "sale_price": "29.99",
                "images": [img],
            }
        )
        product = Product.objects.get(raw_note="Vintage Nike windbreaker")

        # 1. Check dashboard list view
        dash_resp = self.client.get(reverse("inventory:dashboard"))
        self.assertEqual(dash_resp.status_code, 200)
        self.assertContains(dash_resp, "29.99")

        # 2. Check product detail view in English
        detail_resp = self.client.get(reverse("inventory:product_detail", kwargs={"pk": product.pk}))
        self.assertEqual(detail_resp.status_code, 200)
        self.assertContains(detail_resp, "product-price-badge")
        self.assertContains(detail_resp, 'value="29.99"')

        # 3. Check product detail view in Spanish (avoiding HTML5 comma sanitization bug)
        detail_es = self.client.get(
            reverse("inventory:product_detail", kwargs={"pk": product.pk}),
            headers={"accept-language": "es"}
        )
        self.assertEqual(detail_es.status_code, 200)
        content_es = detail_es.content.decode("utf-8")
        self.assertIn("product-price-badge", content_es)
        self.assertIn('value="29.99"', content_es)
        self.assertNotIn('value="29,99"', content_es)


    def test_intake_post_with_blank_sale_price_sets_none(self):
        self.client.force_login(self.user)
        img = make_test_image_file(name="item.jpg", size=(80, 80), color="red")

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
        self.client.force_login(self.user)
        img = make_test_image_file(name="item.jpg", size=(80, 80), color="red")

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
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'name="sale_price"')
        self.assertContains(resp, "Target Sale Price")
        self.assertContains(resp, "€")

    def test_intake_get_renders_validation_and_async_elements(self):
        self.client.force_login(self.user)
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
        self.client.force_login(self.user)
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
        self.client.force_login(self.user)
        resp = self.client.get(self.url, headers={"Accept-Language": "es"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Guardando producto...")
        self.assertContains(resp, "Espera a que finalice el análisis con IA...")
        self.assertContains(resp, "Por favor, adjunta al menos una foto del producto antes de guardar.")
        self.assertContains(resp, "Eliminar foto")
        self.assertContains(resp, "Por favor, selecciona un máximo de 10 fotos.")

    def test_intake_get_renders_hidden_ai_title_field(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'type="hidden" name="ai_title" id="id_ai_title"')

    def test_intake_post_with_ai_title_persists_and_sets_display_title(self):
        self.client.force_login(self.user)
        img = make_test_image_file(name="item.jpg", size=(80, 80), color="red")

        resp = self.client.post(
            self.url,
            {
                "ai_title": "Vintage Levi's 501 Big E",
                "raw_note": "Found at estate sale, denim in pristine condition",
                "sale_price": "85.00",
                "images": [img],
            }
        )
        self.assertRedirects(resp, self.url)
        self.assertEqual(Product.objects.count(), 1)
        product = Product.objects.first()
        self.assertEqual(product.ai_title, "Vintage Levi's 501 Big E")
        self.assertEqual(product.display_title, "Vintage Levi's 501 Big E")
        # Since it has no description yet, status must be DRAFT
        self.assertEqual(product.status, "draft")

    def test_intake_post_without_ai_title_falls_back_to_raw_note_or_id(self):
        self.client.force_login(self.user)
        img = make_test_image_file(name="item.jpg", size=(80, 80), color="red")

        resp = self.client.post(
            self.url,
            {
                "ai_title": "",
                "raw_note": "Leather boots brown size 42",
                "sale_price": "40.00",
                "images": [img],
            }
        )
        self.assertRedirects(resp, self.url)
        product = Product.objects.first()
        self.assertEqual(product.ai_title, "")
        self.assertEqual(product.display_title, "Leather boots brown size 42")


class IntakeLowDPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = create_user_with_group("scanner_assistant")
        cls.url = reverse("inventory:intake")

    def setUp(self):
        self.client.force_login(self.user)

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
        with translation.override("es"):
            resp = self.client.get(self.url, headers={"Accept-Language": "es"})
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
        with translation.override("en"):
            resp = self.client.get(self.url, headers={"Accept-Language": "en"})
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
        img = make_test_image_file(name="compact_test.jpg", size=(80, 80), color="green")
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


class IntakeIdentificationGateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = create_user_with_group("assistant_gate")
        cls.url = reverse("inventory:intake")
        cls.identify_url = reverse("inventory:intake_identify")

    def setUp(self):
        self.client.force_login(self.user)

    def test_submit_button_initially_disabled_in_html(self):
        """Verify the Save button renders with disabled attribute and accessibility attributes on initial page load."""
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

        # Check button attributes
        html = resp.content.decode("utf-8")
        self.assertIn('id="submitBtn"', html)
        self.assertIn("disabled", html)
        self.assertIn('aria-disabled="true"', html)
        self.assertIn('aria-describedby="submitHelpText"', html)

        # Check helper text element
        self.assertIn('id="submitHelpText"', html)
        self.assertIn("Identify product with AI first to enable saving", html)

    def test_submit_button_spanish_localization(self):
        """Verify localized Spanish text for the mandatory identification helper text."""
        with translation.override("es"):
            resp = self.client.get(self.url, headers={"Accept-Language": "es"})
            self.assertEqual(resp.status_code, 200)
            html = resp.content.decode("utf-8")
            self.assertIn("Identifica primero el producto con IA para habilitar el guardado", html)
            self.assertIn("Producto identificado — listo para guardar", html)
            self.assertIn("Por favor, identifica el producto con IA antes de guardar.", html)

    def test_template_contains_identification_gate_controls(self):
        """Verify presence of intake form, AI identify trigger, guarded submit button, and live help text."""
        resp = self.client.get(self.url)
        html = resp.content.decode("utf-8")

        self.assertIn('id="intakeForm"', html)
        self.assertIn('id="identifyBtn"', html)
        self.assertIn('id="submitBtn"', html)
        self.assertIn('id="submitHelpText"', html)
        self.assertIn('aria-disabled="true"', html)

    @patch("inventory.views.identify_intake_product")
    def test_identify_preflight_endpoint_success_enables_gate(self, mock_identify):
        """Verify identify endpoint returns JSON success for assistant."""
        mock_identify.return_value = {
            "success": True,
            "identified_title": "Sony Walkman WM-D6C",
            "category": "Electronics",
            "detected_attributes": ["Vintage", "Cassette Player"],
            "suggested_note": "Includes original carry case and manual.",
            "missing_or_recommended_info": ["Check battery compartment for corrosion."],
            "estimated_retail_price": 350.00,
            "estimated_resale_price": 180.00,
        }

        img = make_test_image_file(name="walkman.jpg", size=(60, 60), color="blue")
        resp = self.client.post(self.identify_url, {"images": [img], "raw_note": "Vintage walkman"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["identified_title"], "Sony Walkman WM-D6C")
        self.assertEqual(data["estimated_retail_price"], 350.00)
        self.assertEqual(data["estimated_resale_price"], 180.00)

    @patch("inventory.views.identify_intake_product")
    def test_identify_preflight_endpoint_failure_fallback_response(self, mock_identify):
        """Verify identify endpoint handles error safely (returning JSON error) without breaking the flow."""
        mock_identify.return_value = {
            "success": False,
            "error": "Could not identify product from photos.",
            "identified_title": None,
            "category": None,
            "detected_attributes": [],
            "suggested_note": None,
            "missing_or_recommended_info": [],
            "estimated_retail_price": None,
            "estimated_resale_price": None,
        }

        img = make_test_image_file(name="unclear.jpg", size=(60, 60), color="blue")
        resp = self.client.post(self.identify_url, {"images": [img]})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["success"])
        self.assertIn("Could not identify product", data["error"])

    def test_backend_submission_persists_valid_product(self):
        """Verify that the backend intake view persists valid submissions successfully."""
        img = make_test_image_file(name="item.jpg", size=(60, 60), color="blue")

        resp = self.client.post(
            self.url,
            {
                "raw_note": "Handmade wooden chair",
                "images": [img],
                "ai_title": "Vintage Oak Dining Chair",
                "estimated_retail_price": "120.00",
                "estimated_resale_price": "60.00",
                "sale_price": "55.00",
            },
        )
        self.assertRedirects(resp, self.url)
        self.assertEqual(Product.objects.count(), 1)
        prod = Product.objects.first()
        self.assertEqual(prod.raw_note, "Handmade wooden chair")
        self.assertEqual(prod.ai_title, "Vintage Oak Dining Chair")
        self.assertEqual(prod.estimated_retail_price, Decimal("120.00"))
        self.assertEqual(prod.estimated_resale_price, Decimal("60.00"))
        self.assertEqual(prod.sale_price, Decimal("55.00"))


