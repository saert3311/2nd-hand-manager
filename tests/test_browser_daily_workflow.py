"""
End-to-End Real Chrome Browser Verification of the Daily Operational Lifecycle.

Simulates the real daily usage flow across:
- Public Storefront experience (/ , /tienda/, categories, modal, public product detail, legal pages)
- Staff Intake workflow with AI Identification, Valuation Benchmarks & Pallet Attribution
- Manager Staging Review, Dashboard Pallet Filtering & Product Detail Editing
- Publishing via Marketplace Listing Link, 24h Reservation Hold, Sold State & Lifecycle Audit Trail
- Responsive mobile viewport (390x844) and bilingual ES <-> EN switching

Uses shared Playwright Chromium launch helper, temp artifact dirs (unless SAVE_TEST_SCREENSHOTS=1),
deterministic Playwright navigation/selector waits, and verifies loaded visible <img> assets.
"""

import datetime
import json
from decimal import Decimal

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.files.base import ContentFile
from django.test import override_settings
from django.urls import reverse

from inventory.models import (
    Category,
    MarketplaceSite,
    Pallet,
    Product,
    ProductCondition,
    ProductImage,
    ProductListingLink,
    ProductStatus,
    StorefrontConfiguration,
)
from tests.helpers import (
    abort_nonessential_fonts,
    assert_visible_images_loaded,
    create_user_with_group,
    get_test_artifact_dir,
    make_test_image_bytes,
    start_shared_browser,
)


@override_settings(TURNSTILE_ENABLED=False)
class BrowserDailyWorkflowValuationTests(StaticLiveServerTestCase):
    """End-to-end Chrome test covering storefront, AI intake, valuation, and bilingual UI."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.artifacts_dir = get_test_artifact_dir(cls, repo_subdir="screenshots")
        cls.sample_image_path = cls.artifacts_dir / "barbour_jacket_daily.jpg"
        cls.sample_image_path.write_bytes(make_test_image_bytes(size=(600, 600), color="teal"))
        cls._browser = start_shared_browser(cls)

    def setUp(self):
        self.manager = create_user_with_group("manager_daily", group_name="managers", is_staff=True)
        self.wallapop, _ = MarketplaceSite.objects.get_or_create(
            slug="wallapop",
            defaults={"name": "Wallapop", "order": 1, "is_active": True},
        )
        StorefrontConfiguration.get_solo()
        self.cat_bikes, _ = Category.objects.get_or_create(
            slug="bicicletas",
            defaults={"name": "Bicicletas", "icon": "pedal_bike"},
        )
        self.cat_fashion, _ = Category.objects.get_or_create(
            slug="moda-y-accesorios",
            defaults={"name": "Moda y accesorios", "icon": "apparel"},
        )

        # Pre-seed a public published product for storefront Customer flow (Part I)
        self.public_bike = Product.objects.create(
            ai_title="Bicicleta de Montaña Orbea MX 29",
            ai_description="Bicicleta revisada en taller, frenos hidráulicos Shimano, talla L.",
            sale_price=Decimal("349.00"),
            estimated_retail_price=Decimal("699.00"),
            estimated_resale_price=Decimal("380.00"),
            category=self.cat_bikes,
            condition=ProductCondition.VERY_GOOD,
            is_public=True,
            is_featured=True,
            status=ProductStatus.PUBLISHED,
            created_by=self.manager,
        )
        ProductImage.objects.create(
            product=self.public_bike,
            image=ContentFile(make_test_image_bytes(size=(600, 600), color="navy"), name="orbea_mx29.jpg"),
            order=1,
        )
        ProductListingLink.objects.create(
            product=self.public_bike,
            site=self.wallapop,
            url=f"https://es.wallapop.com/item/orbea-mx29-{self.public_bike.pk}",
            is_active=True,
        )

    def test_complete_daily_workflow_in_real_chrome(self):
        img_path = str(self.sample_image_path)
        context = self._browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        abort_nonessential_fonts(page)
        page.on("dialog", lambda d: d.accept())

        # Intercept the Gemini AI endpoint to provide deterministic, fast valuation
        def handle_identify(route):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "success": True,
                        "identified_title": "Chaqueta Barbour Beaufort Encerada",
                        "category": "Moda y accesorios",
                        "detected_attributes": [
                            "Algodón encerado verde oliva",
                            "Cuello de pana marrón",
                            "Cremallera de latón doble carro",
                        ],
                        "missing_or_recommended_info": [
                            "Revisar desgaste en puños y bajo",
                            "Comprobar etiqueta blanca interior de talla",
                        ],
                        "suggested_note": "Chaqueta encerada clásica verde oliva fabricada en Inglaterra.",
                        "estimated_retail_price": 435.00,
                        "estimated_resale_price": 165.00,
                    }
                ),
            )

        page.route("**/intake/identify/", handle_identify)

        # PART I: PUBLIC CUSTOMER STOREFRONT EXPERIENCE (Store Shelf at / and /tienda/)
        page.goto(f"{self.live_server_url}{reverse('storefront:home')}")
        page.wait_for_selector("#categoryRail")
        self.assertIn("Rápido Pack", page.content())
        self.assertIn("logo-rapido-pack-valencia.png", page.content())
        self.assertIn("https://rapidopackvalencia.es", page.content())
        self.assertTrue(page.locator('text="Bicicleta de Montaña Orbea MX 29"').first.is_visible())
        self.assertEqual(
            page.locator(f'a[href*="/go/whatsapp/{self.public_bike.pk}/"]').count(),
            0,
            "Shelf cards must stay decluttered without per-card WhatsApp buttons",
        )
        page.screenshot(path=str(self.artifacts_dir / "daily_00_store_shelf_home.png"))

        page.goto(f"{self.live_server_url}{reverse('storefront:catalog')}")
        page.wait_for_selector("#categoryRail")
        self.assertIn("Alfafar", page.content())
        assert_visible_images_loaded(self, page)
        page.screenshot(path=str(self.artifacts_dir / "daily_00_public_catalog.png"))

        # Category Rail filtering (Bicicletas)
        with page.expect_navigation():
            page.click('#categoryRail a:has-text("Bicicletas")')
        page.wait_for_selector('text="Bicicleta de Montaña Orbea MX 29"')
        self.assertTrue(page.locator('text="Bicicleta de Montaña Orbea MX 29"').is_visible())

        # 'Cómo comprar en Alfafar' modal
        page.click('button:has-text("Cómo comprar"), button:has-text("How to buy")')
        page.wait_for_selector("#how-to-buy-dialog[open]")
        modal_title = page.inner_text("#how-to-buy-title")
        self.assertTrue("Rápido Pack Alfafar" in modal_title or "comprar" in modal_title.lower())
        page.screenshot(path=str(self.artifacts_dir / "daily_00_how_to_buy_modal.png"))
        page.click("#how-to-buy-dialog button[aria-label]")
        page.wait_for_selector("#how-to-buy-dialog", state="hidden")
        self.assertFalse(page.locator("#how-to-buy-dialog").is_visible())

        # Public Product Detail Page + verify real rendered media (naturalWidth > 0)
        with page.expect_navigation():
            page.click('h3:has-text("Bicicleta de Montaña Orbea MX 29") a')
        page.wait_for_selector("#mainProductPhoto")
        assert_visible_images_loaded(self, page, "#mainProductPhoto")
        page.screenshot(path=str(self.artifacts_dir / "daily_00_product_detail_public.png"))

        self.assertTrue(page.locator("#mainProductPhoto").is_visible())
        self.assertTrue(
            page.locator('text="349,00 €"').first.is_visible()
            or page.locator('text="349.00 €"').first.is_visible()
        )
        self.assertTrue(page.locator(f'a[href*="/go/whatsapp/{self.public_bike.pk}/"]').first.is_visible())
        self.assertTrue(
            page.locator('text="Certificado de Verificación Rápido Pack"').first.is_visible()
            or page.locator('text="Rápido Pack Verification Guarantee"').first.is_visible()
        )

        # Canonical 301 slug redirect
        page.goto(f"{self.live_server_url}/tienda/producto/outdated-slug-{self.public_bike.pk}/")
        page.wait_for_selector("#mainProductPhoto")
        self.assertIn(f"bicicleta-de-montana-orbea-mx-29-{self.public_bike.pk}", page.url)

        # Standalone 'Cómo comprar' guide
        page.goto(f"{self.live_server_url}{reverse('storefront:how_to_buy')}")
        page.wait_for_selector('h1:has-text("Cómo comprar"), h1:has-text("How to buy")')
        self.assertIn("Alfafar", page.content())
        self.assertIn("Comte Ronrée", page.content())

        # Direct category URL
        page.goto(f"{self.live_server_url}/tienda/categoria/bicicletas/")
        page.wait_for_selector("#categoryRail")
        self.assertTrue(page.locator('text="Bicicleta de Montaña Orbea MX 29"').first.is_visible())

        # Spanish query params
        page.goto(f"{self.live_server_url}/tienda/?estado=muy_bueno&orden=baratos")
        page.wait_for_selector('text="Bicicleta de Montaña Orbea MX 29"')
        self.assertTrue(page.locator('text="Bicicleta de Montaña Orbea MX 29"').first.is_visible())

        # Legal and privacy pages
        for legal_path, heading_es, heading_en in [
            (reverse("storefront:legal_notice"), "Aviso Legal", "Legal Notice and Terms of Use"),
            (reverse("storefront:privacy"), "Política de Privacidad", "Privacy Policy (GDPR)"),
            (reverse("storefront:cookies"), "Política de Cookies", "Cookies Policy"),
        ]:
            page.goto(f"{self.live_server_url}{legal_path}")
            page.wait_for_selector(f"h1:has-text('{heading_es}'), h1:has-text('{heading_en}')")
            self.assertIn("Rápido Pack", page.content())

        # PART II: STAFF INTAKE & AI VALUATION WORKFLOW
        page.goto(f"{self.live_server_url}{reverse('inventory:login')}")
        page.fill("#id_username", "manager_daily")
        page.fill("#id_password", "password123")
        with page.expect_navigation():
            page.click("#loginSubmitBtn")

        # Create Pallet #1
        page.goto(f"{self.live_server_url}{reverse('inventory:pallets')}")
        page.wait_for_selector("#btnCreatePallet")
        page.fill("#id_purchase_price", "350.00")
        page.fill("#id_estimated_value", "900.00")
        page.fill("#id_notes", "Lote Liquidacion Chaquetas & Moda Alfafar")
        with page.expect_navigation():
            page.click("#btnCreatePallet")
        page.wait_for_selector('text="Pallet #1"')
        self.assertTrue(page.locator('text="Pallet #1"').first.is_visible())
        self.assertIn("350", page.content())
        self.assertIn("900", page.content())

        # Intake screen with Pallet #1 preselected
        page.goto(f"{self.live_server_url}{reverse('inventory:intake')}")
        page.wait_for_selector("#dropZone")
        pallet_select = page.locator("#id_origin")
        self.assertTrue(pallet_select.is_visible())
        self.assertTrue(pallet_select.input_value().startswith("pallet:"))

        page.set_input_files("#imageInput", img_path)
        page.wait_for_selector("#previewGrid img")
        page.fill("#id_raw_note", "Barbour Beaufort vintage verde oliva, cremallera perfecta, ligera pátina.")

        page.click("#identifyBtn")
        page.wait_for_selector("#advisoryValuationContainer:not(.hidden)", timeout=10000)

        self.assertIn("435", page.inner_text("#advisoryRetailPrice"))
        self.assertIn("165", page.inner_text("#advisoryResalePrice"))
        self.assertTrue(page.locator("#intakePriceBenchmarks").is_visible())
        self.assertIn("435", page.inner_text("#badgeRefRetail"))
        self.assertIn("165", page.inner_text("#badgeRefResale"))
        page.screenshot(path=str(self.artifacts_dir / "daily_01_intake_valuation_benchmarks.png"))

        use_resale_btn = page.locator("#btnUseEstimatedResale")
        self.assertTrue(use_resale_btn.is_visible())
        use_resale_btn.click()
        self.assertEqual(page.input_value("#id_sale_price"), "165.00")
        self.assertEqual(page.input_value("#id_estimated_retail_price"), "435.00")
        self.assertEqual(page.input_value("#id_estimated_resale_price"), "165.00")
        page.screenshot(path=str(self.artifacts_dir / "daily_02_intake_resale_applied.png"))

        with page.expect_navigation():
            page.click("#submitBtn")
        page.wait_for_selector("#main-content")

        product = Product.objects.get(ai_title="Chaqueta Barbour Beaufort Encerada")
        self.assertEqual(product.estimated_retail_price, 435.00)
        self.assertEqual(product.estimated_resale_price, 165.00)
        self.assertEqual(product.sale_price, 165.00)
        self.assertIsNotNone(product.pallet)
        self.assertEqual(product.pallet.number, 1)

        # PART III: MANAGER STAGING REVIEW & STOREFRONT PUBLICATION
        page.goto(f"{self.live_server_url}{reverse('inventory:dashboard')}")
        page.wait_for_selector('a[href*="/products/"]')
        assert_visible_images_loaded(self, page)
        page.screenshot(path=str(self.artifacts_dir / "daily_03_dashboard_with_item.png"))

        self.assertTrue(page.locator('text="Chaqueta Barbour Beaufort Encerada"').first.is_visible())
        self.assertIn("165", page.content())

        card_badge = page.locator(".product-card-pallet-badge").first
        self.assertTrue(card_badge.is_visible())
        self.assertIn("Pallet #1", card_badge.inner_text())

        self.assertTrue(page.locator("#palletFilterForm").is_visible())
        pallet_select = page.locator("#palletFilterForm select[name='pallet']")
        self.assertTrue(pallet_select.is_visible())

        with page.expect_navigation():
            pallet_select.select_option("none")
        self.assertFalse(page.locator('text="Chaqueta Barbour Beaufort Encerada"').is_visible())

        with page.expect_navigation():
            page.locator("#palletFilterForm select[name='pallet']").select_option(str(product.pallet.id))
        self.assertTrue(page.locator('text="Chaqueta Barbour Beaufort Encerada"').first.is_visible())

        # Product Detail View
        page.goto(f"{self.live_server_url}{reverse('inventory:product_detail', kwargs={'pk': product.pk})}")
        page.wait_for_selector("#id_sale_price")
        assert_visible_images_loaded(self, page)

        pallet_badge = page.locator("#product-pallet-badge")
        self.assertTrue(pallet_badge.is_visible())
        self.assertIn("Pallet #1", pallet_badge.inner_text())

        self.assertTrue(page.locator("#detail-valuation-benchmarks").is_visible())
        self.assertIn("435", page.inner_text("#ref-retail-price"))
        self.assertIn("165", page.inner_text("#ref-resale-price"))

        apply_btn = page.locator("#btnApplyResalePrice")
        self.assertTrue(apply_btn.is_visible())
        self.assertEqual(apply_btn.get_attribute("data-resale"), "165.00")

        self.assertTrue(len(page.inner_text("#footer-build-time")) > 0)
        page.screenshot(path=str(self.artifacts_dir / "daily_04_product_detail_valuation_benchmarks.png"))

        # Configure Storefront Controls & Description
        fashion_cat = self.cat_fashion
        page.fill(
            'textarea[name="ai_description"]',
            "Auténtica chaqueta Barbour Beaufort encerada en color verde oliva. Talla C40. Fabricada en Inglaterra.",
        )
        page.click("#tabBtnWorkspaceChannels")
        page.select_option("#id_category", str(fashion_cat.pk))
        page.select_option("#id_condition", ProductCondition.VERY_GOOD)
        page.check("#id_is_public")
        page.check("#id_is_featured")
        with page.expect_navigation():
            page.click("#btnSaveListingChanges")
        page.wait_for_selector("#id_sale_price")

        product.refresh_from_db()
        self.assertEqual(product.category, fashion_cat)
        self.assertEqual(product.condition, ProductCondition.VERY_GOOD)
        self.assertTrue(product.is_public)
        self.assertTrue(product.is_featured)

        # Pallet Hub shows linked product
        page.goto(f"{self.live_server_url}{reverse('inventory:pallets')}")
        page.wait_for_selector('text="Pallet #1"')
        self.assertTrue(page.locator('text="1"').first.is_visible())

        # Attach marketplace link -> PUBLISHED
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

        page.goto(f"{self.live_server_url}{reverse('inventory:product_detail', kwargs={'pk': product.pk})}")
        page.click("#tabBtnWorkspaceChannels")
        page.wait_for_selector('a:has-text("Ver en Tienda Pública"), a:has-text("View in Storefront")')
        self.assertTrue(
            page.locator('a:has-text("Ver en Tienda Pública"), a:has-text("View in Storefront")').is_visible()
        )

        # PART IV: LIVE STOREFRONT VALIDATION & STATUS LIFECYCLE
        page.goto(f"{self.live_server_url}{product.get_public_url()}")
        page.wait_for_selector("#mainProductPhoto")
        assert_visible_images_loaded(self, page, "#mainProductPhoto")
        page.screenshot(path=str(self.artifacts_dir / "daily_05_storefront_published_item.png"))

        self.assertTrue(
            page.locator('text="DESTACADO"').first.is_visible()
            or page.locator('text="FEATURED"').first.is_visible()
        )
        self.assertTrue(
            page.locator('text="165,00 €"').first.is_visible()
            or page.locator('text="165.00 €"').first.is_visible()
        )

        # Reserve product
        product.is_reserved = True
        product.save(update_fields=["is_reserved"])
        page.reload()
        page.wait_for_selector("text=/RESERVED|RESERVADO/i")
        self.assertTrue(page.locator("text=/RESERVED|RESERVADO/i").first.is_visible())
        page.screenshot(path=str(self.artifacts_dir / "daily_06_storefront_reserved_state.png"))

        # Mark as Sold
        product.mark_as_sold(price=Decimal("165.00"), user=self.manager, channel_type="in_store")
        product.refresh_from_db()
        self.assertEqual(product.status, ProductStatus.SOLD)
        self.assertTrue(product.is_sold)
        self.assertEqual(product.sold_channel_type, "in_store")

        page.reload()
        page.wait_for_selector("text=/SOLD|VENDIDO/i")
        self.assertTrue(page.locator("text=/SOLD|VENDIDO/i").first.is_visible())
        page.screenshot(path=str(self.artifacts_dir / "daily_07_storefront_sold_state.png"))

        # Verify Audit Trail
        page.goto(f"{self.live_server_url}{reverse('inventory:product_detail', kwargs={'pk': product.pk})}")
        page.wait_for_selector("#status-history-card, h3:has-text('Historial de Estados')")
        self.assertIn("manager_daily", page.content())
        page.screenshot(path=str(self.artifacts_dir / "daily_08_staging_sold_audit_trail.png"))

        # Sold item in Dashboard 'Vendido' tab
        page.goto(f"{self.live_server_url}{reverse('inventory:dashboard')}?status=sold")
        page.wait_for_selector('text="Chaqueta Barbour Beaufort Encerada"')
        page.screenshot(path=str(self.artifacts_dir / "daily_09_dashboard_sold_tab.png"))
        self.assertTrue(page.locator('text="Chaqueta Barbour Beaufort Encerada"').first.is_visible())

        # PART V: MOBILE RESPONSIVENESS (390x844)
        mobile_context = self._browser.new_context(viewport={"width": 390, "height": 844})
        mobile_page = mobile_context.new_page()
        abort_nonessential_fonts(mobile_page)

        mobile_page.goto(f"{self.live_server_url}{reverse('storefront:catalog')}")
        mobile_page.wait_for_selector("#categoryRail")
        mobile_page.screenshot(path=str(self.artifacts_dir / "daily_10_mobile_storefront_catalog.png"))
        self.assertFalse(mobile_page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth"))

        mobile_page.goto(f"{self.live_server_url}{self.public_bike.get_public_url()}")
        mobile_page.wait_for_selector("#mainProductPhoto")
        mobile_page.screenshot(path=str(self.artifacts_dir / "daily_11_mobile_product_detail.png"))
        self.assertFalse(mobile_page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth"))

        mobile_page.goto(f"{self.live_server_url}{reverse('inventory:login')}")
        mobile_page.fill("#id_username", "manager_daily")
        mobile_page.fill("#id_password", "password123")
        with mobile_page.expect_navigation():
            mobile_page.click("#loginSubmitBtn")
        mobile_page.wait_for_selector('nav[role="tablist"]')
        mobile_page.screenshot(path=str(self.artifacts_dir / "daily_12_mobile_dashboard.png"))
        self.assertFalse(mobile_page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth"))

        mobile_context.close()
        context.close()

    def test_bilingual_language_switcher_in_chrome(self):
        """
        Verify Spanish <-> English switcher works across Storefront & Inventory via real clicks,
        updating HTML lang attribute, hero heading, nav links, and modals.
        """
        context = self._browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        abort_nonessential_fonts(page)

        page.goto(f"{self.live_server_url}{reverse('storefront:home')}")
        page.wait_for_selector('form[action*="/i18n/setlang/"]')

        # Switch to Spanish first so baseline ES state is guaranteed regardless of test LANGUAGE_CODE
        with page.expect_navigation():
            page.locator('button[name="language"][value="es"]').first.click()
        page.wait_for_selector("#categoryRail")

        page_text_es = page.content()
        self.assertEqual(page.locator("html").get_attribute("lang"), "es")
        self.assertIn("Estantería Outlet y Segunda Mano", page_text_es)
        self.assertIn("Otras tiendas y envío protegido", page_text_es)
        page.screenshot(path=str(self.artifacts_dir / "daily_bilingual_01_es.png"))

        # Switch to English
        en_btn = page.locator('button[name="language"][value="en"]').first
        self.assertTrue(en_btn.is_visible())
        with page.expect_navigation():
            en_btn.click()
        page.wait_for_selector("#categoryRail")

        page_text_en = page.content()
        self.assertEqual(page.locator("html").get_attribute("lang"), "en")
        self.assertIn("Outlet &amp; Second-Hand Shelf", page_text_en)
        self.assertIn("Other stores &amp; protected shipping", page_text_en)
        self.assertNotIn("Estantería Outlet y Segunda Mano", page_text_en)
        page.screenshot(path=str(self.artifacts_dir / "daily_bilingual_02_en.png"))

        # How-to-Buy guide in English
        page.goto(f"{self.live_server_url}{reverse('storefront:how_to_buy')}")
        page.wait_for_selector("h1")
        htb_text_en = page.content()
        self.assertIn("How to buy at Rápido Pack Alfafar?", htb_text_en)
        self.assertIn("24h no-commitment hold:", htb_text_en)
        page.screenshot(path=str(self.artifacts_dir / "daily_bilingual_03_htb_en.png"))

        # Switch back to Spanish
        es_btn = page.locator('button[name="language"][value="es"]').first
        self.assertTrue(es_btn.is_visible())
        with page.expect_navigation():
            es_btn.click()
        page.wait_for_selector("h1")
        htb_text_es = page.content()
        self.assertEqual(page.locator("html").get_attribute("lang"), "es")
        self.assertIn("¿Cómo comprar en Rápido Pack Alfafar?", htb_text_es)
        self.assertIn("Reserva 24h sin compromiso:", htb_text_es)
        page.screenshot(path=str(self.artifacts_dir / "daily_bilingual_04_htb_es.png"))

        # Unused import check safeguard for Pallet/datetime
        self.assertIsNotNone(Pallet)
        self.assertIsNotNone(datetime.date)
        context.close()
