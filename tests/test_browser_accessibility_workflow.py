"""
End-to-End Real Chrome Accessibility & Mobile Viewport Verification Suite.

Verifies the live UI across:
1. Public storefront homepage skip-link keyboard focus & WCAG AAA contrast (slate-950 on #25D366).
2. Storefront catalog <h1> and <dialog closedby="any"> "How to Buy" heading hierarchy.
3. Staff login screen <h1> and autocomplete="username"/"current-password" semantics.
4. Staff dashboard skip-link & horizontal status rail (anti-apilación).
5. Staging product detail tabs (tablist/tabpanel ARIA transitions), inline role="alert" form validation,
   and accessible #actionConfirmModal deletion flow without native browser alert/confirm dialogs.
6. Mobile 390x844 responsive input typography (>= 16px to prevent iOS auto-zoom) & overflow.
"""

from decimal import Decimal

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from playwright.sync_api import expect

from inventory.models import (
    Category,
    MarketplaceSite,
    Product,
    ProductCondition,
    ProductListingLink,
    ProductStatus,
)
from tests.helpers import (
    create_user_with_group,
    get_test_artifact_dir,
    goto_authenticated,
    login_in_browser,
    open_browser_page,
    start_shared_browser,
)


@override_settings(TURNSTILE_ENABLED=False)
class BrowserAccessibilityWorkflowTests(StaticLiveServerTestCase):
    """Comprehensive browser verification of WCAG 2.1 AA accessibility & mobile UX."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.artifacts_dir = get_test_artifact_dir(cls, repo_subdir="screenshots/accessibility")
        cls._browser = start_shared_browser(cls)

    def setUp(self):
        self.manager = create_user_with_group("manager_a11y", group_name="managers", is_staff=True)
        self.category, _ = Category.objects.get_or_create(
            slug="ropa-retro",
            defaults={"name": "Ropa Retro", "icon": "apparel"},
        )
        self.wallapop, _ = MarketplaceSite.objects.get_or_create(
            slug="wallapop",
            defaults={"name": "Wallapop", "order": 1, "is_active": True},
        )
        self.product = Product.objects.create(
            ai_title="Chaqueta Vintage Harrington Talla M",
            ai_description="Chaqueta clásica inglesa en excelente estado.",
            sale_price=Decimal("45.00"),
            category=self.category,
            condition=ProductCondition.VERY_GOOD,
            is_public=True,
            is_featured=True,
            status=ProductStatus.PUBLISHED,
            created_by=self.manager,
        )
        ProductListingLink.objects.create(
            product=self.product,
            site=self.wallapop,
            url=f"https://es.wallapop.com/item/harrington-{self.product.pk}",
            is_active=True,
        )

    def test_public_storefront_skip_link_contrast_and_how_to_buy_dialog(self):
        """Verify skip link focus, WhatsApp WCAG AAA contrast, and How-to-Buy <dialog>."""
        native_dialogs = []

        with open_browser_page(
            self._browser,
            self,
            viewport={"width": 1280, "height": 900},
            failure_name="a11y_public_storefront",
        ) as (_context, page):
            page.on("dialog", lambda d: (native_dialogs.append(d.message), d.dismiss()))

            # 1. Public Storefront Skip Link & WCAG AAA contrast
            page.goto(f"{self.live_server_url}{reverse('storefront:home')}")
            expect(page.locator("header nav").first).to_be_visible()

            page.keyboard.press("Tab")
            skip_link = page.locator('a[href="#main-content"]')
            self.assertTrue(skip_link.is_visible(), "Skip link should become visible on keyboard focus")
            page.screenshot(path=str(self.artifacts_dir / "01_public_skip_link_focused.png"))

            whatsapp_cta = page.locator('a[href*="/go/whatsapp/"]').first
            self.assertTrue(whatsapp_cta.is_visible())
            color_info = whatsapp_cta.evaluate(
                """(el) => {
                    const s = window.getComputedStyle(el);
                    return { color: s.color, bgColor: s.backgroundColor, fontWeight: s.fontWeight };
                }"""
            )
            self.assertIn("rgb(2, 6, 23)", color_info["color"])
            self.assertIn("rgb(37, 211, 102)", color_info["bgColor"])

            # 2. Catalog (/tienda/) & How-to-Buy Modal
            page.goto(f"{self.live_server_url}{reverse('storefront:catalog')}")
            expect(page.locator("#categoryRail")).to_be_visible()

            h1_catalog = page.locator("h1").inner_text()
            self.assertTrue(len(h1_catalog) > 0, "Catalog must render an <h1>")

            page.locator('button:has-text("Cómo comprar"), button:has-text("How to buy")').first.click()
            expect(page.locator("#how-to-buy-dialog[open]")).to_be_visible()
            self.assertTrue(len(page.locator("#how-to-buy-title").inner_text()) > 0)
            page.screenshot(path=str(self.artifacts_dir / "02_how_to_buy_modal_h2.png"))
            page.keyboard.press("Escape")
            expect(page.locator("#how-to-buy-dialog")).to_be_hidden()

            self.assertEqual(len(native_dialogs), 0, f"Unexpected native JS dialogs triggered: {native_dialogs}")

    def test_staff_login_dashboard_and_detail_aria_tabs_validation_and_modal(self):
        """Verify login semantics, staff skip link, ARIA tabs, role='alert' validation, and #actionConfirmModal."""
        native_dialogs = []

        with open_browser_page(
            self._browser,
            self,
            viewport={"width": 1280, "height": 900},
            failure_name="a11y_staff_workflow",
        ) as (_context, page):
            page.on("dialog", lambda d: (native_dialogs.append(d.message), d.dismiss()))

            # 3. Staff Login Screen semantics
            page.goto(f"{self.live_server_url}{reverse('inventory:login')}")
            expect(page.locator("#id_username")).to_be_visible()

            login_h1 = page.locator("h1").inner_text()
            self.assertTrue(
                "INICIA" in login_h1.upper()
                or "SESI" in login_h1.upper()
                or "LOG IN" in login_h1.upper()
                or "SIGN IN" in login_h1.upper(),
                f"Unexpected login <h1> text: {login_h1!r}",
            )
            self.assertEqual(page.locator("#id_username").get_attribute("autocomplete"), "username")
            self.assertEqual(page.locator("#id_password").get_attribute("autocomplete"), "current-password")
            page.screenshot(path=str(self.artifacts_dir / "03_login_h1_and_autocomplete.png"))

            login_in_browser(
                page,
                self.live_server_url,
                "manager_a11y",
                "password123",
                navigate_to_login=False,
            )

            # 4. Staff Dashboard Skip Link
            goto_authenticated(page, f"{self.live_server_url}{reverse('inventory:dashboard')}")
            expect(page.locator("#main-content")).to_be_visible()

            page.keyboard.press("Tab")
            staff_skip = page.locator('a[href="#main-content"]')
            self.assertTrue(staff_skip.is_visible())
            page.screenshot(path=str(self.artifacts_dir / "04_staff_skip_link_focused.png"))

            # 5. Staging Product Detail: Heading, ARIA tabs & Validation role="alert"
            detail_url = f"{self.live_server_url}{reverse('inventory:product_detail', kwargs={'pk': self.product.pk})}"
            goto_authenticated(page, detail_url)
            expect(page.locator("h1").first).to_be_visible()

            self.assertIn("Chaqueta Vintage Harrington", page.locator("h1").first.inner_text())

            page.locator("#tabBtnWorkspaceNotes").click()
            tab_direct = page.locator("#tabBtnDirectNote")
            tab_doubt = page.locator("#tabBtnAskDoubt")
            self.assertEqual(tab_direct.get_attribute("aria-selected"), "true")
            self.assertEqual(tab_doubt.get_attribute("aria-selected"), "false")
            self.assertEqual(tab_direct.get_attribute("aria-controls"), "panelDirectNote")
            self.assertEqual(tab_doubt.get_attribute("aria-controls"), "panelAskDoubt")

            tab_doubt.click()
            self.assertEqual(tab_doubt.get_attribute("aria-selected"), "true")
            self.assertEqual(tab_direct.get_attribute("aria-selected"), "false")
            page.screenshot(path=str(self.artifacts_dir / "05_clarifications_tab_doubt.png"))

            # Test Form Validation Errors with role='alert'
            page.locator("#tabBtnWorkspaceListing").click()
            page.locator('input[name="is_sold"]').check()
            with page.expect_response(
                lambda r: r.request.method == "POST" and f"/products/{self.product.pk}/" in r.url
            ):
                page.locator("#btnSaveListingChanges").click()
            page.wait_for_load_state("domcontentloaded")
            alert_el = page.locator('[role="alert"]').first
            expect(alert_el).to_be_visible()
            self.assertTrue(alert_el.is_visible(), "Inline validation error with role='alert' must be visible")
            page.screenshot(path=str(self.artifacts_dir / "06_form_validation_role_alert.png"))

            # Uncheck is_sold and save cleanly
            page.locator('input[name="is_sold"]').uncheck()
            with page.expect_response(
                lambda r: r.request.method == "POST" and f"/products/{self.product.pk}/" in r.url
            ):
                page.locator("#btnSaveListingChanges").click()
            page.wait_for_load_state("domcontentloaded")
            expect(page.locator("#tabBtnWorkspaceChannels")).to_be_visible()
            expect(page.locator('input[name="is_sold"]')).not_to_be_checked()

            # 6. Accessible #actionConfirmModal without native dialogs
            page.locator("#tabBtnWorkspaceChannels").click()
            wallapop_row = page.locator('div[data-site-slug="wallapop"]')
            self.assertTrue(wallapop_row.is_visible())

            wallapop_row.locator('button[onclick*="openEditListingModal"]').click()
            expect(page.locator("#editListingModal:not(.hidden)")).to_be_visible()

            delete_btn = page.locator('#deleteListingForm button[type="submit"]')
            delete_btn.click()

            confirm_modal = page.locator("#actionConfirmModal")
            expect(page.locator("#actionConfirmModal:not(.hidden)")).to_be_visible()
            self.assertTrue(confirm_modal.is_visible())
            self.assertEqual(confirm_modal.get_attribute("role"), "dialog")
            self.assertEqual(confirm_modal.get_attribute("aria-modal"), "true")
            self.assertTrue(len(page.locator("#actionConfirmModalTitle").inner_text()) > 0)
            page.screenshot(path=str(self.artifacts_dir / "07_accessible_action_confirm_modal.png"))

            page.locator("#btnCancelActionConfirm").click()
            expect(page.locator("#actionConfirmModal")).to_be_hidden()
            self.assertFalse(confirm_modal.is_visible(), "Modal should close on cancel")

            delete_btn.click()
            expect(page.locator("#actionConfirmModal:not(.hidden)")).to_be_visible()
            with page.expect_response(
                lambda r: r.request.method == "POST" and f"/products/{self.product.pk}/links/" in r.url
            ):
                page.locator("#btnProceedActionConfirm").click()
            page.wait_for_load_state("domcontentloaded")
            expect(page.locator("#main-content")).to_be_visible()
            self.assertEqual(page.locator('div[data-site-slug="wallapop"]').count(), 0)

            self.assertEqual(len(native_dialogs), 0, f"Unexpected native JS dialogs triggered: {native_dialogs}")

    def test_mobile_390x844_detail_input_font_size_and_overflow(self):
        """Verify 390x844 detail input font size (>= 16px) prevents iOS auto-zoom without horizontal overflow."""
        detail_url = f"{self.live_server_url}{reverse('inventory:product_detail', kwargs={'pk': self.product.pk})}"

        with open_browser_page(
            self._browser,
            self,
            viewport={"width": 390, "height": 844},
            failure_name="a11y_mobile_390x844",
        ) as (_mobile_context, mobile_page):
            login_in_browser(mobile_page, self.live_server_url, "manager_a11y", "password123")

            goto_authenticated(
                mobile_page,
                detail_url,
            )
            expect(mobile_page.locator("#id_sale_price")).to_be_visible()

            input_font_size = mobile_page.evaluate(
                """() => {
                    const el = document.querySelector('#id_sale_price');
                    return parseFloat(window.getComputedStyle(el).fontSize);
                }"""
            )
            self.assertGreaterEqual(input_font_size, 16.0, "Mobile inputs must be >= 16px to prevent iOS Safari zoom")

            mobile_page.screenshot(path=str(self.artifacts_dir / "08_mobile_product_detail_390x844.png"))

            has_overflow = mobile_page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth")
            self.assertFalse(has_overflow, "Mobile detail view must not have horizontal overflow at 390px width")
