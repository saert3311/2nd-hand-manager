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
from playwright.sync_api import expect

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
    assert_visible_images_loaded,
    create_user_with_group,
    get_test_artifact_dir,
    goto_authenticated,
    login_in_browser,
    make_test_image_bytes,
    open_browser_page,
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

    def test_public_storefront_cookie_catalog_and_legal_flow(self):
        """Verify Storefront home, cookie preferences, catalog filtering, how-to-buy modal, detail, and legal 302s."""
        with open_browser_page(
            self._browser,
            self,
            viewport={"width": 1280, "height": 900},
        ) as (_context, page):
            # 1. Store Shelf at /
            page.goto(f"{self.live_server_url}{reverse('storefront:home')}")
            expect(page.locator("#categoryRail")).to_be_visible()
            self.assertIn("Rápido Pack", page.content())
            self.assertIn("logo-rapido-pack-valencia.png", page.content())
            self.assertIn("https://rapidopackvalencia.es", page.content())
            self.assertTrue(page.locator('text="Bicicleta de Montaña Orbea MX 29"').first.is_visible())
            self.assertEqual(
                page.locator(f'a[href*="/go/whatsapp/{self.public_bike.pk}/"]').count(),
                0,
                "Shelf cards must stay decluttered without per-card WhatsApp buttons",
            )

            # Interactive Cookie Consent Banner + Footer Re-open + Persist across navigations
            expect(page.locator("#cookie-banner-container:not(.hidden)")).to_be_visible()
            self.assertTrue(page.locator("#cookie-banner-container").is_visible())
            page.locator("#cookie-accept-all-btn").click()
            expect(page.locator("#cookie-banner-container")).to_be_hidden()
            self.assertIn("rpv_cookie_consent=", page.evaluate("() => document.cookie"))
            footer_cookie_btn = page.locator("#footer-cookie-settings-btn")
            footer_cookie_btn.scroll_into_view_if_needed()
            footer_cookie_btn.click()
            expect(page.locator("#cookie-banner-container:not(.hidden)")).to_be_visible()
            self.assertTrue(page.locator("#cookie-settings-panel").is_visible())
            self.assertTrue(page.locator("#cookie-analytics-toggle").is_checked())
            page.locator("#cookie-quick-close-btn").click()
            expect(page.locator("#cookie-banner-container")).to_be_hidden()
            page.screenshot(path=str(self.artifacts_dir / "daily_00_store_shelf_home.png"))

            # 2. Catalog (/tienda/) + Category Rail Filtering + GTM dataLayer
            page.goto(f"{self.live_server_url}{reverse('storefront:catalog')}")
            expect(page.locator("#categoryRail")).to_be_visible()
            self.assertIn("Alfafar", page.content())
            assert_visible_images_loaded(self, page)
            page.screenshot(path=str(self.artifacts_dir / "daily_00_public_catalog.png"))

            shelf_events = page.evaluate("() => (window.dataLayer || []).map((e) => e && e.event).filter(Boolean)")
            self.assertIn("view_item_list", shelf_events)
            page.locator('#categoryRail a:has-text("Bicicletas")').first.click()
            page.wait_for_url("**/categoria/bicicletas/**")
            expect(page.locator('text="Bicicleta de Montaña Orbea MX 29"').first).to_be_visible()
            self.assertTrue(page.locator('text="Bicicleta de Montaña Orbea MX 29"').first.is_visible())

            # 3. 'Cómo comprar en Alfafar' modal + GTM how_to_buy_open event
            page.locator('button:has-text("Cómo comprar"), button:has-text("How to buy")').first.click()
            expect(page.locator("#how-to-buy-dialog[open]")).to_be_visible()
            modal_events = page.evaluate("() => (window.dataLayer || []).map((e) => e && e.event).filter(Boolean)")
            self.assertIn("how_to_buy_open", modal_events)
            modal_title = page.locator("#how-to-buy-title").inner_text()
            self.assertTrue("Rápido Pack Alfafar" in modal_title or "comprar" in modal_title.lower())
            page.screenshot(path=str(self.artifacts_dir / "daily_00_how_to_buy_modal.png"))
            page.locator("#how-to-buy-dialog button[aria-label]").first.click()
            expect(page.locator("#how-to-buy-dialog")).to_be_hidden()
            self.assertFalse(page.locator("#how-to-buy-dialog").is_visible())

            # 4. Public Product Detail Page + verify real rendered media + GTM view_item
            page.locator('h3:has-text("Bicicleta de Montaña Orbea MX 29") a').first.click()
            page.wait_for_url(f"**{self.public_bike.get_public_url()}")
            expect(page.locator("#mainProductPhoto")).to_be_visible()
            detail_events = page.evaluate("() => (window.dataLayer || []).map((e) => e && e.event).filter(Boolean)")
            self.assertIn("view_item", detail_events)
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

            # Canonical 301 slug redirect & secondary storefront routes
            page.goto(f"{self.live_server_url}/tienda/producto/outdated-slug-{self.public_bike.pk}/")
            expect(page.locator("#mainProductPhoto")).to_be_visible()
            self.assertIn(f"bicicleta-de-montana-orbea-mx-29-{self.public_bike.pk}", page.url)

            page.goto(f"{self.live_server_url}{reverse('storefront:how_to_buy')}")
            expect(page.locator('h1:has-text("Cómo comprar"), h1:has-text("How to buy")').first).to_be_visible()
            self.assertIn("Alfafar", page.content())
            self.assertIn("Comte Ronrée", page.content())

            page.goto(f"{self.live_server_url}/tienda/categoria/bicicletas/")
            expect(page.locator("#categoryRail")).to_be_visible()
            self.assertTrue(page.locator('text="Bicicleta de Montaña Orbea MX 29"').first.is_visible())

            page.goto(f"{self.live_server_url}/tienda/?estado=muy_bueno&orden=baratos")
            expect(page.locator('text="Bicicleta de Montaña Orbea MX 29"').first).to_be_visible()
            self.assertTrue(page.locator('text="Bicicleta de Montaña Orbea MX 29"').first.is_visible())

            # Canonical footer legal links & HTTP 302 redirects to rapidopackvalencia.es
            for route_name, expected_target in [
                ("storefront:legal_notice", "https://rapidopackvalencia.es/aviso-legal"),
                ("storefront:privacy", "https://rapidopackvalencia.es/privacidad"),
                ("storefront:cookies", "https://rapidopackvalencia.es/cookies"),
            ]:
                self.assertGreater(page.locator(f'footer a[href="{expected_target}"]').count(), 0)
                resp = page.context.request.get(
                    f"{self.live_server_url}{reverse(route_name)}",
                    max_redirects=0,
                )
                self.assertEqual(resp.status, 302)
                self.assertEqual(resp.headers.get("location"), expected_target)

    def _route_mock_intake_identify(self, page):
        """Intercept the Gemini AI intake identify endpoint for fast deterministic valuation."""
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

    def test_staff_pallet_creation_and_ai_intake_valuation_workflow(self):
        """Verify Pallet creation, AI Intake valuation benchmarks, and dashboard pallet filtering."""
        img_path = str(self.sample_image_path)
        with open_browser_page(
            self._browser,
            self,
            viewport={"width": 1280, "height": 900},
        ) as (_context, page):
            page.on("dialog", lambda d: d.accept())
            self._route_mock_intake_identify(page)

            login_in_browser(page, self.live_server_url, "manager_daily", "password123")

            # Create Pallet #1
            goto_authenticated(page, f"{self.live_server_url}{reverse('inventory:pallets')}")
            expect(page.locator("#btnCreatePallet")).to_be_visible()
            page.locator("#id_purchase_price").fill("350.00")
            page.locator("#id_estimated_value").fill("900.00")
            page.locator("#id_notes").fill("Lote Liquidacion Chaquetas & Moda Alfafar")
            with page.expect_response(lambda r: r.request.method == "POST" and "/pallets/" in r.url):
                page.locator("#btnCreatePallet").click()
            page.wait_for_load_state("domcontentloaded")
            expect(page.locator('text="Pallet #1"').first).to_be_visible()
            self.assertTrue(page.locator('text="Pallet #1"').first.is_visible())
            self.assertIn("350", page.content())
            self.assertIn("900", page.content())

            # Intake screen with Pallet #1 preselected
            goto_authenticated(page, f"{self.live_server_url}{reverse('inventory:intake')}")
            expect(page.locator("#dropZone")).to_be_visible()
            pallet_select = page.locator("#id_origin")
            self.assertTrue(pallet_select.is_visible())
            self.assertTrue(pallet_select.input_value().startswith("pallet:"))

            page.set_input_files("#imageInput", img_path)
            expect(page.locator("#previewGrid img").first).to_be_visible()
            page.locator("#id_raw_note").fill("Barbour Beaufort vintage verde oliva, cremallera perfecta, ligera pátina.")

            page.locator("#identifyBtn").click()
            expect(page.locator("#advisoryValuationContainer:not(.hidden)")).to_be_visible(timeout=10000)

            self.assertIn("435", page.locator("#advisoryRetailPrice").inner_text())
            self.assertIn("165", page.locator("#advisoryResalePrice").inner_text())
            self.assertTrue(page.locator("#intakePriceBenchmarks").is_visible())
            self.assertIn("435", page.locator("#badgeRefRetail").inner_text())
            self.assertIn("165", page.locator("#badgeRefResale").inner_text())
            page.screenshot(path=str(self.artifacts_dir / "daily_01_intake_valuation_benchmarks.png"))

            use_resale_btn = page.locator("#btnUseEstimatedResale")
            self.assertTrue(use_resale_btn.is_visible())
            use_resale_btn.click()
            self.assertEqual(page.locator("#id_sale_price").input_value(), "165.00")
            self.assertEqual(page.locator("#id_estimated_retail_price").input_value(), "435.00")
            self.assertEqual(page.locator("#id_estimated_resale_price").input_value(), "165.00")
            page.screenshot(path=str(self.artifacts_dir / "daily_02_intake_resale_applied.png"))

            with page.expect_response(
                lambda r: r.request.method == "POST" and r.url.rstrip("/").endswith("/intake")
            ):
                page.locator("#submitBtn").click()
            expect(page.locator("text=/cataloged successfully|catalogado con éxito/i").first).to_be_visible(timeout=10000)
            page.wait_for_load_state("load")

            product = Product.objects.get(ai_title="Chaqueta Barbour Beaufort Encerada")
            self.assertEqual(product.estimated_retail_price, 435.00)
            self.assertEqual(product.estimated_resale_price, 165.00)
            self.assertEqual(product.sale_price, 165.00)
            self.assertIsNotNone(product.pallet)
            self.assertEqual(product.pallet.number, 1)

            # Manager Staging Review & Dashboard Pallet Filtering
            goto_authenticated(page, f"{self.live_server_url}{reverse('inventory:dashboard')}")
            expect(page.locator('a[href*="/products/"]').first).to_be_visible()
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

            pallet_select.select_option("none")
            page.wait_for_url("**pallet=none**")
            expect(page.locator("#palletFilterForm select[name='pallet']")).to_be_visible()
            self.assertFalse(page.locator('text="Chaqueta Barbour Beaufort Encerada"').is_visible())

            page.locator("#palletFilterForm select[name='pallet']").select_option(str(product.pallet.id))
            page.wait_for_url(f"**pallet={product.pallet.id}**")
            expect(page.locator('text="Chaqueta Barbour Beaufort Encerada"').first).to_be_visible()
            self.assertTrue(page.locator('text="Chaqueta Barbour Beaufort Encerada"').first.is_visible())

    def test_manager_detail_storefront_publish_reserve_and_sold_lifecycle(self):
        """Verify Product Detail valuation benchmarks, Storefront publishing, 24h hold, Sold state, and Audit trail."""
        pallet1 = Pallet.objects.create(
            number=1,
            received_date=datetime.date(2026, 10, 15),
            purchase_price=Decimal("350.00"),
            estimated_value=Decimal("900.00"),
            notes="Lote Liquidacion Chaquetas & Moda Alfafar",
            created_by=self.manager,
        )
        product = Product.objects.create(
            raw_note="Barbour Beaufort vintage verde oliva, cremallera perfecta, ligera pátina.",
            ai_title="Chaqueta Barbour Beaufort Encerada",
            sale_price=Decimal("165.00"),
            estimated_retail_price=Decimal("435.00"),
            estimated_resale_price=Decimal("165.00"),
            pallet=pallet1,
            created_by=self.manager,
        )
        ProductImage.objects.create(
            product=product,
            image=ContentFile(make_test_image_bytes(size=(600, 600), color="teal"), name="barbour_detail.jpg"),
            order=0,
        )

        with open_browser_page(
            self._browser,
            self,
            viewport={"width": 1280, "height": 900},
        ) as (_context, page):
            page.on("dialog", lambda d: d.accept())
            login_in_browser(page, self.live_server_url, "manager_daily", "password123")

            # Product Detail View
            detail_url = f"{self.live_server_url}{reverse('inventory:product_detail', kwargs={'pk': product.pk})}"
            goto_authenticated(page, detail_url)
            expect(page.locator("#id_sale_price")).to_be_visible()
            assert_visible_images_loaded(self, page)

            pallet_badge = page.locator("#product-pallet-badge")
            self.assertTrue(pallet_badge.is_visible())
            self.assertIn("Pallet #1", pallet_badge.inner_text())

            self.assertTrue(page.locator("#detail-valuation-benchmarks").is_visible())
            self.assertIn("435", page.locator("#ref-retail-price").inner_text())
            self.assertIn("165", page.locator("#ref-resale-price").inner_text())

            apply_btn = page.locator("#btnApplyResalePrice")
            self.assertTrue(apply_btn.is_visible())
            self.assertEqual(apply_btn.get_attribute("data-resale"), "165.00")

            self.assertTrue(len(page.locator("#footer-build-time").inner_text()) > 0)
            page.screenshot(path=str(self.artifacts_dir / "daily_04_product_detail_valuation_benchmarks.png"))

            # Configure Storefront Controls & Description
            fashion_cat = self.cat_fashion
            page.locator('textarea[name="ai_description"]').fill(
                "Auténtica chaqueta Barbour Beaufort encerada en color verde oliva. Talla C40. Fabricada en Inglaterra.",
            )
            page.locator("#tabBtnWorkspaceChannels").click()
            page.locator("#id_category").select_option(str(fashion_cat.pk))
            page.locator("#id_condition").select_option(ProductCondition.VERY_GOOD)
            page.locator("#id_is_public").check()
            page.locator("#id_is_featured").check()
            with page.expect_response(
                lambda r: r.request.method == "POST" and f"/products/{product.pk}/" in r.url
            ):
                page.locator("#btnSaveListingChanges").click()
            page.wait_for_load_state("domcontentloaded")
            expect(page.locator("#id_sale_price")).to_be_visible()

            product.refresh_from_db()
            self.assertEqual(product.category, fashion_cat)
            self.assertEqual(product.condition, ProductCondition.VERY_GOOD)
            self.assertTrue(product.is_public)
            self.assertTrue(product.is_featured)

            # Pallet Hub shows linked product
            goto_authenticated(page, f"{self.live_server_url}{reverse('inventory:pallets')}")
            expect(page.locator('text="Pallet #1"').first).to_be_visible()
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

            goto_authenticated(page, detail_url)
            page.locator("#tabBtnWorkspaceChannels").click()
            storefront_btn = page.locator('a:has-text("Ver en Tienda Pública"), a:has-text("View in Storefront")').first
            expect(storefront_btn).to_be_visible()
            self.assertTrue(storefront_btn.is_visible())

            # Live Storefront Validation & Reserved -> Sold Lifecycle
            page.goto(f"{self.live_server_url}{product.get_public_url()}")
            expect(page.locator("#mainProductPhoto")).to_be_visible()
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

            product.is_reserved = True
            product.save(update_fields=["is_reserved"])
            page.reload()
            expect(page.locator("text=/RESERVED|RESERVADO/i").first).to_be_visible()
            self.assertTrue(page.locator("text=/RESERVED|RESERVADO/i").first.is_visible())
            page.screenshot(path=str(self.artifacts_dir / "daily_06_storefront_reserved_state.png"))

            product.mark_as_sold(price=Decimal("165.00"), user=self.manager, channel_type="in_store")
            product.refresh_from_db()
            self.assertEqual(product.status, ProductStatus.SOLD)
            self.assertTrue(product.is_sold)
            self.assertEqual(product.sold_channel_type, "in_store")

            page.reload()
            expect(page.locator("text=/SOLD|VENDIDO/i").first).to_be_visible()
            self.assertTrue(page.locator("text=/SOLD|VENDIDO/i").first.is_visible())
            page.screenshot(path=str(self.artifacts_dir / "daily_07_storefront_sold_state.png"))

            # Audit Trail & Sold Dashboard Tab
            goto_authenticated(page, detail_url)
            expect(page.locator("#status-history-card, h3:has-text('Historial de Estados')").first).to_be_visible()
            self.assertIn("manager_daily", page.content())
            page.screenshot(path=str(self.artifacts_dir / "daily_08_staging_sold_audit_trail.png"))

            goto_authenticated(page, f"{self.live_server_url}{reverse('inventory:dashboard')}?status=sold")
            expect(page.locator('text="Chaqueta Barbour Beaufort Encerada"').first).to_be_visible()
            page.screenshot(path=str(self.artifacts_dir / "daily_09_dashboard_sold_tab.png"))
            self.assertTrue(page.locator('text="Chaqueta Barbour Beaufort Encerada"').first.is_visible())

    def test_mobile_storefront_and_dashboard_390x844_responsive(self):
        """Verify 390x844 mobile layout across Storefront Catalog, Product Detail, and Staff Dashboard."""
        with open_browser_page(
            self._browser,
            self,
            viewport={"width": 390, "height": 844},
        ) as (_mobile_context, mobile_page):
            mobile_page.goto(f"{self.live_server_url}{reverse('storefront:catalog')}")
            expect(mobile_page.locator("#categoryRail")).to_be_visible()
            mobile_page.screenshot(path=str(self.artifacts_dir / "daily_10_mobile_storefront_catalog.png"))
            self.assertFalse(mobile_page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth"))

            mobile_page.goto(f"{self.live_server_url}{self.public_bike.get_public_url()}")
            expect(mobile_page.locator("#mainProductPhoto")).to_be_visible()
            mobile_page.screenshot(path=str(self.artifacts_dir / "daily_11_mobile_product_detail.png"))
            self.assertFalse(mobile_page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth"))

            login_in_browser(mobile_page, self.live_server_url, "manager_daily", "password123")
            expect(mobile_page.locator('nav[role="tablist"]').first).to_be_visible()
            mobile_page.screenshot(path=str(self.artifacts_dir / "daily_12_mobile_dashboard.png"))
            self.assertFalse(mobile_page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth"))

    def test_bilingual_language_switcher_in_chrome(self):
        """
        Verify Spanish <-> English switcher works across Storefront & Inventory via real clicks,
        updating HTML lang attribute, hero heading, nav links, and modals.
        """
        with open_browser_page(
            self._browser,
            self,
            viewport={"width": 1280, "height": 900},
        ) as (_context, page):
            page.goto(f"{self.live_server_url}{reverse('storefront:home')}")
            expect(page.locator('form[action*="/i18n/setlang/"]').first).to_be_visible()

            # Switch to Spanish first so baseline ES state is guaranteed regardless of test LANGUAGE_CODE
            with page.expect_response(lambda r: r.request.method == "POST" and "/i18n/setlang/" in r.url):
                page.locator('button[name="language"][value="es"]').first.click()
            page.wait_for_load_state("domcontentloaded")
            expect(page.locator("html")).to_have_attribute("lang", "es")
            expect(page.locator("#categoryRail")).to_be_visible()

            page_text_es = page.content()
            self.assertEqual(page.locator("html").get_attribute("lang"), "es")
            self.assertIn("Estantería Outlet y Segunda Mano", page_text_es)
            self.assertIn("Control de Cookies", page_text_es)
            self.assertIn("Cómo comprar", page_text_es)
            page.screenshot(path=str(self.artifacts_dir / "daily_bilingual_01_es.png"))

            # Switch to English
            en_btn = page.locator('button[name="language"][value="en"]').first
            self.assertTrue(en_btn.is_visible())
            with page.expect_response(lambda r: r.request.method == "POST" and "/i18n/setlang/" in r.url):
                en_btn.click()
            page.wait_for_load_state("domcontentloaded")
            expect(page.locator("html")).to_have_attribute("lang", "en")
            expect(page.locator("#categoryRail")).to_be_visible()

            page_text_en = page.content()
            self.assertEqual(page.locator("html").get_attribute("lang"), "en")
            self.assertIn("Outlet &amp; Second-Hand Shelf", page_text_en)
            self.assertIn("Cookie Control", page_text_en)
            self.assertIn("How to buy", page_text_en)
            self.assertNotIn("Estantería Outlet y Segunda Mano", page_text_en)
            page.screenshot(path=str(self.artifacts_dir / "daily_bilingual_02_en.png"))

            # How-to-Buy guide in English
            page.goto(f"{self.live_server_url}{reverse('storefront:how_to_buy')}")
            expect(page.locator("h1").first).to_be_visible()
            htb_text_en = page.content()
            self.assertIn("How to buy at Rápido Pack Alfafar?", htb_text_en)
            self.assertIn("24h no-commitment hold:", htb_text_en)
            page.screenshot(path=str(self.artifacts_dir / "daily_bilingual_03_htb_en.png"))

            # Switch back to Spanish
            es_btn = page.locator('button[name="language"][value="es"]').first
            self.assertTrue(es_btn.is_visible())
            with page.expect_response(lambda r: r.request.method == "POST" and "/i18n/setlang/" in r.url):
                es_btn.click()
            page.wait_for_load_state("domcontentloaded")
            expect(page.locator("html")).to_have_attribute("lang", "es")
            expect(page.locator("h1").first).to_be_visible()
            htb_text_es = page.content()
            self.assertEqual(page.locator("html").get_attribute("lang"), "es")
            self.assertIn("¿Cómo comprar en Rápido Pack Alfafar?", htb_text_es)
            self.assertIn("Reserva 24h sin compromiso:", htb_text_es)
            page.screenshot(path=str(self.artifacts_dir / "daily_bilingual_04_htb_es.png"))
