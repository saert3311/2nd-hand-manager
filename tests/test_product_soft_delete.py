from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from inventory.admin import ProductAdmin, admin_site
from inventory.models import (
    Product,
    ProductStatus,
    ProductStatusLog,
)
from inventory.permissions import ROLE_ASSISTANT, ROLE_MANAGER

User = get_user_model()


class ProductSoftDeleteTestCase(TestCase):
    def setUp(self):
        self.assistant_group, _ = Group.objects.get_or_create(name=ROLE_ASSISTANT)
        self.manager_group, _ = Group.objects.get_or_create(name=ROLE_MANAGER)

        self.manager = User.objects.create_user(
            username="testmanager",
            password="managerpassword123",
            is_staff=True,
        )
        self.manager.groups.add(self.manager_group)

        self.assistant = User.objects.create_user(
            username="testassistant",
            password="assistantpassword123",
            is_staff=False,
        )
        self.assistant.groups.add(self.assistant_group)

        self.client = Client()

    # 1. Model Domain Tests
    def test_soft_delete_and_restore_model_methods(self):
        product = Product.objects.create(
            raw_note="Vintage Leather Boots",
            ai_title="Vintage Leather Boots Size 42",
            ai_description="Great boots in excellent vintage condition",
            sale_price=Decimal("55.00"),
            status=ProductStatus.READY,
            created_by=self.assistant,
        )
        self.assertFalse(product.is_deleted)
        self.assertIsNone(product.deleted_at)
        self.assertIsNone(product.deleted_by)

        # Soft delete
        product.soft_delete(user=self.manager, reason="Damaged sole found")
        product.refresh_from_db()

        self.assertTrue(product.is_deleted)
        self.assertIsNotNone(product.deleted_at)
        self.assertEqual(product.deleted_by, self.manager)
        # Original status is preserved
        self.assertEqual(product.status, ProductStatus.READY)

        # Audit log verification
        log = ProductStatusLog.objects.filter(product=product).order_by("-created_at").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.trigger, "soft_deleted")
        self.assertIn("Damaged sole found", log.notes)
        self.assertEqual(log.changed_by, self.manager)

        # Restore
        product.restore(user=self.manager)
        product.refresh_from_db()

        self.assertFalse(product.is_deleted)
        self.assertIsNone(product.deleted_at)
        self.assertIsNone(product.deleted_by)
        self.assertEqual(product.status, ProductStatus.READY)

        restore_log = ProductStatusLog.objects.filter(product=product).order_by("-created_at").first()
        self.assertIsNotNone(restore_log)
        self.assertEqual(restore_log.trigger, "restored")
        self.assertEqual(restore_log.changed_by, self.manager)

    # 2. Dashboard Query and Counter Isolation
    def test_dashboard_excludes_erased_products_from_normal_views_and_counts(self):
        # Create 2 active products
        p1 = Product.objects.create(
            raw_note="Active Shirt",
            status=ProductStatus.DRAFT,
            created_by=self.assistant,
        )
        p2 = Product.objects.create(
            raw_note="Active Coat",
            status=ProductStatus.READY,
            created_by=self.assistant,
        )
        # Create 1 erased product
        p_erased = Product.objects.create(
            raw_note="Erased Pants",
            status=ProductStatus.DRAFT,
            created_by=self.assistant,
        )
        p_erased.soft_delete(user=self.manager)

        self.client.login(username="testmanager", password="managerpassword123")
        response = self.client.get(reverse("inventory:dashboard"))
        self.assertEqual(response.status_code, 200)

        products = list(response.context["products"])
        self.assertIn(p1, products)
        self.assertIn(p2, products)
        self.assertNotIn(p_erased, products)

        # Counters isolation
        self.assertEqual(response.context["total_count"], 2)
        self.assertEqual(response.context["erased_count"], 1)

    def test_dashboard_erased_tab_shows_only_erased_products(self):
        p_active = Product.objects.create(
            raw_note="Active Bag",
            status=ProductStatus.DRAFT,
            created_by=self.assistant,
        )
        p_erased = Product.objects.create(
            raw_note="Erased Bag",
            status=ProductStatus.DRAFT,
            created_by=self.assistant,
        )
        p_erased.soft_delete(user=self.manager)

        self.client.login(username="testmanager", password="managerpassword123")
        response = self.client.get(reverse("inventory:dashboard") + "?status=erased")
        self.assertEqual(response.status_code, 200)

        products = list(response.context["products"])
        self.assertIn(p_erased, products)
        self.assertNotIn(p_active, products)
        self.assertEqual(response.context["erased_count"], 1)

        content = response.content.decode("utf-8")
        self.assertIn("tab-erased", content)

    # 3. Multi-field Search Scoping Isolation
    def test_search_isolation_between_active_and_erased(self):
        p_active = Product.objects.create(
            raw_note="SpecialExclusiveItemActive",
            status=ProductStatus.READY,
            created_by=self.assistant,
        )
        p_erased = Product.objects.create(
            raw_note="SpecialExclusiveItemErased",
            status=ProductStatus.READY,
            created_by=self.assistant,
        )
        p_erased.soft_delete(user=self.manager)

        self.client.login(username="testmanager", password="managerpassword123")

        # Global search: should only match active item
        resp_active = self.client.get(reverse("inventory:dashboard") + "?q=SpecialExclusiveItem")
        active_list = list(resp_active.context["products"])
        self.assertIn(p_active, active_list)
        self.assertNotIn(p_erased, active_list)

        # Search inside erased category: should only match erased item
        resp_erased = self.client.get(reverse("inventory:dashboard") + "?status=erased&q=SpecialExclusiveItem")
        erased_list = list(resp_erased.context["products"])
        self.assertIn(p_erased, erased_list)
        self.assertNotIn(p_active, erased_list)

    # 4. View POST Execution & Manager Authorization
    def test_manager_can_soft_delete_and_restore_via_views(self):
        product = Product.objects.create(
            raw_note="Hat to be erased",
            status=ProductStatus.DRAFT,
            created_by=self.assistant,
        )

        self.client.login(username="testmanager", password="managerpassword123")

        # Soft delete POST
        delete_url = reverse("inventory:product_soft_delete", kwargs={"pk": product.pk})
        resp = self.client.post(delete_url)
        self.assertRedirects(resp, reverse("inventory:dashboard") + "?status=erased")

        product.refresh_from_db()
        self.assertTrue(product.is_deleted)
        self.assertEqual(product.deleted_by, self.manager)

        # Restore POST
        restore_url = reverse("inventory:product_restore", kwargs={"pk": product.pk})
        resp_restore = self.client.post(restore_url)
        self.assertRedirects(resp_restore, reverse("inventory:product_detail", kwargs={"pk": product.pk}))

        product.refresh_from_db()
        self.assertFalse(product.is_deleted)
        self.assertIsNone(product.deleted_at)

    def test_assistant_cannot_soft_delete_or_restore(self):
        product = Product.objects.create(
            raw_note="Hat protected",
            status=ProductStatus.DRAFT,
            created_by=self.assistant,
        )

        self.client.login(username="testassistant", password="assistantpassword123")

        # Assistant attempt to delete -> 403 Forbidden
        delete_url = reverse("inventory:product_soft_delete", kwargs={"pk": product.pk})
        resp = self.client.post(delete_url)
        self.assertEqual(resp.status_code, 403)

        product.refresh_from_db()
        self.assertFalse(product.is_deleted)

        # Mark as deleted by manager first
        product.soft_delete(user=self.manager)

        # Assistant attempt to restore -> 403 Forbidden
        restore_url = reverse("inventory:product_restore", kwargs={"pk": product.pk})
        resp_restore = self.client.post(restore_url)
        self.assertEqual(resp_restore.status_code, 403)

    def test_assistant_cannot_view_erased_product_detail(self):
        product = Product.objects.create(
            raw_note="Erased product hidden",
            status=ProductStatus.DRAFT,
            created_by=self.assistant,
        )
        product.soft_delete(user=self.manager)

        # Assistant gets redirected
        self.client.login(username="testassistant", password="assistantpassword123")
        resp = self.client.get(reverse("inventory:product_detail", kwargs={"pk": product.pk}))
        self.assertRedirects(resp, reverse("inventory:dashboard"))

        # Manager can view erased product detail with banner
        self.client.login(username="testmanager", password="managerpassword123")
        resp_mgr = self.client.get(reverse("inventory:product_detail", kwargs={"pk": product.pk}))
        self.assertEqual(resp_mgr.status_code, 200)
        content = resp_mgr.content.decode("utf-8")
        self.assertIn("erasedProductBanner", content)
        self.assertIn("btnRestoreProduct", content)

    def test_views_reject_non_post_requests(self):
        product = Product.objects.create(
            raw_note="HTTP Method Test Item",
            status=ProductStatus.DRAFT,
            created_by=self.assistant,
        )
        self.client.login(username="testmanager", password="managerpassword123")

        get_resp_delete = self.client.get(reverse("inventory:product_soft_delete", kwargs={"pk": product.pk}))
        self.assertEqual(get_resp_delete.status_code, 405)

        get_resp_restore = self.client.get(reverse("inventory:product_restore", kwargs={"pk": product.pk}))
        self.assertEqual(get_resp_restore.status_code, 405)

    # 5. Admin Integration Tests
    def test_admin_bulk_soft_delete_and_restore(self):
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.test import RequestFactory

        p1 = Product.objects.create(raw_note="Admin item 1", created_by=self.assistant)
        p2 = Product.objects.create(raw_note="Admin item 2", created_by=self.assistant)

        admin_instance = ProductAdmin(Product, admin_site)

        request = RequestFactory().get("/")
        request.user = self.manager
        setattr(request, "session", "session")
        messages = FallbackStorage(request)
        setattr(request, "_messages", messages)

        # Test soft_delete_selected
        admin_instance.soft_delete_selected(
            request=request,
            queryset=Product.objects.filter(pk__in=[p1.pk, p2.pk]),
        )
        p1.refresh_from_db()
        p2.refresh_from_db()
        self.assertTrue(p1.is_deleted)
        self.assertTrue(p2.is_deleted)

        # Test restore_selected
        admin_instance.restore_selected(
            request=request,
            queryset=Product.objects.filter(pk__in=[p1.pk, p2.pk]),
        )
        p1.refresh_from_db()
        p2.refresh_from_db()
        self.assertFalse(p1.is_deleted)
        self.assertFalse(p2.is_deleted)

    # 6. Bilingual Localization Verification
    def test_spanish_localization(self):
        product = Product.objects.create(raw_note="i18n test item", created_by=self.assistant)
        product.soft_delete(user=self.manager)

        self.client.login(username="testmanager", password="managerpassword123")

        response = self.client.get(
            reverse("inventory:product_detail", kwargs={"pk": product.pk}),
            HTTP_ACCEPT_LANGUAGE="es",
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Este producto está en la papelera", content)
        self.assertIn("Restaurar producto", content)
