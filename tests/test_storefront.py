from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from inventory.models import (
    OFFICIAL_CATEGORIES,
    Category,
    ClarificationStatus,
    MarketplaceSite,
    Product,
    ProductClarification,
    ProductCondition,
    ProductListingLink,
    ProductStatus,
    StorefrontConfiguration,
)
from inventory.services.ai_service import infer_taxonomy_heuristically

User = get_user_model()


class StorefrontMarketplaceTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            username="secret_staff_agent_6644",
            password="password123",
            is_staff=True,
        )
        self.wallapop_site, _ = MarketplaceSite.objects.get_or_create(
            slug="wallapop",
            defaults={
                "name": "Wallapop",
                "base_url": "https://es.wallapop.com",
                "is_active": True,
                "order": 1,
            },
        )
        self.vinted_site, _ = MarketplaceSite.objects.get_or_create(
            slug="vinted",
            defaults={
                "name": "Vinted",
                "base_url": "https://www.vinted.es",
                "is_active": True,
                "order": 2,
            },
        )
        self.bicycles_cat = Category.objects.get(slug="bicicletas")
        self.tech_cat = Category.objects.get(slug="tecnologia-y-electronica")
        self.collectibles_cat = Category.objects.get(slug="coleccionismo")

    def _create_published_product(
        self,
        title="Bicicleta de Montaña Orbea MX 29",
        description="Cuadro de aluminio revisado en nuestro taller de Alfafar.",
        raw_note="SECRET_RAW_NOTE_DO_NOT_LEAK_9911 comprado en lote por 40 euros",
        price=Decimal("349.00"),
        category=None,
        condition=ProductCondition.VERY_GOOD,
        is_public=True,
        is_featured=False,
        is_reserved=False,
    ) -> Product:
        product = Product.objects.create(
            raw_note=raw_note,
            ai_title=title,
            ai_description=description,
            sale_price=price,
            category=category or self.bicycles_cat,
            condition=condition,
            is_public=is_public,
            is_featured=is_featured,
            is_reserved=is_reserved,
            created_by=self.staff_user,
        )
        ProductListingLink.objects.create(
            product=product,
            site=self.wallapop_site,
            url=f"https://es.wallapop.com/item/test-{product.pk}",
            is_active=True,
        )
        product.refresh_Lifecycle_status = product.compute_lifecycle_status()
        product.status = ProductStatus.PUBLISHED
        product.save()
        return product

    def test_official_12_categories_and_storefront_config_seeded(self):
        categories = Category.objects.filter(is_active=True).order_by("order")
        self.assertEqual(categories.count(), 12)
        expected_slugs = [slug for slug, _, _, _, _ in OFFICIAL_CATEGORIES]
        self.assertEqual(list(categories.values_list("slug", flat=True)), expected_slugs)

        config = StorefrontConfiguration.get_solo()
        self.assertEqual(config.store_name, "Rápido Pack")
        self.assertEqual(config.domain, "rapidopack.es")
        self.assertIn("Alfafar", config.address)

    def test_public_visible_queryset_and_7_day_sold_retention(self):
        pub_product = self._create_published_product(title="Visible Published Item")

        # Private published product should be excluded
        private_product = self._create_published_product(
            title="Hidden Private Item",
            is_public=False,
        )

        # Draft, Price Pending & Blocked products must be excluded; Ready with price > 0 is visible
        draft_product = Product.objects.create(
            raw_note="Draft note",
            ai_title="",
            ai_description="",
            is_public=True,
        )
        price_pending_product = Product.objects.create(
            raw_note="Price pending note",
            ai_title="Price Pending Title",
            ai_description="Price Pending Description",
            sale_price=None,
            is_public=True,
        )
        ready_product = Product.objects.create(
            raw_note="Ready note",
            ai_title="Ready Title",
            ai_description="Ready Description",
            sale_price=Decimal("25.00"),
            is_public=True,
        )

        # Recently sold (< 7 days ago) should remain visible for social proof
        recent_sold = self._create_published_product(title="Recently Sold Camera")
        recent_sold.mark_as_sold(price=Decimal("120.00"))
        Product.objects.filter(pk=recent_sold.pk).update(
            sold_at=timezone.now() - timedelta(days=3)
        )

        # Sold > 7 days ago should be hidden automatically
        expired_sold = self._create_published_product(title="Old Sold Camera")
        expired_sold.mark_as_sold(price=Decimal("90.00"))
        Product.objects.filter(pk=expired_sold.pk).update(
            sold_at=timezone.now() - timedelta(days=8)
        )

        visible_pks = set(Product.objects.public_visible().values_list("pk", flat=True))
        self.assertIn(pub_product.pk, visible_pks)
        self.assertIn(ready_product.pk, visible_pks)
        self.assertIn(recent_sold.pk, visible_pks)
        self.assertNotIn(private_product.pk, visible_pks)
        self.assertNotIn(draft_product.pk, visible_pks)
        self.assertNotIn(price_pending_product.pk, visible_pks)
        self.assertNotIn(expired_sold.pk, visible_pks)

        # Expired sold item returns 404 on public detail view
        resp_expired = self.client.get(expired_sold.get_public_url())
        self.assertEqual(resp_expired.status_code, 404)

    def test_public_storefront_never_leaks_internal_notes_or_clarifications(self):
        product = self._create_published_product(
            title="Cámara Retro Canon AE-1 Program",
            description="Revisada en nuestro taller de Alfafar con objetivo 50mm.",
            raw_note="SECRET_RAW_NOTE_DO_NOT_LEAK_9911 coste 30EUR proveedor privado",
        )
        # Attach a resolved clarification so product stays PUBLISHED
        ProductClarification.objects.create(
            product=product,
            question="SECRET_CLARIFICATION_QUESTION_8822",
            answer="SECRET_CLARIFICATION_ANSWER_7733",
            status=ClarificationStatus.RESOLVED,
            asked_by=self.staff_user,
            answered_by=self.staff_user,
        )

        forbidden_secrets = [
            "SECRET_RAW_NOTE_DO_NOT_LEAK_9911",
            "SECRET_CLARIFICATION_QUESTION_8822",
            "SECRET_CLARIFICATION_ANSWER_7733",
            "secret_staff_agent_6644",
        ]

        # 1. Check Catalog Homepage (/)
        catalog_resp = self.client.get(reverse("storefront:catalog"))
        self.assertEqual(catalog_resp.status_code, 200)
        catalog_html = catalog_resp.content.decode("utf-8")
        self.assertIn("Cámara Retro Canon AE-1 Program", catalog_html)
        for secret in forbidden_secrets:
            self.assertNotIn(secret, catalog_html)

        # 2. Check Search Query against raw_note (must return 0 matches and never leak)
        search_resp = self.client.get(
            reverse("storefront:catalog"),
            {"q": "SECRET_RAW_NOTE_DO_NOT_LEAK_9911"},
        )
        self.assertEqual(search_resp.status_code, 200)
        self.assertEqual(search_resp.context["total_count"], 0)

        # 3. Check Public Product Detail Page (/p/<slug>-<pk>/) including OG & JSON-LD
        detail_resp = self.client.get(product.get_public_url())
        self.assertEqual(detail_resp.status_code, 200)
        detail_html = detail_resp.content.decode("utf-8")
        self.assertIn("Cámara Retro Canon AE-1 Program", detail_html)
        self.assertIn("Revisada en nuestro taller de Alfafar", detail_html)
        for secret in forbidden_secrets:
            self.assertNotIn(secret, detail_html)

        # 4. Check Sitemap (/sitemap.xml)
        sitemap_resp = self.client.get(reverse("storefront:sitemap"))
        self.assertEqual(sitemap_resp.status_code, 200)
        sitemap_xml = sitemap_resp.content.decode("utf-8")
        for secret in forbidden_secrets:
            self.assertNotIn(secret, sitemap_xml)

    def test_catalog_filtering_searching_and_sorting(self):
        p_bike = self._create_published_product(
            title="Bicicleta Orbea MX",
            price=Decimal("350.00"),
            category=self.bicycles_cat,
            condition=ProductCondition.VERY_GOOD,
            is_featured=True,
        )
        p_camera = self._create_published_product(
            title="Cámara Vintage Kodak",
            price=Decimal("15.00"),
            category=self.collectibles_cat,
            condition=ProductCondition.VINTAGE,
            is_featured=False,
        )
        p_headphones = self._create_published_product(
            title="Auriculares Sony Studio",
            price=Decimal("35.00"),
            category=self.tech_cat,
            condition=ProductCondition.NEW_WITH_TAGS,
            is_featured=False,
        )

        # Filter by category
        resp_cat = self.client.get(reverse("storefront:catalog"), {"category": "bicicletas"})
        self.assertEqual([p.pk for p in resp_cat.context["products"]], [p_bike.pk])

        # Filter by condition
        resp_cond = self.client.get(
            reverse("storefront:catalog"),
            {"condition": ProductCondition.VINTAGE},
        )
        self.assertEqual([p.pk for p in resp_cond.context["products"]], [p_camera.pk])

        # Filter by price range (< 20 €)
        resp_under_20 = self.client.get(reverse("storefront:catalog"), {"price": "under_20"})
        self.assertEqual([p.pk for p in resp_under_20.context["products"]], [p_camera.pk])

        # Filter by price range (20 € - 50 €)
        resp_20_50 = self.client.get(reverse("storefront:catalog"), {"price": "20_50"})
        self.assertEqual([p.pk for p in resp_20_50.context["products"]], [p_headphones.pk])

        # Filter by price range (> 50 €)
        resp_over_50 = self.client.get(reverse("storefront:catalog"), {"price": "over_50"})
        self.assertEqual([p.pk for p in resp_over_50.context["products"]], [p_bike.pk])

        # Search by reference number (e.g. Ref. #0001)
        resp_ref = self.client.get(
            reverse("storefront:catalog"),
            {"q": p_headphones.public_reference},
        )
        self.assertEqual([p.pk for p in resp_ref.context["products"]], [p_headphones.pk])

        # Sort by price ascending
        resp_asc = self.client.get(reverse("storefront:catalog"), {"sort": "price_asc"})
        self.assertEqual(
            [p.pk for p in resp_asc.context["products"]],
            [p_camera.pk, p_headphones.pk, p_bike.pk],
        )

        # Sort by price descending
        resp_desc = self.client.get(reverse("storefront:catalog"), {"sort": "price_desc"})
        self.assertEqual(
            [p.pk for p in resp_desc.context["products"]],
            [p_bike.pk, p_headphones.pk, p_camera.pk],
        )

    def test_product_detail_canonical_redirect_and_click_tracking(self):
        product = self._create_published_product(
            title="Amplificador Pioneer SX-780",
            price=Decimal("280.00"),
            category=self.tech_cat,
            condition=ProductCondition.VINTAGE,
            is_featured=True,
        )
        link = product.listing_links.first()

        # Non-canonical slug redirects (302) to canonical URL
        wrong_url = reverse(
            "storefront:product_detail",
            kwargs={"slug": "wrong-slug-name", "pk": product.pk},
        )
        redirect_resp = self.client.get(wrong_url)
        self.assertEqual(redirect_resp.status_code, 302)
        self.assertEqual(redirect_resp["Location"], product.get_public_url())

        # Canonical URL returns 200 and increments views_count
        self.assertEqual(product.views_count, 0)
        detail_resp = self.client.get(product.get_public_url())
        self.assertEqual(detail_resp.status_code, 200)
        product.refresh_from_db()
        self.assertEqual(product.views_count, 1)

        # Outbound WhatsApp redirect (/go/whatsapp/<pk>/) increments whatsapp_clicks
        self.assertEqual(product.whatsapp_clicks, 0)
        wa_resp = self.client.get(reverse("storefront:go_whatsapp", kwargs={"pk": product.pk}))
        self.assertEqual(wa_resp.status_code, 302)
        self.assertTrue(wa_resp["Location"].startswith("https://wa.me/"))
        product.refresh_from_db()
        self.assertEqual(product.whatsapp_clicks, 1)

        # Outbound Marketplace link redirect (/go/link/<link_pk>/) increments clicks_count
        self.assertEqual(link.clicks_count, 0)
        link_resp = self.client.get(
            reverse("storefront:go_marketplace_link", kwargs={"link_pk": link.pk})
        )
        self.assertEqual(link_resp.status_code, 302)
        self.assertEqual(link_resp["Location"], link.url)
        link.refresh_from_db()
        self.assertEqual(link.clicks_count, 1)
        product.refresh_from_db()
        self.assertEqual(product.total_marketplace_clicks, 1)

    def test_seo_metadata_sitemap_robots_and_legal_pages(self):
        product = self._create_published_product(
            title="Cafetera DeLonghi Dedica EC685",
            price=Decimal("75.00"),
            is_reserved=True,
        )
        detail_resp = self.client.get(product.get_public_url())
        html = detail_resp.content.decode("utf-8")
        self.assertIn('property="og:type" content="product"', html)
        self.assertIn('property="product:price:amount" content="75.00"', html)
        self.assertIn('type="application/ld+json"', html)
        self.assertIn("https://schema.org/LimitedAvailability", html)

        # Sitemap XML
        sitemap_resp = self.client.get(reverse("storefront:sitemap"))
        self.assertEqual(sitemap_resp.status_code, 200)
        self.assertIn(product.get_public_url(), sitemap_resp.content.decode("utf-8"))

        # Robots.txt
        robots_resp = self.client.get(reverse("storefront:robots"))
        self.assertEqual(robots_resp.status_code, 200)
        robots_txt = robots_resp.content.decode("utf-8")
        self.assertIn("Allow: /p/", robots_txt)
        self.assertIn("Disallow: /dashboard/", robots_txt)
        self.assertIn("Disallow: /intake/", robots_txt)

        # Legal pages
        for route_name in ("legal_notice", "privacy_policy", "cookies_policy"):
            resp = self.client.get(reverse(f"storefront:{route_name}"))
            self.assertEqual(resp.status_code, 200)
            self.assertIn("Carrer del Comte Ronrée, 8", resp.content.decode("utf-8"))

    def test_heuristic_taxonomy_and_classify_products_command(self):
        slug, cond = infer_taxonomy_heuristically(
            "Bicicleta de montaña Orbea 29 pulgadas",
            "En muy buen estado, lista para rodar",
            "",
        )
        self.assertEqual(slug, "bicicletas")
        self.assertEqual(cond, "very_good")

        unclassified = Product.objects.create(
            raw_note="Pluma estilográfica Pelikan antigua años 80",
            ai_title="Pluma Estilográfica Pelikan Vintage Años 80",
            ai_description="Pieza de colección histórica en funcionamiento.",
            category=None,
            condition=ProductCondition.GOOD,
        )
        out = StringIO()
        call_command("classify_products", "--all", stdout=out)
        unclassified.refresh_from_db()
        self.assertIsNotNone(unclassified.category)
        self.assertEqual(unclassified.category.slug, "coleccionismo")
        self.assertEqual(unclassified.condition, ProductCondition.VINTAGE)
