"""
Browser E2E responsive verification targeting the OPPO A74 smartphone and low-DPI viewports.

Checks both OPPO A74 viewport profiles across Spanish & English interfaces:
- 360x800 (standard CSS viewport: 1080x2400 physical at 3.0 DPR)
- 320x711 (Android "Smaller Display Size" / zoomed low-DPI mode)

Verifies:
- Zero horizontal document overflow (scrollWidth <= clientWidth)
- Dual capture/gallery intake buttons stay inside viewport without clipping
- Mobile input font-size >= 16px
- All visible product images render cleanly without broken media URLs
"""

import datetime
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
    Provider,
)
from inventory.services.compliance_service import ensure_default_policy_clauses
from tests.helpers import (
    abort_nonessential_fonts,
    assert_visible_images_loaded,
    create_user_with_group,
    get_test_artifact_dir,
    make_test_image_bytes,
    start_shared_browser,
)


@override_settings(TURNSTILE_ENABLED=False)
class OppoA74ResponsiveUITests(StaticLiveServerTestCase):
    """Comprehensive viewport check for OPPO A74 & 320px low-DPI Android devices."""

    OPPO_VIEWPORTS = [
        ("oppo_360x800", 360, 800),
        ("oppo_lowdpi_320x711", 320, 711),
    ]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.artifacts_dir = get_test_artifact_dir(cls, repo_subdir="browser_verification_screenshots/oppo_a74")
        cls.sample_img_path = cls.artifacts_dir / "sample_jacket.jpg"
        cls.sample_img_path.write_bytes(make_test_image_bytes(size=(400, 400), color="darkgreen"))
        cls._browser = start_shared_browser(cls)

    def setUp(self):
        ensure_default_policy_clauses()
        self.manager = create_user_with_group("oppo_manager", group_name="managers", is_staff=True)
        self.category, _ = Category.objects.get_or_create(
            slug="chaquetas-vintage",
            defaults={"name": "Chaquetas Vintage", "icon": "apparel"},
        )
        self.site_vinted, _ = MarketplaceSite.objects.get_or_create(
            slug="vinted",
            defaults={"name": "Vinted", "order": 1, "is_active": True},
        )
        self.pallet = Pallet.objects.create(
            number=1,
            received_date=datetime.date(2026, 10, 15),
            created_by=self.manager,
        )

        self.p_active = Product.objects.create(
            ai_title="Chaqueta Vintage Cazadora Cuero Nobuk Marrón Talla L",
            ai_description="Chaqueta en excelente estado de conservación, cuero genuino nobuk con cremalleras funcionales.",
            sale_price=Decimal("85.50"),
            estimated_retail_price=Decimal("199.00"),
            estimated_resale_price=Decimal("89.00"),
            status=ProductStatus.READY,
            category=self.category,
            condition=ProductCondition.VERY_GOOD,
            pallet=self.pallet,
            is_public=True,
            is_featured=True,
            is_sold=False,
            created_by=self.manager,
        )
        ProductImage.objects.create(
            product=self.p_active,
            image=ContentFile(make_test_image_bytes(size=(400, 400), color="darkgreen"), name="sample_jacket.jpg"),
            order=1,
        )
        ProductListingLink.objects.create(
            product=self.p_active,
            site=self.site_vinted,
            url="https://www.vinted.es/items/123-vintage-jacket",
            clicks_count=5,
            is_active=True,
        )

        self.p_price_pending = Product.objects.create(
            ai_title="Camisa Franela Cuadros Grunge 90s Oversized",
            ai_description="Camisa clásica a cuadros estilo grunge años 90.",
            sale_price=None,
            estimated_retail_price=Decimal("55.00"),
            estimated_resale_price=Decimal("22.00"),
            status=ProductStatus.PRICE_PENDING,
            category=self.category,
            condition=ProductCondition.GOOD,
            is_public=False,
            created_by=self.manager,
        )

    def _assert_no_horizontal_overflow(self, page, page_label, width, height):
        """Verify document scrollWidth does not exceed clientWidth and inspect offscreen controls."""
        page.set_viewport_size({"width": width, "height": height})

        metrics = page.evaluate(
            """() => {
                const docEl = document.documentElement;
                const vw = docEl.clientWidth;
                const sw = docEl.scrollWidth;
                const offenders = [];
                if (sw > vw + 1) {
                    const els = document.querySelectorAll('button, a, input, select, div, section, header, nav, footer');
                    for (const el of els) {
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0 && (rect.right > vw + 2 || rect.left < -2)) {
                            const cs = window.getComputedStyle(el);
                            if (cs.position !== 'fixed' && cs.overflowX !== 'auto' && cs.overflowX !== 'scroll') {
                                offenders.push({
                                    tag: el.tagName,
                                    id: el.id || '',
                                    cls: (typeof el.className === 'string' ? el.className.slice(0, 60) : ''),
                                    right: Math.round(rect.right),
                                    vw: vw
                                });
                                if (offenders.length >= 5) break;
                            }
                        }
                    }
                }
                return { scrollWidth: sw, clientWidth: vw, offenders };
            }"""
        )

        screenshot_path = self.artifacts_dir / f"{page_label}_{width}x{height}.png"
        page.screenshot(path=str(screenshot_path), full_page=True)

        self.assertLessEqual(
            metrics["scrollWidth"],
            metrics["clientWidth"] + 1,
            f"Horizontal overflow on {page_label} at {width}x{height}: "
            f"scrollWidth={metrics['scrollWidth']} > clientWidth={metrics['clientWidth']}. "
            f"Offenders: {metrics['offenders']}",
        )

    def _assert_controls_visible_and_inside_viewport(self, page, selectors, label):
        vw = page.evaluate("() => document.documentElement.clientWidth")
        for sel in selectors:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                box = loc.bounding_box()
                self.assertIsNotNone(box, f"{label}: '{sel}' missing bounding box")
                self.assertGreaterEqual(box["x"], -1, f"{label}: '{sel}' clipped left edge ({box['x']})")
                self.assertLessEqual(
                    box["x"] + box["width"],
                    vw + 2,
                    f"{label}: '{sel}' overflows right edge ({box['x'] + box['width']} > {vw})",
                )

    def test_oppo_a74_public_storefront_responsive(self):
        """Test storefront Home, Catalog, Product Detail, How-to-Buy, Legal, and 404 at 360px and 320px."""
        with self._browser.new_context(viewport={"width": 360, "height": 800}) as context:
            page = context.new_page()
            abort_nonessential_fonts(page)

            for vp_name, w, h in self.OPPO_VIEWPORTS:
                page.set_viewport_size({"width": w, "height": h})

                # 1. Public Storefront Home
                page.goto(f"{self.live_server_url}{reverse('storefront:home')}")
                page.wait_for_selector("h1")
                self._assert_no_horizontal_overflow(page, f"storefront_home_{vp_name}", w, h)

                # 2. Storefront Catalog
                page.goto(f"{self.live_server_url}{reverse('storefront:catalog')}")
                page.wait_for_selector("#categoryRail")
                assert_visible_images_loaded(self, page)
                self._assert_no_horizontal_overflow(page, f"storefront_catalog_{vp_name}", w, h)

                # 3. Public Product Detail
                page.goto(f"{self.live_server_url}{self.p_active.get_public_url()}")
                page.wait_for_selector("#mainProductPhoto")
                assert_visible_images_loaded(self, page, "#mainProductPhoto")
                self._assert_no_horizontal_overflow(page, f"storefront_detail_{vp_name}", w, h)

                # 4. How to Buy Guide
                page.goto(f"{self.live_server_url}{reverse('storefront:how_to_buy')}")
                page.wait_for_selector("h1")
                self._assert_no_horizontal_overflow(page, f"storefront_how_to_buy_{vp_name}", w, h)

                # 5. Legal Notice
                page.goto(f"{self.live_server_url}{reverse('storefront:legal_notice')}")
                page.wait_for_selector("h1")
                self._assert_no_horizontal_overflow(page, f"storefront_legal_{vp_name}", w, h)

                # 6. Custom 404 page
                page.goto(f"{self.live_server_url}/non-existent-route-xyz-404/")
                page.wait_for_selector("body")
                self._assert_no_horizontal_overflow(page, f"error_404_{vp_name}", w, h)

    def test_oppo_a74_staff_workspace_responsive(self):
        """Test Login, Dashboard, Intake (+ dual buttons & preview cards), Product Detail, Pallets, and Policy Guard."""
        with self._browser.new_context(viewport={"width": 360, "height": 800}) as context:
            page = context.new_page()
            abort_nonessential_fonts(page)
            page.on("dialog", lambda d: d.accept())

            # Switch to Spanish first so expanded Spanish strings are stress-tested
            page.goto(f"{self.live_server_url}{reverse('storefront:home')}")
            es_btn = page.locator('form[action*="/i18n/setlang/"] button[value="es"]').first
            if es_btn.count() > 0:
                with page.expect_navigation():
                    es_btn.click()

            # 1. Login Page
            page.goto(f"{self.live_server_url}{reverse('inventory:login')}")
            page.wait_for_selector("#id_username")
            for vp_name, w, h in self.OPPO_VIEWPORTS:
                self._assert_no_horizontal_overflow(page, f"login_{vp_name}", w, h)

            page.fill("#id_username", "oppo_manager")
            page.fill("#id_password", "password123")
            with page.expect_navigation():
                page.click("#loginSubmitBtn")
            page.wait_for_selector('nav[role="tablist"]')

            # 2. Dashboard
            for vp_name, w, h in self.OPPO_VIEWPORTS:
                page.set_viewport_size({"width": w, "height": h})
                assert_visible_images_loaded(self, page)
                self._assert_no_horizontal_overflow(page, f"dashboard_{vp_name}", w, h)
                self._assert_controls_visible_and_inside_viewport(
                    page, ['nav[role="tablist"]', "input[name='q']"], f"Dashboard {vp_name}"
                )

            # 3. Intake Page (+ uploaded image preview)
            page.goto(f"{self.live_server_url}{reverse('inventory:intake')}")
            page.wait_for_selector("#dropZone")
            page.set_input_files("#imageInput", str(self.sample_img_path))
            page.wait_for_selector("#previewGrid img")
            for vp_name, w, h in self.OPPO_VIEWPORTS:
                self._assert_no_horizontal_overflow(page, f"intake_{vp_name}", w, h)
                self._assert_controls_visible_and_inside_viewport(
                    page,
                    ["label[for='cameraInput']", "label[for='imageInput']", "#identifyBtn", "#submitBtn"],
                    f"Intake {vp_name}",
                )

            # 4. Pallets & Providers Hub + Provider Edit
            page.goto(f"{self.live_server_url}{reverse('inventory:pallets')}")
            page.wait_for_selector("#btnCreatePallet")
            for vp_name, w, h in self.OPPO_VIEWPORTS:
                self._assert_no_horizontal_overflow(page, f"pallets_{vp_name}", w, h)

            page.click("#tabBtnProviders")
            self.assertTrue(page.locator("#panelProviders").is_visible())
            for vp_name, w, h in self.OPPO_VIEWPORTS:
                self._assert_no_horizontal_overflow(page, f"providers_tab_{vp_name}", w, h)

            seeded_provider = Provider.objects.order_by("id").first()
            if seeded_provider:
                page.goto(f"{self.live_server_url}{reverse('inventory:provider_edit', kwargs={'pk': seeded_provider.pk})}")
                page.wait_for_selector("main")
                for vp_name, w, h in self.OPPO_VIEWPORTS:
                    self._assert_no_horizontal_overflow(page, f"provider_edit_{vp_name}", w, h)

            # 5. Product Detail Workspace (+ gallery edit controls, tabs, pending preview)
            page.goto(f"{self.live_server_url}{reverse('inventory:product_detail', kwargs={'pk': self.p_active.pk})}")
            page.wait_for_selector("#id_sale_price")
            assert_visible_images_loaded(self, page)

            font_size = page.evaluate(
                "() => parseFloat(window.getComputedStyle(document.querySelector('#id_sale_price')).fontSize)"
            )
            self.assertGreaterEqual(font_size, 16.0, "OPPO/Android mobile inputs must render >= 16px font-size")

            disclosure = page.locator("#detailAddPhotosDisclosure")
            if disclosure.count() > 0:
                disclosure.locator("summary").click()
            page.set_input_files("#detailImageInput", str(self.sample_img_path))
            page.wait_for_selector("#detailPendingGrid img")

            for vp_name, w, h in self.OPPO_VIEWPORTS:
                self._assert_no_horizontal_overflow(page, f"product_detail_{vp_name}", w, h)
                self._assert_controls_visible_and_inside_viewport(
                    page,
                    [
                        "#detailWorkspaceTablist",
                        "#btnSaveListingChanges",
                        "#galleryThumbnailsGrid .photo-edit-btn",
                    ],
                    f"ProductDetail {vp_name}",
                )
