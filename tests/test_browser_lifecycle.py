import os
import shutil

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from playwright.sync_api import sync_playwright

from inventory.models import MarketplaceSite, Product, ProductStatus

User = get_user_model()


@override_settings(TURNSTILE_ENABLED=False)
class BrowserRefinedLifecycleTests(StaticLiveServerTestCase):
    """
    End-to-end real browser verification using Google Chrome via Playwright.
    Tests the complete normal daily workflow:
    1. Intake with AI preflight auto-filling hidden title without generic fallback.
    2. Automatic DRAFT status when no description.
    3. Staging manager adding description -> auto-transition to PRICE_PENDING.
    4. Dashboard filter tab 'Precio pendiente' with live badge counter.
    5. Manager setting price -> auto-transition to READY.
    6. Manager adding marketplace link -> auto-transition to PUBLISHED.
    7. Manager deleting link -> auto-reversion to READY.
    8. Marking sold -> SOLD, and marking unsold -> auto-reversion to READY.
    """

    @classmethod
    def setUpClass(cls):
        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
        super().setUpClass()
        os.makedirs("screenshots", exist_ok=True)
        os.makedirs("tmp_test_images", exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        if os.path.exists("tmp_test_images"):
            shutil.rmtree("tmp_test_images", ignore_errors=True)

    def setUp(self):
        self.manager = User.objects.create_user(
            username="manager_chrome",
            password="password123",
            is_staff=True,
        )
        self.wallapop, _ = MarketplaceSite.objects.get_or_create(
            slug="wallapop",
            defaults={"name": "Wallapop", "order": 1, "is_active": True},
        )

    def create_dummy_image_file(self, filename="sample.jpg"):
        path = os.path.join("tmp_test_images", filename)
        img = Image.new("RGB", (200, 200), color="blue")
        img.save(path, format="JPEG")
        return os.path.abspath(path)

    def test_full_daily_workflow_in_real_chrome(self):
        img_path = self.create_dummy_image_file("nike_acg.jpg")

        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            context = browser.new_context(viewport={"width": 1280, "height": 800}, locale="es-ES")
            page = context.new_page()

            # Automatically accept any confirm dialogs (e.g. deleting marketplace link)
            page.on("dialog", lambda dialog: dialog.accept())

            # Mock intake AI identification route to avoid real external Gemini network quota
            def handle_identify(route):
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body='''{
                        "success": true,
                        "identified_title": "Vintage Nike ACG Windbreaker Jacket",
                        "category": "Ropa Vintage",
                        "detected_attributes": ["Nylon ripstop", "Logotipo ACG bordado", "Capucha oculta"],
                        "missing_or_recommended_info": ["Revisar cremallera frontal"],
                        "suggested_note": "Chaqueta vintage Nike ACG color azul marino, talla L, buen estado general."
                    }'''
                )

            page.route("**/intake/identify/", handle_identify)

            # 1. Login
            page.goto(f"{self.live_server_url}{reverse('inventory:login')}")
            user_input = page.locator("#id_username")
            user_input.click()
            user_input.fill("manager_chrome")
            pass_input = page.locator("#id_password")
            pass_input.click()
            pass_input.fill("password123")
            page.screenshot(path="screenshots/debug_00_login_filled.png")
            with page.expect_navigation():
                page.click("#loginSubmitBtn")

            # 2. Intake View
            page.goto(f"{self.live_server_url}{reverse('inventory:intake')}")
            page.wait_for_selector("#dropZone")

            # Upload photo
            page.set_input_files("#imageInput", img_path)
            page.wait_for_selector("#previewGrid img")

            # Click "Identificar producto"
            page.click("#identifyBtn")
            page.wait_for_selector("#aiAdvisoryBanner:not(.hidden)")

            # Verify hidden ai_title input was populated with AI identification
            ai_title_val = page.input_value("#id_ai_title")
            self.assertEqual(ai_title_val, "Vintage Nike ACG Windbreaker Jacket")

            # Fill raw field notes, leave price blank
            page.fill("#id_raw_note", "Chaqueta Nike ACG encontrada en mercadillo vintage, buen estado.")
            page.screenshot(path="screenshots/01_intake_preflight_filled.png")

            # Submit intake form
            page.click("#submitBtn")
            page.wait_for_load_state("networkidle")

            # Verify product in database
            product = Product.objects.get(ai_title="Vintage Nike ACG Windbreaker Jacket")
            self.assertEqual(product.status, ProductStatus.DRAFT)
            self.assertIsNone(product.sale_price)
            self.assertEqual(product.display_title, "Vintage Nike ACG Windbreaker Jacket")

            # 3. Dashboard View - Verify Price Pending Tab & Initial Draft
            page.goto(f"{self.live_server_url}{reverse('inventory:dashboard')}")
            page.wait_for_selector("a[href*='status=price_pending']")
            page.screenshot(path="screenshots/02_dashboard_initial_draft.png")

            # 4. Open Product Staging Detail
            page.goto(f"{self.live_server_url}{reverse('inventory:product_detail', kwargs={'pk': product.pk})}")
            page.wait_for_selector("#product-status-badge")
            status_text = page.inner_text("#product-status-badge")
            self.assertTrue("BORRADOR" in status_text.upper() or "DRAFT" in status_text.upper())
            page.screenshot(path="screenshots/03_staging_initial_draft.png")

            # 5. Manager adds Description, but leaves price empty -> Auto-transitions to PRICE_PENDING
            page.fill('textarea[name="ai_description"]', "Chaqueta cortavientos técnica vintage Nike ACG de los años 90. Tejido ripstop repelente al agua con cremalleras selladas.")
            page.click('button:has-text("Guardar cambios"), button:has-text("Save Listing Changes")')
            page.wait_for_load_state("networkidle")

            product.refresh_from_db()
            self.assertEqual(product.status, ProductStatus.PRICE_PENDING)

            status_badge_text = page.inner_text("#product-status-badge")
            self.assertTrue(
                "PRECIO PENDIENTE" in status_badge_text.upper() or "PRICE PENDING" in status_badge_text.upper(),
                f"Expected Price Pending in badge, got: {status_badge_text}"
            )
            page.screenshot(path="screenshots/04_staging_price_pending.png")

            # 6. Dashboard - Filter by 'price_pending'
            page.goto(f"{self.live_server_url}{reverse('inventory:dashboard')}")
            price_pending_tab = page.wait_for_selector("a[href*='status=price_pending']")
            self.assertIn("(1)", price_pending_tab.inner_text())

            price_pending_tab.click()
            page.wait_for_load_state("networkidle")
            page.screenshot(path="screenshots/05_dashboard_filtered_price_pending.png")
            # Verify product card is displayed in filtered list
            self.assertTrue(page.locator('text="Vintage Nike ACG Windbreaker Jacket"').is_visible())

            # 7. Open Staging, enter Price 79.99 -> Auto-transitions to READY
            page.goto(f"{self.live_server_url}{reverse('inventory:product_detail', kwargs={'pk': product.pk})}")
            page.fill('input[name="sale_price"]', "79.99")
            page.click('button:has-text("Guardar cambios"), button:has-text("Save Listing Changes")')
            page.wait_for_load_state("networkidle")

            product.refresh_from_db()
            self.assertEqual(product.status, ProductStatus.READY)
            status_badge_text = page.inner_text("#product-status-badge")
            self.assertTrue("LISTO" in status_badge_text.upper() or "READY" in status_badge_text.upper())
            page.screenshot(path="screenshots/06_staging_ready.png")

            # 8. Add Marketplace Listing Link -> Auto-transitions to PUBLISHED
            wallapop_row = page.locator('div[data-site-slug="wallapop"]')
            self.assertTrue(wallapop_row.is_visible())
            wallapop_row.locator('input[name="url"]').fill("https://es.wallapop.com/item/vintage-nike-acg-102938475")
            wallapop_row.locator('form:has(input[value="save"]) button[type="submit"]').click()
            page.wait_for_load_state("networkidle")

            product.refresh_from_db()
            self.assertEqual(product.status, ProductStatus.PUBLISHED)
            status_badge_text = page.inner_text("#product-status-badge")
            self.assertTrue("PUBLICADO" in status_badge_text.upper() or "PUBLISHED" in status_badge_text.upper())
            page.screenshot(path="screenshots/07_staging_published.png")

            # 9. Deactivate/Delete Marketplace Link -> Auto-reverts to READY
            wallapop_row = page.locator('div[data-site-slug="wallapop"]')
            delete_btn = wallapop_row.locator('form:has(input[value="delete"]) button[type="submit"]')
            delete_btn.click()
            page.wait_for_selector("#actionConfirmModal:not(.hidden)")
            page.click("#btnProceedActionConfirm")
            page.wait_for_load_state("networkidle")

            product.refresh_from_db()
            self.assertEqual(product.status, ProductStatus.READY)
            status_badge_text = page.inner_text("#product-status-badge")
            self.assertTrue("LISTO" in status_badge_text.upper() or "READY" in status_badge_text.upper())
            page.screenshot(path="screenshots/08_staging_reverted_to_ready.png")

            # 10. Mark as Sold -> SOLD
            page.check('input[name="is_sold"]')
            page.click('button.quick-channel-btn[data-channel="in_store"]')
            page.click('button:has-text("Guardar cambios"), button:has-text("Save Listing Changes")')
            page.wait_for_load_state("networkidle")

            product.refresh_from_db()
            self.assertEqual(product.status, ProductStatus.SOLD)
            self.assertTrue(product.is_sold)
            status_badge_text = page.inner_text("#product-status-badge")
            self.assertTrue("VENDIDO" in status_badge_text.upper() or "SOLD" in status_badge_text.upper())
            page.screenshot(path="screenshots/09_staging_sold.png")

            # 11. Mark as Unsold -> Auto-reverts to READY
            page.uncheck('input[name="is_sold"]')
            page.click('button:has-text("Guardar cambios"), button:has-text("Save Listing Changes")')
            page.wait_for_load_state("networkidle")

            product.refresh_from_db()
            self.assertEqual(product.status, ProductStatus.READY)
            self.assertFalse(product.is_sold)
            status_badge_text = page.inner_text("#product-status-badge")
            self.assertTrue("LISTO" in status_badge_text.upper() or "READY" in status_badge_text.upper())
            page.screenshot(path="screenshots/10_staging_unsold_back_to_ready.png")

            browser.close()
