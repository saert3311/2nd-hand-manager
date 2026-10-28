import io
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from PIL import Image

from inventory.models import (
    Category,
    MarketplaceSite,
    Product,
    ProductCondition,
    ProductImage,
    ProductListingLink,
    ProductStatus,
)

User = get_user_model()


class ProductDetailMobileUXTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.mgr_group, _ = Group.objects.get_or_create(name="managers")
        self.asst_group, _ = Group.objects.get_or_create(name="assistants")

        self.manager = User.objects.create_user(
            username="test_mgr",
            password="password123",
            is_staff=True,
        )
        self.manager.groups.add(self.mgr_group)

        self.assistant = User.objects.create_user(
            username="test_asst",
            password="password123",
        )
        self.assistant.groups.add(self.asst_group)

        self.category = Category.objects.create(name="Chaquetas", slug="chaquetas")
        self.product = Product.objects.create(
            ai_title="Chaqueta Denim Vintage Talla M",
            ai_description="Chaqueta vaquera clasica en buen estado.",
            raw_note="Notas de intake tomadas en almacen.",
            sale_price=Decimal("45.00"),
            status=ProductStatus.READY,
            category=self.category,
            condition=ProductCondition.VERY_GOOD,
            is_public=True,
            created_by=self.manager,
        )

        # Create dummy image
        buf = io.BytesIO()
        img = Image.new("RGB", (300, 300), color="blue")
        img.save(buf, format="JPEG")
        buf.seek(0)
        uploaded = SimpleUploadedFile("initial.jpg", buf.read(), content_type="image/jpeg")

        self.product_image = ProductImage.objects.create(
            product=self.product,
            image=uploaded,
            order=0,
        )

    def test_product_edit_image_requires_manager(self):
        """Assistant cannot edit existing product photos."""
        self.client.login(username="test_asst", password="password123")
        url = reverse(
            "inventory:product_edit_image",
            kwargs={"pk": self.product.pk, "image_id": self.product_image.id},
        )
        buf = io.BytesIO()
        img = Image.new("RGB", (200, 200), color="red")
        img.save(buf, format="JPEG")
        buf.seek(0)
        resp = self.client.post(
            url,
            {"image": SimpleUploadedFile("cropped.jpg", buf.read(), content_type="image/jpeg")},
        )
        self.assertEqual(resp.status_code, 403)

    def test_product_edit_image_success(self):
        """Manager can successfully crop & rotate an existing photo via AJAX POST."""
        self.client.login(username="test_mgr", password="password123")
        url = reverse(
            "inventory:product_edit_image",
            kwargs={"pk": self.product.pk, "image_id": self.product_image.id},
        )
        buf = io.BytesIO()
        img = Image.new("RGB", (400, 400), color="green")
        img.save(buf, format="JPEG")
        buf.seek(0)
        resp = self.client.post(
            url,
            {"image": SimpleUploadedFile("cropped.jpg", buf.read(), content_type="image/jpeg")},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("image_id"), self.product_image.id)
        self.assertTrue(data.get("is_primary"))
        self.assertTrue(data.get("image_url"))

        self.product_image.refresh_from_db()
        self.assertTrue(self.product_image.image.name.endswith(".webp"))

    def test_product_edit_image_missing_file_returns_400(self):
        """Sending empty payload to edit endpoint returns 400 error."""
        self.client.login(username="test_mgr", password="password123")
        url = reverse(
            "inventory:product_edit_image",
            kwargs={"pk": self.product.pk, "image_id": self.product_image.id},
        )
        resp = self.client.post(url, {})
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data.get("success"))

    def test_product_edit_image_flags_sync_if_published(self):
        """Editing an image on a published product flags needs_platform_sync = True."""
        site, _ = MarketplaceSite.objects.get_or_create(slug="wallapop", defaults={"name": "Wallapop"})
        ProductListingLink.objects.create(
            product=self.product,
            site=site,
            url="https://es.wallapop.com/item/test-123",
            is_active=True,
        )
        self.product.status = ProductStatus.PUBLISHED
        self.product.needs_platform_sync = False
        self.product.save()

        self.client.login(username="test_mgr", password="password123")
        url = reverse(
            "inventory:product_edit_image",
            kwargs={"pk": self.product.pk, "image_id": self.product_image.id},
        )
        buf = io.BytesIO()
        img = Image.new("RGB", (300, 300), color="yellow")
        img.save(buf, format="JPEG")
        buf.seek(0)
        resp = self.client.post(
            url,
            {"image": SimpleUploadedFile("cropped.jpg", buf.read(), content_type="image/jpeg")},
        )
        self.assertEqual(resp.status_code, 200)
        self.product.refresh_from_db()
        self.assertTrue(self.product.needs_platform_sync)

    def test_product_detail_template_elements_and_mobile_responsive_classes(self):
        """Validates mobile responsive classes, 2-column thumbnails, and hidden sections."""
        self.client.login(username="test_mgr", password="password123")
        url = reverse("inventory:product_detail", kwargs={"pk": self.product.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")

        # 1. Lightbox modal and cropper vendor
        self.assertIn('id="imagePreviewModal"', html)
        self.assertIn("cropper.min.css", html)
        self.assertIn("cropper.min.js", html)
        self.assertIn('id="applyCropBtn"', html)
        self.assertIn('id="rotateLeftBtn"', html)
        self.assertIn('id="rotateRightBtn"', html)

        # 2. 2-column thumbnails for existing and pending grids
        self.assertIn('id="galleryThumbnailsGrid" class="grid grid-cols-2', html)
        self.assertIn('id="detailPendingGrid" class="grid grid-cols-2', html)

        # 3. Edit button on existing photo thumbnail
        self.assertIn('class="photo-edit-btn absolute bottom-1 right-1', html)

        # 4. Hidden on mobile sections: notes, history, taxonomy
        self.assertIn('<!-- Preserved Raw Notes Card (Hidden on Mobile) -->', html)
        self.assertIn('hidden lg:block bg-amber-50/60', html)

        self.assertIn('<!-- Product State Change History / Audit Trail Card (Hidden on Mobile) -->', html)
        self.assertIn('id="status-history-section" class="hidden lg:block', html)

        self.assertIn('<!-- Public Storefront Taxonomy & Visibility Controls (Hidden on Mobile) -->', html)
        self.assertIn('hidden lg:block pt-4 border-t', html)

        # 5. Flex ordering: Gemini & listing copy on top on mobile
        self.assertIn('flex flex-col lg:grid lg:grid-cols-12 gap-6', html)
        self.assertIn('order-1 lg:order-2 lg:col-span-7', html)
        self.assertIn('order-2 lg:order-1 lg:col-span-5', html)

        # 6. Responsive top action button bar
        self.assertIn('flex items-center gap-1.5 w-full sm:w-auto', html)
        self.assertIn('class="sm:hidden"', html)
        self.assertIn('class="hidden sm:inline"', html)
