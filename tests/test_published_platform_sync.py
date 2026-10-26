import io
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from PIL import Image

from inventory.models import (
    ClarificationCategory,
    ClarificationStatus,
    MarketplaceSite,
    Product,
    ProductClarification,
    ProductImage,
    ProductListingLink,
    ProductStatus,
)
from inventory.permissions import ROLE_ASSISTANT, ROLE_MANAGER

User = get_user_model()


def create_test_image(filename="test.png", color="red"):
    img_byte_arr = io.BytesIO()
    image = Image.new("RGB", (100, 100), color=color)
    image.save(img_byte_arr, format="PNG")
    img_byte_arr.seek(0)
    return SimpleUploadedFile(filename, img_byte_arr.read(), content_type="image/png")


class PublishedProductPlatformSyncTests(TestCase):
    def setUp(self):
        # Set up roles
        self.mgr_group, _ = Group.objects.get_or_create(name=ROLE_MANAGER)
        self.asst_group, _ = Group.objects.get_or_create(name=ROLE_ASSISTANT)

        self.manager = User.objects.create_user(
            username="manager_sync",
            password="password123",
            is_staff=True,
        )
        self.manager.groups.add(self.mgr_group)

        self.assistant = User.objects.create_user(
            username="assistant_sync",
            password="password123",
        )
        self.assistant.groups.add(self.asst_group)

        self.client_mgr = Client()
        self.client_mgr.login(username="manager_sync", password="password123")

        self.client_asst = Client()
        self.client_asst.login(username="assistant_sync", password="password123")

        self.site, _ = MarketplaceSite.objects.get_or_create(
            slug="wallapop",
            defaults={
                "name": "Wallapop",
                "base_url": "https://es.wallapop.com",
                "order": 1,
                "is_active": True,
            },
        )
        self.site.is_active = True
        self.site.save()

        # Create published product with 2 images
        self.product = Product.objects.create(
            raw_note="Vintage Schott Jacket",
            ai_title="Schott Leather Moto Jacket Size 42",
            ai_description="Authentic heavy Schott NYC steerhide motorcycle jacket in excellent condition.",
            sale_price=Decimal("250.00"),
            created_by=self.manager,
        )
        self.img1 = ProductImage.objects.create(
            product=self.product,
            image=create_test_image("img1.png", "blue"),
            order=0,
        )
        self.img2 = ProductImage.objects.create(
            product=self.product,
            image=create_test_image("img2.png", "green"),
            order=1,
        )
        self.link = ProductListingLink.objects.create(
            product=self.product,
            site=self.site,
            url="https://es.wallapop.com/item/schott-123",
            is_active=True,
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, ProductStatus.PUBLISHED)
        self.assertFalse(self.product.needs_platform_sync)

    def test_initial_published_product_is_in_sync(self):
        self.assertFalse(self.product.needs_platform_sync)
        self.assertIsNone(self.product.last_platform_synced_at)

    def test_price_change_on_published_product_triggers_sync(self):
        self.product.sale_price = Decimal("220.00")
        self.product.save(changed_by=self.manager)
        self.product.refresh_from_db()
        self.assertTrue(self.product.needs_platform_sync)

    def test_title_change_on_published_product_triggers_sync(self):
        self.product.ai_title = "Schott Leather Moto Jacket Size 42 Black"
        self.product.save(changed_by=self.manager)
        self.product.refresh_from_db()
        self.assertTrue(self.product.needs_platform_sync)

    def test_description_change_on_published_product_triggers_sync(self):
        self.product.ai_description = "Updated description: Schott steerhide moto jacket with brass zippers."
        self.product.save(changed_by=self.manager)
        self.product.refresh_from_db()
        self.assertTrue(self.product.needs_platform_sync)

    def test_unrelated_field_change_does_not_trigger_sync(self):
        # Changing raw_note should not trigger platform sync
        self.product.raw_note = "Updated internal notes only"
        self.product.save(changed_by=self.manager)
        self.product.refresh_from_db()
        self.assertFalse(self.product.needs_platform_sync)

    def test_draft_product_price_change_does_not_trigger_sync(self):
        draft = Product.objects.create(
            raw_note="Raw unlisted item",
            created_by=self.manager,
        )
        self.assertEqual(draft.status, ProductStatus.DRAFT)
        draft.sale_price = Decimal("50.00")
        draft.save(changed_by=self.manager)
        draft.refresh_from_db()
        self.assertFalse(draft.needs_platform_sync)

    def test_mark_platform_synced_method_clears_flag_and_logs(self):
        self.product.needs_platform_sync = True
        self.product.save(update_fields=["needs_platform_sync"])

        self.product.mark_platform_synced(user=self.manager)
        self.product.refresh_from_db()

        self.assertFalse(self.product.needs_platform_sync)
        self.assertIsNotNone(self.product.last_platform_synced_at)

        log = self.product.status_logs.filter(trigger="platform_sync_cleared").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.changed_by, self.manager)
        self.assertIn("synchronized", log.notes.lower())

    def test_clarification_question_on_published_product_triggers_sync(self):
        ProductClarification.objects.create(
            product=self.product,
            category=ClarificationCategory.MEASUREMENTS,
            question="Is the chest 42 inches pit to pit?",
            asked_by=self.manager,
        )
        self.product.refresh_from_db()
        self.assertTrue(self.product.needs_platform_sync)

    def test_direct_clarification_note_on_published_product_triggers_sync(self):
        ProductClarification.objects.create(
            product=self.product,
            category=ClarificationCategory.MATERIAL_AUTHENTICITY,
            is_direct_note=True,
            question="Direct Note",
            answer="Lining is 100% heavy quilted nylon.",
            asked_by=self.assistant,
            answered_by=self.assistant,
            status=ClarificationStatus.RESOLVED,
        )
        self.product.refresh_from_db()
        self.assertTrue(self.product.needs_platform_sync)

    def test_manager_can_upload_additional_photos(self):
        url = reverse("inventory:product_upload_images", kwargs={"pk": self.product.pk})
        new_photo = create_test_image("img3.png", "yellow")
        response = self.client_mgr.post(url, {"images": [new_photo]}, follow=True)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(self.product.images.count(), 3)
        self.product.refresh_from_db()
        self.assertTrue(self.product.needs_platform_sync)

    def test_upload_exceeding_10_photos_is_rejected(self):
        # Create 8 more images so total is 10
        for i in range(8):
            ProductImage.objects.create(
                product=self.product,
                image=create_test_image(f"batch_{i}.png", "purple"),
                order=2 + i,
            )
        self.assertEqual(self.product.images.count(), 10)

        url = reverse("inventory:product_upload_images", kwargs={"pk": self.product.pk})
        extra_photo = create_test_image("img11.png", "white")
        response = self.client_mgr.post(url, {"images": [extra_photo]}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.product.images.count(), 10)
        self.assertContains(response, "maximum is 10")

    def test_manager_can_delete_photo_and_triggers_sync(self):
        url = reverse("inventory:product_delete_image", kwargs={"pk": self.product.pk, "image_id": self.img2.id})
        response = self.client_mgr.post(url, follow=True)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(self.product.images.count(), 1)
        self.assertFalse(ProductImage.objects.filter(id=self.img2.id).exists())
        self.product.refresh_from_db()
        self.assertTrue(self.product.needs_platform_sync)

    def test_cannot_delete_last_remaining_photo(self):
        # Delete img2 first
        self.img2.delete()
        self.assertEqual(self.product.images.count(), 1)

        # Attempt to delete img1
        url = reverse("inventory:product_delete_image", kwargs={"pk": self.product.pk, "image_id": self.img1.id})
        response = self.client_mgr.post(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.product.images.count(), 1)
        self.assertContains(response, "Cannot delete the only photo")

    def test_reordering_primary_cover_on_published_product_triggers_sync(self):
        url = reverse("inventory:product_reorder_images", kwargs={"pk": self.product.pk})
        # Reverse image order so img2 becomes the cover (#0)
        response = self.client_mgr.post(
            url,
            data={"image_ids": [self.img2.id, self.img1.id]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.product.refresh_from_db()
        self.assertTrue(self.product.needs_platform_sync)
        primary = self.product.primary_image
        self.assertEqual(primary.id, self.img2.id)

    def test_reordering_without_changing_cover_does_not_trigger_sync(self):
        # Add third image
        img3 = ProductImage.objects.create(
            product=self.product,
            image=create_test_image("img3.png", "orange"),
            order=2,
        )
        url = reverse("inventory:product_reorder_images", kwargs={"pk": self.product.pk})
        # Swap img2 and img3 (img1 remains #0 cover)
        response = self.client_mgr.post(
            url,
            data={"image_ids": [self.img1.id, img3.id, self.img2.id]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.product.refresh_from_db()
        self.assertFalse(self.product.needs_platform_sync)

    def test_assistant_cannot_upload_or_delete_photos(self):
        upload_url = reverse("inventory:product_upload_images", kwargs={"pk": self.product.pk})
        res1 = self.client_asst.post(upload_url, {"images": [create_test_image("asst.png")]})
        self.assertIn(res1.status_code, (302, 403))

        del_url = reverse("inventory:product_delete_image", kwargs={"pk": self.product.pk, "image_id": self.img2.id})
        res2 = self.client_asst.post(del_url)
        self.assertIn(res2.status_code, (302, 403))

    def test_mark_platform_synced_view_clears_flag(self):
        self.product.needs_platform_sync = True
        self.product.save(update_fields=["needs_platform_sync"])

        url = reverse("inventory:product_mark_platform_synced", kwargs={"pk": self.product.pk})
        response = self.client_mgr.post(url, follow=True)
        self.assertEqual(response.status_code, 200)

        self.product.refresh_from_db()
        self.assertFalse(self.product.needs_platform_sync)
        self.assertIsNotNone(self.product.last_platform_synced_at)
        self.assertContains(response, "Platforms marked as updated successfully")

    def test_assistant_cannot_mark_platform_synced(self):
        url = reverse("inventory:product_mark_platform_synced", kwargs={"pk": self.product.pk})
        response = self.client_asst.post(url)
        self.assertIn(response.status_code, (302, 403))

    def test_dashboard_sub_filtering_out_of_sync(self):
        # Product 1 is out of sync
        self.product.needs_platform_sync = True
        self.product.save(update_fields=["needs_platform_sync"])

        # Product 2 is published and in sync
        p2 = Product.objects.create(
            raw_note="Product 2",
            ai_title="Levis Vintage 501",
            ai_description="Original 90s vintage denim",
            sale_price=Decimal("80.00"),
            created_by=self.manager,
        )
        ProductListingLink.objects.create(
            product=p2,
            site=self.site,
            url="https://es.wallapop.com/item/levis-2",
            is_active=True,
        )
        p2.refresh_from_db()
        self.assertFalse(p2.needs_platform_sync)

        # 1. Check all published filter
        res_all = self.client_mgr.get(reverse("inventory:dashboard") + "?status=published")
        self.assertEqual(res_all.status_code, 200)
        self.assertContains(res_all, self.product.ai_title)
        self.assertContains(res_all, p2.ai_title)
        self.assertEqual(res_all.context["published_count"], 2)
        self.assertEqual(res_all.context["out_of_sync_count"], 1)

        # 2. Check out_of_sync subfilter
        res_sync = self.client_mgr.get(reverse("inventory:dashboard") + "?status=published&sync=out_of_sync")
        self.assertEqual(res_sync.status_code, 200)
        self.assertContains(res_sync, self.product.ai_title)
        self.assertNotContains(res_sync, p2.ai_title)

    def test_product_detail_workspace_renders_banner_when_out_of_sync(self):
        self.product.needs_platform_sync = True
        self.product.save(update_fields=["needs_platform_sync"])

        url = reverse("inventory:product_detail", kwargs={"pk": self.product.pk})
        response = self.client_mgr.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "platformSyncBanner")
        self.assertContains(response, "Update Required on Marketplaces")
        self.assertContains(response, "btnMarkPlatformSynced")

    def test_spanish_localization(self):
        self.product.needs_platform_sync = True
        self.product.save(update_fields=["needs_platform_sync"])

        self.client_mgr.cookies.load({"django_language": "es"})
        url = reverse("inventory:product_detail", kwargs={"pk": self.product.pk})
        response = self.client_mgr.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Actualización requerida en plataformas")
        self.assertContains(response, "Marcar plataformas como actualizadas")
