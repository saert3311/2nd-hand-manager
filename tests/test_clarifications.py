from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from inventory.admin import ProductAdmin, ProductClarificationAdmin, ProductClarificationInline, manager_admin_site
from inventory.models import (
    ClarificationCategory,
    ClarificationStatus,
    MarketplaceSite,
    Product,
    ProductClarification,
    ProductListingLink,
    ProductStatus,
)

User = get_user_model()


class ProductLifecycleAndClarificationModelTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="manager", password="password123", is_staff=True)
        self.assistant = User.objects.create_user(username="assistant", password="password123")

    def test_product_default_status_is_draft(self):
        product = Product.objects.create(raw_note="Vintage denim jacket", created_by=self.assistant)
        self.assertEqual(product.status, ProductStatus.DRAFT)
        self.assertFalse(product.is_sold)

    def test_product_status_choices(self):
        valid_statuses = [
            ProductStatus.DRAFT,
            ProductStatus.AWAITING_INFO,
            ProductStatus.READY,
            ProductStatus.SOLD,
            ProductStatus.BLOCKED,
        ]
        product = Product.objects.create(raw_note="Item")
        for st in valid_statuses:
            Product.objects.filter(pk=product.pk).update(status=st)
            product.refresh_from_db()
            self.assertEqual(product.status, st)

    def test_product_is_sold_synchronization(self):
        product = Product.objects.create(
            raw_note="Item",
            ai_title="Vintage Item",
            ai_description="Detailed description of vintage item.",
            sale_price=Decimal("120.00"),
        )
        self.assertEqual(product.status, ProductStatus.READY)
        self.assertFalse(product.is_sold)

        # 1. Setting status = SOLD syncs is_sold to True
        product.status = ProductStatus.SOLD
        product.save()
        product.refresh_from_db()
        self.assertTrue(product.is_sold)

        # 2. Setting is_sold = False syncs status to READY (since it has title, desc, price)
        product.is_sold = False
        product.save()
        product.refresh_from_db()
        self.assertEqual(product.status, ProductStatus.READY)
        self.assertFalse(product.is_sold)

        # 3. mark_as_sold method updates status to SOLD
        product.mark_as_sold(price=Decimal("120.00"))
        product.refresh_from_db()
        self.assertEqual(product.status, ProductStatus.SOLD)
        self.assertTrue(product.is_sold)
        self.assertEqual(product.sale_price, Decimal("120.00"))

        # 4. mark_as_unsold method updates status to READY
        product.mark_as_unsold()
        product.refresh_from_db()
        self.assertEqual(product.status, ProductStatus.READY)
        self.assertFalse(product.is_sold)

    def test_product_clarification_creation_and_defaults(self):
        product = Product.objects.create(raw_note="Leather boots")
        clarification = ProductClarification.objects.create(
            product=product,
            category=ClarificationCategory.MEASUREMENTS,
            question="What is the insole length in cm?",
            asked_by=self.manager,
        )
        self.assertEqual(clarification.status, ClarificationStatus.PENDING)
        self.assertEqual(clarification.category, ClarificationCategory.MEASUREMENTS)
        self.assertEqual(clarification.question, "What is the insole length in cm?")
        self.assertEqual(clarification.asked_by, self.manager)
        self.assertEqual(clarification.answer, "")
        self.assertIsNone(clarification.answered_by)
        self.assertIsNone(clarification.answered_at)
        self.assertIsNotNone(clarification.created_at)

    def test_product_clarification_resolution(self):
        product = Product.objects.create(raw_note="Leather boots")
        clarification = ProductClarification.objects.create(
            product=product,
            category=ClarificationCategory.MATERIAL_AUTHENTICITY,
            question="Is it genuine cowhide?",
            asked_by=self.manager,
        )
        clarification.resolve(answer="Yes, 100% genuine full-grain leather.", answered_by=self.assistant)
        clarification.refresh_from_db()

        self.assertEqual(clarification.status, ClarificationStatus.RESOLVED)
        self.assertEqual(clarification.answer, "Yes, 100% genuine full-grain leather.")
        self.assertEqual(clarification.answered_by, self.assistant)
        self.assertIsNotNone(clarification.answered_at)

    def test_product_clarification_str_representation(self):
        product = Product.objects.create(raw_note="Harley Tee", ai_title="Harley Davidson Tee")
        clarification = ProductClarification.objects.create(
            product=product,
            category=ClarificationCategory.TAG_COMPOSITION,
            question="What does the care tag say?",
            asked_by=self.manager,
        )
        self.assertIn("Harley Davidson Tee", str(clarification))
        self.assertIn(clarification.get_category_display(), str(clarification))

    def test_cascade_deletion(self):
        product = Product.objects.create(raw_note="To delete")
        ProductClarification.objects.create(
            product=product,
            category=ClarificationCategory.GENERAL,
            question="Any box included?",
            asked_by=self.manager,
        )
        self.assertEqual(ProductClarification.objects.filter(product=product).count(), 1)
        product.delete()
        self.assertEqual(ProductClarification.objects.filter(product_id=product.id).count(), 0)

    def test_admin_registration(self):
        # Inlines in ProductAdmin
        inline_classes = [inline.__class__ if not isinstance(inline, type) else inline for inline in ProductAdmin.inlines]
        self.assertIn(ProductClarificationInline, inline_classes)

        # Registered in manager_admin_site
        self.assertIn(ProductClarification, manager_admin_site._registry)
        self.assertIsInstance(manager_admin_site._registry[ProductClarification], ProductClarificationAdmin)


class NotificationContextProcessorAndAlertTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.manager = User.objects.create_user(username="manager", password="password123", is_staff=True)
        self.assistant = User.objects.create_user(username="assistant", password="password123")
        self.product = Product.objects.create(raw_note="Vintage wool coat")

    def test_context_processor_returns_count(self):
        from django.contrib.auth.models import AnonymousUser
        from django.test import RequestFactory

        from inventory.context_processors import notifications

        factory = RequestFactory()

        # Anonymous user gets 0
        req_anon = factory.get("/")
        req_anon.user = AnonymousUser()
        self.assertEqual(notifications(req_anon), {"pending_clarifications_count": 0})

        # Authenticated user with no clarifications gets 0
        req_auth = factory.get("/")
        req_auth.user = self.assistant
        self.assertEqual(notifications(req_auth), {"pending_clarifications_count": 0})

        # Create 2 pending clarifications and 1 resolved
        ProductClarification.objects.create(
            product=self.product,
            category=ClarificationCategory.MEASUREMENTS,
            question="What is chest width?",
            asked_by=self.manager,
        )
        ProductClarification.objects.create(
            product=self.product,
            category=ClarificationCategory.MATERIAL_AUTHENTICITY,
            question="Is it pure virgin wool?",
            asked_by=self.manager,
        )
        resolved = ProductClarification.objects.create(
            product=self.product,
            category=ClarificationCategory.TAG_COMPOSITION,
            question="Made in which country?",
            asked_by=self.manager,
        )
        resolved.resolve(answer="Made in Scotland", answered_by=self.assistant)

        self.assertEqual(notifications(req_auth), {"pending_clarifications_count": 2})

    def test_navbar_renders_badge_when_pending_exist(self):
        self.client.login(username="assistant", password="password123")
        ProductClarification.objects.create(
            product=self.product,
            category=ClarificationCategory.MEASUREMENTS,
            question="What is chest width?",
            asked_by=self.manager,
        )

        resp = self.client.get(reverse("inventory:dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "status=awaiting_info")
        self.assertContains(resp, "badge-pending-clarifications")
        self.assertContains(resp, "1")

    def test_navbar_badge_omitted_when_zero_pending(self):
        self.client.login(username="assistant", password="password123")
        resp = self.client.get(reverse("inventory:dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "badge-pending-clarifications")

    def test_intake_page_renders_alert_banner_when_pending_exist(self):
        self.client.login(username="assistant", password="password123")
        ProductClarification.objects.create(
            product=self.product,
            category=ClarificationCategory.MEASUREMENTS,
            question="What is chest width?",
            asked_by=self.manager,
        )

        resp = self.client.get(reverse("inventory:intake"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "alert-pending-clarifications-banner")
        self.assertContains(resp, "status=awaiting_info")

    def test_intake_page_banner_omitted_when_zero_pending(self):
        self.client.login(username="assistant", password="password123")
        resp = self.client.get(reverse("inventory:intake"))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "alert-pending-clarifications-banner")


class ProductDetailClarificationViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.manager = User.objects.create_user(username="manager", password="password123", is_staff=True)
        self.assistant = User.objects.create_user(username="assistant", password="password123")
        self.product = Product.objects.create(
            raw_note="Oversized trench coat",
            ai_title="Vintage Oversized Trench Coat",
            ai_description="Classic beige oversized trench coat in great condition.",
            sale_price=Decimal("89.00"),
            created_by=self.assistant,
        )

    def test_manager_can_add_clarification_and_shifts_status_to_awaiting_info(self):
        self.client.login(username="manager", password="password123")
        url = reverse("inventory:add_clarification", kwargs={"pk": self.product.pk})
        resp = self.client.post(url, {
            "category": ClarificationCategory.MEASUREMENTS,
            "question": "What is the sleeve length?",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse("inventory:product_detail", kwargs={"pk": self.product.pk}))

        self.assertEqual(self.product.clarifications.count(), 1)
        clarif = self.product.clarifications.first()
        self.assertEqual(clarif.question, "What is the sleeve length?")
        self.assertEqual(clarif.category, ClarificationCategory.MEASUREMENTS)
        self.assertEqual(clarif.asked_by, self.manager)
        self.assertEqual(clarif.status, ClarificationStatus.PENDING)

        self.product.refresh_from_db()
        self.assertEqual(self.product.status, ProductStatus.AWAITING_INFO)

    def test_assistant_cannot_add_clarification(self):
        self.client.login(username="assistant", password="password123")
        url = reverse("inventory:add_clarification", kwargs={"pk": self.product.pk})
        resp = self.client.post(url, {
            "category": ClarificationCategory.MEASUREMENTS,
            "question": "Assistant should not ask",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.product.clarifications.count(), 0)

    def test_assistant_can_answer_clarification_and_auto_transitions_to_ready(self):
        clarif = ProductClarification.objects.create(
            product=self.product,
            category=ClarificationCategory.MATERIAL_AUTHENTICITY,
            question="Is there an internal composition tag?",
            asked_by=self.manager,
        )
        self.product.status = ProductStatus.AWAITING_INFO
        self.product.save()

        self.client.login(username="assistant", password="password123")
        url = reverse("inventory:answer_clarification", kwargs={"pk": self.product.pk, "clarification_pk": clarif.pk})
        resp = self.client.post(url, {
            "answer": "Yes, 100% Cotton, Made in England.",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse("inventory:product_detail", kwargs={"pk": self.product.pk}))

        clarif.refresh_from_db()
        self.assertEqual(clarif.status, ClarificationStatus.RESOLVED)
        self.assertEqual(clarif.answer, "Yes, 100% Cotton, Made in England.")
        self.assertEqual(clarif.answered_by, self.assistant)
        self.assertIsNotNone(clarif.answered_at)

        self.product.refresh_from_db()
        self.assertEqual(self.product.status, ProductStatus.READY)

    def test_staging_ui_renders_status_badge_and_caution_gate(self):
        self.product.status = ProductStatus.AWAITING_INFO
        self.product.save()

        self.client.login(username="manager", password="password123")
        resp = self.client.get(reverse("inventory:product_detail", kwargs={"pk": self.product.pk}))
        self.assertEqual(resp.status_code, 200)

        # Status badge rendered
        self.assertContains(resp, "product-status-badge")
        # Publishing gate caution rendered
        self.assertContains(resp, "publishing-gate-caution")

    def test_staging_ui_renders_ai_regeneration_callout_when_resolved_exist(self):
        clarif = ProductClarification.objects.create(
            product=self.product,
            category=ClarificationCategory.MEASUREMENTS,
            question="Armpit width?",
            asked_by=self.manager,
        )
        clarif.resolve(answer="58 cm pit to pit", answered_by=self.assistant)

        self.client.login(username="manager", password="password123")
        resp = self.client.get(reverse("inventory:product_detail", kwargs={"pk": self.product.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "ai-regeneration-callout")


class DashboardClarificationAndLifecycleTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.manager = User.objects.create_user(username="manager", password="password123", is_staff=True)
        self.assistant = User.objects.create_user(username="assistant", password="password123")
        self.client.login(username="manager", password="password123")

        self.site_vinted, _ = MarketplaceSite.objects.get_or_create(slug="vinted", defaults={"name": "Vinted", "is_active": True})
        self.site_ebay, _ = MarketplaceSite.objects.get_or_create(slug="ebay", defaults={"name": "eBay", "is_active": True})

        self.prod_draft = Product.objects.create(raw_note="Draft jacket", status=ProductStatus.DRAFT, created_by=self.assistant)
        self.prod_awaiting = Product.objects.create(raw_note="Awaiting info shoes", status=ProductStatus.AWAITING_INFO, created_by=self.assistant)
        self.prod_ready = Product.objects.create(raw_note="Ready boots", status=ProductStatus.READY, created_by=self.assistant)
        self.prod_sold = Product.objects.create(raw_note="Sold watch", status=ProductStatus.SOLD, created_by=self.assistant)
        self.prod_blocked = Product.objects.create(raw_note="Blocked replica coat", status=ProductStatus.BLOCKED, created_by=self.assistant)

        # Attach links to vinted
        ProductListingLink.objects.create(product=self.prod_draft, site=self.site_vinted, url="https://vinted.fr/1", is_active=True)
        ProductListingLink.objects.create(product=self.prod_awaiting, site=self.site_vinted, url="https://vinted.fr/2", is_active=True)
        ProductListingLink.objects.create(product=self.prod_sold, site=self.site_ebay, url="https://ebay.com/1", is_active=True)

    def test_filter_by_awaiting_info(self):
        resp = self.client.get(reverse("inventory:dashboard"), {"status": "awaiting_info"})
        self.assertEqual(resp.status_code, 200)
        products = list(resp.context["products"])
        self.assertIn(self.prod_awaiting, products)
        self.assertNotIn(self.prod_draft, products)
        self.assertNotIn(self.prod_sold, products)
        self.assertNotIn(self.prod_blocked, products)

    def test_filter_by_blocked(self):
        resp = self.client.get(reverse("inventory:dashboard"), {"status": "blocked"})
        self.assertEqual(resp.status_code, 200)
        products = list(resp.context["products"])
        self.assertIn(self.prod_blocked, products)
        self.assertNotIn(self.prod_awaiting, products)

    def test_status_counters_overall_and_scoped_to_platform(self):
        resp = self.client.get(reverse("inventory:dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["total_count"], 5)
        self.assertEqual(resp.context["awaiting_info_count"], 1)
        self.assertEqual(resp.context["sold_count"], 1)
        self.assertEqual(resp.context["blocked_count"], 1)

        # Scoped to Vinted
        resp_vinted = self.client.get(reverse("inventory:dashboard"), {"platform": "vinted"})
        self.assertEqual(resp_vinted.status_code, 200)
        self.assertEqual(resp_vinted.context["total_count"], 2)
        self.assertEqual(resp_vinted.context["awaiting_info_count"], 1)
        self.assertEqual(resp_vinted.context["sold_count"], 0)


class AIServiceClarificationEnrichmentTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="manager", password="password123", is_staff=True)
        self.assistant = User.objects.create_user(username="assistant", password="password123")
        self.product = Product.objects.create(raw_note="Harris Tweed wool blazer", created_by=self.assistant)

    @override_settings(GEMINI_API_KEY="test-key")
    @patch("inventory.services.ai_service.genai.Client")
    def test_generate_product_listing_includes_resolved_clarifications_in_prompt(self, mock_client_cls):
        from inventory.services.ai_service import ProductListingSchema, generate_product_listing

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.parsed = ProductListingSchema(
            title="Vintage Harris Tweed Wool Blazer",
            description="Classic tailored blazer with confirmed pure wool."
        )
        mock_client.models.generate_content.return_value = mock_response

        # Add resolved clarification
        clarif = ProductClarification.objects.create(
            product=self.product,
            category=ClarificationCategory.MATERIAL_AUTHENTICITY,
            question="Is there an internal woolmark tag?",
            asked_by=self.manager,
        )
        clarif.resolve(answer="Yes, 100% Pure Scottish Virgin Wool with Orb mark", answered_by=self.assistant)

        result = generate_product_listing(self.product)
        self.assertEqual(result["title"], "Vintage Harris Tweed Wool Blazer")

        # Verify prompt contents sent to Gemini
        call_kwargs = mock_client.models.generate_content.call_args.kwargs
        contents = call_kwargs["contents"]
        prompt_text = contents[0]
        self.assertIn("Harris Tweed wool blazer", prompt_text)
        self.assertIn("Is there an internal woolmark tag?", prompt_text)
        self.assertIn("100% Pure Scottish Virgin Wool with Orb mark", prompt_text)


class ClarificationLifecycleSynchronizationAndOrphanPreventionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.manager = User.objects.create_user(username="mgr_sync", password="password123", is_staff=True)
        self.assistant = User.objects.create_user(username="asst_sync", password="password123")
        self.product = Product.objects.create(
            raw_note="Silk vintage shirt",
            ai_title="Vintage Silk Shirt",
            ai_description="100% pure silk vintage button down shirt in excellent condition.",
            sale_price=Decimal("35.00"),
            created_by=self.assistant,
        )

    def test_creating_pending_clarification_automatically_sets_status_to_awaiting_info(self):
        self.assertEqual(self.product.status, ProductStatus.READY)
        ProductClarification.objects.create(
            product=self.product,
            category=ClarificationCategory.MEASUREMENTS,
            question="What is the chest measurement?",
            asked_by=self.manager,
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, ProductStatus.AWAITING_INFO)

    def test_resolving_clarification_transitions_status_to_ready_when_none_remain(self):
        clarif = ProductClarification.objects.create(
            product=self.product,
            category=ClarificationCategory.TAG_COMPOSITION,
            question="Is it 100% silk?",
            asked_by=self.manager,
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, ProductStatus.AWAITING_INFO)

        clarif.resolve("Yes, 100% mulberry silk", answered_by=self.assistant)
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, ProductStatus.READY)

    def test_deleting_clarification_transitions_status_to_ready_when_none_remain(self):
        clarif = ProductClarification.objects.create(
            product=self.product,
            category=ClarificationCategory.GENERAL,
            question="Is this vintage?",
            asked_by=self.manager,
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, ProductStatus.AWAITING_INFO)

        clarif.delete()
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, ProductStatus.READY)

    def test_sold_product_is_not_overwritten_by_clarification_signal(self):
        self.product.mark_as_sold(price=Decimal("45.00"))
        self.assertEqual(self.product.status, ProductStatus.SOLD)
        self.assertTrue(self.product.is_sold)

        ProductClarification.objects.create(
            product=self.product,
            category=ClarificationCategory.GENERAL,
            question="Should not change sold status",
            asked_by=self.manager,
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, ProductStatus.SOLD)
        self.assertTrue(self.product.is_sold)

    def test_notifications_excludes_sold_products_with_pending_clarifications(self):
        from django.test.client import RequestFactory

        from inventory.context_processors import notifications

        self.product.mark_as_sold(price=Decimal("45.00"))
        ProductClarification.objects.create(
            product=self.product,
            category=ClarificationCategory.GENERAL,
            question="Unanswered question on sold product",
            asked_by=self.manager,
        )

        factory = RequestFactory()
        req = factory.get("/")
        req.user = self.manager
        self.assertEqual(notifications(req)["pending_clarifications_count"], 0)

    def test_dashboard_awaiting_info_filter_includes_products_with_pending_clarifications(self):
        Product.objects.filter(pk=self.product.pk).update(status=ProductStatus.DRAFT)
        ProductClarification.objects.create(
            product=self.product,
            category=ClarificationCategory.MEASUREMENTS,
            question="Arm length?",
            asked_by=self.manager,
        )
        Product.objects.filter(pk=self.product.pk).update(status=ProductStatus.DRAFT)

        self.client.login(username="mgr_sync", password="password123")
        resp = self.client.get(reverse("inventory:dashboard"), {"status": "awaiting_info"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn(self.product, list(resp.context["products"]))
        self.assertEqual(resp.context["awaiting_info_count"], 1)

    def test_product_update_form_blocks_ready_status_when_pending_clarifications_exist(self):
        from inventory.forms import ProductUpdateForm

        ProductClarification.objects.create(
            product=self.product,
            category=ClarificationCategory.MEASUREMENTS,
            question="Pending question",
            asked_by=self.manager,
        )
        form = ProductUpdateForm(
            data={"status": ProductStatus.READY, "is_sold": False, "ai_title": "Test Title"},
            instance=self.product,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("status", form.errors)



