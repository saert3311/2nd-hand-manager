from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import translation

from inventory.forms import ProductUpdateForm
from inventory.models import (
    MarketplaceSite,
    Product,
    ProductListingLink,
    ProductStatus,
    ProductStatusLog,
    SaleChannelType,
)
from inventory.permissions import ROLE_ASSISTANT, ROLE_MANAGER

User = get_user_model()


class SaleChannelTestCase(TestCase):
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

        self.wallapop, _ = MarketplaceSite.objects.get_or_create(
            slug="wallapop",
            defaults={
                "name": "Wallapop",
                "base_url": "https://es.wallapop.com",
                "is_active": True,
                "order": 1,
            },
        )
        self.vinted, _ = MarketplaceSite.objects.get_or_create(
            slug="vinted",
            defaults={
                "name": "Vinted",
                "base_url": "https://www.vinted.es",
                "is_active": True,
                "order": 2,
            },
        )

        self.client = Client()

    # 1. Model Domain Tests
    def test_sale_channel_defaults(self):
        product = Product.objects.create(
            raw_note="Vintage jacket",
            ai_title="Vintage Denim Jacket",
            ai_description="Classic blue jacket",
            sale_price=Decimal("45.00"),
            created_by=self.assistant,
        )
        self.assertEqual(product.sold_channel_type, "")
        self.assertIsNone(product.sold_marketplace)
        self.assertEqual(product.sold_channel_notes, "")
        self.assertEqual(product.sale_channel_display, "")

    def test_mark_as_sold_in_store(self):
        product = Product.objects.create(
            raw_note="Vintage jacket",
            ai_title="Vintage Denim Jacket",
            ai_description="Classic blue jacket",
            sale_price=Decimal("45.00"),
            created_by=self.assistant,
        )
        product.mark_as_sold(
            price=Decimal("40.00"),
            user=self.manager,
            channel_type=SaleChannelType.IN_STORE,
            notes="Cash register #2",
        )
        product.refresh_from_db()

        self.assertTrue(product.is_sold)
        self.assertEqual(product.status, ProductStatus.SOLD)
        self.assertIsNotNone(product.sold_at)
        self.assertEqual(product.sale_price, Decimal("40.00"))
        self.assertEqual(product.sold_channel_type, SaleChannelType.IN_STORE)
        self.assertIsNone(product.sold_marketplace)
        self.assertEqual(product.sold_channel_notes, "Cash register #2")
        self.assertEqual(product.sale_channel_display, "In-Store")

        log = ProductStatusLog.objects.filter(product=product).order_by("-created_at").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.to_status, ProductStatus.SOLD)
        self.assertEqual(log.changed_by, self.manager)
        self.assertIn("In-Store", log.notes)
        self.assertIn("€40.00", log.notes)
        self.assertIn("Cash register #2", log.notes)

    def test_mark_as_sold_marketplace(self):
        product = Product.objects.create(
            raw_note="Rare sneakers",
            ai_title="Nike Air Max 90",
            ai_description="Mint condition shoes",
            sale_price=Decimal("95.00"),
            created_by=self.assistant,
        )
        product.mark_as_sold(
            price=Decimal("90.00"),
            user=self.manager,
            channel_type=SaleChannelType.MARKETPLACE,
            marketplace=self.wallapop,
            notes="Order #W-98765",
        )
        product.refresh_from_db()

        self.assertTrue(product.is_sold)
        self.assertEqual(product.status, ProductStatus.SOLD)
        self.assertEqual(product.sold_channel_type, SaleChannelType.MARKETPLACE)
        self.assertEqual(product.sold_marketplace, self.wallapop)
        self.assertEqual(product.sold_channel_notes, "Order #W-98765")
        self.assertEqual(product.sale_channel_display, "Wallapop")

        log = ProductStatusLog.objects.filter(product=product).order_by("-created_at").first()
        self.assertIn("Wallapop", log.notes)
        self.assertIn("Order #W-98765", log.notes)

    def test_mark_as_sold_other(self):
        product = Product.objects.create(
            raw_note="Ceramic vase",
            ai_title="Vintage Ceramic Vase",
            ai_description="Mid-century modern decor",
            sale_price=Decimal("30.00"),
        )
        product.mark_as_sold(
            channel_type=SaleChannelType.OTHER,
            notes="Sold to neighbor",
        )
        product.refresh_from_db()

        self.assertEqual(product.sold_channel_type, SaleChannelType.OTHER)
        self.assertEqual(product.sale_channel_display, "Other")
        self.assertEqual(product.sold_channel_notes, "Sold to neighbor")

    def test_mark_as_unsold_resets_channels(self):
        product = Product.objects.create(
            raw_note="Retro radio",
            ai_title="Retro AM/FM Radio",
            ai_description="Working condition radio",
            sale_price=Decimal("50.00"),
        )
        product.mark_as_sold(
            channel_type=SaleChannelType.MARKETPLACE,
            marketplace=self.vinted,
            notes="Buyer canceled",
        )
        self.assertTrue(product.is_sold)

        product.mark_as_unsold(user=self.manager)
        product.refresh_from_db()

        self.assertFalse(product.is_sold)
        self.assertNotEqual(product.status, ProductStatus.SOLD)
        self.assertIsNone(product.sold_at)
        self.assertEqual(product.sold_channel_type, "")
        self.assertIsNone(product.sold_marketplace)
        self.assertEqual(product.sold_channel_notes, "")
        self.assertEqual(product.sale_channel_display, "")

    def test_marketplace_deletion_set_null_cascade_safety(self):
        product = Product.objects.create(
            raw_note="Antique lamp",
            ai_title="Brass Desk Lamp",
            ai_description="Vintage brass lamp",
            sale_price=Decimal("60.00"),
        )
        product.mark_as_sold(
            channel_type=SaleChannelType.MARKETPLACE,
            marketplace=self.wallapop,
        )
        self.assertEqual(product.sold_marketplace, self.wallapop)

        # Deleting the MarketplaceSite must NOT delete the product (SET_NULL safety)
        self.wallapop.delete()
        product.refresh_from_db()

        self.assertTrue(Product.objects.filter(pk=product.pk).exists())
        self.assertIsNone(product.sold_marketplace)
        self.assertEqual(product.sold_channel_type, SaleChannelType.MARKETPLACE)
        self.assertEqual(product.sale_channel_display, "Marketplace")

    # 2. Form Validation Tests
    def test_form_marking_sold_without_channel_fails(self):
        product = Product.objects.create(
            raw_note="Leather boots",
            ai_title="Leather Chelsea Boots",
            ai_description="Size 42 boots",
            sale_price=Decimal("70.00"),
        )
        form_data = {
            "ai_title": product.ai_title,
            "ai_description": product.ai_description,
            "sale_price": "70.00",
            "status": "ready",
            "is_sold": True,
            "sold_channel_type": "",
            "sold_marketplace": "",
            "sold_channel_notes": "",
        }
        form = ProductUpdateForm(data=form_data, instance=product)
        self.assertFalse(form.is_valid())
        self.assertIn("sold_channel_type", form.errors)

    def test_form_marking_sold_marketplace_without_site_fails(self):
        product = Product.objects.create(
            raw_note="Silk scarf",
            ai_title="Vintage Silk Scarf",
            ai_description="Floral print",
            sale_price=Decimal("25.00"),
        )
        form_data = {
            "ai_title": product.ai_title,
            "ai_description": product.ai_description,
            "sale_price": "25.00",
            "status": "ready",
            "is_sold": True,
            "sold_channel_type": "marketplace",
            "sold_marketplace": "",
            "sold_channel_notes": "",
        }
        form = ProductUpdateForm(data=form_data, instance=product)
        self.assertFalse(form.is_valid())
        self.assertIn("sold_marketplace", form.errors)

    def test_form_marking_sold_in_store_valid(self):
        product = Product.objects.create(
            raw_note="Wool sweater",
            ai_title="Chunky Wool Sweater",
            ai_description="Warm winter sweater",
            sale_price=Decimal("35.00"),
        )
        form_data = {
            "ai_title": product.ai_title,
            "ai_description": product.ai_description,
            "sale_price": "35.00",
            "status": "ready",
            "is_sold": True,
            "sold_channel_type": "in_store",
            "sold_marketplace": "",
            "sold_channel_notes": "Ticket #54321",
        }
        form = ProductUpdateForm(data=form_data, instance=product)
        self.assertTrue(form.is_valid(), form.errors)
        saved_product = form.save()
        self.assertTrue(saved_product.is_sold)
        self.assertEqual(saved_product.sold_channel_type, "in_store")
        self.assertEqual(saved_product.sold_channel_notes, "Ticket #54321")

    def test_form_marking_sold_marketplace_valid(self):
        product = Product.objects.create(
            raw_note="Watch",
            ai_title="Seiko Automatic Watch",
            ai_description="Stainless steel",
            sale_price=Decimal("120.00"),
        )
        form_data = {
            "ai_title": product.ai_title,
            "ai_description": product.ai_description,
            "sale_price": "120.00",
            "status": "ready",
            "is_sold": True,
            "sold_channel_type": "marketplace",
            "sold_marketplace": str(self.vinted.id),
            "sold_channel_notes": "Buyer: @marialopez",
        }
        form = ProductUpdateForm(data=form_data, instance=product)
        self.assertTrue(form.is_valid(), form.errors)
        saved_product = form.save()
        self.assertTrue(saved_product.is_sold)
        self.assertEqual(saved_product.sold_channel_type, "marketplace")
        self.assertEqual(saved_product.sold_marketplace, self.vinted)

    def test_form_unmarking_sold_clears_channel(self):
        product = Product.objects.create(
            raw_note="Old camera",
            ai_title="Olympus 35mm Camera",
            ai_description="Vintage film camera",
            sale_price=Decimal("80.00"),
            is_sold=True,
            status=ProductStatus.SOLD,
            sold_channel_type=SaleChannelType.IN_STORE,
            sold_channel_notes="Returned item",
        )
        form_data = {
            "ai_title": product.ai_title,
            "ai_description": product.ai_description,
            "sale_price": "80.00",
            "status": "ready",
            "is_sold": False,
            "sold_channel_type": "in_store",
            "sold_marketplace": "",
            "sold_channel_notes": "Returned item",
        }
        form = ProductUpdateForm(data=form_data, instance=product)
        self.assertTrue(form.is_valid(), form.errors)
        saved_product = form.save()
        self.assertFalse(saved_product.is_sold)
        self.assertEqual(saved_product.sold_channel_type, "")
        self.assertIsNone(saved_product.sold_marketplace)
        self.assertEqual(saved_product.sold_channel_notes, "")

    # 3. View & Integration Tests
    def test_product_detail_post_mark_as_sold_in_store(self):
        self.client.force_login(self.manager)
        product = Product.objects.create(
            raw_note="Vintage chair",
            ai_title="Mid-Century Wooden Chair",
            ai_description="Restored chair",
            sale_price=Decimal("65.00"),
        )
        url = reverse("inventory:product_detail", kwargs={"pk": product.pk})
        response = self.client.post(
            url,
            {
                "ai_title": product.ai_title,
                "ai_description": product.ai_description,
                "sale_price": "65.00",
                "status": "ready",
                "is_sold": "on",
                "sold_channel_type": "in_store",
                "sold_marketplace": "",
                "sold_channel_notes": "Store counter #1",
            },
        )
        self.assertRedirects(response, url)
        product.refresh_from_db()
        self.assertTrue(product.is_sold)
        self.assertEqual(product.sold_channel_type, "in_store")
        self.assertEqual(product.sold_channel_notes, "Store counter #1")

    def test_product_detail_page_renders_sold_channel_badges_and_quick_picks(self):
        self.client.force_login(self.manager)
        product = Product.objects.create(
            raw_note="Leather wallet",
            ai_title="Handcrafted Leather Wallet",
            ai_description="Genuine brown leather",
            sale_price=Decimal("20.00"),
        )
        ProductListingLink.objects.create(
            product=product,
            site=self.wallapop,
            url="https://es.wallapop.com/item/wallet-123",
            is_active=True,
        )

        url = reverse("inventory:product_detail", kwargs={"pk": product.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Check quick-pick chip for published Wallapop link
        self.assertContains(response, "Wallapop")
        self.assertContains(response, "id_sold_channel_type")
        self.assertContains(response, "id_sold_marketplace")
        self.assertContains(response, "id_sold_channel_notes")

    def test_dashboard_sold_subfiltering_by_channel(self):
        self.client.force_login(self.manager)

        # 1 in-store sold
        p_store = Product.objects.create(
            raw_note="P1",
            ai_title="Item In-Store",
            ai_description="Desc",
            sale_price=Decimal("15.00"),
        )
        p_store.mark_as_sold(channel_type=SaleChannelType.IN_STORE)

        # 1 marketplace sold (Wallapop)
        p_walla = Product.objects.create(
            raw_note="P2",
            ai_title="Item Wallapop",
            ai_description="Desc",
            sale_price=Decimal("25.00"),
        )
        p_walla.mark_as_sold(channel_type=SaleChannelType.MARKETPLACE, marketplace=self.wallapop)

        # 1 active unsold item
        Product.objects.create(
            raw_note="P3",
            ai_title="Item Active",
            ai_description="Desc",
            sale_price=Decimal("30.00"),
        )

        dashboard_url = reverse("inventory:dashboard")

        # All Sold
        resp_all = self.client.get(dashboard_url, {"status": "sold"})
        self.assertEqual(resp_all.status_code, 200)
        self.assertEqual(resp_all.context["sold_count"], 2)
        self.assertEqual(resp_all.context["sold_in_store_count"], 1)
        self.assertEqual(resp_all.context["sold_marketplace_count"], 1)
        self.assertEqual(len(resp_all.context["products"]), 2)

        # Filter by In-Store
        resp_store = self.client.get(dashboard_url, {"status": "sold", "channel": "in_store"})
        self.assertEqual(resp_store.status_code, 200)
        self.assertEqual(len(resp_store.context["products"]), 1)
        self.assertEqual(resp_store.context["products"][0].pk, p_store.pk)

        # Filter by Marketplace
        resp_market = self.client.get(dashboard_url, {"status": "sold", "channel": "marketplace"})
        self.assertEqual(resp_market.status_code, 200)
        self.assertEqual(len(resp_market.context["products"]), 1)
        self.assertEqual(resp_market.context["products"][0].pk, p_walla.pk)

    # 4. Admin Integration Tests
    def test_product_admin_displays_sale_channel_col(self):
        self.client.force_login(self.manager)
        product = Product.objects.create(
            raw_note="Admin test",
            ai_title="Admin Product Test",
            ai_description="Desc",
            sale_price=Decimal("50.00"),
        )
        product.mark_as_sold(channel_type=SaleChannelType.IN_STORE)

        admin_url = reverse("admin:inventory_product_changelist")
        response = self.client.get(admin_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "In-Store")
        self.assertContains(response, "🏪")

    # 5. Bilingual Localization Tests
    def test_spanish_translations_for_sale_channels(self):
        with translation.override("es"):
            product = Product.objects.create(
                raw_note="Spanish test",
                ai_title="Prueba Espanol",
                ai_description="Desc",
                sale_price=Decimal("20.00"),
            )
            product.mark_as_sold(channel_type=SaleChannelType.IN_STORE)
            self.assertEqual(product.sale_channel_display, "Tienda física")

            product.mark_as_sold(channel_type=SaleChannelType.OTHER)
            self.assertEqual(product.sale_channel_display, "Otro")
