from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from inventory.models import (
    Category,
    MarketplaceSite,
    Product,
    ProductCondition,
    ProductListingLink,
    ProductStatus,
)

User = get_user_model()


class MarketplaceLinksMobileTests(TestCase):
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

        self.category = Category.objects.create(name="Ropa Vintage", slug="ropa-vintage")
        self.product = Product.objects.create(
            ai_title="Camisa Retro 90s",
            ai_description="Camisa vintage en algodon 100%.",
            raw_note="Nota de prueba.",
            sale_price=Decimal("28.00"),
            status=ProductStatus.READY,
            category=self.category,
            condition=ProductCondition.GOOD,
            created_by=self.manager,
        )

        # Ensure Marketplace sites exist
        self.site_wallapop, _ = MarketplaceSite.objects.get_or_create(
            slug="wallapop",
            defaults={"name": "Wallapop", "is_active": True, "order": 1},
        )
        self.site_vinted, _ = MarketplaceSite.objects.get_or_create(
            slug="vinted",
            defaults={"name": "Vinted", "is_active": True, "order": 2},
        )
        self.site_milanuncios, _ = MarketplaceSite.objects.get_or_create(
            slug="milanuncios",
            defaults={"name": "Milanuncios", "is_active": True, "order": 3},
        )

    def test_context_partitions_active_links_and_unlinked_sites(self):
        """Verify view context cleanly splits active listing links from unlinked sites."""
        # Create an active link for Wallapop
        ProductListingLink.objects.create(
            product=self.product,
            site=self.site_wallapop,
            url="https://es.wallapop.com/item/camisa-retro-90s-12345",
            is_active=True,
        )

        self.client.login(username="test_mgr", password="password123")
        url = reverse("inventory:product_detail", kwargs={"pk": self.product.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("active_listing_links", response.context)
        self.assertIn("unlinked_sites", response.context)

        active_links = response.context["active_listing_links"]
        unlinked = response.context["unlinked_sites"]

        self.assertEqual(len(active_links), 1)
        self.assertEqual(active_links[0].site.slug, "wallapop")

        unlinked_slugs = {s.slug for s in unlinked}
        self.assertNotIn("wallapop", unlinked_slugs)
        self.assertIn("vinted", unlinked_slugs)
        self.assertIn("milanuncios", unlinked_slugs)

    def test_active_listing_tiles_rendered_without_duplicate_inputs(self):
        """Active links render compact tiles with 1-tap copy & open buttons, but NO permanent input boxes."""
        ProductListingLink.objects.create(
            product=self.product,
            site=self.site_wallapop,
            url="https://es.wallapop.com/item/camisa-retro-90s-12345",
            clicks_count=7,
            is_active=True,
        )

        self.client.login(username="test_mgr", password="password123")
        url = reverse("inventory:product_detail", kwargs={"pk": self.product.pk})
        response = self.client.get(url)

        html = response.content.decode("utf-8")
        # Assert tile elements
        self.assertIn('data-site-slug="wallapop"', html)
        self.assertIn("Wallapop", html)
        self.assertIn("7 clicks", html)
        self.assertIn("Copy Link", html)
        self.assertIn("copyLinkUrl(", html)
        self.assertIn("https://es.wallapop.com/item/camisa-retro-90s-12345", html)

        # Assert modals exist
        self.assertIn('id="addListingModal"', html)
        self.assertIn('id="editListingModal"', html)
        self.assertIn('openEditListingModal(', html)

        # Assert no permanent form input exists inside the active tile (only in modals)
        self.assertNotIn('<input type="url" name="url" value="https://es.wallapop.com', html)

    def test_empty_state_rendered_when_no_active_links(self):
        """When product has no active listings, a clean empty state and add button render."""
        self.client.login(username="test_mgr", password="password123")
        url = reverse("inventory:product_detail", kwargs={"pk": self.product.pk})
        response = self.client.get(url)

        html = response.content.decode("utf-8")
        self.assertIn('id="noActiveLinksState"', html)
        self.assertIn("No marketplace links active yet", html)
        self.assertIn('id="openAddListingBtn"', html)

    def test_manage_link_add_and_update(self):
        """Managers can save and update links via POST to inventory:manage_link."""
        self.client.login(username="test_mgr", password="password123")
        manage_url = reverse("inventory:manage_link", kwargs={"pk": self.product.pk})

        # Add link
        post_data = {
            "action": "save",
            "site_id": self.site_vinted.id,
            "url": "https://www.vinted.es/items/99887766-camisa-retro",
        }
        res = self.client.post(manage_url, post_data)
        self.assertRedirects(res, reverse("inventory:product_detail", kwargs={"pk": self.product.pk}))

        link = ProductListingLink.objects.get(product=self.product, site=self.site_vinted)
        self.assertEqual(link.url, "https://www.vinted.es/items/99887766-camisa-retro")
        self.assertTrue(link.is_active)

        # Update link
        update_data = {
            "action": "save",
            "site_id": self.site_vinted.id,
            "url": "https://www.vinted.es/items/99887766-camisa-retro-v2",
        }
        res = self.client.post(manage_url, update_data)
        link.refresh_from_db()
        self.assertEqual(link.url, "https://www.vinted.es/items/99887766-camisa-retro-v2")

        # Delete link
        delete_data = {
            "action": "delete",
            "link_id": link.id,
        }
        res = self.client.post(manage_url, delete_data)
        self.assertFalse(ProductListingLink.objects.filter(product=self.product, site=self.site_vinted).exists())

    def test_assistant_cannot_manage_links(self):
        """Assistants are blocked from adding or removing marketplace links."""
        self.client.login(username="test_asst", password="password123")
        manage_url = reverse("inventory:manage_link", kwargs={"pk": self.product.pk})

        post_data = {
            "action": "save",
            "site_id": self.site_vinted.id,
            "url": "https://www.vinted.es/items/111",
        }
        res = self.client.post(manage_url, post_data)
        # Should redirect back with error message, no link created
        self.assertRedirects(res, reverse("inventory:product_detail", kwargs={"pk": self.product.pk}))
        self.assertFalse(ProductListingLink.objects.filter(product=self.product, site=self.site_vinted).exists())

        # Assistant detail view should not show add/edit modal triggers
        detail_url = reverse("inventory:product_detail", kwargs={"pk": self.product.pk})
        detail_res = self.client.get(detail_url)
        html = detail_res.content.decode("utf-8")
        self.assertNotIn('id="openAddListingBtn"', html)
        self.assertNotIn('id="addListingModal"', html)
