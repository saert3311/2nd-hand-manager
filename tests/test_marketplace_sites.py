from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from inventory.admin import MarketplaceSiteAdmin, ProductAdmin, ProductListingLinkInline, admin_site
from inventory.models import MarketplaceSite, Product, ProductListingLink
from inventory.permissions import ROLE_ASSISTANT, ROLE_MANAGER

User = get_user_model()


class MarketplaceSiteModelTests(TestCase):
    def test_default_seeded_sites_exist(self):
        """Verify that seed migration populated default resale platforms."""
        slugs = list(MarketplaceSite.objects.values_list("slug", flat=True))
        self.assertIn("wallapop", slugs)
        self.assertIn("vinted", slugs)
        self.assertIn("milanuncios", slugs)
        self.assertIn("ebay", slugs)

    def test_auto_slug_generation(self):
        """Verify that slug is generated from name if left empty."""
        site = MarketplaceSite.objects.create(name="Vestiaire Collective")
        self.assertEqual(site.slug, "vestiaire-collective")
        self.assertEqual(str(site), "Vestiaire Collective")

    def test_unique_name_constraint(self):
        """Verify that creating a site with duplicate name fails."""
        with self.assertRaises(IntegrityError):
            MarketplaceSite.objects.create(name="Wallapop", slug="wallapop-dup")

    def test_ordering(self):
        """Verify that sites are ordered by display order then name."""
        MarketplaceSite.objects.all().delete()
        s2 = MarketplaceSite.objects.create(name="Z-Platform", order=10)
        s1 = MarketplaceSite.objects.create(name="A-Platform", order=5)
        s3 = MarketplaceSite.objects.create(name="B-Platform", order=10)

        ordered = list(MarketplaceSite.objects.all())
        self.assertEqual(ordered, [s1, s3, s2])


class ProductListingLinkModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lister", password="pw")
        self.product = Product.objects.create(raw_note="Vintage Jacket", created_by=self.user)
        self.site = MarketplaceSite.objects.get(slug="wallapop")

    def test_create_link_and_str(self):
        """Verify link creation and string display."""
        link = ProductListingLink.objects.create(
            product=self.product,
            site=self.site,
            url="https://es.wallapop.com/item/jacket-123",
        )
        self.assertIn("Wallapop", str(link))
        self.assertIn("Vintage Jacket", str(link))

    def test_unique_product_site_link_constraint(self):
        """Verify that each product can have at most one link per site."""
        ProductListingLink.objects.create(
            product=self.product,
            site=self.site,
            url="https://es.wallapop.com/item/jacket-123",
        )
        with self.assertRaises(IntegrityError):
            ProductListingLink.objects.create(
                product=self.product,
                site=self.site,
                url="https://es.wallapop.com/item/jacket-456",
            )

    def test_cascade_delete_with_product(self):
        """Verify that deleting product cascades to its listing links."""
        ProductListingLink.objects.create(
            product=self.product,
            site=self.site,
            url="https://es.wallapop.com/item/jacket-123",
        )
        self.assertEqual(ProductListingLink.objects.count(), 1)
        self.product.delete()
        self.assertEqual(ProductListingLink.objects.count(), 0)


class MarketplaceAdminIntegrationTests(TestCase):
    def setUp(self):
        self.mgr_group, _ = Group.objects.get_or_create(name=ROLE_MANAGER)
        self.asst_group, _ = Group.objects.get_or_create(name=ROLE_ASSISTANT)

        self.manager = User.objects.create_user(username="admin_mgr", password="pw", is_staff=True)
        self.manager.groups.add(self.mgr_group)

        self.assistant = User.objects.create_user(username="field_asst", password="pw", is_staff=False)
        self.assistant.groups.add(self.asst_group)

        self.product = Product.objects.create(raw_note="Bag")
        self.site = MarketplaceSite.objects.get(slug="vinted")

    def test_manager_can_access_marketplace_site_admin(self):
        self.client.login(username="admin_mgr", password="pw")
        response = self.client.get(reverse("admin:inventory_marketplacesite_changelist"))
        self.assertEqual(response.status_code, 200)

    def test_assistant_cannot_access_marketplace_site_admin(self):
        self.client.login(username="field_asst", password="pw")
        response = self.client.get(reverse("admin:inventory_marketplacesite_changelist"))
        self.assertEqual(response.status_code, 403)

    def test_product_admin_contains_listing_links_inline(self):
        """Verify that ProductAdmin has ProductListingLinkInline registered."""
        self.assertIn(ProductListingLinkInline, ProductAdmin.inlines)

    def test_marketplace_site_admin_links_count(self):
        """Verify links_count returns correct related count."""
        admin_instance = MarketplaceSiteAdmin(MarketplaceSite, admin_site)
        self.assertEqual(admin_instance.links_count(self.site), 0)

        ProductListingLink.objects.create(
            product=self.product,
            site=self.site,
            url="https://www.vinted.es/items/123",
        )
        self.assertEqual(admin_instance.links_count(self.site), 1)


class ProductDetailLinksViewTests(TestCase):
    def setUp(self):
        self.mgr_group, _ = Group.objects.get_or_create(name=ROLE_MANAGER)
        self.asst_group, _ = Group.objects.get_or_create(name=ROLE_ASSISTANT)

        self.manager = User.objects.create_user(username="store_mgr", password="pw", is_staff=True)
        self.manager.groups.add(self.mgr_group)

        self.assistant = User.objects.create_user(username="scout_asst", password="pw", is_staff=False)
        self.assistant.groups.add(self.asst_group)

        self.product = Product.objects.create(raw_note="Vintage Camera", created_by=self.assistant)
        self.wallapop = MarketplaceSite.objects.get(slug="wallapop")
        self.vinted = MarketplaceSite.objects.get(slug="vinted")

    def test_product_detail_renders_all_active_platforms(self):
        self.client.login(username="store_mgr", password="pw")
        response = self.client.get(reverse("inventory:product_detail", kwargs={"pk": self.product.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Marketplace Listing Links")
        self.assertContains(response, "Wallapop")
        self.assertContains(response, "Vinted")
        self.assertContains(response, "No marketplace links active yet")

        # When a platform is linked, it renders the active tile with 'Listed' badge
        ProductListingLink.objects.create(
            product=self.product,
            site=self.wallapop,
            url="https://es.wallapop.com/item/vintage-camera-12345",
            is_active=True,
        )
        response_with_link = self.client.get(reverse("inventory:product_detail", kwargs={"pk": self.product.pk}))
        self.assertContains(response_with_link, "Listed")

    def test_manager_saves_valid_marketplace_link(self):
        self.client.login(username="store_mgr", password="pw")
        url = reverse("inventory:manage_link", kwargs={"pk": self.product.pk})
        response = self.client.post(
            url,
            {
                "action": "save",
                "site_id": self.wallapop.id,
                "url": "https://es.wallapop.com/item/vintage-camera-12345",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            ProductListingLink.objects.filter(
                product=self.product,
                site=self.wallapop,
                url="https://es.wallapop.com/item/vintage-camera-12345",
            ).exists()
        )
        self.assertContains(response, "Link for Wallapop saved successfully.")

    def test_manager_updates_existing_marketplace_link(self):
        link = ProductListingLink.objects.create(
            product=self.product,
            site=self.vinted,
            url="https://www.vinted.es/items/old-link",
        )
        self.client.login(username="store_mgr", password="pw")
        url = reverse("inventory:manage_link", kwargs={"pk": self.product.pk})
        self.client.post(
            url,
            {
                "action": "save",
                "site_id": self.vinted.id,
                "url": "https://www.vinted.es/items/new-link",
            },
            follow=True,
        )
        link.refresh_from_db()
        self.assertEqual(link.url, "https://www.vinted.es/items/new-link")

    def test_saving_empty_url_clears_link(self):
        ProductListingLink.objects.create(
            product=self.product,
            site=self.wallapop,
            url="https://es.wallapop.com/item/123",
        )
        self.client.login(username="store_mgr", password="pw")
        url = reverse("inventory:manage_link", kwargs={"pk": self.product.pk})
        response = self.client.post(
            url,
            {
                "action": "save",
                "site_id": self.wallapop.id,
                "url": "   ",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ProductListingLink.objects.filter(product=self.product, site=self.wallapop).exists())
        self.assertContains(response, "Marketplace link cleared.")

    def test_invalid_url_rejected(self):
        self.client.login(username="store_mgr", password="pw")
        url = reverse("inventory:manage_link", kwargs={"pk": self.product.pk})
        response = self.client.post(
            url,
            {
                "action": "save",
                "site_id": self.wallapop.id,
                "url": "javascript:alert(1)",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ProductListingLink.objects.filter(product=self.product, site=self.wallapop).exists())
        self.assertContains(response, "Please provide a valid URL starting with http:// or https://.")

    def test_manager_deletes_link(self):
        link = ProductListingLink.objects.create(
            product=self.product,
            site=self.wallapop,
            url="https://es.wallapop.com/item/123",
        )
        self.client.login(username="store_mgr", password="pw")
        url = reverse("inventory:manage_link", kwargs={"pk": self.product.pk})
        response = self.client.post(
            url,
            {
                "action": "delete",
                "link_id": link.id,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ProductListingLink.objects.filter(pk=link.id).exists())
        self.assertContains(response, "Marketplace link removed successfully.")

    def test_assistant_cannot_manage_links(self):
        self.client.login(username="scout_asst", password="pw")
        url = reverse("inventory:manage_link", kwargs={"pk": self.product.pk})
        response = self.client.post(
            url,
            {
                "action": "save",
                "site_id": self.wallapop.id,
                "url": "https://es.wallapop.com/item/123",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ProductListingLink.objects.filter(product=self.product, site=self.wallapop).exists())
        self.assertContains(response, "Manager privileges required to manage listing links.")


class DashboardMarketplacePlatformFilterTests(TestCase):
    def setUp(self):
        self.manager_group, _ = Group.objects.get_or_create(name=ROLE_MANAGER)
        self.manager = User.objects.create_user(username="mgr_user", password="pw")
        self.manager.groups.add(self.manager_group)
        self.client.login(username="mgr_user", password="pw")

        self.wallapop = MarketplaceSite.objects.get(slug="wallapop")
        self.vinted = MarketplaceSite.objects.get(slug="vinted")
        self.milanuncios = MarketplaceSite.objects.get(slug="milanuncios")
        self.ebay = MarketplaceSite.objects.get(slug="ebay")

        # Create products
        self.p1 = Product.objects.create(
            raw_note="Leather Jacket",
            ai_title="Vintage Leather Biker Jacket",
            is_sold=False,
            created_by=self.manager,
        )
        self.p2 = Product.objects.create(
            raw_note="Denim Shirt",
            ai_title="Western Denim Shirt",
            is_sold=True,
            created_by=self.manager,
        )
        self.p3 = Product.objects.create(
            raw_note="Wool Coat",
            ai_title="Winter Wool Coat",
            is_sold=False,
            created_by=self.manager,
        )

        # Links setup:
        # p1 is on Wallapop
        ProductListingLink.objects.create(
            product=self.p1,
            site=self.wallapop,
            url="https://es.wallapop.com/item/jacket-1",
            is_active=True,
        )
        # p2 is on Wallapop AND Vinted
        ProductListingLink.objects.create(
            product=self.p2,
            site=self.wallapop,
            url="https://es.wallapop.com/item/shirt-2",
            is_active=True,
        )
        ProductListingLink.objects.create(
            product=self.p2,
            site=self.vinted,
            url="https://www.vinted.es/items/shirt-2",
            is_active=True,
        )
        # p3 has NO links
        # milanuncios and ebay have NO links

    def test_available_platforms_only_includes_sites_with_published_products(self):
        """Selector must only include platforms that have at least 1 active product link."""
        response = self.client.get(reverse("inventory:dashboard"))
        self.assertEqual(response.status_code, 200)

        available_platforms = list(response.context["available_platforms"])
        slugs = [p.slug for p in available_platforms]
        self.assertIn("wallapop", slugs)
        self.assertIn("vinted", slugs)
        self.assertNotIn("milanuncios", slugs)
        self.assertNotIn("ebay", slugs)

        # Verify annotated counts: Wallapop has 2 products, Vinted has 1 product
        counts_by_slug = {p.slug: p.published_count for p in available_platforms}
        self.assertEqual(counts_by_slug["wallapop"], 2)
        self.assertEqual(counts_by_slug["vinted"], 1)

    def test_platform_selector_omitted_when_no_published_links(self):
        """When no products have links, available_platforms is empty and selector is omitted."""
        ProductListingLink.objects.all().delete()
        response = self.client.get(reverse("inventory:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["available_platforms"]), 0)
        self.assertNotContains(response, 'id="platformFilterForm"')

    def test_filter_by_platform_wallapop(self):
        """Filtering by ?platform=wallapop returns only products published on Wallapop."""
        response = self.client.get(reverse("inventory:dashboard"), {"platform": "wallapop"})
        self.assertEqual(response.status_code, 200)
        products = list(response.context["products"])
        self.assertEqual(len(products), 2)
        self.assertIn(self.p1, products)
        self.assertIn(self.p2, products)
        self.assertNotIn(self.p3, products)

    def test_filter_by_platform_vinted(self):
        """Filtering by ?platform=vinted returns only products published on Vinted."""
        response = self.client.get(reverse("inventory:dashboard"), {"platform": "vinted"})
        self.assertEqual(response.status_code, 200)
        products = list(response.context["products"])
        self.assertEqual(len(products), 1)
        self.assertIn(self.p2, products)
        self.assertNotIn(self.p1, products)
        self.assertNotIn(self.p3, products)

    def test_scoped_status_counters_for_selected_platform(self):
        """Status counters reflect the active platform scope when a platform is selected."""
        # For Wallapop: 2 total (p1 active, p2 sold)
        response_wallapop = self.client.get(reverse("inventory:dashboard"), {"platform": "wallapop"})
        self.assertEqual(response_wallapop.context["total_count"], 2)
        self.assertEqual(response_wallapop.context["active_count"], 1)
        self.assertEqual(response_wallapop.context["sold_count"], 1)

        # For Vinted: 1 total (p2 sold, 0 active)
        response_vinted = self.client.get(reverse("inventory:dashboard"), {"platform": "vinted"})
        self.assertEqual(response_vinted.context["total_count"], 1)
        self.assertEqual(response_vinted.context["active_count"], 0)
        self.assertEqual(response_vinted.context["sold_count"], 1)

        # For All Platforms: 3 total (p1 & p3 active, p2 sold)
        response_all = self.client.get(reverse("inventory:dashboard"))
        self.assertEqual(response_all.context["total_count"], 3)
        self.assertEqual(response_all.context["active_count"], 2)
        self.assertEqual(response_all.context["sold_count"], 1)

    def test_multi_filter_combination_status_and_platform(self):
        """Combining ?platform=wallapop&status=sold filters accurately."""
        response = self.client.get(reverse("inventory:dashboard"), {"platform": "wallapop", "status": "sold"})
        self.assertEqual(response.status_code, 200)
        products = list(response.context["products"])
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0], self.p2)

        response_active = self.client.get(reverse("inventory:dashboard"), {"platform": "wallapop", "status": "active"})
        self.assertEqual(response_active.status_code, 200)
        products_active = list(response_active.context["products"])
        self.assertEqual(len(products_active), 1)
        self.assertEqual(products_active[0], self.p1)

    def test_multi_filter_combination_search_and_platform(self):
        """Combining search and platform filter works seamlessly."""
        response = self.client.get(reverse("inventory:dashboard"), {"platform": "wallapop", "q": "Leather"})
        self.assertEqual(response.status_code, 200)
        products = list(response.context["products"])
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0], self.p1)

    def test_invalid_platform_slug_returns_empty_gracefully(self):
        """Invalid platform slug returns empty product catalog with HTTP 200 without error."""
        response = self.client.get(reverse("inventory:dashboard"), {"platform": "nonexistent"})
        self.assertEqual(response.status_code, 200)
        products = list(response.context["products"])
        self.assertEqual(len(products), 0)
        self.assertEqual(response.context["total_count"], 0)

    def test_pagination_preserves_platform_query_string(self):
        """Pagination query_string retains the platform parameter."""
        response = self.client.get(reverse("inventory:dashboard"), {"platform": "wallapop", "status": "active"})
        self.assertEqual(response.status_code, 200)
        query_string = response.context["query_string"]
        self.assertIn("platform=wallapop", query_string)
        self.assertIn("status=active", query_string)

    def test_inactive_listing_link_excluded_from_counts(self):
        """Links with is_active=False do not count towards published count."""
        # Deactivate link for p1 on Wallapop
        link = ProductListingLink.objects.get(product=self.p1, site=self.wallapop)
        link.is_active = False
        link.save()

        response = self.client.get(reverse("inventory:dashboard"))
        available_platforms = list(response.context["available_platforms"])
        counts_by_slug = {p.slug: p.published_count for p in available_platforms}
        # Wallapop should now have count 1 (only p2)
        self.assertEqual(counts_by_slug["wallapop"], 1)

