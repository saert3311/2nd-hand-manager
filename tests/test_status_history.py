from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from inventory.middleware import (
    CurrentUserMiddleware,
    get_current_user,
    reset_current_user,
    set_current_user,
)
from inventory.models import (
    ClarificationCategory,
    MarketplaceSite,
    Product,
    ProductClarification,
    ProductListingLink,
    ProductStatus,
    ProductStatusLog,
    log_status_change,
)

User = get_user_model()


class ProductStatusLogModelTests(TestCase):
    def setUp(self):
        self.assistant = User.objects.create_user(
            username="assistant_bob",
            password="password123",
        )
        self.manager = User.objects.create_user(
            username="manager_alice",
            password="password123",
            is_staff=True,
        )
        # Note: creating a product automatically invokes Product.save(), which creates the initial intake log
        self.product = Product.objects.create(
            raw_note="Vintage Schott leather jacket size 42",
            created_by=self.assistant,
        )

    def test_initial_intake_creates_first_status_log(self):
        # Product creation should automatically record None -> DRAFT with trigger intake
        logs = self.product.status_logs.order_by("created_at")
        self.assertEqual(logs.count(), 1)
        initial_log = logs.first()
        self.assertIsNone(initial_log.from_status)
        self.assertEqual(initial_log.to_status, ProductStatus.DRAFT)
        self.assertEqual(initial_log.changed_by, self.assistant)
        self.assertEqual(initial_log.trigger, "intake")

    def test_log_status_change_creates_explicit_record(self):
        log = log_status_change(
            product=self.product,
            from_status=ProductStatus.DRAFT,
            to_status=ProductStatus.PRICE_PENDING,
            user=self.manager,
            trigger="staging_update",
            notes="Added AI description",
        )
        self.assertIsNotNone(log)
        self.assertEqual(log.product, self.product)
        self.assertEqual(log.from_status, ProductStatus.DRAFT)
        self.assertEqual(log.to_status, ProductStatus.PRICE_PENDING)
        self.assertEqual(log.changed_by, self.manager)
        self.assertEqual(log.trigger, "staging_update")
        self.assertEqual(log.notes, "Added AI description")
        self.assertIsNotNone(log.created_at)

    def test_log_status_change_ignores_noop_transition(self):
        # When from_status == to_status on an existing product, no duplicate log row should be created
        initial_count = self.product.status_logs.count()
        log = log_status_change(
            product=self.product,
            from_status=ProductStatus.DRAFT,
            to_status=ProductStatus.DRAFT,
            user=self.assistant,
        )
        self.assertIsNone(log)
        self.assertEqual(self.product.status_logs.count(), initial_count)

    def test_log_status_change_system_user_fallback(self):
        log = log_status_change(
            product=self.product,
            from_status=ProductStatus.DRAFT,
            to_status=ProductStatus.PRICE_PENDING,
            user=None,
            trigger="system_sync",
            notes="Automated lifecycle sync",
        )
        self.assertIsNotNone(log)
        self.assertIsNone(log.changed_by)
        self.assertEqual(log.trigger, "system_sync")

    def test_string_representation(self):
        log = log_status_change(
            product=self.product,
            from_status=ProductStatus.DRAFT,
            to_status=ProductStatus.READY,
            user=self.manager,
        )
        s = str(log)
        self.assertIn(str(self.product.id), s)
        self.assertIn("draft", s)
        self.assertIn("ready", s)

    def test_cascade_deletion_with_product(self):
        self.assertGreaterEqual(ProductStatusLog.objects.filter(product=self.product).count(), 1)
        self.product.delete()
        self.assertEqual(ProductStatusLog.objects.count(), 0)


class ProductLifecycleTransitionLoggingTests(TestCase):
    def setUp(self):
        self.assistant = User.objects.create_user(
            username="assistant_carl",
            password="password123",
        )
        self.manager = User.objects.create_user(
            username="manager_diana",
            password="password123",
            is_staff=True,
        )
        self.site, _ = MarketplaceSite.objects.get_or_create(
            slug="wallapop",
            defaults={
                "name": "Wallapop",
                "base_url": "https://es.wallapop.com",
            },
        )

    def test_full_lifecycle_trail(self):
        # 1. Intake: assistant creates draft product
        product = Product.objects.create(
            raw_note="1970s Omega Seamaster Automatic Watch",
            created_by=self.assistant,
        )
        self.assertEqual(product.status, ProductStatus.DRAFT)
        self.assertEqual(product.status_logs.count(), 1)
        log1 = product.status_logs.latest("created_at")
        self.assertIsNone(log1.from_status)
        self.assertEqual(log1.to_status, ProductStatus.DRAFT)
        self.assertEqual(log1.changed_by, self.assistant)
        self.assertEqual(log1.trigger, "intake")

        # 2. Manager adds title & description -> PRICE_PENDING
        product.ai_title = "Vintage Omega Seamaster Automatic 1970s"
        product.ai_description = "Stainless steel watch in excellent working condition."
        product.save(changed_by=self.manager)
        self.assertEqual(product.status, ProductStatus.PRICE_PENDING)
        self.assertEqual(product.status_logs.count(), 2)
        log2 = product.status_logs.latest("created_at")
        self.assertEqual(log2.from_status, ProductStatus.DRAFT)
        self.assertEqual(log2.to_status, ProductStatus.PRICE_PENDING)
        self.assertEqual(log2.changed_by, self.manager)
        self.assertEqual(log2.trigger, "description_added")

        # 3. Manager assigns sale price -> READY
        product.sale_price = Decimal("450.00")
        product.save(changed_by=self.manager)
        self.assertEqual(product.status, ProductStatus.READY)
        self.assertEqual(product.status_logs.count(), 3)
        log3 = product.status_logs.latest("created_at")
        self.assertEqual(log3.from_status, ProductStatus.PRICE_PENDING)
        self.assertEqual(log3.to_status, ProductStatus.READY)
        self.assertEqual(log3.changed_by, self.manager)
        self.assertEqual(log3.trigger, "price_assigned")

        # 4. Manager opens clarification doubt -> AWAITING_INFO
        clarification = ProductClarification.objects.create(
            product=product,
            category=ClarificationCategory.FLAWS_CONDITION,
            question="Is the acrylic crystal scratched or replaced?",
            asked_by=self.manager,
        )
        product.refresh_from_db()
        self.assertEqual(product.status, ProductStatus.AWAITING_INFO)
        self.assertEqual(product.status_logs.count(), 4)
        log4 = product.status_logs.latest("created_at")
        self.assertEqual(log4.from_status, ProductStatus.READY)
        self.assertEqual(log4.to_status, ProductStatus.AWAITING_INFO)
        self.assertEqual(log4.changed_by, self.manager)
        self.assertEqual(log4.trigger, "clarification_opened")

        # 5. Assistant answers clarification -> READY
        clarification.resolve(
            answer="Original crystal with light surface wear, unpolished.",
            answered_by=self.assistant,
        )
        product.refresh_from_db()
        self.assertEqual(product.status, ProductStatus.READY)
        self.assertEqual(product.status_logs.count(), 5)
        log5 = product.status_logs.latest("created_at")
        self.assertEqual(log5.from_status, ProductStatus.AWAITING_INFO)
        self.assertEqual(log5.to_status, ProductStatus.READY)
        self.assertEqual(log5.changed_by, self.assistant)
        self.assertEqual(log5.trigger, "clarification_resolved")

        # 6. Manager adds marketplace listing link -> PUBLISHED
        link = ProductListingLink.objects.create(
            product=product,
            site=self.site,
            url="https://es.wallapop.com/item/omega-watch-12345",
            is_active=True,
        )
        product.refresh_from_db()
        self.assertEqual(product.status, ProductStatus.PUBLISHED)
        self.assertEqual(product.status_logs.count(), 6)
        log6 = product.status_logs.latest("created_at")
        self.assertEqual(log6.from_status, ProductStatus.READY)
        self.assertEqual(log6.to_status, ProductStatus.PUBLISHED)
        self.assertEqual(log6.trigger, "marketplace_link_added")

        # 7. Mark as sold -> SOLD
        product.mark_as_sold(price=Decimal("420.00"), user=self.manager)
        product.refresh_from_db()
        self.assertEqual(product.status, ProductStatus.SOLD)
        self.assertTrue(product.is_sold)
        self.assertEqual(product.sale_price, Decimal("420.00"))
        self.assertEqual(product.status_logs.count(), 7)
        log7 = product.status_logs.latest("created_at")
        self.assertEqual(log7.from_status, ProductStatus.PUBLISHED)
        self.assertEqual(log7.to_status, ProductStatus.SOLD)
        self.assertEqual(log7.changed_by, self.manager)
        self.assertEqual(log7.trigger, "marked_sold")
        self.assertIn("€420.00", log7.notes)

        # 8. Revert unsold -> PUBLISHED (because active link exists)
        product.mark_as_unsold(user=self.manager)
        product.refresh_from_db()
        self.assertEqual(product.status, ProductStatus.PUBLISHED)
        self.assertFalse(product.is_sold)
        self.assertEqual(product.status_logs.count(), 8)
        log8 = product.status_logs.latest("created_at")
        self.assertEqual(log8.from_status, ProductStatus.SOLD)
        self.assertEqual(log8.to_status, ProductStatus.PUBLISHED)
        self.assertEqual(log8.changed_by, self.manager)
        self.assertEqual(log8.trigger, "reverted_unsold")

        # 9. Delete marketplace link -> READY
        link.delete()
        product.refresh_from_db()
        self.assertEqual(product.status, ProductStatus.READY)
        self.assertEqual(product.status_logs.count(), 9)
        log9 = product.status_logs.latest("created_at")
        self.assertEqual(log9.from_status, ProductStatus.PUBLISHED)
        self.assertEqual(log9.to_status, ProductStatus.READY)
        self.assertEqual(log9.trigger, "marketplace_link_removed")


class CurrentUserMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="middleware_user", password="password")

    def test_middleware_captures_and_cleans_user(self):
        self.assertIsNone(get_current_user())

        def dummy_view(request):
            # Inside the request context, current user should be available
            captured = get_current_user()
            product = Product.objects.create(raw_note="Created inside middleware view")
            return captured, product

        middleware = CurrentUserMiddleware(dummy_view)
        request = self.factory.get("/")
        request.user = self.user

        captured_user, product = middleware(request)
        self.assertEqual(captured_user, self.user)

        # Product created during this request should have the user automatically attributed
        log = product.status_logs.first()
        self.assertEqual(log.changed_by, self.user)

        # After middleware finishes, context should be clean (None)
        self.assertIsNone(get_current_user())

    def test_set_and_reset_current_user_helpers(self):
        self.assertIsNone(get_current_user())
        token = set_current_user(self.user)
        self.assertEqual(get_current_user(), self.user)
        reset_current_user(token)
        self.assertIsNone(get_current_user())


class AdminStatusLogIntegrationTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username="manager_mary",
            password="password123",
            is_staff=True,
            is_superuser=True,
        )
        self.assistant = User.objects.create_user(
            username="assistant_tom",
            password="password123",
        )
        self.product = Product.objects.create(
            raw_note="Vintage denim jacket",
            created_by=self.assistant,
        )

    def test_admin_permissions_immutability(self):
        from inventory.admin import ProductStatusLogAdmin, ProductStatusLogInline, admin_site

        request = RequestFactory().get("/")
        request.user = self.manager
        model_admin = ProductStatusLogAdmin(ProductStatusLog, admin_site)
        inline = ProductStatusLogInline(Product, admin_site)

        # Immutability: cannot add, change, or delete status logs
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))

        self.assertFalse(inline.has_add_permission(request, self.product))
        self.assertFalse(inline.has_change_permission(request, self.product))
        self.assertFalse(inline.has_delete_permission(request, self.product))

    def test_admin_changelist_and_inline_accessible_by_manager(self):
        from django.urls import reverse

        self.client.login(username="manager_mary", password="password123")
        changelist_url = reverse("admin:inventory_productstatuslog_changelist")
        resp = self.client.get(changelist_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Vintage denim jacket")

        product_change_url = reverse("admin:inventory_product_change", args=[self.product.pk])
        resp_inline = self.client.get(product_change_url)
        self.assertEqual(resp_inline.status_code, 200)
        self.assertContains(resp_inline, "Product Status Logs")

    def test_admin_changelist_forbidden_for_assistant(self):
        from django.urls import reverse

        self.client.login(username="assistant_tom", password="password123")
        changelist_url = reverse("admin:inventory_productstatuslog_changelist")
        resp = self.client.get(changelist_url)
        self.assertEqual(resp.status_code, 403)


class ProductDetailStatusTimelineViewTests(TestCase):
    def setUp(self):

        self.assistant = User.objects.create_user(
            username="assistant_pete",
            password="password123",
        )
        self.manager = User.objects.create_user(
            username="manager_sara",
            password="password123",
            is_staff=True,
        )
        self.product = Product.objects.create(
            raw_note="1980s Vintage Leather Boots size 41",
            created_by=self.assistant,
        )
        # Add another state change
        self.product.ai_title = "Vintage Brown Leather Boots"
        self.product.ai_description = "Handmade leather boots with rubber soles."
        self.product.save(changed_by=self.manager)

    def test_product_detail_renders_timeline_card(self):
        from django.urls import reverse

        self.client.login(username="manager_sara", password="password123")
        url = reverse("inventory:product_detail", args=[self.product.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "status-history-section")
        self.assertContains(resp, "Lifecycle Audit Trail")
        self.assertContains(resp, "2 changes")
        self.assertContains(resp, "assistant_pete")
        self.assertContains(resp, "manager_sara")
        self.assertContains(resp, "intake")
        self.assertContains(resp, "description_added")

    def test_product_detail_accessible_to_assistant_with_timeline(self):
        from django.urls import reverse

        self.client.login(username="assistant_pete", password="password123")
        url = reverse("inventory:product_detail", args=[self.product.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "status-history-section")
        self.assertContains(resp, "Lifecycle Audit Trail")


