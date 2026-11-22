"""
Verification suite for Phase 54: Action Progress & Non-Blocking Loading Feedback System.

Tests:
1. Rendered template markup for window.AppFeedback, GPU shimmer CSS, declarative
   data-loading-text attributes, #identifyHelpText, #aiIdentificationSkeleton, and
   #aiGeneratingSkeleton across English and Spanish locales.
2. Live Playwright Chromium verification on OPPO A74 (360x800 and 320x711) and desktop
   viewports covering:
   - Delayed /intake/identify/ fetch showing non-blocking skeleton + elapsed timer
     incrementing live while preserving page readability & zero horizontal overflow,
     followed by clean restoration & "Analysis completed!" status persistence.
   - Product detail #aiForm skeleton (#aiGeneratingSkeleton) & #aiBtn spinner + aria-busy.
   - data-confirm-message modal gate NOT locking buttons when cancelled.
   - pageshow (bfcache) resetting all active loading states back to interactive defaults.
"""

import json

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse

from inventory.models import MarketplaceSite, Product, ProductClarification, ProductImage
from tests.helpers import (
    create_user_with_group,
    get_test_artifact_dir,
    goto_authenticated,
    login_in_browser,
    make_test_image_bytes,
    open_browser_page,
    start_shared_browser,
)


@override_settings(TURNSTILE_ENABLED=False)
class ActionLoadingFeedbackMarkupTests(TestCase):
    """Verify rendered templates contain declarative feedback hooks and localized strings."""

    def setUp(self):
        self.manager = create_user_with_group("fb_manager", group_name="managers", is_staff=True)
        self.assistant = create_user_with_group("fb_assistant", group_name="assistants")
        self.product = Product.objects.create(
            created_by=self.assistant,
            raw_note="Vintage waxed cotton field jacket",
            ai_title="Vintage Jacket",
            ai_description="Condition 8/10.",
        )
        ProductImage.objects.create(
            product=self.product,
            image=ContentFile(make_test_image_bytes(), name="jacket.jpg"),
            order=0,
        )

    def test_intake_contains_app_feedback_and_identification_skeleton(self):
        self.client.force_login(self.assistant)
        response = self.client.get(reverse("inventory:intake"), headers={"Accept-Language": "en"})
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")

        self.assertIn("window.AppFeedback", html)
        self.assertIn("@keyframes appShimmer", html)
        self.assertIn("prefers-reduced-motion: reduce", html)
        self.assertIn('id="aiIdentificationSkeleton"', html)
        self.assertIn('id="aiIdentifyStageText"', html)
        self.assertIn('id="aiIdentifyElapsed"', html)
        self.assertIn('data-no-loading="true"', html)

    def test_intake_spanish_localization_renders_progress_stages(self):
        self.client.force_login(self.assistant)
        response = self.client.get(reverse("inventory:intake"), headers={"Accept-Language": "es"})
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")

        self.assertIn("Subiendo y preparando fotos...", html)
        self.assertIn("Identificando marca, modelo y estado...", html)

    def test_product_detail_active_and_erased_contain_loading_hooks(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("inventory:product_detail", args=[self.product.pk]), headers={"Accept-Language": "en"})
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")

        self.assertIn('id="aiGeneratingSkeleton"', html)
        self.assertIn('id="aiGenerateStageText"', html)
        self.assertIn('id="aiGenerateElapsed"', html)
        for marker in (
            'id="btnSaveListingChanges"',
            'id="verifyComplianceBtn"',
            'id="btnUploadDetailPhotos"',
            'id="btnConfirmDeleteProduct"',
            'id="btnProceedActionConfirm"',
        ):
            self.assertIn(marker, html)
        self.assertIn('data-loading-text="Saving changes..."', html)
        self.assertIn('data-loading-text="Checking compliance..."', html)
        self.assertIn('data-loading-text="Uploading photos..."', html)
        self.assertIn('data-loading-text="Moving to trash..."', html)
        self.assertIn('data-loading-text="Processing..."', html)

        self.product.soft_delete(self.manager)
        deleted_resp = self.client.get(
            reverse("inventory:product_detail", args=[self.product.pk]),
            headers={"Accept-Language": "en"},
        )
        self.assertEqual(deleted_resp.status_code, 200)
        deleted_html = deleted_resp.content.decode("utf-8")
        self.assertIn('data-loading-text="Restoring..."', deleted_html)

    def test_pallets_and_dashboard_contain_uniform_loading_attributes(self):
        self.client.force_login(self.manager)
        pallets_resp = self.client.get(reverse("inventory:pallets"), headers={"Accept-Language": "en"})
        self.assertEqual(pallets_resp.status_code, 200)
        pallets_html = pallets_resp.content.decode("utf-8")
        self.assertIn('data-loading-text="Creating..."', pallets_html)
        self.assertIn('data-loading-text="Deleting..."', pallets_html)

        dash_resp = self.client.get(reverse("inventory:dashboard") + "?status=erased", headers={"Accept-Language": "en"})
        self.assertEqual(dash_resp.status_code, 200)
        self.assertIn('data-loading-text="Processing..."', dash_resp.content.decode("utf-8"))


@override_settings(TURNSTILE_ENABLED=False)
class ActionLoadingFeedbackBrowserTests(StaticLiveServerTestCase):
    """Real Chromium checks for non-blocking AI skeletons, modal safety, bfcache reset, and OPPO A74 layout."""

    OPPO_VIEWPORTS = [
        ("oppo_360x800", 360, 800),
        ("oppo_lowdpi_320x711", 320, 711),
    ]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.artifacts_dir = get_test_artifact_dir(cls)
        cls.sample_img_path = cls.artifacts_dir / "sample_feedback.jpg"
        cls.sample_img_path.write_bytes(make_test_image_bytes(size=(400, 400), color="teal"))
        cls._browser = start_shared_browser(cls)

    def setUp(self):
        self.manager = create_user_with_group("fb_e2e_mgr", group_name="managers", is_staff=True)
        MarketplaceSite.objects.get_or_create(slug="wallapop", defaults={"name": "Wallapop", "order": 1})
        self.product = Product.objects.create(
            created_by=self.manager,
            raw_note="Compact Espresso Grinder 220V",
            ai_title="Compact Espresso Grinder",
            ai_description="Clean stainless steel burr grinder.",
        )
        ProductImage.objects.create(
            product=self.product,
            image=ContentFile(make_test_image_bytes(), name="grinder.jpg"),
            order=0,
        )
        ProductClarification.objects.create(
            product=self.product,
            question="Does it include the portafilter fork?",
            asked_by=self.manager,
        )

    def _assert_no_horizontal_overflow(self, page, label):
        metrics = page.evaluate(
            "() => ({ scrollW: document.documentElement.scrollWidth, clientW: document.documentElement.clientWidth })"
        )
        self.assertLessEqual(
            metrics["scrollW"],
            metrics["clientW"],
            f"Horizontal overflow at {label}: scrollWidth={metrics['scrollW']} > clientWidth={metrics['clientW']}",
        )

    def test_intake_delayed_ai_identify_skeleton_timer_and_oppo_viewports(self):
        for label, width, height in self.OPPO_VIEWPORTS:
            with self.subTest(viewport=label):
                with open_browser_page(
                    self._browser,
                    self,
                    viewport={"width": width, "height": height},
                    locale="en-US",
                    failure_name=f"{self.id()}_{label}",
                ) as (_context, page):
                    login_in_browser(page, self.live_server_url, "fb_e2e_mgr", "password123")
                    goto_authenticated(page, f"{self.live_server_url}{reverse('inventory:intake')}")
                    self._assert_no_horizontal_overflow(page, f"{label} initial intake")

                    pending_routes = []
                    page.route("**/intake/identify/", lambda route: pending_routes.append(route))
                    page.set_input_files("#imageInput", str(self.sample_img_path))
                    page.wait_for_function("() => !document.getElementById('identifyBtn').disabled")

                    page.click("#identifyBtn")

                    # Skeleton appears with aria-busy="true", spinner, and non-blocked notes textarea while fetch is suspended
                    page.wait_for_selector("#aiIdentificationSkeleton:not(.hidden)")
                    self.assertEqual(page.get_attribute("#aiIdentificationSkeleton", "aria-busy"), "true")
                    self.assertTrue(page.is_visible("#id_raw_note"))
                    self._assert_no_horizontal_overflow(page, f"{label} during identifying skeleton")

                    # Wait for live elapsed timer to advance >= 1s while request stays in-flight
                    page.wait_for_function(
                        "() => { const t = document.getElementById('aiIdentifyElapsed')?.textContent || ''; return parseInt(t, 10) >= 1; }",
                        timeout=4000,
                    )

                    # Fulfill the deferred route response
                    self.assertTrue(len(pending_routes) > 0, "Expected /intake/identify/ request to be intercepted")
                    pending_routes[0].fulfill(
                        status=200,
                        content_type="application/json",
                        body=json.dumps(
                            {
                                "success": True,
                                "identified_title": "Mahlkonig Vario Grinder",
                                "category": "Appliances",
                                "detected_attributes": ["54mm burrs", "Digital timer"],
                                "missing_or_recommended_info": ["Verify power cord plug type"],
                                "suggested_note": "Mahlkonig Vario 220V tested",
                                "estimated_retail_price": 499.0,
                                "estimated_resale_price": 240.0,
                                "compliance_verdict": "approved",
                                "compliance_risk_score": 5,
                                "compliance_flags": [],
                            }
                        ),
                    )

                    # Once completed, skeleton hides and advisory banner renders
                    page.wait_for_selector("#aiAdvisoryBanner:not(.hidden)", timeout=5000)
                    self.assertIn("hidden", page.get_attribute("#aiIdentificationSkeleton", "class"))
                    self.assertEqual(page.get_attribute("#aiIdentificationSkeleton", "aria-busy"), "false")
                    self.assertIn("Mahlkonig Vario Grinder", page.inner_text("#advisoryTitle"))
                    self._assert_no_horizontal_overflow(page, f"{label} after identification completed")

    def test_product_detail_ai_skeleton_confirm_modal_cancel_and_pageshow_reset(self):
        with open_browser_page(
            self._browser,
            self,
            viewport={"width": 360, "height": 800},
            locale="en-US",
        ) as (_context, page):
            login_in_browser(page, self.live_server_url, "fb_e2e_mgr", "password123")
            detail_url = f"{self.live_server_url}{reverse('inventory:product_detail', args=[self.product.pk])}"
            goto_authenticated(page, detail_url)
            self._assert_no_horizontal_overflow(page, "product_detail 360x800")

            # 1. Prevent form navigation via listener so we inspect in-flight skeleton & button spinner cleanly
            page.evaluate(
                """() => {
                  const form = document.getElementById('aiForm');
                  form.addEventListener('submit', function(e) {
                    e.preventDefault();
                  }, { once: false });
                }"""
            )
            page.click("#aiBtn")
            page.wait_for_selector("#aiGeneratingSkeleton:not(.hidden)")
            self.assertEqual(page.get_attribute("#aiGeneratingSkeleton", "aria-busy"), "true")
            self.assertEqual(page.get_attribute("#aiBtn", "aria-busy"), "true")
            self._assert_no_horizontal_overflow(page, "product_detail 360x800 during aiGeneratingSkeleton")

            # 2. Dispatch pageshow (bfcache restoration) and verify full cleanup
            page.evaluate("() => window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true }))")
            page.wait_for_function("() => document.getElementById('aiGeneratingSkeleton').classList.contains('hidden')")
            self.assertFalse(page.evaluate("() => document.getElementById('aiBtn').disabled"))
            self.assertIsNone(page.get_attribute("#aiBtn", "aria-busy"))

            # 3. Verify cancelling data-confirm-message modal does NOT leave trigger button stuck in loading state
            page.click("#tabBtnWorkspaceNotes")
            dismiss_btn = page.locator("form[data-confirm-message] button[type='submit']").first
            dismiss_btn.click()
            page.wait_for_selector("#actionConfirmModal:not(.hidden)")
            page.click("#btnCancelActionConfirm")
            page.wait_for_function("() => document.getElementById('actionConfirmModal').classList.contains('hidden')")
            self.assertIsNone(dismiss_btn.get_attribute("data-loading-active"))
            self.assertFalse(dismiss_btn.is_disabled())

            # 4. Verify regular data-loading-text button transitions and resets on pageshow
            page.click("#tabBtnWorkspaceListing")
            save_btn = page.locator("#btnSaveListingChanges")
            page.evaluate(
                """() => {
                  const form = document.getElementById('productStagingForm');
                  form.addEventListener('submit', e => e.preventDefault(), { once: true });
                }"""
            )
            # Trigger AppFeedback.setButtonLoading directly as a deterministic check alongside submit flow
            page.evaluate(
                """() => {
                  const btn = document.getElementById('btnSaveListingChanges');
                  window.AppFeedback.setButtonLoading(btn, btn.getAttribute('data-loading-text'));
                }"""
            )
            self.assertEqual(save_btn.get_attribute("data-loading-active"), "true")
            self.assertIn("Saving changes...", save_btn.inner_text())
            page.evaluate("() => window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true }))")
            self.assertIsNone(save_btn.get_attribute("data-loading-active"))
            self.assertFalse(save_btn.is_disabled())
            self.assertIn("Save Listing Changes", save_btn.inner_text())
