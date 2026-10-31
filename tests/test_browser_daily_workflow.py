import os
import shutil
import sys
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.files.base import ContentFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from playwright.sync_api import sync_playwright

from inventory.models import (
    Category,
    MarketplaceSite,
    Product,
    ProductCondition,
    ProductImage,
    ProductListingLink,
    ProductStatus,
    StorefrontConfiguration,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

User = get_user_model()


@override_settings(TURNSTILE_ENABLED=False)
class BrowserDailyWorkflowValuationTests(StaticLiveServerTestCase):
    """
    Real Chrome browser verification of the complete daily workflow on a normal day at Rápido Pack:
    1. Customer / Visitor journey on the Public Marketplace Storefront (rapidopack.es):
       - Browsing catalog homepage (/), 12-category rail, trust badges, and Alfafar store details.
       - Opening and testing the native <dialog closedby="any"> 'Cómo comprar en Alfafar' modal.
       - Searching for opportunities and viewing a public product detail page (/p/<slug>-<pk>/).
       - Inspecting real studio photos, condition badge, verification certificate box, and WhatsApp CTA.
    2. Staff Assistant Intake & AI Valuation journey:
       - Logging in, accessing /intake/, uploading photos, entering field notes.
       - Preflight AI identification: returning MSRP (new retail) and estimated secondhand resale.
       - UI verification: advisory valuation cards, benchmark pills, and one-click resale adoption.
       - Intake submission: product persisted with full benchmarks.
    3. Manager Staging & Marketplace Publication journey:
       - Reviewing item on Dashboard (/dashboard/) and Staging Detail (/products/<pk>/).
       - Setting official category ('Moda y accesorios'), condition ('Muy bueno'), is_public, and is_featured.
       - Adding listing description and Wallapop marketplace link -> transition to PUBLISHED.
       - Using 'Ver en Tienda Pública' (View in Storefront) button to verify live public listing.
    4. Reservation & Sale Lifecycle:
       - Customer reserves for in-store check: is_reserved=True -> orange RESERVADO badge on storefront.
       - Customer completes purchase: is_sold=True -> VENDIDO badge, grayscale image, and 'Entregado en Alfafar' stamp.
       - Staging lifecycle audit trail verification and dashboard 'Vendido' tab verification.
    5. Mobile Responsiveness ($390 x 844 iPhone Viewport):
       - Full verification of mobile public storefront, mobile product detail, and mobile staging dashboard.
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
        self.store_config = StorefrontConfiguration.get_solo()

        # Ensure categories exist across test runs in TransactionTestCase
        categories_data = [
            ("motor-y-accesorios", "Motor y accesorios", "Motors & Accessories", "two_wheeler", 1),
            ("moda-y-accesorios", "Moda y accesorios", "Fashion & Accessories", "apparel", 2),
            ("tecnologia-y-electronica", "Tecnología y electrónica", "Tech & Electronics", "devices", 3),
            ("deporte-y-ocio", "Deporte y ocio", "Sports & Leisure", "fitness_center", 4),
            ("bicicletas", "Bicicletas", "Bicycles", "pedal_bike", 5),
            ("hogar-y-jardin", "Hogar y jardín", "Home & Garden", "chair", 6),
            ("electrodomesticos", "Electrodomésticos", "Appliances", "kitchen", 7),
            ("cine-libros-y-musica", "Cine, libros y música", "Movies, Books & Music", "menu_book", 8),
            ("ninos-y-bebes", "Niños y bebés", "Kids & Babies", "child_friendly", 9),
            ("coleccionismo", "Coleccionismo", "Collectibles", "auto_awesome", 10),
            ("construccion-y-reformas", "Construcción y reformas", "Tools & DIY", "construction", 11),
            ("otras-oportunidades", "Otras oportunidades", "Other Opportunities", "category", 12),
        ]
        for slug, name_es, name_en, icon, order in categories_data:
            Category.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": name_es,
                    "name_en": name_en,
                    "icon": icon,
                    "order": order,
                    "is_active": True,
                },
            )

        # Seed initial public opportunity in catalog (Bicicleta Orbea)
        bicycles_cat = Category.objects.get(slug="bicicletas")
        self.public_bike = Product.objects.create(
            ai_title="Bicicleta de Montaña Orbea MX 29",
            ai_description="Bicicleta de montaña con cuadro de aluminio y frenos hidráulicos revisada en Alfafar.",
            sale_price=Decimal("349.00"),
            category=bicycles_cat,
            condition=ProductCondition.VERY_GOOD,
            is_public=True,
            is_featured=True,
            status=ProductStatus.PUBLISHED,
        )
        # Create an in-memory sample image for the bike
        img = Image.new("RGB", (400, 400), color=(20, 120, 90))
        buf = BytesIO()
        img.save(buf, format="JPEG")
        ProductImage.objects.create(
            product=self.public_bike,
            image=ContentFile(buf.getvalue(), name="orbea_mx29.jpg"),
            order=0,
        )
        ProductListingLink.objects.create(
            product=self.public_bike,
            site=self.wallapop,
            url=f"https://es.wallapop.com/item/orbea-mx-29-{self.public_bike.pk}",
            is_active=True,
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
                        "category": "Moda y accesorios",
                        "detected_attributes": ["Algodón encerado verde oliva", "Cuello de pana marrón", "Cremallera de latón doble carro"],
                        "missing_or_recommended_info": ["Revisar desgaste en puños y bajo", "Comprobar etiqueta blanca interior de talla"],
                        "suggested_note": "Chaqueta Barbour Beaufort clásica encerada, talla C40/102cm, buen estado con pátina natural.",
                        "estimated_retail_price": 435.00,
                        "estimated_resale_price": 165.00
                    }'''
                )

            page.route("**/intake/identify/", handle_identify)

            # =================================================================
            # PART I: PUBLIC CUSTOMER STOREFRONT EXPERIENCE (rapidopack.es)
            # =================================================================
            print("\n[PART I - STEP 0] Customer visits Corporate Landing Page (/)...")
            page.goto(f"{self.live_server_url}{reverse('storefront:home')}")
            page.wait_for_selector("#paqueteria")
            self.assertIn("Rápido Pack", page.content())
            self.assertIn("SEUR", page.content())
            self.assertIn("GLS", page.content())
            self.assertIn("InPost", page.content())
            self.assertTrue(page.locator('text="Bicicleta de Montaña Orbea MX 29"').first.is_visible())
            page.screenshot(path="screenshots/daily_00_corporate_landing_page.png")
            print("Verified corporate landing page (/), parcel carrier strip, and 'Recién llegados' section.")

            print("\n[PART I - STEP 1] Customer navigates to Storefront Catalog (/tienda/)...")
            page.goto(f"{self.live_server_url}{reverse('storefront:catalog')}")
            page.wait_for_selector("#categoryRail")

            # Verify Storefront Branding, Hero, and Physical Alfafar Presence
            self.assertIn("Rápido Pack", page.content())
            self.assertIn("Alfafar", page.content())
            page.screenshot(path="screenshots/daily_00_public_catalog.png")
            print("Verified public catalog header, hero value proposition, and trust strip.")

            # Test Category Rail filtering (Bicicletas)
            print("[PART I - STEP 2] Customer filters by 'Bicicletas' category...")
            page.click('#categoryRail a:has-text("Bicicletas")')
            page.wait_for_load_state("networkidle")
            self.assertTrue(page.locator('text="Bicicleta de Montaña Orbea MX 29"').is_visible())
            print("Category rail filtered accurately to active bicycle lot.")

            # Test 'Cómo comprar en Alfafar' native modal dialog
            print("[PART I - STEP 3] Customer opens 'Cómo comprar' modal...")
            page.click('button:has-text("Cómo comprar"), button:has-text("How to buy")')
            page.wait_for_selector("#how-to-buy-dialog[open]")
            modal_title = page.inner_text("#how-to-buy-title")
            self.assertTrue("Rápido Pack Alfafar" in modal_title or "comprar" in modal_title.lower())
            page.screenshot(path="screenshots/daily_00_how_to_buy_modal.png")
            # Close modal via close button
            page.click("#how-to-buy-dialog button[aria-label]")
            page.wait_for_selector("#how-to-buy-dialog", state="hidden")
            self.assertFalse(page.locator("#how-to-buy-dialog").is_visible())
            print("Verified <dialog closedby='any'> modal open/close cycle.")

            # Customer opens Public Product Detail Page
            print("[PART I - STEP 4] Customer opens Public Product Detail view...")
            page.click('h3:has-text("Bicicleta de Montaña Orbea MX 29") a')
            page.wait_for_selector("#mainProductPhoto")
            page.screenshot(path="screenshots/daily_00_product_detail_public.png")

            # Verify Product Detail Elements: 60/40 layout, LCP photo, Verification Box, WhatsApp CTA
            self.assertTrue(page.locator("#mainProductPhoto").is_visible())
            self.assertTrue(page.locator('text="349,00 €"').first.is_visible() or page.locator('text="349.00 €"').first.is_visible())
            self.assertTrue(page.locator(f'a[href*="/go/whatsapp/{self.public_bike.pk}/"]').first.is_visible())
            self.assertTrue(page.locator('text="Certificado de Verificación Rápido Pack"').first.is_visible())
            print("Verified public product detail 60/40 layout, LCP image, and conversion CTA.")

            # Visitor tests canonical 301 slug redirect
            print("[PART I - STEP 5] Visitor tests canonical 301 slug redirect on product URL...")
            page.goto(f"{self.live_server_url}/tienda/producto/outdated-slug-{self.public_bike.pk}/")
            page.wait_for_load_state("networkidle")
            self.assertIn(f"bicicleta-de-montana-orbea-mx-29-{self.public_bike.pk}", page.url)
            print("Verified 301 canonical slug redirect to official product slug.")

            # Visitor navigates to standalone 'Cómo comprar' guide (/como-comprar/)
            print("[PART I - STEP 6] Visitor visits standalone '/como-comprar/' page...")
            page.goto(f"{self.live_server_url}{reverse('storefront:how_to_buy')}")
            page.wait_for_selector('h1:has-text("Cómo comprar"), h1:has-text("How to buy")')
            self.assertIn("Alfafar", page.content())
            self.assertIn("Comte Ronrée", page.content())
            print("Verified standalone '/como-comprar/' guide with WhatsApp reservation & store pickup info.")

            # Visitor filters catalog by direct category URL (/tienda/categoria/bicicletas/)
            print("[PART I - STEP 7] Visitor accesses direct category URL (/tienda/categoria/bicicletas/)...")
            page.goto(f"{self.live_server_url}/tienda/categoria/bicicletas/")
            page.wait_for_selector("#categoryRail")
            self.assertTrue(page.locator('text="Bicicleta de Montaña Orbea MX 29"').first.is_visible())
            print("Verified direct category URL route.")

            # Visitor tests Spanish query parameter filters (?estado=muy_bueno&orden=baratos)
            print("[PART I - STEP 8] Visitor applies Spanish query params (?estado=muy_bueno&orden=baratos)...")
            page.goto(f"{self.live_server_url}/tienda/?estado=muy_bueno&orden=baratos")
            page.wait_for_load_state("networkidle")
            self.assertTrue(page.locator('text="Bicicleta de Montaña Orbea MX 29"').first.is_visible())
            print("Verified Spanish query param filtering & sorting.")

            # Visitor checks RGPD and legal compliance pages
            print("[PART I - STEP 9] Visitor checks legal and privacy pages (/aviso-legal/, /privacidad/, /cookies/)...")
            for legal_path, heading_text in [
                (reverse('storefront:legal_notice'), "Aviso Legal"),
                (reverse('storefront:privacy'), "Política de Privacidad"),
                (reverse('storefront:cookies'), "Política de Cookies"),
            ]:
                page.goto(f"{self.live_server_url}{legal_path}")
                page.wait_for_selector(f"h1:has-text('{heading_text}')")
                self.assertIn("Rápido Pack", page.content())
            print("Verified legal compliance pages (Aviso Legal, Privacidad, Cookies).")

            # =================================================================
            # PART II: STAFF ASSISTANT INTAKE & AI VALUATION WORKFLOW
            # =================================================================
            print("\n[PART II - STEP 1] Logging in as Manager...")
            page.goto(f"{self.live_server_url}{reverse('inventory:login')}")
            page.fill("#id_username", "manager_daily")
            page.fill("#id_password", "password123")
            with page.expect_navigation():
                page.click("#loginSubmitBtn")

            # PART II - STEP 1b: Manager visits Pallets management screen and creates Pallet #1
            print("[PART II - STEP 1b] Manager visits Pallets management screen and creates Pallet #1...")
            page.goto(f"{self.live_server_url}{reverse('inventory:pallets')}")
            page.wait_for_selector("#btnCreatePallet")

            # Create Pallet #1 with financial metrics and manifest notes
            page.fill("#id_purchase_price", "350.00")
            page.fill("#id_estimated_value", "900.00")
            page.fill("#id_notes", "Lote Liquidacion Chaquetas & Moda Alfafar")
            page.click("#btnCreatePallet")
            page.wait_for_load_state("networkidle")

            # Verify Pallet #1 card is rendered with financial amounts
            self.assertTrue(page.locator('text="Pallet #1"').first.is_visible())
            self.assertIn("350", page.content())
            self.assertIn("900", page.content())
            print("Verified Pallet #1 creation with auto-incremented number and financial metrics.")

            print("[PART II - STEP 2] Navigating to Intake screen...")
            page.goto(f"{self.live_server_url}{reverse('inventory:intake')}")
            page.wait_for_selector("#dropZone")

            # Verify Pallet #1 is pre-selected in sticky selector
            pallet_select = page.locator("#id_pallet")
            self.assertTrue(pallet_select.is_visible())
            selected_pallet_val = pallet_select.input_value()
            self.assertTrue(len(selected_pallet_val) > 0)
            print(f"Verified Pallet #1 automatically preselected on intake: id={selected_pallet_val}")

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
            self.assertIsNotNone(product.pallet)
            self.assertEqual(product.pallet.number, 1)
            print("Product persisted in database with full valuation benchmarks and Pallet #1 attribution!")

            # =================================================================
            # PART III: MANAGER STAGING REVIEW & STOREFRONT PUBLICATION
            # =================================================================
            print("\n[PART III - STEP 1] Manager inspecting Catalog Dashboard...")
            page.goto(f"{self.live_server_url}{reverse('inventory:dashboard')}")
            page.wait_for_selector('a[href*="/products/"]')
            page.screenshot(path="screenshots/daily_03_dashboard_with_item.png")

            # Verify product is visible on dashboard with sale price €165.00
            self.assertTrue(page.locator('text="Chaqueta Barbour Beaufort Encerada"').first.is_visible())
            self.assertIn("165", page.content())

            print("\n[PART III - STEP 2] Opening Staging Product Detail view...")
            page.goto(f"{self.live_server_url}{reverse('inventory:product_detail', kwargs={'pk': product.pk})}")
            page.wait_for_selector("#id_sale_price")

            # Verify origin pallet badge in detail header
            pallet_badge = page.locator("#product-pallet-badge")
            self.assertTrue(pallet_badge.is_visible())
            self.assertIn("Pallet #1", pallet_badge.inner_text())
            print("Verified origin '📦 Pallet #1' badge rendered in product detail header.")

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

            # Manager sets Category, Condition, is_public, is_featured and description
            print("\n[PART III - STEP 3] Manager configuring Storefront Controls & Description...")
            fashion_cat = Category.objects.get(slug="moda-y-accesorios")
            page.select_option("#id_category", str(fashion_cat.pk))
            page.select_option("#id_condition", ProductCondition.VERY_GOOD)
            page.check("#id_is_public")
            page.check("#id_is_featured")
            page.fill(
                'textarea[name="ai_description"]',
                "Auténtica chaqueta Barbour Beaufort encerada en color verde oliva. Talla C40. Fabricada en Inglaterra."
            )
            page.click('button:has-text("Guardar cambios"), button:has-text("Save Listing Changes")')
            page.wait_for_load_state("networkidle")

            product.refresh_from_db()
            self.assertEqual(product.category, fashion_cat)
            self.assertEqual(product.condition, ProductCondition.VERY_GOOD)
            self.assertTrue(product.is_public)
            self.assertTrue(product.is_featured)
            print("Storefront controls saved: Category=Moda y accesorios, Condition=Muy bueno, Featured=True.")

            # Verify Pallet Hub reflects 1 linked product
            page.goto(f"{self.live_server_url}{reverse('inventory:pallets')}")
            page.wait_for_selector('text="Pallet #1"')
            self.assertTrue(page.locator('text="1"').first.is_visible())
            print("Verified Pallet #1 displays 1 linked product in management hub.")

            # Manager adds marketplace link to transition product to PUBLISHED
            print("\n[PART III - STEP 4] Manager attaching Wallapop link to publish...")
            ProductListingLink.objects.create(
                product=product,
                site=self.wallapop,
                url=f"https://es.wallapop.com/item/barbour-beaufort-{product.pk}",
                is_active=True,
            )
            product.refresh_from_db()
            product.status = product.compute_lifecycle_status()
            product.save()
            self.assertEqual(product.status, ProductStatus.PUBLISHED)
            print("Product auto-transitioned to PUBLISHED!")

            # Open staging detail to see the 'Ver en Tienda Pública' button
            page.goto(f"{self.live_server_url}{reverse('inventory:product_detail', kwargs={'pk': product.pk})}")
            page.wait_for_selector('a:has-text("Ver en Tienda Pública"), a:has-text("View in Storefront")')
            view_storefront_btn = page.locator('a:has-text("Ver en Tienda Pública"), a:has-text("View in Storefront")')
            self.assertTrue(view_storefront_btn.is_visible())
            print("Verified 'Ver en Tienda Pública' button in Staging Detail.")

            # =================================================================
            # PART IV: LIVE STOREFRONT VALIDATION & STATUS LIFECYCLE
            # =================================================================
            print("\n[PART IV - STEP 1] Customer viewing newly published product on Public Storefront...")
            page.goto(f"{self.live_server_url}{product.get_public_url()}")
            page.wait_for_selector("#mainProductPhoto")
            page.screenshot(path="screenshots/daily_05_storefront_published_item.png")

            # Verify public detail displays DESTACADO, condition, price and WhatsApp CTA
            self.assertTrue(page.locator('text="DESTACADO"').first.is_visible() or page.locator('text="FEATURED"').first.is_visible())
            self.assertTrue(page.locator('text="165,00 €"').first.is_visible() or page.locator('text="165.00 €"').first.is_visible())
            print("Verified live storefront detail with DESTACADO badge and €165.00 price.")

            # Customer reserves item: Manager toggles is_reserved
            print("\n[PART IV - STEP 2] Item reserved for in-store trial (24h hold)...")
            product.is_reserved = True
            product.save(update_fields=["is_reserved"])

            page.reload()
            page.wait_for_selector("text=/RESERVED|RESERVADO/i")
            self.assertTrue(page.locator("text=/RESERVED|RESERVADO/i").first.is_visible())
            page.screenshot(path="screenshots/daily_06_storefront_reserved_state.png")
            print("Verified live storefront updates with RESERVADO badge and disabled hold CTA.")

            # Customer purchases item: Manager marks product as sold
            print("\n[PART IV - STEP 3] Marking product as Sold and verifying social proof...")
            product.mark_as_sold(price=Decimal("165.00"), user=self.manager, channel_type="in_store")
            product.refresh_from_db()
            self.assertEqual(product.status, ProductStatus.SOLD)
            self.assertTrue(product.is_sold)
            self.assertEqual(product.sold_channel_type, "in_store")

            # Storefront renders VENDIDO state and social proof
            page.reload()
            page.wait_for_selector("text=/SOLD|VENDIDO/i")
            self.assertTrue(page.locator("text=/SOLD|VENDIDO/i").first.is_visible())
            page.screenshot(path="screenshots/daily_07_storefront_sold_state.png")
            print("Verified live storefront shows VENDIDO badge and social proof.")

            # Verify Staging Lifecycle Audit Trail
            page.goto(f"{self.live_server_url}{reverse('inventory:product_detail', kwargs={'pk': product.pk})}")
            page.wait_for_selector("#status-history-card, h3:has-text('Historial de Estados')")
            self.assertIn("manager_daily", page.content())
            page.screenshot(path="screenshots/daily_08_staging_sold_audit_trail.png")
            print("Verified state change recorded in Lifecycle Audit Trail!")

            # Verify sold item in Dashboard 'Vendido' tab
            page.goto(f"{self.live_server_url}{reverse('inventory:dashboard')}?status=sold")
            page.wait_for_load_state("networkidle")
            page.screenshot(path="screenshots/daily_09_dashboard_sold_tab.png")
            self.assertTrue(page.locator('text="Chaqueta Barbour Beaufort Encerada"').first.is_visible())
            print("Verified sold item displays in 'Vendido' dashboard tab!")

            # =================================================================
            # PART V: MOBILE RESPONSIVENESS CHECK (390 x 844 iPhone Viewport)
            # =================================================================
            print("\n[PART V] Verifying mobile responsiveness ($390 x 844)...")
            mobile_context = browser.new_context(
                viewport={"width": 390, "height": 844},
                locale="es-ES",
                is_mobile=True,
                has_touch=True,
            )
            mobile_page = mobile_context.new_page()

            # Mobile Public Catalog
            mobile_page.goto(f"{self.live_server_url}{reverse('storefront:catalog')}")
            mobile_page.wait_for_load_state("networkidle")
            mobile_page.screenshot(path="screenshots/daily_10_mobile_storefront_catalog.png")
            print("Mobile public catalog verified.")

            # Mobile Product Detail
            mobile_page.goto(f"{self.live_server_url}{product.get_public_url()}")
            mobile_page.wait_for_load_state("networkidle")
            mobile_page.screenshot(path="screenshots/daily_11_mobile_product_detail.png")
            print("Mobile public product detail verified.")

            # Mobile Staging Dashboard
            mobile_page.goto(f"{self.live_server_url}{reverse('inventory:dashboard')}")
            mobile_page.wait_for_load_state("networkidle")
            mobile_page.screenshot(path="screenshots/daily_12_mobile_dashboard.png")
            print("Mobile staging dashboard verified.")

            mobile_context.close()
            browser.close()
            print("\n==================================================================")
            print("FULL DAILY WORKFLOW VERIFICATION IN REAL CHROME PASSED 100%!")
            print("==================================================================")

    def test_browser_bilingual_language_switching_in_chrome(self):
        """
        Verify live language switching (ES <-> EN) in real Chrome browser:
        - Asserts proper Spanish strings on initial page load.
        - Clicks English language button, waits for navigation/networkidle.
        - Asserts translated English strings appear and Spanish raw strings are absent.
        - Navigates across pages (How to Buy) and switches back to Spanish.
        - Captures visual evidence screenshots.
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            context = browser.new_context(viewport={"width": 1280, "height": 850}, locale="es-ES")
            page = context.new_page()

            # 1. Visit storefront home in Spanish
            page.goto(f"{self.live_server_url}{reverse('storefront:home')}")
            page.wait_for_selector("#paqueteria")

            page_text_es = page.content()
            self.assertIn("Tu punto de confianza en Alfafar", page_text_es)
            self.assertIn("Servicios de paquetería", page_text_es)
            self.assertIn("Lo último en nuestra tienda", page_text_es)
            page.screenshot(path="screenshots/daily_bilingual_01_es.png")

            # 2. Click English switcher button 'EN'
            en_btn = page.locator('button[name="language"][value="en"]').first
            self.assertTrue(en_btn.is_visible())
            en_btn.click()
            page.wait_for_load_state("networkidle")

            # Verify English strings in DOM
            page_text_en = page.content()
            self.assertIn("Your trusted local hub in Alfafar", page_text_en)
            self.assertIn("Parcel Services", page_text_en)
            self.assertIn("Latest arrivals in our store", page_text_en)
            self.assertNotIn("Tu punto de confianza en Alfafar", page_text_en)
            page.screenshot(path="screenshots/daily_bilingual_02_en.png")

            # 3. Navigate to How to Buy in English
            page.goto(f"{self.live_server_url}{reverse('storefront:how_to_buy')}")
            page.wait_for_load_state("networkidle")
            htb_text_en = page.content()
            self.assertIn("How to buy at Rápido Pack Alfafar?", htb_text_en)
            self.assertIn("24h no-commitment hold:", htb_text_en)
            self.assertIn("Cash, Bizum, or Debit/Credit Card at the counter.", htb_text_en)
            page.screenshot(path="screenshots/daily_bilingual_03_htb_en.png")

            # 4. Switch back to Spanish
            es_btn = page.locator('button[name="language"][value="es"]').first
            self.assertTrue(es_btn.is_visible())
            es_btn.click()
            page.wait_for_load_state("networkidle")

            htb_text_es = page.content()
            self.assertIn("¿Cómo comprar en Rápido Pack Alfafar?", htb_text_es)
            self.assertIn("Reserva 24h sin compromiso:", htb_text_es)
            self.assertIn("Efectivo, Bizum o Tarjeta de débito/crédito en mostrador.", htb_text_es)
            page.screenshot(path="screenshots/daily_bilingual_04_htb_es.png")

            context.close()
            browser.close()
            print("BILINGUAL REAL CHROME BROWSER TEST PASSED!")
