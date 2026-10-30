from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import activate, deactivate

from inventory.admin import ProductStatusLogAdmin, admin_site
from inventory.models import (
    Category,
    MarketplaceSite,
    Product,
    ProductCondition,
    ProductImage,
    ProductListingLink,
    ProductStatus,
    ProductStatusLog,
)
from inventory.services.trash_service import (
    empty_all_trash,
    get_trash_metrics,
    get_trash_retention_days,
    purge_expired_trash,
    purge_product_and_media,
)

User = get_user_model()


@override_settings(TURNSTILE_ENABLED=False)
class TrashRetentionAndCleanupTests(TestCase):
    def setUp(self):
        # Create user roles
        self.manager = User.objects.create_user(
            username="test_manager",
            password="password123",
            is_staff=True,
        )
        self.assistant = User.objects.create_user(
            username="test_assistant",
            password="password123",
        )
        asst_group, _ = Group.objects.get_or_create(name="assistants")
        self.assistant.groups.add(asst_group)

        self.category, _ = Category.objects.get_or_create(slug="consoles", defaults={"name": "Consoles"})
        self.site, _ = MarketplaceSite.objects.get_or_create(slug="wallapop", defaults={"name": "Wallapop", "is_active": True})

    def _create_product(self, title="Test Console", is_deleted=False, deleted_days_ago=None):
        prod = Product.objects.create(
            category=self.category,
            raw_note="Good condition",
            ai_title=title,
            ai_description="A test console in great condition.",
            condition=ProductCondition.VERY_GOOD,
            sale_price=Decimal("49.99"),
            status=ProductStatus.READY,
            created_by=self.assistant,
        )
        # Attach dummy image
        img = ProductImage.objects.create(
            product=prod,
            image=SimpleUploadedFile("photo1.webp", b"dummy image data", content_type="image/webp"),
            order=0,
        )
        if is_deleted:
            prod.is_deleted = True
            if deleted_days_ago is not None:
                prod.deleted_at = timezone.now() - timedelta(days=deleted_days_ago)
            else:
                prod.deleted_at = timezone.now()
            prod.deleted_by = self.manager
            prod.save()
        return prod, img

    def test_get_trash_retention_days_setting(self):
        with override_settings(TRASH_RETENTION_DAYS=45):
            self.assertEqual(get_trash_retention_days(), 45)
        with override_settings(TRASH_RETENTION_DAYS="invalid"):
            self.assertEqual(get_trash_retention_days(), 30)

    def test_get_trash_metrics(self):
        # 1 active product
        self._create_product("Active Prod", is_deleted=False)
        # 1 deleted 40 days ago (expired with 30-day retention)
        self._create_product("Old Deleted", is_deleted=True, deleted_days_ago=40)
        # 1 deleted 5 days ago (not expired)
        self._create_product("Recent Deleted", is_deleted=True, deleted_days_ago=5)

        metrics = get_trash_metrics(days=30)
        self.assertEqual(metrics["trash_count"], 2)
        self.assertEqual(metrics["expired_count"], 1)
        self.assertEqual(metrics["total_images"], 2)
        self.assertEqual(metrics["retention_days"], 30)

    def test_purge_active_product_raises_error(self):
        prod, _ = self._create_product("Active Item", is_deleted=False)
        with self.assertRaises(ValueError):
            purge_product_and_media(prod, user=self.manager)

    @patch("django.core.files.storage.default_storage.delete")
    def test_purge_product_and_media_success_and_tombstone(self, mock_storage_delete):
        prod, img = self._create_product("Item To Purge", is_deleted=True, deleted_days_ago=10)
        prod_id = prod.pk
        prod_title = prod.display_title
        image_name = img.image.name

        # Add listing link to verify cascade
        ProductListingLink.objects.create(product=prod, site=self.site, url="https://wallapop.com/item/1")

        result = purge_product_and_media(prod, user=self.manager)
        self.assertTrue(result["success"])
        self.assertEqual(result["images_purged"], 1)
        mock_storage_delete.assert_called_with(image_name)

        # Product and relations deleted
        self.assertFalse(Product.objects.filter(pk=prod_id).exists())
        self.assertFalse(ProductImage.objects.filter(product_id=prod_id).exists())
        self.assertFalse(ProductListingLink.objects.filter(product_id=prod_id).exists())

        # Tombstone status log created
        log = ProductStatusLog.objects.filter(product_id_snapshot=prod_id, trigger="permanently_purged").first()
        self.assertIsNotNone(log)
        self.assertIsNone(log.product)
        self.assertEqual(log.product_title_snapshot, prod_title)
        self.assertEqual(log.changed_by, self.manager)
        self.assertIn("permanently purged", log.notes)

    @patch("django.core.files.storage.default_storage.delete")
    def test_purge_expired_trash_retention_and_dry_run(self, mock_storage_delete):
        # 1 deleted 35 days ago (expired)
        old_prod, _ = self._create_product("Old 35d", is_deleted=True, deleted_days_ago=35)
        # 1 deleted 10 days ago (fresh)
        fresh_prod, _ = self._create_product("Fresh 10d", is_deleted=True, deleted_days_ago=10)

        # Dry run simulation
        dry_res = purge_expired_trash(days=30, dry_run=True, user=self.manager)
        self.assertTrue(dry_res["dry_run"])
        self.assertEqual(dry_res["eligible_count"], 1)
        self.assertEqual(dry_res["eligible_images"], 1)
        self.assertEqual(dry_res["products"][0]["id"], old_prod.pk)
        # Ensure no records or files deleted during dry-run
        self.assertTrue(Product.objects.filter(pk=old_prod.pk).exists())
        mock_storage_delete.assert_not_called()

        # Real purge
        purge_res = purge_expired_trash(days=30, dry_run=False, user=self.manager)
        self.assertFalse(purge_res["dry_run"])
        self.assertEqual(purge_res["purged_count"], 1)
        self.assertEqual(purge_res["purged_images"], 1)

        self.assertFalse(Product.objects.filter(pk=old_prod.pk).exists())
        self.assertTrue(Product.objects.filter(pk=fresh_prod.pk).exists())

    @patch("django.core.files.storage.default_storage.delete")
    def test_empty_all_trash(self, mock_storage_delete):
        prod1, _ = self._create_product("Trash 1", is_deleted=True, deleted_days_ago=40)
        prod2, _ = self._create_product("Trash 2", is_deleted=True, deleted_days_ago=5)
        active_prod, _ = self._create_product("Active Keep", is_deleted=False)

        res = empty_all_trash(user=self.manager)
        self.assertEqual(res["purged_count"], 2)
        self.assertEqual(res["purged_images"], 2)

        self.assertFalse(Product.objects.filter(pk=prod1.pk).exists())
        self.assertFalse(Product.objects.filter(pk=prod2.pk).exists())
        self.assertTrue(Product.objects.filter(pk=active_prod.pk).exists())

    def test_purge_expired_trash_management_command(self):
        prod_expired, _ = self._create_product("Exp 45", is_deleted=True, deleted_days_ago=45)
        prod_fresh, _ = self._create_product("Fresh 5", is_deleted=True, deleted_days_ago=5)

        # Dry-run command
        call_command("purge_expired_trash", "--dry-run", "--quiet")
        self.assertTrue(Product.objects.filter(pk=prod_expired.pk).exists())

        # Purge command with default 30 days
        call_command("purge_expired_trash", "--quiet")
        self.assertFalse(Product.objects.filter(pk=prod_expired.pk).exists())
        self.assertTrue(Product.objects.filter(pk=prod_fresh.pk).exists())

        # Purge all command
        call_command("purge_expired_trash", "--all", "--quiet")
        self.assertFalse(Product.objects.filter(pk=prod_fresh.pk).exists())

    @patch("django.core.files.storage.default_storage.delete")
    def test_product_permanent_delete_view_permissions_and_execution(self, mock_storage_delete):
        prod, _ = self._create_product("Item To Delete", is_deleted=True, deleted_days_ago=10)
        url = reverse("inventory:product_permanent_delete", kwargs={"pk": prod.pk})

        # Anonymous cannot delete
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp.url)

        # Assistant cannot delete (403 Forbidden)
        self.client.login(username="test_assistant", password="password123")
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Product.objects.filter(pk=prod.pk).exists())
        self.client.logout()

        # Manager GET is 405 Method Not Allowed
        self.client.login(username="test_manager", password="password123")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 405)

        # Manager POST permanently deletes
        resp = self.client.post(url)
        self.assertRedirects(resp, f"{reverse('inventory:dashboard')}?status=erased")
        self.assertFalse(Product.objects.filter(pk=prod.pk).exists())

    def test_product_permanent_delete_view_rejects_active_product(self):
        active_prod, _ = self._create_product("Active Reject", is_deleted=False)
        url = reverse("inventory:product_permanent_delete", kwargs={"pk": active_prod.pk})

        self.client.login(username="test_manager", password="password123")
        resp = self.client.post(url)
        self.assertRedirects(resp, reverse("inventory:product_detail", kwargs={"pk": active_prod.pk}))
        self.assertTrue(Product.objects.filter(pk=active_prod.pk).exists())

    @patch("django.core.files.storage.default_storage.delete")
    def test_dashboard_empty_trash_view(self, mock_storage_delete):
        old_prod, _ = self._create_product("Old Expired", is_deleted=True, deleted_days_ago=35)
        fresh_prod, _ = self._create_product("Fresh Recent", is_deleted=True, deleted_days_ago=5)
        url = reverse("inventory:dashboard_empty_trash")

        # Assistant 403
        self.client.login(username="test_assistant", password="password123")
        resp = self.client.post(url, {"mode": "expired"})
        self.assertEqual(resp.status_code, 403)
        self.client.logout()

        self.client.login(username="test_manager", password="password123")

        # Manager GET 405
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 405)

        # Mode: expired
        resp = self.client.post(url, {"mode": "expired"})
        self.assertRedirects(resp, f"{reverse('inventory:dashboard')}?status=erased")
        self.assertFalse(Product.objects.filter(pk=old_prod.pk).exists())
        self.assertTrue(Product.objects.filter(pk=fresh_prod.pk).exists())

        # Mode: all
        resp = self.client.post(url, {"mode": "all"})
        self.assertRedirects(resp, f"{reverse('inventory:dashboard')}?status=erased")
        self.assertFalse(Product.objects.filter(pk=fresh_prod.pk).exists())

    def test_dashboard_trash_toolbar_and_detail_button_rendering(self):
        prod, _ = self._create_product("Soft Deleted Item", is_deleted=True, deleted_days_ago=35)

        self.client.login(username="test_manager", password="password123")

        # Dashboard Trash view
        dash_url = f"{reverse('inventory:dashboard')}?status=erased"
        resp = self.client.get(dash_url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("trash_metrics", resp.context)
        self.assertEqual(resp.context["trash_metrics"]["expired_count"], 1)
        self.assertContains(resp, "trashManagementToolbar")
        self.assertContains(resp, "btnEmptyExpiredTrash")
        self.assertContains(resp, "btnEmptyAllTrash")

        # Product detail view of soft-deleted item
        detail_url = reverse("inventory:product_detail", kwargs={"pk": prod.pk})
        resp = self.client.get(detail_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "btnPermanentDelete")
        self.assertContains(resp, "btnPermanentDeleteTop")

    def test_admin_product_status_log_purged_display(self):
        prod, _ = self._create_product("Item Admin", is_deleted=True, deleted_days_ago=10)
        prod_id = prod.pk
        purge_product_and_media(prod, user=self.manager)

        log = ProductStatusLog.objects.filter(product_id_snapshot=prod_id, trigger="permanently_purged").first()
        self.assertIsNotNone(log)

        admin = ProductStatusLogAdmin(ProductStatusLog, admin_site)
        link_html = admin.product_link(log)
        self.assertIn(f"#{prod_id}", link_html)
        self.assertIn("Purged", link_html)

        badge_html = admin.to_status_badge(log)
        self.assertIn("Purged", badge_html)

    def test_spanish_localization(self):
        activate("es")
        try:
            prod, _ = self._create_product("Producto Español", is_deleted=True, deleted_days_ago=35)
            self.client.login(username="test_manager", password="password123")

            dash_url = f"{reverse('inventory:dashboard')}?status=erased"
            resp = self.client.get(dash_url, headers={"accept-language": "es"})
            self.assertEqual(resp.status_code, 200)
            self.assertContains(resp, "Papelera y limpieza de almacenamiento")
            self.assertContains(resp, "Vaciar caducados")
            self.assertContains(resp, "Vaciar toda la papelera")

            detail_url = reverse("inventory:product_detail", kwargs={"pk": prod.pk})
            resp = self.client.get(detail_url, headers={"accept-language": "es"})
            self.assertEqual(resp.status_code, 200)
            self.assertContains(resp, "Eliminar definitivamente")
        finally:
            deactivate()
