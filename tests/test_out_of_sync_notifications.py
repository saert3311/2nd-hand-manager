import io
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import translation
from PIL import Image

from inventory.models import (
    ClarificationCategory,
    MarketplaceSite,
    Product,
    ProductClarification,
    ProductImage,
    ProductListingLink,
    ProductStatus,
)
from inventory.permissions import ROLE_ASSISTANT, ROLE_MANAGER
from inventory.services.push_service import send_out_of_sync_notification

User = get_user_model()


def create_test_image(filename="test.png", color="blue"):
    img_byte_arr = io.BytesIO()
    image = Image.new("RGB", (100, 100), color=color)
    image.save(img_byte_arr, format="PNG")
    img_byte_arr.seek(0)
    return SimpleUploadedFile(filename, img_byte_arr.read(), content_type="image/png")


@override_settings(
    PUSH_NOTIFICATIONS_LIVE_SIGNALS=True,
    VAPID_PUBLIC_KEY="test_vapid_public_key",
    VAPID_PRIVATE_KEY="test_vapid_private_key",
)
class OutOfSyncNotificationServiceTests(TestCase):
    def setUp(self):
        self.mgr_group, _ = Group.objects.get_or_create(name=ROLE_MANAGER)
        self.manager = User.objects.create_user(
            username="manager_service_test",
            password="password123",
            is_staff=True,
        )
        self.manager.groups.add(self.mgr_group)

        self.product = Product.objects.create(
            ai_title="Vintage Leather Jacket",
            ai_description="Classic vintage leather biker jacket.",
            sale_price=Decimal("120.00"),
            status=ProductStatus.READY,
        )

    @override_settings(PUSH_NOTIFICATIONS_LIVE_SIGNALS=False)
    @patch("inventory.services.push_service.send_push_to_group")
    def test_send_out_of_sync_notification_disabled_when_live_signals_false(self, mock_push):
        sent = send_out_of_sync_notification(self.product)
        self.assertEqual(sent, 0)
        mock_push.assert_not_called()

    @override_settings(VAPID_PUBLIC_KEY="", VAPID_PRIVATE_KEY="")
    @patch("inventory.services.push_service.send_push_to_group")
    def test_send_out_of_sync_notification_disabled_when_push_not_configured(self, mock_push):
        sent = send_out_of_sync_notification(self.product)
        self.assertEqual(sent, 0)
        mock_push.assert_not_called()

    @patch("inventory.services.push_service.send_push_to_group")
    def test_send_out_of_sync_notification_dispatches_to_role_manager(self, mock_push):
        mock_push.return_value = 1
        sent = send_out_of_sync_notification(self.product)
        self.assertEqual(sent, 1)

        mock_push.assert_called_once()
        _, kwargs = mock_push.call_args
        self.assertEqual(kwargs["group_name"], ROLE_MANAGER)
        self.assertIn(self.product.display_title, kwargs["title"])
        self.assertIn("⚠️", kwargs["title"])
        self.assertEqual(kwargs["url"], f"/products/{self.product.pk}/")
        self.assertEqual(kwargs["tag"], f"product-out-of-sync-{self.product.pk}")

    @patch("inventory.services.push_service.send_push_to_group")
    def test_send_out_of_sync_notification_spanish_localization(self, mock_push):
        mock_push.return_value = 1
        with translation.override("es"):
            send_out_of_sync_notification(self.product)

        mock_push.assert_called_once()
        _, kwargs = mock_push.call_args
        self.assertIn("⚠️ Producto desincronizado:", kwargs["title"])
        self.assertIn("Cambios detectados en producto publicado", kwargs["body"])

    @patch("inventory.services.push_service.send_push_to_group")
    def test_send_out_of_sync_notification_with_change_reasons(self, mock_push):
        mock_push.return_value = 1
        self.product.needs_platform_sync = True
        self.product.platform_sync_reasons = ["photos", "price"]

        # English
        with translation.override("en"):
            send_out_of_sync_notification(self.product)
        _, kwargs_en = mock_push.call_args
        self.assertIn("Updated: Photos, Price. External platform listings require updating.", kwargs_en["body"])

        # Spanish
        with translation.override("es"):
            send_out_of_sync_notification(self.product)
        _, kwargs_es = mock_push.call_args
        self.assertIn("Actualizado: Fotos, Precio. Se requiere actualizar las plataformas externas.", kwargs_es["body"])


@override_settings(
    PUSH_NOTIFICATIONS_LIVE_SIGNALS=True,
    VAPID_PUBLIC_KEY="test_vapid_public_key",
    VAPID_PRIVATE_KEY="test_vapid_private_key",
)
class OutOfSyncNotificationLifecycleTests(TestCase):
    def setUp(self):
        self.mgr_group, _ = Group.objects.get_or_create(name=ROLE_MANAGER)
        self.asst_group, _ = Group.objects.get_or_create(name=ROLE_ASSISTANT)

        self.manager = User.objects.create_user(
            username="manager_lifecycle",
            password="password123",
            is_staff=True,
        )
        self.manager.groups.add(self.mgr_group)

        self.assistant = User.objects.create_user(
            username="assistant_lifecycle",
            password="password123",
        )
        self.assistant.groups.add(self.asst_group)

        self.client_mgr = Client()
        self.client_mgr.login(username="manager_lifecycle", password="password123")

        self.site, _ = MarketplaceSite.objects.get_or_create(
            slug="wallapop",
            defaults={"name": "Wallapop", "domain": "wallapop.com", "order": 1},
        )

        # Create published product with photo and active link
        self.product = Product.objects.create(
            ai_title="Chaqueta Vintage",
            ai_description="Chaqueta vintage de cuero auténtico.",
            sale_price=Decimal("150.00"),
            created_by=self.assistant,
        )
        ProductImage.objects.create(product=self.product, image=create_test_image("img1.png"), order=0)
        ProductListingLink.objects.create(
            product=self.product,
            site=self.site,
            url="https://es.wallapop.com/item/test-item-123",
            is_active=True,
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, ProductStatus.PUBLISHED)
        self.assertFalse(self.product.needs_platform_sync)

    @patch("inventory.services.push_service.send_out_of_sync_notification")
    def test_price_change_on_published_product_triggers_notification(self, mock_notify):
        mock_notify.return_value = 1
        self.product.sale_price = Decimal("130.00")
        self.product.save()

        self.product.refresh_from_db()
        self.assertTrue(self.product.needs_platform_sync)
        mock_notify.assert_called_once_with(self.product)

    @patch("inventory.services.push_service.send_out_of_sync_notification")
    def test_subsequent_price_change_on_already_out_of_sync_does_not_spam(self, mock_notify):
        mock_notify.return_value = 1
        # Initial change transitions False -> True
        self.product.sale_price = Decimal("130.00")
        self.product.save()
        self.assertEqual(mock_notify.call_count, 1)

        # Subsequent change while needs_platform_sync remains True
        self.product.sale_price = Decimal("120.00")
        self.product.save()
        # Must still be 1 (no duplicate notification dispatched)
        self.assertEqual(mock_notify.call_count, 1)

    @patch("inventory.services.push_service.send_out_of_sync_notification")
    def test_title_change_on_published_product_triggers_notification(self, mock_notify):
        mock_notify.return_value = 1
        self.product.ai_title = "Chaqueta Vintage Especial Edición"
        self.product.save()

        self.product.refresh_from_db()
        self.assertTrue(self.product.needs_platform_sync)
        mock_notify.assert_called_once_with(self.product)

    @patch("inventory.services.push_service.send_out_of_sync_notification")
    def test_description_change_on_published_product_triggers_notification(self, mock_notify):
        mock_notify.return_value = 1
        self.product.ai_description = "Chaqueta vintage de cuero auténtico con cremalleras metálicas YKK."
        self.product.save()

        self.product.refresh_from_db()
        self.assertTrue(self.product.needs_platform_sync)
        mock_notify.assert_called_once_with(self.product)

    @patch("inventory.services.push_service.send_out_of_sync_notification")
    def test_clear_platform_sync_does_not_trigger_notification(self, mock_notify):
        # First put it out of sync
        self.product.needs_platform_sync = True
        self.product.save(update_fields=["needs_platform_sync"])
        mock_notify.reset_mock()

        # Clear platform sync
        self.product.mark_platform_synced(user=self.manager)
        self.product.refresh_from_db()
        self.assertFalse(self.product.needs_platform_sync)

        # Notification must NOT be dispatched on clearance
        mock_notify.assert_not_called()

    @patch("inventory.services.push_service.send_out_of_sync_notification")
    def test_re_sync_cycle_after_clearance_triggers_notification(self, mock_notify):
        # 1. Put out of sync
        self.product.sale_price = Decimal("140.00")
        self.product.save()
        self.assertEqual(mock_notify.call_count, 1)

        # 2. Mark synced
        self.product.mark_platform_synced(user=self.manager)
        self.product.refresh_from_db()
        self.assertFalse(self.product.needs_platform_sync)
        mock_notify.reset_mock()

        # 3. New edit after sync was cleared
        self.product.sale_price = Decimal("135.00")
        self.product.save()
        self.product.refresh_from_db()
        self.assertTrue(self.product.needs_platform_sync)

        # Fresh notification must be dispatched
        mock_notify.assert_called_once_with(self.product)

    @patch("inventory.services.push_service.send_out_of_sync_notification")
    def test_photo_upload_on_published_product_triggers_notification(self, mock_notify):
        mock_notify.return_value = 1
        upload_url = reverse("inventory:product_upload_images", kwargs={"pk": self.product.pk})
        img = create_test_image("img2.png", color="green")
        response = self.client_mgr.post(upload_url, {"images": [img]}, follow=True)

        self.assertEqual(response.status_code, 200)
        self.product.refresh_from_db()
        self.assertTrue(self.product.needs_platform_sync)
        self.assertEqual(mock_notify.call_count, 1)

    @patch("inventory.services.push_service.send_out_of_sync_notification")
    def test_photo_delete_on_published_product_triggers_notification(self, mock_notify):
        # Add a 2nd image first without triggering published sync
        img2 = ProductImage.objects.create(product=self.product, image=create_test_image("img2.png"), order=1)
        self.product.needs_platform_sync = False
        self.product.save(update_fields=["needs_platform_sync"])
        mock_notify.reset_mock()

        # Delete image
        del_url = reverse("inventory:product_delete_image", kwargs={"pk": self.product.pk, "image_id": img2.pk})
        response = self.client_mgr.post(del_url, follow=True)

        self.assertEqual(response.status_code, 200)
        self.product.refresh_from_db()
        self.assertTrue(self.product.needs_platform_sync)
        self.assertEqual(mock_notify.call_count, 1)

    @patch("inventory.services.push_service.send_out_of_sync_notification")
    def test_photo_reorder_cover_on_published_product_triggers_notification(self, mock_notify):
        img1 = self.product.images.first()
        img2 = ProductImage.objects.create(product=self.product, image=create_test_image("img2.png"), order=1)
        self.product.needs_platform_sync = False
        self.product.save(update_fields=["needs_platform_sync"])
        mock_notify.reset_mock()

        reorder_url = reverse("inventory:product_reorder_images", kwargs={"pk": self.product.pk})
        # Switch order so img2 is new cover (#0)
        response = self.client_mgr.post(
            reorder_url,
            data={"image_ids": [img2.pk, img1.pk]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.product.refresh_from_db()
        self.assertTrue(self.product.needs_platform_sync)
        self.assertEqual(mock_notify.call_count, 1)

    @patch("inventory.services.push_service.send_out_of_sync_notification")
    def test_clarification_on_published_product_triggers_notification(self, mock_notify):
        mock_notify.return_value = 1
        ProductClarification.objects.create(
            product=self.product,
            category=ClarificationCategory.FLAWS_CONDITION,
            question="¿Tiene roces en la manga izquierda?",
            asked_by=self.manager,
        )
        self.product.refresh_from_db()
        self.assertTrue(self.product.needs_platform_sync)
        self.assertEqual(mock_notify.call_count, 1)

    @patch("inventory.services.push_service.send_out_of_sync_notification")
    def test_draft_or_unpublished_product_edits_do_not_trigger_notification(self, mock_notify):
        # Create an unpublished draft product
        draft_product = Product.objects.create(
            status=ProductStatus.DRAFT,
            created_by=self.assistant,
        )
        mock_notify.reset_mock()

        # Edit draft product
        draft_product.ai_title = "New draft title"
        draft_product.save()

        draft_product.refresh_from_db()
        self.assertFalse(draft_product.needs_platform_sync)
        mock_notify.assert_not_called()

    @patch("inventory.services.push_service.send_out_of_sync_notification")
    def test_soft_deleted_product_does_not_trigger_notification(self, mock_notify):
        # Soft delete the published product
        self.product.soft_delete(user=self.manager)
        mock_notify.reset_mock()

        # Modify soft-deleted product
        self.product.sale_price = Decimal("99.00")
        self.product.save()

        mock_notify.assert_not_called()
