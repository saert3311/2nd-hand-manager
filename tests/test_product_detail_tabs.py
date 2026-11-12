import io
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import translation
from PIL import Image

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
