"""
Browser tests verifying tablet & desktop dashboard status tab-rail single-line horizontal
alignment (anti-apilación) without overflowing controls.
Narrow mobile viewports (320x711, 360x800, 390x844) are covered by test_oppo_a74_responsive.py
and test_browser_phase39_workflow.py.
"""

from decimal import Decimal

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse

from inventory.models import Product, ProductStatus
from tests.helpers import (
    abort_nonessential_fonts,
    create_user_with_group,
    get_test_artifact_dir,
    start_shared_browser,
)


@override_settings(TURNSTILE_ENABLED=False)
class DashboardResponsiveUITests(StaticLiveServerTestCase):
    """Verify dashboard status tab bar stays single-line across tablet & desktop viewports."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.artifacts_dir = get_test_artifact_dir(cls, repo_subdir="browser_verification_screenshots")
        cls._browser = start_shared_browser(cls)

    def setUp(self):
        self.manager = create_user_with_group("testmanager", group_name="managers", is_staff=True)

        long_titles = [
            "Ultra Long Vintage Leather Jacket With Intricate Floral Embroidery",
            "Mid-Century Modern Scandinavian Teak Lounge Chair With Cushions",
            "Authentic 1990s Nintendo Game Boy Color Complete In Box With Games",
            "Heavy Duty Cast Iron Dutch Oven Enamel Coated Red Classic Edition",
            "Signed Limited Edition Screenprint Poster Framed Archival Quality",
        ]
        statuses = [
            ProductStatus.DRAFT,
            ProductStatus.PRICE_PENDING,
            ProductStatus.READY,
            ProductStatus.PUBLISHED,
            ProductStatus.AWAITING_INFO,
        ]

        for idx, (title, st) in enumerate(zip(long_titles, statuses)):
            Product.objects.create(
                ai_title=title,
                ai_description="Sample condition report description for verification test.",
                raw_note=f"Item {idx} raw field note",
                sale_price=Decimal("45.00") if st != ProductStatus.PRICE_PENDING else None,
                status=st,
                created_by=self.manager,
            )

    def test_dashboard_tabs_horizontal_alignment_tablet_and_desktop(self):
        """
        Verify status navigation tabs sit cleanly on a single line (no multi-line wrapping)
        and the main document does not horizontally overflow across 768px..1440px viewports.
        """
        viewports = [
            ("tablet_768x1024", 768, 1024),
            ("small_desktop_1024x768", 1024, 768),
            ("desktop_1440x900", 1440, 900),
        ]

        with self._browser.new_context(viewport={"width": 1280, "height": 800}) as context:
            page = context.new_page()
            abort_nonessential_fonts(page)

            page.goto(f"{self.live_server_url}{reverse('inventory:login')}")
            page.wait_for_selector("#id_username")
            page.fill("#id_username", "testmanager")
            page.fill("#id_password", "password123")
            with page.expect_navigation():
                page.click("#loginSubmitBtn")
            page.wait_for_selector('nav[role="tablist"]')

            for label, width, height in viewports:
                page.set_viewport_size({"width": width, "height": height})

                self.assertTrue(page.locator("#palletFilterForm").is_visible(), f"Pallet filter form must be visible at {label}")
                self.assertTrue(
                    page.locator("#dashboardResultsBar").is_visible(),
                    f"Results bar must be visible at {label}",
                )
                selector = page.locator("#perPageSelector")
                self.assertTrue(selector.is_visible(), f"Page size selector must be visible at {label}")
                selector_box = selector.bounding_box()
                self.assertIsNotNone(selector_box)
                self.assertLessEqual(
                    selector_box["x"] + selector_box["width"],
                    width + 1,
                    f"Page size selector overflows viewport at {label}",
                )

                if width >= 1024:
                    overflow = page.evaluate(
                        "() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"
                    )
                    self.assertFalse(overflow, f"Horizontal overflow detected on dashboard at {label}")

                tablist = page.locator('nav[role="tablist"]')
                self.assertTrue(tablist.is_visible(), f"Status tablist must be visible at {label}")
                self.assertTrue(page.locator("#tab-ready").count() > 0, f"Ready to Publish tab must exist at {label}")

                tabs = tablist.locator('a[role="tab"]').all()
                self.assertGreaterEqual(len(tabs), 5, f"Expected at least 5 status tabs at {label}")

                box_0 = tabs[0].bounding_box()
                self.assertIsNotNone(box_0)
                first_top = box_0["y"]
                for i, tab in enumerate(tabs):
                    box = tab.bounding_box()
                    self.assertIsNotNone(box)
                    self.assertAlmostEqual(
                        box["y"],
                        first_top,
                        delta=4.0,
                        msg=f"Tab {i} at {label} is vertically stacked / apilado! box.y={box['y']} vs first_top={first_top}",
                    )
                    self.assertGreaterEqual(box["height"], 32.0, f"Touch target height too small at {label}")

                screenshot_path = self.artifacts_dir / f"dashboard_{label}.png"
                page.screenshot(path=str(screenshot_path))
                self.assertTrue(screenshot_path.exists())
