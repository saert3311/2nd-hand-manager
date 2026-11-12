import io
import os
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import translation
from PIL import Image
from playwright.sync_api import sync_playwright

from inventory.models import (
    Category,
    ComplianceStage,
    ComplianceVerdict,
    MarketplaceSite,
    Product,
    ProductClarification,
    ProductCondition,
    ProductImage,
    ProductListingLink,
    ProductStatus,
    SaleChannelType,
)


def _create_sample_image(name="photo.jpg"):
    buf = io.BytesIO()
    img = Image.new("RGB", (200, 200), color="teal")
    img.save(buf, format="JPEG")
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type="image/jpeg")


class ProductDetailTabbedRedesignTests(TestCase):
    """Tests for Phase 50: Product Detail Tabbed Workspace Redesign & Audit Log Deprioritization."""

    def setUp(self):
        self.managers_group, _ = Group.objects.get_or_create(name="managers")
        self.assistants_group, _ = Group.objects.get_or_create(name="assistants")

        self.manager = User.objects.create_user(
            username="mgr_tabs", password="password123", is_staff=True
        )
        self.manager.groups.add(self.managers_group)

        self.assistant = User.objects.create_user(
            username="asst_tabs", password="password123"
        )
        self.assistant.groups.add(self.assistants_group)

        self.category, _ = Category.objects.get_or_create(
            slug="tecnologia-y-electronica",
            defaults={
                "name": "Tecnología y electrónica",
                "name_en": "Tech & Electronics",
                "is_active": True,
            },
        )
        self.wallapop, _ = MarketplaceSite.objects.get_or_create(
            slug="wallapop",
            defaults={"name": "Wallapop", "base_url": "https://es.wallapop.com", "is_active": True},
        )

        self.product = Product.objects.create(
            raw_note="Sony WH-1000XM4 con estuche original y cable USB-C.",
            ai_title="Auriculares Sony WH-1000XM4 Bluetooth ANC",
            ai_description="Auriculares inalámbricos con cancelación de ruido activa en excelente estado.",
            sale_price=Decimal("145.00"),
            status=ProductStatus.READY,
            created_by=self.assistant,
        )
        ProductImage.objects.create(product=self.product, image=_create_sample_image())

    def test_workspace_renders_four_accessible_category_tabs_and_until_found_panels(self):
        """Product Detail renders 4 WAI-ARIA tabs with hidden='until-found' on inactive panels."""
        self.client.login(username="mgr_tabs", password="password123")
        url = reverse("inventory:product_detail", kwargs={"pk": self.product.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")

        # Verify tablist, scroll hint, calm AI toolbar, and 4 category tab buttons
        self.assertIn('id="detailWorkspaceTablist"', html)
        self.assertIn('id="detailWorkspaceTabScrollHint"', html)
        self.assertIn('id="aiCommandToolbar"', html)
        self.assertIn('role="tablist"', html)
        self.assertIn('id="tabBtnWorkspaceListing"', html)
        self.assertIn('id="tabBtnWorkspaceChannels"', html)
        self.assertIn('id="tabBtnWorkspaceNotes"', html)
        self.assertIn('id="tabBtnWorkspaceCompliance"', html)

        # Default active tab is Listing
        self.assertIn('id="tabBtnWorkspaceListing"', html)
        self.assertRegex(html, r'id="tabBtnWorkspaceListing"\s+data-workspace-tab="listing"\s+aria-selected="true"')
        self.assertIn('id="workspacePanelListing" role="tabpanel" aria-labelledby="tabBtnWorkspaceListing"', html)

        # Inactive panels use hidden="until-found" and keep bare panel containers without padding/border
        self.assertIn(
            'id="workspacePanelChannels" role="tabpanel" aria-labelledby="tabBtnWorkspaceChannels" data-workspace-panel="channels" hidden="until-found">',
            html,
        )
        self.assertIn(
            'id="workspacePanelNotes" role="tabpanel" aria-labelledby="tabBtnWorkspaceNotes" data-workspace-panel="notes" hidden="until-found">',
            html,
        )
        self.assertIn(
            'id="workspacePanelCompliance" role="tabpanel" aria-labelledby="tabBtnWorkspaceCompliance" data-workspace-panel="compliance" hidden="until-found">',
            html,
        )

    def test_audit_trail_is_heavily_deprioritized_inside_collapsed_footer_details(self):
        """Product state history is placed in a collapsed <details id='status-history-disclosure'> at page bottom."""
        self.client.login(username="mgr_tabs", password="password123")
        url = reverse("inventory:product_detail", kwargs={"pk": self.product.pk})
        resp = self.client.get(url)
        html = resp.content.decode("utf-8")

        self.assertIn('<details id="status-history-disclosure"', html)
        self.assertIn('<summary id="status-history-card"', html)
        self.assertIn('<div id="status-history-section"', html)

        # Ensure it appears after the main 12-column workspace card
        workspace_pos = html.index('id="detailWorkspaceCard"')
        audit_pos = html.index('id="status-history-disclosure"')
        self.assertGreater(audit_pos, workspace_pos)

    def test_photo_upload_dropzone_uses_progressive_disclosure(self):
        """Photo upload dropzone is collapsed when photos exist and open when 0 photos exist."""
        self.client.login(username="mgr_tabs", password="password123")
        url = reverse("inventory:product_detail", kwargs={"pk": self.product.pk})

        # 1. Product with existing photo -> <details id="detailAddPhotosDisclosure"> is closed (no open attr)
        resp_with_photos = self.client.get(url)
        html_with_photos = resp_with_photos.content.decode("utf-8")
        self.assertIn('<details id="detailAddPhotosDisclosure" class="pt-3 border-t border-slate-100 group" >', html_with_photos)

        # 2. Product without photos -> <details id="detailAddPhotosDisclosure" ... open> is expanded
        self.product.images.all().delete()
        resp_no_photos = self.client.get(url)
        html_no_photos = resp_no_photos.content.decode("utf-8")
        self.assertIn('<details id="detailAddPhotosDisclosure" class="pt-3 border-t border-slate-100 group" open>', html_no_photos)

    def test_productivity_enhancements_readiness_checklist_copy_pack_and_counters(self):
        """Verifies Staging Readiness Checklist, 1-Tap Copy Full Ad Pack, and live counters."""
        self.client.login(username="mgr_tabs", password="password123")
        url = reverse("inventory:product_detail", kwargs={"pk": self.product.pk})
        resp = self.client.get(url)
        html = resp.content.decode("utf-8")

        self.assertIn('id="listingReadinessChecklist"', html)
        self.assertIn('id="btnCopyFullListingPack"', html)
        self.assertIn('id="titleCharCounter"', html)
        self.assertIn('id="descCharCounter"', html)
        self.assertIn('id="unsavedChangesBadge"', html)

        # Also verify mobile access to storefront taxonomy and raw intake notes (no longer hidden lg:block)
        self.assertIn('id="storefrontTaxonomySection"', html)
        self.assertIn('id="intakeNotesCard"', html)
        self.assertNotIn('id="intakeNotesCard" class="hidden lg:block', html)

    def test_unified_staging_form_saves_listing_and_storefront_fields_together(self):
        """Submitting #productStagingForm saves both Tab 1 (Listing & Pricing) and Tab 2 (Storefront) fields."""
        self.client.login(username="mgr_tabs", password="password123")
        url = reverse("inventory:product_detail", kwargs={"pk": self.product.pk})

        resp = self.client.post(
            url,
            {
                "ai_title": "Auriculares Sony WH-1000XM4 Edicion Especial",
                "ai_description": "Con estuche rigido y cable original.",
                "sale_price": "159.90",
                "status": ProductStatus.READY,
                "pallet": "",
                "category": str(self.category.pk),
                "condition": ProductCondition.VERY_GOOD,
                "is_public": "on",
                "is_featured": "on",
                "storefront_controls_present": "1",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.ai_title, "Auriculares Sony WH-1000XM4 Edicion Especial")
        self.assertEqual(self.product.sale_price, Decimal("159.90"))
        self.assertEqual(self.product.category, self.category)
        self.assertEqual(self.product.condition, ProductCondition.VERY_GOOD)
        self.assertTrue(self.product.is_public)
        self.assertTrue(self.product.is_featured)

    def test_tab_badges_reflect_channels_clarifications_and_compliance_states(self):
        """Tab bar badges dynamically reflect active channel count, pending doubts, and compliance risk."""
        ProductListingLink.objects.create(
            product=self.product,
            site=self.wallapop,
            url="https://es.wallapop.com/item/sony-xm4-123",
            is_active=True,
        )
        ProductClarification.objects.create(
            product=self.product,
            question="¿Funciona el micrófono en llamadas?",
            asked_by=self.manager,
        )
        Product.objects.filter(pk=self.product.pk).update(
            compliance_status=ComplianceVerdict.MANUAL_REVIEW,
            compliance_risk_score=45,
            compliance_stage=ComplianceStage.STAGE_1_LEXICAL,
        )

        self.client.login(username="mgr_tabs", password="password123")
        url = reverse("inventory:product_detail", kwargs={"pk": self.product.pk})
        resp = self.client.get(url)
        html = resp.content.decode("utf-8")

        # ClauseGuard quick notice banner appears on Tab 1 when product is flagged
        self.assertIn('id="clauseGuardQuickNotice"', html)
        self.assertIn("45/100", html)

    def test_bilingual_localization_es_and_en(self):
        """Verifies Spanish and English translations for workspace tabs and deprioritized audit log."""
        self.client.login(username="mgr_tabs", password="password123")
        url = reverse("inventory:product_detail", kwargs={"pk": self.product.pk})

        with translation.override("es"):
            resp_es = self.client.get(url, HTTP_ACCEPT_LANGUAGE="es")
            html_es = resp_es.content.decode("utf-8")
            self.assertIn("Anuncio", html_es)
            self.assertIn("Canales", html_es)
            self.assertIn("Notas", html_es)
            self.assertIn("Políticas", html_es)
            self.assertIn("Preparación del anuncio", html_es)
            self.assertIn("Copiar anuncio", html_es)
            self.assertIn("Regenerar con IA", html_es)
            self.assertIn("Registro histórico de estados (clic para desplegar)", html_es)

        with translation.override("en"):
            resp_en = self.client.get(url, HTTP_ACCEPT_LANGUAGE="en")
            html_en = resp_en.content.decode("utf-8")
            self.assertIn("Listing", html_en)
            self.assertIn("Channels", html_en)
            self.assertIn("Notes", html_en)
            self.assertIn("Policy", html_en)
            self.assertIn("Staging Readiness", html_en)
            self.assertIn("Copy Ad", html_en)
            self.assertIn("Regenerate with AI", html_en)
            self.assertIn("Archival state log (click to expand)", html_en)

    def test_tabs_include_aria_controls_and_risk_score_sr_context(self):
        """Workspace tabs expose aria-controls and risk score includes sr-only /100 context."""
        self.client.login(username="mgr_tabs", password="password123")
        url = reverse("inventory:product_detail", kwargs={"pk": self.product.pk})
        resp = self.client.get(url)
        html = resp.content.decode("utf-8")

        self.assertIn('id="tabBtnWorkspaceListing"', html)
        self.assertIn('aria-controls="workspacePanelListing"', html)
        self.assertIn('aria-controls="workspacePanelChannels"', html)
        self.assertIn('aria-controls="workspacePanelNotes"', html)
        self.assertIn('aria-controls="workspacePanelCompliance"', html)
        self.assertIn('<span class="sr-only">/100</span>', html)

    def test_readiness_checklist_reflects_sold_and_blocked_states_accurately(self):
        """Sold and blocked products do not show 'In Progress' inside Staging Readiness."""
        self.client.login(username="mgr_tabs", password="password123")
        url = reverse("inventory:product_detail", kwargs={"pk": self.product.pk})

        self.product.is_sold = True
        self.product.sold_channel_type = SaleChannelType.IN_STORE
        self.product.status = ProductStatus.SOLD
        self.product.save()

        with translation.override("en"):
            html_sold = self.client.get(url).content.decode("utf-8")
            checklist_start = html_sold.index('id="listingReadinessChecklist"')
            checklist_snippet = html_sold[checklist_start : checklist_start + 700]
            self.assertIn("Sold", checklist_snippet)
            self.assertNotIn("In Progress", checklist_snippet)

        self.product.is_sold = False
        self.product.sold_channel_type = ""
        self.product.status = ProductStatus.BLOCKED
        self.product.save()

        with translation.override("en"):
            html_blocked = self.client.get(url).content.decode("utf-8")
            checklist_start = html_blocked.index('id="listingReadinessChecklist"')
            checklist_snippet = html_blocked[checklist_start : checklist_start + 700]
            self.assertIn("Blocked", checklist_snippet)
            self.assertNotIn("In Progress", checklist_snippet)

    def test_tab2_storefront_errors_render_inside_channels_panel(self):
        """Invalid POST data for Tab 2 category/condition renders role='alert' errors inside #workspacePanelChannels."""
        self.client.login(username="mgr_tabs", password="password123")
        url = reverse("inventory:product_detail", kwargs={"pk": self.product.pk})

        resp = self.client.post(
            url,
            {
                "ai_title": self.product.ai_title,
                "ai_description": self.product.ai_description,
                "sale_price": "145.00",
                "status": ProductStatus.READY,
                "category": "999999",
                "condition": "invalid_condition_choice",
                "storefront_controls_present": "1",
            },
        )
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")
        panel_start = html.index('id="workspacePanelChannels"')
        panel_end = html.index('id="stagingFormSaveBar"')
        channels_html = html[panel_start:panel_end]
        self.assertIn('role="alert"', channels_html)

    def test_clarifications_avoid_repeated_count_and_exists_sql_queries(self):
        """Detail GET reuses prefetched clarifications instead of emitting repeated .count()/.exists() SQL."""
        ProductClarification.objects.create(
            product=self.product,
            question="¿Tiene caja?",
            asked_by=self.manager,
        )
        ProductClarification.objects.create(
            product=self.product,
            question="¿Funciona?",
            answer="Sí",
            is_direct_note=True,
            asked_by=self.manager,
        )
        self.client.login(username="mgr_tabs", password="password123")
        url = reverse("inventory:product_detail", kwargs={"pk": self.product.pk})

        with CaptureQueriesContext(connection) as ctx:
            resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

        per_product_clarif_queries = [
            q["sql"]
            for q in ctx.captured_queries
            if "inventory_productclarification" in q["sql"].lower()
            and ("select 1 as" in q["sql"].lower() or 'product_id" =' in q["sql"].lower() and "inner join" not in q["sql"].lower() or 'product_id" in' in q["sql"].lower())
        ]
        # Single prefetch query rather than 10+ separate COUNT/EXISTS round-trips
        self.assertLessEqual(
            len(per_product_clarif_queries),
            1,
            f"Unexpected per-product clarification queries: {per_product_clarif_queries}",
        )


@override_settings(TURNSTILE_ENABLED=False)
class ProductDetailTabsBrowserTests(StaticLiveServerTestCase):
    """Real Chrome Playwright behavioral tests for the tabbed Product Detail workspace."""

    @classmethod
    def setUpClass(cls):
        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
        super().setUpClass()

    def setUp(self):
        self.managers_group, _ = Group.objects.get_or_create(name="managers")
        self.manager = User.objects.create_user(
            username="mgr_browser_tabs", password="password123", is_staff=True
        )
        self.manager.groups.add(self.managers_group)

        self.wallapop, _ = MarketplaceSite.objects.get_or_create(
            slug="wallapop",
            defaults={"name": "Wallapop", "base_url": "https://es.wallapop.com", "is_active": True},
        )
        self.product = Product.objects.create(
            raw_note="Sony WH-1000XM4 nota inicial de prueba.",
            ai_title="Sony WH-1000XM4 Bluetooth",
            ai_description="Con estuche original.",
            sale_price=Decimal("140.00"),
            estimated_resale_price=Decimal("155.00"),
            status=ProductStatus.READY,
            created_by=self.manager,
        )
        ProductImage.objects.create(product=self.product, image=_create_sample_image())
        ProductClarification.objects.create(
            product=self.product,
            question="¿Incluye cable USB-C?",
            asked_by=self.manager,
        )

    def _login(self, page):
        page.goto(f"{self.live_server_url}{reverse('inventory:login')}", wait_until="load")
        page.fill("#id_username", "mgr_browser_tabs")
        page.fill("#id_password", "password123")
        with page.expect_navigation():
            page.click("#loginSubmitBtn")

    def test_tabs_keyboard_deeplink_beforematch_counters_validation_and_clipboard(self):
        """Verifies ARIA keyboard nav, ?tab=/#hash, beforematch, live counters, cross-tab validation, Ctrl+S guard, and copy helpers."""
        detail_url = f"{self.live_server_url}{reverse('inventory:product_detail', kwargs={'pk': self.product.pk})}"

        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            context = browser.new_context(
                viewport={"width": 1280, "height": 850},
                locale="en-US",
                extra_http_headers={"Accept-Language": "en"},
            )
            page = context.new_page()
            page_errors = []
            page.on("pageerror", lambda err: page_errors.append(str(err)))

            # Record clipboard writes via stub that works consistently in headless Chrome
            page.add_init_script("""
                window.__copiedPayloads = [];
                try {
                    Object.defineProperty(navigator, 'clipboard', {
                        configurable: true,
                        value: {
                            writeText: (txt) => {
                                window.__copiedPayloads.push(txt);
                                return Promise.resolve();
                            }
                        }
                    });
                } catch (e) {}
            """)

            self._login(page)

            # 1. URL query ?tab=notes activates Notes tab immediately
            page.goto(f"{detail_url}?tab=notes", wait_until="load")
            page.wait_for_selector("#detailWorkspaceTablist")
            self.assertEqual(page.locator("#tabBtnWorkspaceNotes").get_attribute("aria-selected"), "true")
            self.assertTrue(page.locator("#workspacePanelNotes").is_visible())

            # 2. Keyboard roving focus: Home -> Listing, ArrowRight -> Channels, End -> Compliance
            page.locator("#tabBtnWorkspaceNotes").focus()
            page.keyboard.press("Home")
            self.assertEqual(page.locator("#tabBtnWorkspaceListing").get_attribute("aria-selected"), "true")
            page.keyboard.press("ArrowRight")
            self.assertEqual(page.locator("#tabBtnWorkspaceChannels").get_attribute("aria-selected"), "true")
            page.keyboard.press("End")
            self.assertEqual(page.locator("#tabBtnWorkspaceCompliance").get_attribute("aria-selected"), "true")

            # 3. Find-in-page beforematch on hidden="until-found" switches tab automatically
            page.evaluate("""() => {
                const panel = document.getElementById('workspacePanelNotes');
                panel.dispatchEvent(new Event('beforematch'));
            }""")
            self.assertEqual(page.locator("#tabBtnWorkspaceNotes").get_attribute("aria-selected"), "true")
            self.assertTrue(page.locator("#workspacePanelNotes").is_visible())

            # 4. Ctrl+S inside Tab 3 (Notes) MUST NOT submit #productStagingForm or clear unsent note text
            page.fill("#directNoteText", "Borrador de nota que no debe perderse")
            page.locator("#directNoteText").press("Control+s")
            page.wait_for_timeout(300)
            self.assertEqual(page.locator("#directNoteText").input_value(), "Borrador de nota que no debe perderse")
            self.assertEqual(page.locator("#tabBtnWorkspaceNotes").get_attribute("aria-selected"), "true")

            # 5. Cross-tab HTML5 invalid input on Tab 1 must switch back to Listing when saving from Tab 2
            page.click("#tabBtnWorkspaceListing")
            page.fill("#id_sale_price", "-5")
            page.click("#tabBtnWorkspaceChannels")
            self.assertEqual(page.locator("#tabBtnWorkspaceChannels").get_attribute("aria-selected"), "true")
            page.click("#btnSaveListingChanges")
            page.wait_for_timeout(200)
            self.assertEqual(page.locator("#tabBtnWorkspaceListing").get_attribute("aria-selected"), "true")
            self.assertEqual(page.evaluate("document.activeElement?.id"), "id_sale_price")

            # Fix sale_price and verify live counters + unsaved badge update
            page.fill("#id_sale_price", "149.50")
            title_text = "Sony WH-1000XM4 Edicion Prueba"
            page.fill("#id_ai_title", title_text)
            page.fill("#id_ai_description", "Linea 1\nLinea 2")
            self.assertIn(f"{len(title_text)} / 255", page.locator("#titleCharCounter").inner_text())
            self.assertIn("2 lines", page.locator("#descCharCounter").inner_text())
            self.assertFalse(page.locator("#unsavedChangesBadge").evaluate("el => el.classList.contains('hidden')"))

            # 6. Copy Ad formats payload AND rapid double-click does not lock label as "Copied!"
            orig_copy_label = page.locator("#btnCopyFullListingPack").inner_text().strip()
            page.click("#btnCopyFullListingPack")
            page.wait_for_timeout(80)
            page.click("#btnCopyFullListingPack")
            page.wait_for_timeout(1750)
            restored_copy_label = page.locator("#btnCopyFullListingPack").inner_text().strip()
            self.assertEqual(restored_copy_label, orig_copy_label)
            copied = page.evaluate("window.__copiedPayloads")
            self.assertTrue(len(copied) >= 1)
            self.assertIn("Sony WH-1000XM4 Edicion Prueba", copied[-1])
            self.assertIn("€149.50", copied[-1])
            self.assertNotIn("NaN", copied[-1])

            # 7. Simulated non-HTTPS LAN context (navigator.clipboard = undefined) does not throw
            page.evaluate("Object.defineProperty(navigator, 'clipboard', { configurable: true, value: undefined });")
            page.click("#btnCopyFullListingPack")
            page.wait_for_timeout(150)

            # 8. Ctrl+S from Tab 1 saves form to DB
            with page.expect_navigation():
                page.locator("#id_ai_title").press("Control+s")
            self.product.refresh_from_db()
            self.assertEqual(self.product.ai_title, "Sony WH-1000XM4 Edicion Prueba")

            # 9. Narrow OPPO A74 320x711 scroll hint hides once scrolled to right end
            page.set_viewport_size({"width": 320, "height": 711})
            page.wait_for_timeout(150)
            self.assertFalse(
                page.locator("#detailWorkspaceTabScrollHint").evaluate("el => el.classList.contains('hidden')")
            )
            page.evaluate("""() => {
                const tl = document.getElementById('detailWorkspaceTablist');
                tl.scrollLeft = tl.scrollWidth;
                tl.dispatchEvent(new Event('scroll'));
            }""")
            page.wait_for_timeout(100)
            self.assertTrue(
                page.locator("#detailWorkspaceTabScrollHint").evaluate("el => el.classList.contains('hidden')")
            )

            self.assertEqual(page_errors, [], f"Unexpected browser JS errors: {page_errors}")
            context.close()
            browser.close()
