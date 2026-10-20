import os
import shutil
import sys

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from playwright.sync_api import sync_playwright

from inventory.models import MarketplaceSite, Product, ProductStatus

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

User = get_user_model()


@override_settings(TURNSTILE_ENABLED=False)
class BrowserDailyWorkflowValuationTests(StaticLiveServerTestCase):
    """
    Real Chrome browser verification of the complete daily workflow on a normal day:
    1. Assistant intake: uploading photo and field notes.
    2. Preflight AI identification: returning MSRP (new retail) and estimated secondhand resale.
    3. UI verification: advisory valuation cards and benchmark pills.
    4. One-click adoption: assistant clicks 'Usar precio de reventa estimado'.
    5. Intake submission: persists product with valuation benchmarks and sale price.
    6. Manager staging review: dashboard inspection and detail view benchmark badges.
    7. Manager workflow: 'Aplicar reventa' quick button, description entry, and lifecycle progression.
    8. Sales tracking: marking as sold and verifying audit trail & footer compilation info.
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
            username="manager_daily",
            password="password123",
            is_staff=True,
        )
        self.wallapop, _ = MarketplaceSite.objects.get_or_create(
            slug="wallapop",
            defaults={"name": "Wallapop", "order": 1, "is_active": True},
        )

    def create_dummy_image_file(self, filename="sample.jpg"):
        path = os.path.join("tmp_test_images", filename)
        img = Image.new("RGB", (300, 300), color=(30, 80, 160))
        img.save(path, format="JPEG")
        return os.path.abspath(path)

    def test_complete_daily_workflow_with_ai_valuation_in_chrome(self):
        img_path = self.create_dummy_image_file("barbour_jacket.jpg")

        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            context = browser.new_context(viewport={"width": 1280, "height": 850}, locale="es-ES")
            page = context.new_page()

            # Mock preflight AI identification route
            def handle_identify(route):
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body='''{
                        "success": true,
                        "identified_title": "Chaqueta Barbour Beaufort Encerada",
                        "category": "Ropa Vintage",
                        "detected_attributes": ["Algodón encerado verde oliva", "Cuello de pana marrón", "Cremallera de latón doble carro"],
                        "missing_or_recommended_info": ["Revisar desgaste en puños y bajo", "Comprobar etiqueta blanca interior de talla"],
                        "suggested_note": "Chaqueta Barbour Beaufort clásica encerada, talla C40/102cm, buen estado con pátina natural.",
                        "estimated_retail_price": 435.00,
                        "estimated_resale_price": 165.00
                    }'''
                )

            page.route("**/intake/identify/", handle_identify)

            # =================================================================
            # 1. LOGIN
            # =================================================================
            print("\n[STEP 1] Logging in as Manager...")
            page.goto(f"{self.live_server_url}{reverse('inventory:login')}")
            page.fill("#id_username", "manager_daily")
            page.fill("#id_password", "password123")
            with page.expect_navigation():
                page.click("#loginSubmitBtn")

            # =================================================================
            # 2. INTAKE WITH AI PREFLIGHT APPRAISAL
            # =================================================================
            print("[STEP 2] Navigating to Intake screen...")
            page.goto(f"{self.live_server_url}{reverse('inventory:intake')}")
            page.wait_for_selector("#dropZone")

            # Upload product photo
            print("Uploading photo...")
            page.set_input_files("#imageInput", img_path)
            page.wait_for_selector("#previewGrid img")

            # Fill raw note
            page.fill("#id_raw_note", "Barbour Beaufort vintage verde oliva, cremallera perfecta, ligera pátina.")

            # Trigger AI identification
            print("Triggering AI identification...")
            page.click("#identifyBtn")
            page.wait_for_selector("#advisoryValuationContainer:not(.hidden)", timeout=10000)

            # Verify AI Advisory Banner with MSRP and Used Resale
            retail_banner = page.inner_text("#advisoryRetailPrice")
            resale_banner = page.inner_text("#advisoryResalePrice")
            print(f"Advisory valuation banner: MSRP={retail_banner}, Resale={resale_banner}")
            self.assertIn("435", retail_banner)
            self.assertIn("165", resale_banner)

            # Verify Benchmark Pills near Sale Price input
            benchmarks_el = page.locator("#intakePriceBenchmarks")
            self.assertTrue(benchmarks_el.is_visible())
            badge_retail = page.inner_text("#badgeRefRetail")
            badge_resale = page.inner_text("#badgeRefResale")
            print(f"Benchmark reference badges verified: MSRP 435 in '{badge_retail.encode('ascii', 'ignore').decode()}', Resale 165 in '{badge_resale.encode('ascii', 'ignore').decode()}'")
            self.assertIn("435", badge_retail)
            self.assertIn("165", badge_resale)

            # Capture visual screenshot of intake valuation benchmarks
            page.screenshot(path="screenshots/daily_01_intake_valuation_benchmarks.png")

            # Click 'Usar precio de reventa estimado' button
            print("Clicking 'Usar precio de reventa estimado'...")
            use_resale_btn = page.locator("#btnUseEstimatedResale")
            self.assertTrue(use_resale_btn.is_visible())
            use_resale_btn.click()

            sale_price_val = page.input_value("#id_sale_price")
            print(f"Sale price automatically filled with: {sale_price_val}")
            self.assertEqual(sale_price_val, "165.00")

            # Hidden inputs verification
            self.assertEqual(page.input_value("#id_estimated_retail_price"), "435.00")
            self.assertEqual(page.input_value("#id_estimated_resale_price"), "165.00")

            page.screenshot(path="screenshots/daily_02_intake_resale_applied.png")

            # Submit intake form
            print("Submitting intake form...")
            page.click("#submitBtn")
            page.wait_for_load_state("networkidle")

            # Verify in database
            product = Product.objects.get(ai_title="Chaqueta Barbour Beaufort Encerada")
            self.assertEqual(product.estimated_retail_price, 435.00)
            self.assertEqual(product.estimated_resale_price, 165.00)
            self.assertEqual(product.sale_price, 165.00)
            print("Product persisted in database with full valuation benchmarks!")

            # =================================================================
            # 3. MANAGER DASHBOARD INSPECTION
            # =================================================================
            print("\n[STEP 3] Manager inspecting Catalog Dashboard...")
            page.goto(f"{self.live_server_url}{reverse('inventory:dashboard')}")
            page.wait_for_selector('a[href*="/products/"]')
            page.screenshot(path="screenshots/daily_03_dashboard_with_item.png")

            # Verify product is visible on dashboard with sale price €165.00
            self.assertTrue(page.locator('text="Chaqueta Barbour Beaufort Encerada"').is_visible())
            self.assertIn("165", page.content())

            # =================================================================
            # 4. PRODUCT DETAIL STAGING REVIEW & BENCHMARKS
            # =================================================================
            print("\n[STEP 4] Opening Staging Product Detail view...")
            page.goto(f"{self.live_server_url}{reverse('inventory:product_detail', kwargs={'pk': product.pk})}")
            page.wait_for_selector("#id_sale_price")

            # Verify benchmark badges beside Sale Price input
            detail_benchmarks = page.locator("#detail-valuation-benchmarks")
            self.assertTrue(detail_benchmarks.is_visible())
            ref_retail_text = page.inner_text("#ref-retail-price")
            ref_resale_text = page.inner_text("#ref-resale-price")
            print(f"Detail staging benchmark badges verified: MSRP 435 in '{ref_retail_text.encode('ascii', 'ignore').decode()}', Resale 165 in '{ref_resale_text.encode('ascii', 'ignore').decode()}'")
            self.assertIn("435", ref_retail_text)
            self.assertIn("165", ref_resale_text)

            # Verify 'Aplicar reventa' button
            apply_btn = page.locator("#btnApplyResalePrice")
            self.assertTrue(apply_btn.is_visible())
            self.assertEqual(apply_btn.get_attribute("data-resale"), "165.00")

            # Verify footer compilation info
            footer_time = page.inner_text("#footer-build-time")
            footer_sha = page.inner_text("#footer-build-sha")
            print(f"Footer compilation info: {footer_time} | {footer_sha}")
            self.assertTrue(len(footer_time) > 0)

            page.screenshot(path="screenshots/daily_04_product_detail_valuation_benchmarks.png")

            # =================================================================
            # 5. LISTING DESCRIPTION ENTRY & READY TRANSITION
            # =================================================================
            print("\n[STEP 5] Manager drafting listing description...")
            page.fill(
                'textarea[name="ai_description"]',
                "Auténtica chaqueta Barbour Beaufort encerada en color verde oliva. Talla C40. Fabricada en Inglaterra."
            )
            page.click('button:has-text("Guardar cambios"), button:has-text("Save Listing Changes")')
            page.wait_for_load_state("networkidle")

            product.refresh_from_db()
            # Since sale_price was pre-entered at 165.00, adding description fast-tracks directly to READY!
            self.assertEqual(product.status, ProductStatus.READY)
            status_text = page.inner_text("#product-status-badge")
            self.assertTrue("LISTO" in status_text.upper() or "READY" in status_text.upper())
            print("Product auto-transitioned to READY status!")

            # =================================================================
            # 6. MARK AS SOLD & LIFECYCLE AUDIT TRAIL VERIFICATION
            # =================================================================
            print("\n[STEP 6] Marking product as Sold and verifying Audit Trail...")
            page.check('input[name="is_sold"]')
            page.click('button:has-text("Guardar cambios"), button:has-text("Save Listing Changes")')
            page.wait_for_load_state("networkidle")

            product.refresh_from_db()
            self.assertEqual(product.status, ProductStatus.SOLD)
            self.assertTrue(product.is_sold)

            # Verify Lifecycle Audit Trail Card
            audit_card = page.locator("#status-history-card, h3:has-text('Historial de Estados')")
            self.assertTrue(audit_card.is_visible())
            self.assertIn("manager_daily", page.content())
            print("Verified state change recorded in Lifecycle Audit Trail!")

            page.screenshot(path="screenshots/daily_05_product_marked_sold_audit_trail.png")

            # =================================================================
            # 7. DASHBOARD 'VENDIDO' TAB VERIFICATION
            # =================================================================
            print("\n[STEP 7] Verifying marked item under Dashboard 'Vendido' tab...")
            page.goto(f"{self.live_server_url}{reverse('inventory:dashboard')}?status=sold")
            page.wait_for_load_state("networkidle")
            page.screenshot(path="screenshots/daily_06_dashboard_sold_tab.png")
            self.assertTrue(page.locator('text="Chaqueta Barbour Beaufort Encerada"').is_visible())
            print("Verified sold item displays in 'Vendido' dashboard tab!")

            # =================================================================
            # 8. MOBILE RESPONSIVENESS CHECK (390 x 844 iPhone Viewport)
            # =================================================================
            print("\n[STEP 8] Verifying mobile responsiveness ($390 x 844)...")
            mobile_context = browser.new_context(
                viewport={"width": 390, "height": 844},
                locale="es-ES",
                is_mobile=True,
                has_touch=True,
            )
            mobile_page = mobile_context.new_page()

            # Mobile Product Detail
            mobile_page.goto(f"{self.live_server_url}{reverse('inventory:product_detail', kwargs={'pk': product.pk})}")
            mobile_page.wait_for_load_state("networkidle")
            mobile_page.screenshot(path="screenshots/daily_07_mobile_product_detail.png")

            # Mobile Dashboard
            mobile_page.goto(f"{self.live_server_url}{reverse('inventory:dashboard')}")
            mobile_page.wait_for_load_state("networkidle")
            mobile_page.screenshot(path="screenshots/daily_08_mobile_dashboard.png")

            mobile_context.close()
            browser.close()
            print("\n==================================================================")
            print("FULL DAILY WORKFLOW VERIFICATION IN REAL CHROME PASSED 100%!")
            print("==================================================================")
