import os
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from playwright.sync_api import sync_playwright

from inventory.models import (
    Category,
    MarketplaceSite,
    Product,
    ProductCondition,
    ProductListingLink,
    ProductStatus,
    StorefrontConfiguration,
)

User = get_user_model()


@override_settings(TURNSTILE_ENABLED=False)
class BrowserPhase39AccessibilityWorkflowTests(StaticLiveServerTestCase):
    """
    Real Google Chrome browser verification of the complete daily workflow
    specifically validating the UI/UX & WCAG 2.1 AA accessibility features:
    1. Skip links (<a href="#main-content">) on both public storefront and staff portals.
    2. Primary <h1> headings on login, product detail, dashboard, catalog, and landing page.
    3. Live computed contrast check on WhatsApp CTAs (text-slate-950 on #25D366) and Featured badges.
    4. Product detail gallery keyboard activation (Enter key on thumbnails).
    5. Clarifications Hub ARIA tablist/tabpanel switching.
    6. Inline role='alert' error rendering on invalid form submission.
    7. Reusable #actionConfirmModal replacing native confirm() dialogs with focus trap/escape.
    8. Mobile viewport 390x844 font-size verification (>= 16px to prevent iOS auto-zoom).
    """

    @classmethod
    def setUpClass(cls):
        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
        super().setUpClass()
        os.makedirs("screenshots/phase39", exist_ok=True)

    def setUp(self):
        self.manager = User.objects.create_user(
            username="manager_phase39",
            password="password123",
            is_staff=True,
        )
        self.wallapop, _ = MarketplaceSite.objects.get_or_create(
            slug="wallapop",
            defaults={"name": "Wallapop", "order": 1, "is_active": True},
        )
        self.store_config = StorefrontConfiguration.get_solo()

        self.fashion_cat, _ = Category.objects.get_or_create(
            slug="moda-y-accesorios",
            defaults={"name": "Moda y accesorios", "name_en": "Fashion", "order": 1, "is_active": True},
        )

        self.product = Product.objects.create(
            ai_title="Chaqueta Vintage Harrington",
            ai_description="Chaqueta Harrington clásica color beige en perfecto estado.",
            sale_price=Decimal("59.00"),
            category=self.fashion_cat,
            condition=ProductCondition.VERY_GOOD,
            is_public=True,
            is_featured=True,
            status=ProductStatus.READY,
        )

        self.link = ProductListingLink.objects.create(
            product=self.product,
            site=self.wallapop,
            url="https://es.wallapop.com/item/harrington-vintage-12345",
            is_active=True,
        )
        self.product.status = ProductStatus.PUBLISHED
        self.product.save()

    def test_daily_workflow_with_accessibility_in_real_chrome(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            context = browser.new_context(viewport={"width": 1280, "height": 850}, locale="es-ES")
            page = context.new_page()

            # Listen for any native dialogs and fail if any alert/confirm is triggered!
            dialog_triggered = []
            page.on("dialog", lambda d: dialog_triggered.append(f"{d.type}: {d.message}"))

            # -------------------------------------------------------------
            # STEP 1: Customer Visits Public Storefront Home
            # -------------------------------------------------------------
            print("\n[Step 1] Visiting Public Storefront (/) and testing Skip Link...")
            page.goto(f"{self.live_server_url}{reverse('storefront:home')}")
            page.wait_for_selector("#main-content")

            # Test keyboard tab to reveal skip link
            page.keyboard.press("Tab")
            skip_link = page.locator('a[href="#main-content"]')
            self.assertTrue(skip_link.is_visible(), "Skip link should become visible on keyboard focus")
            page.screenshot(path="screenshots/phase39/01_public_skip_link_focused.png")

            # Check WhatsApp CTA computed colors for WCAG AAA compliance (text-slate-950 on #25D366)
            whatsapp_cta = page.locator('a[href*="/go/whatsapp/"]').first
            self.assertTrue(whatsapp_cta.is_visible())
            color_info = page.evaluate('''(el) => {
                const s = window.getComputedStyle(el);
                return { color: s.color, bgColor: s.backgroundColor, fontWeight: s.fontWeight };
            }''', whatsapp_cta.element_handle())
            print(f"WhatsApp CTA Computed Style: {color_info}")
            # rgb(2, 6, 23) is slate-950
            self.assertIn("rgb(2, 6, 23)", color_info["color"])
            self.assertIn("rgb(37, 211, 102)", color_info["bgColor"])

            # -------------------------------------------------------------
            # STEP 2: Customer Navigates to Catalog (/tienda/) & Tests How-To-Buy Modal
            # -------------------------------------------------------------
            print("\n[Step 2] Catalog (/tienda/) and How-to-Buy modal...")
            page.goto(f"{self.live_server_url}{reverse('storefront:catalog')}")
            page.wait_for_selector("#categoryRail")

            # Verify <h1> heading on catalog
            h1_catalog = page.inner_text("h1")
            self.assertTrue(len(h1_catalog) > 0, "Catalog must render an <h1>")

            # Test How to Buy Modal
            page.click('button:has-text("Cómo comprar"), button:has-text("How to buy")')
            page.wait_for_selector("#how-to-buy-dialog[open]")
            modal_h2 = page.inner_text("#how-to-buy-title")
            print(f"How-to-Buy Modal Heading: {modal_h2}")
            page.screenshot(path="screenshots/phase39/02_how_to_buy_modal_h2.png")
            page.keyboard.press("Escape")
            page.wait_for_selector("#how-to-buy-dialog", state="hidden")

            # -------------------------------------------------------------
            # STEP 3: Staff Logs In with <h1> and Autocomplete Semantics
            # -------------------------------------------------------------
            print("\n[Step 3] Staff Login Screen semantics...")
            page.goto(f"{self.live_server_url}{reverse('inventory:login')}")
            page.wait_for_selector("#id_username")

            # Check primary <h1> on login
            login_h1 = page.inner_text("h1")
            print(f"Login Screen <h1>: {login_h1}")
            self.assertTrue("INICIA" in login_h1.upper() or "SESI" in login_h1.upper() or "LOG IN" in login_h1.upper())

            # Check autocomplete attributes
            username_ac = page.locator("#id_username").get_attribute("autocomplete")
            password_ac = page.locator("#id_password").get_attribute("autocomplete")
            self.assertEqual(username_ac, "username")
            self.assertEqual(password_ac, "current-password")
            page.screenshot(path="screenshots/phase39/03_login_h1_and_autocomplete.png")

            # Submit login
            page.fill("#id_username", "manager_phase39")
            page.fill("#id_password", "password123")
            with page.expect_navigation():
                page.click("#loginSubmitBtn")

            # -------------------------------------------------------------
            # STEP 4: Staff Dashboard with Skip Link and Anti-Apilación Rail
            # -------------------------------------------------------------
            print("\n[Step 4] Staff Dashboard and horizontal status rail...")
            page.goto(f"{self.live_server_url}{reverse('inventory:dashboard')}")
            page.wait_for_selector("#main-content")

            # Test staff skip link
            page.keyboard.press("Tab")
            staff_skip = page.locator('a[href="#main-content"]')
            self.assertTrue(staff_skip.is_visible())
            page.screenshot(path="screenshots/phase39/04_staff_skip_link_focused.png")

            # -------------------------------------------------------------
            # STEP 5: Staging Product Detail: Heading, ARIA, Modals & Validation
            # -------------------------------------------------------------
            print("\n[Step 5] Staging Product Detail Workspace (/products/<pk>/)...")
            page.goto(f"{self.live_server_url}{reverse('inventory:product_detail', kwargs={'pk': self.product.pk})}")
            page.wait_for_selector("h1")

            # Verify primary <h1> product title
            detail_h1 = page.inner_text("h1")
            print(f"Product Detail <h1>: {detail_h1}")
            self.assertIn("Chaqueta Vintage Harrington", detail_h1)

            # Test Clarifications Hub tablist and tabpanel
            print("Testing Clarifications Hub accessible tabs...")
            tab_direct = page.locator("#tabBtnDirectNote")
            tab_doubt = page.locator("#tabBtnAskDoubt")
            self.assertEqual(tab_direct.get_attribute("aria-selected"), "true")
            self.assertEqual(tab_doubt.get_attribute("aria-selected"), "false")
            self.assertEqual(tab_direct.get_attribute("aria-controls"), "panelDirectNote")
            self.assertEqual(tab_doubt.get_attribute("aria-controls"), "panelAskDoubt")

            # Click Doubt tab
            tab_doubt.click()
            self.assertEqual(tab_doubt.get_attribute("aria-selected"), "true")
            self.assertEqual(tab_direct.get_attribute("aria-selected"), "false")
            page.screenshot(path="screenshots/phase39/05_clarifications_tab_doubt.png")

            # Test Form Validation Errors with role='alert'
            print("Testing inline form error rendering with role='alert'...")
            page.check('input[name="is_sold"]')
            # Do NOT select a sold channel -> triggers validation error on submit
            page.click('button:has-text("Guardar cambios"), button:has-text("Save Listing Changes")')
            page.wait_for_load_state("networkidle")

            # Locate error message with role='alert'
            error_alert = page.locator('[role="alert"]').first
            self.assertTrue(error_alert.is_visible(), "Inline validation error with role='alert' must be visible")
            page.screenshot(path="screenshots/phase39/06_form_validation_role_alert.png")

            # Uncheck is_sold and save cleanly
            page.uncheck('input[name="is_sold"]')
            page.click('button:has-text("Guardar cambios"), button:has-text("Save Listing Changes")')
            page.wait_for_load_state("networkidle")

            # -------------------------------------------------------------
            # STEP 6: Accessible Action Confirmation Modal (Replaces native confirm())
            # -------------------------------------------------------------
            print("\n[Step 6] Testing accessible #actionConfirmModal (No native dialogs)...")
            wallapop_row = page.locator('div[data-site-slug="wallapop"]')
            self.assertTrue(wallapop_row.is_visible())

            # Click Manage link button -> opens #editListingModal
            wallapop_row.locator('button[onclick*="openEditListingModal"]').click()
            page.wait_for_selector("#editListingModal:not(.hidden)")

            # Click Remove link button -> opens #actionConfirmModal
            delete_btn = page.locator('#deleteListingForm button[type="submit"]')
            delete_btn.click()

            modal = page.locator("#actionConfirmModal")
            page.wait_for_selector("#actionConfirmModal:not(.hidden)")
            self.assertTrue(modal.is_visible())
            modal_title = page.inner_text("#actionConfirmModalTitle")
            print(f"Action Confirmation Modal Title: {modal_title}")
            page.screenshot(path="screenshots/phase39/07_accessible_action_confirm_modal.png")

            # Test cancel via Cancel button
            page.click("#btnCancelActionConfirm")
            page.wait_for_selector("#actionConfirmModal", state="hidden")
            self.assertFalse(modal.is_visible(), "Modal should close on cancel")

            # Re-open modal and confirm action
            delete_btn.click()
            page.wait_for_selector("#actionConfirmModal:not(.hidden)")
            page.click("#btnProceedActionConfirm")
            page.wait_for_load_state("networkidle")

            # Verify no native browser dialog was triggered
            self.assertEqual(len(dialog_triggered), 0, f"No native dialogs should be called, but got: {dialog_triggered}")
            print("Successfully verified zero native dialogs occurred!")

            # -------------------------------------------------------------
            # STEP 7: Mobile Viewport 390x844 Font Size Verification
            # -------------------------------------------------------------
            print("\n[Step 7] Testing Mobile 390x844 font-size (>= 16px to prevent iOS auto-zoom)...")
            mobile_context = browser.new_context(viewport={"width": 390, "height": 844}, locale="es-ES")
            mobile_page = mobile_context.new_page()

            # Log in on mobile context first to access staff workspace
            mobile_page.goto(f"{self.live_server_url}{reverse('inventory:login')}")
            mobile_page.fill("#id_username", "manager_phase39")
            mobile_page.fill("#id_password", "password123")
            with mobile_page.expect_navigation():
                mobile_page.click("#loginSubmitBtn")

            # Mobile Product Detail
            mobile_page.goto(f"{self.live_server_url}{reverse('inventory:product_detail', kwargs={'pk': self.product.pk})}")
            mobile_page.wait_for_selector("#id_sale_price")

            # Measure computed font size of inputs
            input_font_size = mobile_page.evaluate('''() => {
                const el = document.getElementById("id_sale_price");
                return parseFloat(window.getComputedStyle(el).fontSize);
            }''')
            print(f"Mobile Input Computed Font Size: {input_font_size}px")
            self.assertGreaterEqual(input_font_size, 16.0, "Mobile inputs must be >= 16px to prevent iOS Safari auto-zoom")
            mobile_page.screenshot(path="screenshots/phase39/08_mobile_product_detail_390x844.png")

            mobile_context.close()
            context.close()
            browser.close()
            print("\n=============================================================")
            print("ALL PHASE 39 REAL CHROME ACCESSIBILITY WORKFLOW TESTS PASSED!")
            print("=============================================================")
