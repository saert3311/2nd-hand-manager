from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from inventory.models import Product, ProductClarification, ProductStatus


class UIAccessibilityAndDesignSystemTest(TestCase):
    """
    Phase 39: Automated UI/UX Design System, Usability & WCAG 2.1 AA Accessibility Test Suite.
    Verifies skip links, landmark semantics, heading hierarchy, form error rendering,
    elimination of sub-12px micro-fonts & native JS blocking dialogs, and relative rem typography.
    """

    def setUp(self):
        self.managers_group, _ = Group.objects.get_or_create(name="managers")
        self.assistants_group, _ = Group.objects.get_or_create(name="assistants")

        self.manager = User.objects.create_user(
            username="a11y_manager",
            password="testpassword123",
            is_staff=True,
        )
        self.manager.groups.add(self.managers_group)

        self.assistant = User.objects.create_user(
            username="a11y_assistant",
            password="testpassword123",
        )
        self.assistant.groups.add(self.assistants_group)

        self.product = Product.objects.create(
            raw_note="Vintage leather jacket size L",
            ai_title="Chaqueta de Cuero Vintage Talla L",
            ai_description="Chaqueta de cuero genuino en excelente estado.",
            sale_price=Decimal("45.00"),
            status=ProductStatus.READY,
            is_public=True,
            is_featured=True,
            created_by=self.assistant,
        )

    def test_staff_and_public_shells_include_skip_link_and_main_landmark(self):
        """[A-01] & [A-02] Both base shells must provide a skip-to-main-content link and #main-content landmark."""
        # Public storefront shell
        pub_resp = self.client.get(reverse("storefront:home"))
        self.assertEqual(pub_resp.status_code, 200)
        pub_html = pub_resp.content.decode("utf-8")
        self.assertIn('href="#main-content"', pub_html)
        self.assertIn('id="main-content"', pub_html)
        self.assertIn('<meta name="text-scale" content="scale">', pub_html)

        # Staff shell
        self.client.force_login(self.manager)
        staff_resp = self.client.get(reverse("inventory:dashboard"))
        self.assertEqual(staff_resp.status_code, 200)
        staff_html = staff_resp.content.decode("utf-8")
        self.assertIn('href="#main-content"', staff_html)
        self.assertIn('id="main-content"', staff_html)
        self.assertIn('id="desktop-nav"', staff_html)
        self.assertIn('aria-label="', staff_html)

    def test_login_page_has_primary_h1_and_autocomplete_attributes(self):
        """[V-01] & [A-09] Login screen must have a primary <h1> and standard autocomplete attributes."""
        resp = self.client.get(reverse("inventory:login"))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")
        self.assertIn("<h1", html)
        self.assertIn('autocomplete="username"', html)
        self.assertIn('autocomplete="current-password"', html)

    def test_primary_h1_present_across_all_views(self):
        """[V-01] & [U-05] Every primary view must render a top-level <h1> heading."""
        # Public views
        for url in [
            reverse("storefront:home"),
            reverse("storefront:catalog"),
            reverse("storefront:how_to_buy"),
            reverse("storefront:legal_notice"),
            reverse("storefront:privacy"),
            reverse("storefront:cookies"),
            self.product.get_public_url(),
        ]:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, f"Failed GET {url}")
            self.assertIn("<h1", resp.content.decode("utf-8"), f"Missing <h1> on {url}")

        # Staff views
        self.client.force_login(self.manager)
        for url in [
            reverse("inventory:dashboard"),
            reverse("inventory:intake"),
            reverse("inventory:product_detail", args=[self.product.pk]),
        ]:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, f"Failed GET {url}")
            html = resp.content.decode("utf-8")
            self.assertIn("<h1", html, f"Missing <h1> on {url}")

        # Product detail must display product title inside <h1>
        detail_html = self.client.get(
            reverse("inventory:product_detail", args=[self.product.pk])
        ).content.decode("utf-8")
        self.assertIn(self.product.display_title, detail_html)

    def test_product_detail_renders_inline_field_errors_with_role_alert(self):
        """[U-03] Submitting invalid staging data on product_detail must surface inline role='alert' error messages."""
        self.client.force_login(self.manager)
        detail_url = reverse("inventory:product_detail", args=[self.product.pk])

        # Mark as sold without specifying sold_channel_type -> triggers form validation error
        resp = self.client.post(
            detail_url,
            {
                "ai_title": self.product.ai_title,
                "ai_description": self.product.ai_description,
                "sale_price": "45.00",
                "status": ProductStatus.READY,
                "is_sold": "on",
                "sold_channel_type": "",
                "storefront_controls_present": "1",
                "category": "",
                "condition": "",
            },
        )
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")
        self.assertIn('role="alert"', html)

    def test_product_detail_clarification_tabs_and_labels_are_accessible(self):
        """[A-06] & [A-08] Clarification tabs must expose aria-controls/role=tabpanel and explicit label associations."""
        ProductClarification.objects.create(
            product=self.product,
            question="Can you confirm sleeve length?",
            asked_by=self.manager,
        )
        self.client.force_login(self.manager)
        resp = self.client.get(reverse("inventory:product_detail", args=[self.product.pk]))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")

        self.assertIn('aria-controls="panelDirectNote"', html)
        self.assertIn('aria-controls="panelAskDoubt"', html)
        self.assertIn('role="tabpanel"', html)
        self.assertIn('for="directNoteCategory"', html)
        self.assertIn('for="directNoteText"', html)
        self.assertIn('for="askDoubtCategory"', html)
        self.assertIn('for="askDoubtQuestion"', html)
        self.assertIn('id="actionConfirmModal"', html)

    def test_templates_contain_no_sub_12px_micro_fonts_or_blocking_native_dialogs(self):
        """[V-05], [V-06], [U-02] Zero templates may contain text-[10px], text-[11px], py-0.2, confirm(, or alert(."""
        base_dir = Path(settings.BASE_DIR)
        template_dirs = [
            base_dir / "inventory" / "templates",
            base_dir / "storefront" / "templates",
        ]
        forbidden_tokens = [
            "text-[10px]",
            "text-[11px]",
            "py-0.2",
            "return confirm(",
            "alert(",
        ]

        for t_dir in template_dirs:
            for html_file in t_dir.rglob("*.html"):
                content = html_file.read_text(encoding="utf-8")
                for token in forbidden_tokens:
                    self.assertNotIn(
                        token,
                        content,
                        f"Forbidden pattern '{token}' found in {html_file.relative_to(base_dir)}",
                    )

    def test_storefront_uses_relative_rem_typography_and_wcag_aa_cta_contrast(self):
        """[V-07], [V-08], [V-09], [V-10] Storefront uses rem font sizes and high-contrast slate-950 text on WhatsApp/Featured."""
        base_public = (
            Path(settings.BASE_DIR) / "storefront" / "templates" / "storefront" / "base_public.html"
        ).read_text(encoding="utf-8")

        self.assertIn('"0.75rem"', base_public)
        self.assertNotIn('"11px"', base_public)
        self.assertIn("bg-[#25D366] hover:bg-[#20ba59] text-slate-950", base_public)

        # Check product card featured badge contrast
        card_html = (
            Path(settings.BASE_DIR)
            / "storefront"
            / "templates"
            / "storefront"
            / "partials"
            / "_product_card.html"
        ).read_text(encoding="utf-8")
        self.assertIn("bg-amber-400 text-slate-950", card_html)
        self.assertNotIn("bg-[#F59E0B] text-surface-container-lowest", card_html)
