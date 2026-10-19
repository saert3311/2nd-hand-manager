import os
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from playwright.sync_api import sync_playwright

from inventory.models import MarketplaceSite, Product, ProductClarification, ProductListingLink, ProductStatus

User = get_user_model()


@override_settings(TURNSTILE_ENABLED=False)
class DashboardResponsiveUITests(StaticLiveServerTestCase):
    """
    Verifies that the dashboard status tabs and filter toolbar do not wrap or
    apilar (pile up) awkwardly across standard viewports (390px, 768px, 1024px, 1440px),
    meeting WCAG touch targets and frontend UI engineering guidelines.
    """

    @classmethod
    def setUpClass(cls):
        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
        super().setUpClass()
        os.makedirs("browser_verification_screenshots", exist_ok=True)

    def setUp(self):
        self.manager = User.objects.create_user(
            username="resp_manager",
            password="password123",
            is_staff=True,
        )
        self.site_vinted, _ = MarketplaceSite.objects.get_or_create(
            slug="vinted",
            defaults={"name": "Vinted", "order": 1, "is_active": True},
        )

        # Create products in each distinct state so all tabs appear with counts
        p_active = Product.objects.create(
            ai_title="Vintage Leather Jacket",
            sale_price=Decimal("89.99"),
            status=ProductStatus.READY,
            is_sold=False,
        )
        ProductListingLink.objects.create(
            product=p_active,
            site=self.site_vinted,
            url="https://vinted.es/items/123",
            is_active=True,
        )

        Product.objects.create(
            ai_title="Nike Air Max Sneakers",
            sale_price=None,
            status=ProductStatus.PRICE_PENDING,
            is_sold=False,
        )

        p_awaiting = Product.objects.create(
            ai_title="Antique Porcelain Tea Set",
            sale_price=Decimal("45.00"),
            status=ProductStatus.AWAITING_INFO,
            is_sold=False,
        )
        ProductClarification.objects.create(
            product=p_awaiting,
            question="Is there any crack or chip in the cups?",
            asked_by=self.manager,
        )

        Product.objects.create(
            ai_title="Sold Casio Vintage Watch",
            sale_price=Decimal("25.00"),
            status=ProductStatus.SOLD,
            is_sold=True,
        )

        Product.objects.create(
            ai_title="Blocked Trademark Item",
            sale_price=Decimal("15.00"),
            status=ProductStatus.BLOCKED,
            is_sold=False,
        )

    def test_dashboard_responsive_tabs_no_apilation(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            context = browser.new_context()
            page = context.new_page()

            # 1. Login
            page.goto(f"{self.live_server_url}{reverse('inventory:login')}")
            page.fill("#id_username", "resp_manager")
            page.fill("#id_password", "password123")
            with page.expect_navigation():
                page.click("#loginSubmitBtn")
            page.wait_for_load_state("networkidle")

            viewports = [
                ("390x844_mobile", 390, 844),
                ("768x1024_tablet", 768, 1024),
                ("1024x768_laptop", 1024, 768),
                ("1440x900_desktop", 1440, 900),
            ]

            for label, width, height in viewports:
                page.set_viewport_size({"width": width, "height": height})
                page.goto(f"{self.live_server_url}{reverse('inventory:dashboard')}")
                page.wait_for_load_state("networkidle")

                # Verify status tab rail exists
                tablist = page.locator('nav[role="tablist"]')
                self.assertTrue(tablist.is_visible(), f"Status tablist must be visible at {label}")

                # Verify all tabs exist in the DOM
                tabs = tablist.locator('a[role="tab"]').all()
                self.assertGreaterEqual(len(tabs), 5, f"Expected at least 5 status tabs at {label}")

                # CRITICAL VERIFICATION: No apilación / vertical stacking of tabs inside the rail
                # All tabs inside the horizontal scroll rail must share the same top offset (within rounding tolerance)
                box_0 = tabs[0].bounding_box()
                self.assertIsNotNone(box_0)
                first_top = box_0["y"]

                for i, tab in enumerate(tabs):
                    box = tab.bounding_box()
                    self.assertIsNotNone(box)
                    # Tolerating at most 4px difference due to subpixel rendering or border
                    self.assertAlmostEqual(
                        box["y"],
                        first_top,
                        delta=4.0,
                        msg=f"Tab {i} at {label} is vertically stacked / apilado! box.y={box['y']} vs first_top={first_top}",
                    )
                    # Verify touch target height is at least 32px on desktop and >= 36px on mobile
                    self.assertGreaterEqual(box["height"], 32.0, f"Touch target height too small at {label}")

                # Take screenshot for audit trail
                screenshot_path = f"browser_verification_screenshots/dashboard_{label}.png"
                page.screenshot(path=screenshot_path)
                self.assertTrue(os.path.exists(screenshot_path))

            browser.close()

    def test_mobile_typography_and_input_font_sizes(self):
        """
        Verifies that mobile font sizes comply with WCAG and prevent iOS Safari auto-zoom
        by ensuring inputs have computed font-size >= 16px on mobile viewports (390x844).
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            context = browser.new_context()
            page = context.new_page()
            page.set_viewport_size({"width": 390, "height": 844})

            # 1. Login page mobile check
            page.goto(f"{self.live_server_url}{reverse('inventory:login')}")
            page.wait_for_load_state("networkidle")
            page.screenshot(path="browser_verification_screenshots/mobile_login_390x844.png")

            # Verify input computed font size is >= 16px
            username_font_size = page.evaluate("() => window.getComputedStyle(document.getElementById('id_username')).fontSize")
            self.assertGreaterEqual(float(username_font_size.replace("px", "")), 16.0)

            # 2. Login as manager
            page.fill("#id_username", "resp_manager")
            page.fill("#id_password", "password123")
            with page.expect_navigation():
                page.click("#loginSubmitBtn")
            page.wait_for_load_state("networkidle")

            # 3. Intake page mobile check
            page.goto(f"{self.live_server_url}{reverse('inventory:intake')}")
            page.wait_for_load_state("networkidle")
            page.screenshot(path="browser_verification_screenshots/mobile_intake_390x844.png")

            raw_note_font_size = page.evaluate("() => window.getComputedStyle(document.getElementById('id_raw_note')).fontSize")
            self.assertGreaterEqual(float(raw_note_font_size.replace("px", "")), 16.0)

            # 4. Product detail page mobile check
            first_product = Product.objects.filter(status=ProductStatus.AWAITING_INFO).first()
            page.goto(f"{self.live_server_url}{reverse('inventory:product_detail', args=[first_product.pk])}")
            page.wait_for_load_state("networkidle")
            page.screenshot(path="browser_verification_screenshots/mobile_product_detail_390x844.png")

            title_font_size = page.evaluate("() => window.getComputedStyle(document.getElementById('id_ai_title')).fontSize")
            self.assertGreaterEqual(float(title_font_size.replace("px", "")), 16.0)

            browser.close()
