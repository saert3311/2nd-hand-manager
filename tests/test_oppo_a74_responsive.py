import os
import shutil
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from playwright.sync_api import sync_playwright

from inventory.models import (
    Category,
    MarketplaceSite,
    Product,
    ProductCondition,
    ProductImage,
    ProductListingLink,
    ProductStatus,
    StorefrontConfiguration,
)

User = get_user_model()


@override_settings(TURNSTILE_ENABLED=False)
class OppoA74ResponsiveUITests(StaticLiveServerTestCase):
    """
    Validates responsive behavior, absence of horizontal overflow, and layout integrity
    on narrow Android mobile viewports, specifically:
    1. OPPO A74 Standard: 360x800, DPR 2.0/3.0
    2. OPPO A74 Display Zoom / Low Effective DPI: 320x711, DPR 1.5/2.0
    """

    @classmethod
    def setUpClass(cls):
        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
        super().setUpClass()
        os.makedirs("browser_verification_screenshots/oppo_a74", exist_ok=True)
        os.makedirs("tmp_test_images", exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        if os.path.exists("tmp_test_images"):
            shutil.rmtree("tmp_test_images", ignore_errors=True)

    def setUp(self):
        self.manager = User.objects.create_user(
            username="manager_oppo",
            password="password123",
            is_staff=True,
        )
        self.assistant = User.objects.create_user(
            username="asst_oppo",
            password="password123",
        )
        # Groups
        from django.contrib.auth.models import Group

        mgr_group, _ = Group.objects.get_or_create(name="managers")
        asst_group, _ = Group.objects.get_or_create(name="assistants")
        self.manager.groups.add(mgr_group)
        self.assistant.groups.add(asst_group)

        # Storefront config
        StorefrontConfiguration.objects.get_or_create(
            pk=1,
            defaults={
                "store_name": "Moda Vintage Madrid",
                "tagline_es": "Ropa de segunda mano y vintage seleccionada",
                "whatsapp_number": "34600000000",
            },
        )

        # Category
        self.category, _ = Category.objects.get_or_create(
            slug="chaquetas-y-abrigos",
            defaults={
                "name": "Chaquetas y Abrigos",
                "name_en": "Jackets & Coats",
                "order": 1,
                "is_active": True,
            },
        )

        # Marketplace site
        self.site_wallapop, _ = MarketplaceSite.objects.get_or_create(
            slug="wallapop",
            defaults={"name": "Wallapop", "order": 2, "is_active": True},
        )
        self.site_vinted, _ = MarketplaceSite.objects.get_or_create(
            slug="vinted",
            defaults={"name": "Vinted", "order": 1, "is_active": True},
        )

        # Create dummy image
        img_path = os.path.join("tmp_test_images", "sample_jacket.jpg")
        img = Image.new("RGB", (400, 400), color="darkgreen")
        img.save(img_path, format="JPEG")

        # Active Product
        self.p_active = Product.objects.create(
            ai_title="Chaqueta Vintage Cazadora Cuero Nobuk Marrón Talla L",
            ai_description="Chaqueta en excelente estado de conservación, cuero genuino nobuk con cremalleras funcionales.",
            sale_price=Decimal("85.50"),
            estimated_retail_price=Decimal("199.00"),
            estimated_resale_price=Decimal("89.00"),
            status=ProductStatus.READY,
            category=self.category,
            condition=ProductCondition.VERY_GOOD,
            is_public=True,
            is_featured=True,
            is_sold=False,
            created_by=self.manager,
        )
        with open(img_path, "rb") as f:
            from django.core.files.base import ContentFile

            ProductImage.objects.create(
                product=self.p_active,
                image=ContentFile(f.read(), name="sample_jacket.webp"),
                order=1,
            )

        ProductListingLink.objects.create(
            product=self.p_active,
            site=self.site_vinted,
            url="https://www.vinted.es/items/123-vintage-jacket",
            clicks_count=5,
            is_active=True,
        )

        # Price Pending Product
        self.p_price_pending = Product.objects.create(
            ai_title="Camisa Franela Cuadros Grunge 90s Oversized",
            ai_description="Camisa clásica a cuadros estilo grunge años 90.",
            sale_price=None,
            status=ProductStatus.PRICE_PENDING,
            category=self.category,
            is_public=False,
            is_sold=False,
            created_by=self.assistant,
        )

        # Erased Product
        self.p_erased = Product.objects.create(
            ai_title="Pantalón Descatalogado Erróneo",
            ai_description="Producto con taras no apto.",
            sale_price=Decimal("20.00"),
            status=ProductStatus.DRAFT,
            is_deleted=True,
            created_by=self.manager,
        )

    def _assert_no_horizontal_overflow(self, page, page_label, width, height):
        """
        Asserts that document.documentElement does not exceed the viewport clientWidth.
        Collects offending elements if overflow is detected.
        """
        metrics = page.evaluate("""() => {
            const doc = document.documentElement;
            const body = document.body;
            const clientWidth = doc.clientWidth;
            const scrollWidth = Math.max(doc.scrollWidth, body.scrollWidth);
            const overflow = scrollWidth > clientWidth + 0.5;
            let offenders = [];
            if (overflow) {
                document.querySelectorAll('*').forEach(el => {
                    if (el.closest('.overflow-x-auto, [style*="overflow-x: auto"], [style*="overflow-x:auto"], nav[role="tablist"], #categoryRail')) {
                        return;
                    }
                    const rect = el.getBoundingClientRect();
                    if (rect.right > clientWidth + 1.5) {
                        offenders.push({
                            tag: el.tagName,
                            id: el.id,
                            className: (el.className || '').toString().slice(0, 100),
                            rectRight: Math.round(rect.right),
                            rectWidth: Math.round(rect.width),
                            text: (el.innerText || '').slice(0, 50).trim()
                        });
                    }
                });
            }
            return {
                clientWidth,
                scrollWidth,
                overflow,
                offenders: offenders.slice(0, 10)
            };
        }""")

        screenshot_path = f"browser_verification_screenshots/oppo_a74/{page_label}_{width}x{height}.png"
        page.screenshot(path=screenshot_path, full_page=True)

        self.assertFalse(
            metrics["overflow"],
            f"Horizontal overflow detected on {page_label} at {width}x{height}! "
            f"scrollWidth={metrics['scrollWidth']} > clientWidth={metrics['clientWidth']}. "
            f"Offenders: {metrics['offenders']}",
        )

    def test_oppo_a74_public_storefront_viewports(self):
        """
        Tests public storefront routes on both 360x800 and 320x711 viewports.
        """
        viewports = [
            ("oppo_a74_standard", 360, 800, 2.0),
            ("oppo_a74_zoomed_low_dpi", 320, 711, 1.5),
        ]

        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)

            for label, width, height, dsf in viewports:
                context = browser.new_context(
                    viewport={"width": width, "height": height},
                    device_scale_factor=dsf,
                    is_mobile=True,
                    has_touch=True,
                    locale="es-ES",
                )
                page = context.new_page()

                # 1. Home
                page.goto(f"{self.live_server_url}{reverse('storefront:home')}")
                page.wait_for_load_state("networkidle")
                self._assert_no_horizontal_overflow(page, f"home_{label}", width, height)

                # 2. Catalog
                page.goto(f"{self.live_server_url}{reverse('storefront:catalog')}")
                page.wait_for_load_state("networkidle")
                self._assert_no_horizontal_overflow(page, f"catalog_{label}", width, height)

                # 3. Category Catalog
                page.goto(
                    f"{self.live_server_url}{reverse('storefront:category', kwargs={'category_slug': self.category.slug})}"
                )
                page.wait_for_load_state("networkidle")
                self._assert_no_horizontal_overflow(page, f"category_{label}", width, height)

                # 4. Public Product Detail
                page.goto(
                    f"{self.live_server_url}{reverse('storefront:product_detail', kwargs={'slug': self.p_active.slug, 'pk': self.p_active.pk})}"
                )
                page.wait_for_load_state("networkidle")
                self._assert_no_horizontal_overflow(page, f"public_detail_{label}", width, height)

                # 5. How to buy
                page.goto(f"{self.live_server_url}{reverse('storefront:how_to_buy')}")
                page.wait_for_load_state("networkidle")
                self._assert_no_horizontal_overflow(page, f"how_to_buy_{label}", width, height)

                # 6. Legal notice
                page.goto(f"{self.live_server_url}{reverse('storefront:legal_notice')}")
                page.wait_for_load_state("networkidle")
                self._assert_no_horizontal_overflow(page, f"legal_notice_{label}", width, height)

                context.close()

            browser.close()

    def test_oppo_a74_staging_panel_viewports(self):
        """
        Tests internal management & intake routes on both 360x800 and 320x711 viewports.
        """
        viewports = [
            ("oppo_a74_standard", 360, 800, 2.0),
            ("oppo_a74_zoomed_low_dpi", 320, 711, 1.5),
        ]

        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)

            for label, width, height, dsf in viewports:
                context = browser.new_context(
                    viewport={"width": width, "height": height},
                    device_scale_factor=dsf,
                    is_mobile=True,
                    has_touch=True,
                    locale="es-ES",
                )
                page = context.new_page()

                # 1. Login page
                page.goto(f"{self.live_server_url}{reverse('inventory:login')}")
                page.wait_for_load_state("networkidle")
                self._assert_no_horizontal_overflow(page, f"login_{label}", width, height)

                # Login as manager
                page.fill("#id_username", "manager_oppo")
                page.fill("#id_password", "password123")
                with page.expect_navigation():
                    page.click("#loginSubmitBtn")
                page.wait_for_load_state("networkidle")

                # 2. Staging Dashboard (All active tab)
                page.goto(f"{self.live_server_url}{reverse('inventory:dashboard')}")
                page.wait_for_load_state("networkidle")
                self._assert_no_horizontal_overflow(page, f"dashboard_{label}", width, height)

                # 3. Staging Dashboard (Erased / Trash tab)
                page.goto(f"{self.live_server_url}{reverse('inventory:dashboard')}?status=erased")
                page.wait_for_load_state("networkidle")
                self._assert_no_horizontal_overflow(page, f"dashboard_erased_{label}", width, height)

                # 4. Staging Intake page + Photo Crop & Rotate Modal on mobile
                page.goto(f"{self.live_server_url}{reverse('inventory:intake')}")
                page.wait_for_load_state("networkidle")
                self._assert_no_horizontal_overflow(page, f"intake_{label}", width, height)

                # Attach photo, open Cropper.js modal via .photo-edit-btn, rotate 90 deg, and apply
                page.set_input_files("#imageInput", os.path.join("tmp_test_images", "sample_jacket.jpg"))
                page.wait_for_selector(".photo-edit-btn", timeout=5000)
                page.click(".photo-edit-btn")
                page.wait_for_selector("#imagePreviewModal:not(.hidden) .cropper-container", timeout=5000)
                self._assert_no_horizontal_overflow(page, f"intake_crop_modal_{label}", width, height)
                page.click("#rotateRightBtn")
                page.click("#applyCropBtn")
                page.wait_for_selector("#imagePreviewModal.hidden", state="attached", timeout=5000)

                # 5. Staging Product Detail view
                page.goto(f"{self.live_server_url}{reverse('inventory:product_detail', kwargs={'pk': self.p_active.pk})}")
                page.wait_for_load_state("networkidle")
                self._assert_no_horizontal_overflow(page, f"staging_detail_{label}", width, height)

                # Verify hidden sections on narrow mobile viewports (notes, history)
                self.assertFalse(page.locator("#status-history-section").is_visible())

                # Verify mobile order: Gemini AI banner appears before photo gallery on mobile
                ai_box = page.locator("#aiForm").bounding_box()
                gallery_box = page.locator("#galleryThumbnailsGrid").bounding_box()
                marketplace_box = page.locator("#marketplaceLinksCard").bounding_box()
                if ai_box and gallery_box:
                    self.assertLess(ai_box["y"], gallery_box["y"])
                if gallery_box and marketplace_box:
                    self.assertLess(gallery_box["y"], marketplace_box["y"])

                # Test Detail View Add More Photos & Lightbox Cropper on Mobile
                # 6. Test Marketplace Links Mobile Redesign: Active Tiles & Modals
                self.assertTrue(page.locator('[data-site-slug="vinted"]').is_visible())
                page.click("#openAddListingBtn")
                page.wait_for_selector("#addListingModal:not(.hidden)", timeout=5000)
                self._assert_no_horizontal_overflow(page, f"add_listing_modal_{label}", width, height)
                page.keyboard.press("Escape")
                page.wait_for_selector("#addListingModal.hidden", state="attached", timeout=5000)

                page.click('[data-site-slug="vinted"] button[title*="Edit"]')
                page.wait_for_selector("#editListingModal:not(.hidden)", timeout=5000)
                self._assert_no_horizontal_overflow(page, f"edit_listing_modal_{label}", width, height)
                page.keyboard.press("Escape")
                page.wait_for_selector("#editListingModal.hidden", state="attached", timeout=5000)

                page.set_input_files("#detailImageInput", os.path.join("tmp_test_images", "sample_jacket.jpg"))
                page.wait_for_selector("#detailPendingGrid .photo-edit-btn", timeout=5000)
                page.click("#detailPendingGrid .photo-edit-btn")
                page.wait_for_selector("#imagePreviewModal:not(.hidden) .cropper-container", timeout=5000)
                self._assert_no_horizontal_overflow(page, f"detail_crop_modal_{label}", width, height)
                page.click("#rotateRightBtn")
                page.click("#applyCropBtn")
                page.wait_for_selector("#imagePreviewModal.hidden", state="attached", timeout=5000)

                # 7. Pallets Management view
                page.goto(f"{self.live_server_url}{reverse('inventory:pallets')}")
                page.wait_for_load_state("networkidle")
                self._assert_no_horizontal_overflow(page, f"pallets_{label}", width, height)

                context.close()

            browser.close()
