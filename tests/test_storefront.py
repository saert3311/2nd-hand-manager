import re
from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

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

        # 0. Check Corporate Landing Page (/)
        home_resp = self.client.get(reverse("storefront:home"))
        self.assertEqual(home_resp.status_code, 200)
        home_html = home_resp.content.decode("utf-8")
        self.assertIn("Cámara Retro Canon AE-1 Program", home_html)
        for secret in forbidden_secrets:
            self.assertNotIn(secret, home_html)

        # 1. Check Store Catalog (/tienda/)
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

        # 3. Check Public Product Detail Page (/tienda/producto/<slug>-<pk>/) including OG & JSON-LD
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

    def test_root_serves_store_shelf_with_astro_nav_and_button_free_cards(self):
        # Create available products (with MSRP for -XX% PVP pill), 1 reserved, and 1 sold
        available_products = []
        for i in range(1, 6):
            p = self._create_published_product(
                title=f"Oportunidad Disponible {i}",
                price=Decimal("40.00"),
            )
            p.estimated_retail_price = Decimal("80.00")
            p.save(update_fields=["estimated_retail_price"])
            available_products.append(p)

        reserved_prod = self._create_published_product(
            title="Oportunidad Reservada Shelf",
            is_reserved=True,
        )
        sold_prod = self._create_published_product(title="Oportunidad Vendida Shelf")
        sold_prod.mark_as_sold(price=Decimal("50.00"))

        resp = self.client.get(reverse("storefront:home"))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")

        # Verify integration links to external Astro landing page (rapidopackvalencia.es)
        # and pixel-parity Astro top bar (logo, phone pill, live status, Outlet active pill, mobile drawer)
        self.assertIn("https://rapidopackvalencia.es/", html)
        self.assertIn("https://rapidopackvalencia.es/paqueteria", html)
        self.assertIn("https://rapidopackvalencia.es/contacto", html)
        self.assertIn("https://rapidopackvalencia.es/aviso-legal", html)
        self.assertIn("https://rapidopackvalencia.es/privacidad", html)
        self.assertIn("https://rapidopackvalencia.es/cookies", html)
        self.assertIn("logo-rapido-pack-valencia.png", html)
        self.assertIn("640 39 74 34", html)
        self.assertIn('id="header-live-status"', html)
        self.assertIn('id="mobileNavDrawer"', html)
        self.assertIn(">Outlet<", html)
        self.assertIn("Alfafar · Valencia", html)
        self.assertIn('underline decoration-white/20 underline-offset-4', html)

        # Verify Store Shelf structure, dropdown filters, category rail, LocalBusiness JSON-LD & external store links
        self.assertIn('id="priceDropdown"', html)
        self.assertIn('id="conditionDropdown"', html)
        self.assertIn('id="categoryRail"', html)
        self.assertIn('href="/categoria/bicicletas/', html)
        self.assertNotIn('href="/tienda/categoria/', html)
        self.assertIn('"@type": "LocalBusiness"', html)
        self.assertIn("-50%", html)

        # Verify button-free shelf cards: zero per-product WhatsApp buttons on the catalog grid
        for prod in available_products:
            self.assertNotIn(f"/go/whatsapp/{prod.pk}/", html)
            self.assertIn(prod.get_public_url(), html)

        # Verify all public-visible products (available + reserved + <7d sold) are surfaced on /
        shelf_pks = {p.pk for p in resp.context["products"]}
        for prod in available_products:
            self.assertIn(prod.pk, shelf_pks)
        self.assertIn(reserved_prod.pk, shelf_pks)
        self.assertIn(sold_prod.pk, shelf_pks)

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

        # Filter by SEO category URL (/categoria/<slug>/, without /tienda/ prefix)
        cat_route = reverse("storefront:category", kwargs={"category_slug": "bicicletas"})
        self.assertEqual(cat_route, "/categoria/bicicletas/")
        resp_cat_route = self.client.get(cat_route)
        self.assertEqual(resp_cat_route.status_code, 200)
        self.assertEqual([p.pk for p in resp_cat_route.context["products"]], [p_bike.pk])

        # Legacy /tienda/categoria/<slug>/ 301 redirects permanently to /categoria/<slug>/
        legacy_cat_resp = self.client.get("/tienda/categoria/bicicletas/?orden=precio-asc")
        self.assertEqual(legacy_cat_resp.status_code, 301)
        self.assertEqual(legacy_cat_resp["Location"], "/categoria/bicicletas/?orden=precio-asc")

        # Filter by category query param
        resp_cat = self.client.get(reverse("storefront:catalog"), {"categoria": "bicicletas"})
        self.assertEqual([p.pk for p in resp_cat.context["products"]], [p_bike.pk])

        # Filter by condition (Spanish slug ?estado=muy-bueno and enum ?condition=vintage)
        resp_cond_es = self.client.get(
            reverse("storefront:catalog"),
            {"estado": "muy-bueno"},
        )
        self.assertEqual([p.pk for p in resp_cond_es.context["products"]], [p_bike.pk])

        resp_cond = self.client.get(
            reverse("storefront:catalog"),
            {"condition": ProductCondition.VINTAGE},
        )
        self.assertEqual([p.pk for p in resp_cond.context["products"]], [p_camera.pk])

        # Filter by price range (< 20 € via ?precio=0-20)
        resp_under_20 = self.client.get(reverse("storefront:catalog"), {"precio": "0-20"})
        self.assertEqual([p.pk for p in resp_under_20.context["products"]], [p_camera.pk])

        # Filter by price range (20 € - 50 € via ?precio=20-50)
        resp_20_50 = self.client.get(reverse("storefront:catalog"), {"precio": "20-50"})
        self.assertEqual([p.pk for p in resp_20_50.context["products"]], [p_headphones.pk])

        # Filter by price range (> 50 € via ?precio=50+)
        resp_over_50 = self.client.get(reverse("storefront:catalog"), {"precio": "50+"})
        self.assertEqual([p.pk for p in resp_over_50.context["products"]], [p_bike.pk])

        # Search by reference number (e.g. Ref. #0001)
        resp_ref = self.client.get(
            reverse("storefront:catalog"),
            {"q": p_headphones.public_reference},
        )
        self.assertEqual([p.pk for p in resp_ref.context["products"]], [p_headphones.pk])

        # Sort by price ascending (?orden=precio-asc)
        resp_asc = self.client.get(reverse("storefront:catalog"), {"orden": "precio-asc"})
        self.assertEqual(
            [p.pk for p in resp_asc.context["products"]],
            [p_camera.pk, p_headphones.pk, p_bike.pk],
        )

        # Sort by price descending (?orden=precio-desc)
        resp_desc = self.client.get(reverse("storefront:catalog"), {"orden": "precio-desc"})
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

        # Non-canonical slug redirects (301 permanent) to canonical URL
        wrong_url = reverse(
            "storefront:product_detail",
            kwargs={"slug": "wrong-slug-name", "pk": product.pk},
        )
        redirect_resp = self.client.get(wrong_url)
        self.assertEqual(redirect_resp.status_code, 301)
        self.assertEqual(redirect_resp["Location"], product.get_public_url())

        # Legacy /p/<slug>-<pk>/ redirects (301 permanent) to /tienda/producto/<slug>-<pk>/
        legacy_resp = self.client.get(f"/p/{product.slug}-{product.pk}/")
        self.assertEqual(legacy_resp.status_code, 301)
        self.assertEqual(legacy_resp["Location"], product.get_public_url())

        # Canonical URL returns 200 and increments views_count
        self.assertEqual(product.views_count, 0)
        detail_resp = self.client.get(product.get_public_url())
        self.assertEqual(detail_resp.status_code, 200)
        product.refresh_from_db()
        self.assertEqual(product.views_count, 1)

        # General store WhatsApp redirect (/go/whatsapp/)
        store_wa_resp = self.client.get(reverse("storefront:go_whatsapp"))
        self.assertEqual(store_wa_resp.status_code, 302)
        self.assertTrue(store_wa_resp["Location"].startswith("https://wa.me/"))

        # Outbound Product WhatsApp redirect (/go/whatsapp/<pk>/) increments whatsapp_clicks
        self.assertEqual(product.whatsapp_clicks, 0)
        wa_resp = self.client.get(
            reverse("storefront:go_whatsapp_product", kwargs={"pk": product.pk})
        )
        self.assertEqual(wa_resp.status_code, 302)
        self.assertTrue(wa_resp["Location"].startswith("https://wa.me/"))
        product.refresh_from_db()
        self.assertEqual(product.whatsapp_clicks, 1)

        # Outbound Marketplace link redirect (/go/link/<link_pk>/) increments clicks_count
        self.assertEqual(link.clicks_count, 0)
        link_resp = self.client.get(
            reverse("storefront:go_listing", kwargs={"link_pk": link.pk})
        )
        self.assertEqual(link_resp.status_code, 302)
        self.assertEqual(link_resp["Location"], link.url)
        link.refresh_from_db()
        self.assertEqual(link.clicks_count, 1)
        product.refresh_from_db()
        self.assertEqual(product.total_marketplace_clicks, 1)

    def test_seo_metadata_sitemap_robots_how_to_buy_and_legal_pages(self):
        product = self._create_published_product(
            title="Cafetera DeLonghi Dedica EC685",
            price=Decimal("75.00"),
            category=self.tech_cat,
            is_reserved=True,
        )
        detail_resp = self.client.get(product.get_public_url())
        html = detail_resp.content.decode("utf-8")
        self.assertEqual(html.count('rel="canonical"'), 1)
        self.assertIn('hreflang="es"', html)
        self.assertIn('hreflang="en"', html)
        self.assertIn('hreflang="x-default"', html)
        self.assertIn('property="og:locale"', html)
        self.assertIn('property="og:type" content="product"', html)
        self.assertIn('property="product:price:amount" content="75.00"', html)
        self.assertIn('type="application/ld+json"', html)
        self.assertIn('"@type": "BreadcrumbList"', html)
        self.assertIn("https://schema.org/LimitedAvailability", html)
        self.assertIn("storefront/css/storefront.css", html)
        self.assertIn("defer onload=\"applyRpvTailwindConfig()\"", html)

        # Homepage LocalBusiness schema consistency & indexable directives
        home_html = self.client.get(reverse("storefront:home")).content.decode("utf-8")
        self.assertIn('"+34640397434"', home_html)
        self.assertIn('"https://rapidopackvalencia.es/"', home_html)
        self.assertIn('<meta name="robots" content="index, follow, max-image-preview:large">', home_html)

        # Populated category page has unique meta description, BreadcrumbList JSON-LD, and index directive
        cat_html = self.client.get(
            reverse("storefront:category", kwargs={"category_slug": self.tech_cat.slug})
        ).content.decode("utf-8")
        self.assertIn("inspected second-hand and outlet items", cat_html)
        self.assertIn('"@type": "BreadcrumbList"', cat_html)
        self.assertIn('<meta name="robots" content="index, follow, max-image-preview:large">', cat_html)

        # Empty categories & filtered/search views are marked noindex, follow to prevent Soft 404 / faceted bloat
        empty_cat_html = self.client.get(
            reverse("storefront:category", kwargs={"category_slug": self.collectibles_cat.slug})
        ).content.decode("utf-8")
        self.assertIn('<meta name="robots" content="noindex, follow">', empty_cat_html)
        search_html = self.client.get(f"{reverse('storefront:home')}?q=cafetera").content.decode("utf-8")
        self.assertIn('<meta name="robots" content="noindex, follow">', search_html)

        # Standalone How-to-Buy page (/como-comprar/)
        how_resp = self.client.get(reverse("storefront:how_to_buy"))
        self.assertEqual(how_resp.status_code, 200)
        how_html = how_resp.content.decode("utf-8")
        self.assertIn("Alfafar", how_html)
        self.assertEqual(how_html.count('rel="canonical"'), 1)
        self.assertIn('property="og:url"', how_html)

        # Sitemap XML excludes /tienda/ duplicate and empty categories
        sitemap_resp = self.client.get(reverse("storefront:sitemap"))
        self.assertEqual(sitemap_resp.status_code, 200)
        sitemap_xml = sitemap_resp.content.decode("utf-8")
        self.assertIn(product.get_public_url(), sitemap_xml)
        self.assertIn(reverse("storefront:how_to_buy"), sitemap_xml)
        self.assertIn(reverse("storefront:category", kwargs={"category_slug": self.tech_cat.slug}), sitemap_xml)
        self.assertNotIn(f"<loc>http://testserver{reverse('storefront:catalog')}</loc>", sitemap_xml)
        self.assertNotIn(reverse("storefront:category", kwargs={"category_slug": self.bicycles_cat.slug}), sitemap_xml)
        self.assertNotIn(
            reverse("storefront:category", kwargs={"category_slug": self.collectibles_cat.slug}), sitemap_xml
        )

        # JSON-LD escaping prevents </script> break-out XSS in titles/descriptions
        xss_product = self._create_published_product(
            title="Monitor </script><script>alert(1)</script> & Co",
            description="Descripción segura con </script> y & más detalles.",
            category=self.tech_cat,
        )
        xss_html = self.client.get(xss_product.get_public_url()).content.decode("utf-8")
        self.assertNotIn("</script><script>alert(1)</script>", xss_html)
        self.assertIn(r"\u003c/script\u003e", xss_html)

        # Robots.txt
        robots_resp = self.client.get(reverse("storefront:robots"))
        self.assertEqual(robots_resp.status_code, 200)
        robots_txt = robots_resp.content.decode("utf-8")
        self.assertIn("Allow: /categoria/", robots_txt)
        self.assertIn("Allow: /tienda/", robots_txt)
        self.assertIn("Disallow: /panel/", robots_txt)
        self.assertIn("Disallow: /dashboard/", robots_txt)
        self.assertIn("Disallow: /intake/", robots_txt)

        # Legal pages redirect to canonical rapidopackvalencia.es URLs and are omitted from store sitemap
        expected_redirects = {
            "legal_notice": "https://rapidopackvalencia.es/aviso-legal",
            "privacy": "https://rapidopackvalencia.es/privacidad",
            "cookies": "https://rapidopackvalencia.es/cookies",
        }
        for route_name, target_url in expected_redirects.items():
            route_path = reverse(f"storefront:{route_name}")
            resp = self.client.get(route_path, follow=False)
            self.assertEqual(resp.status_code, 302)
            self.assertEqual(resp["Location"], target_url)
            self.assertNotIn(route_path, sitemap_xml)

        # Storefront favicons match rapidopackvalencia.es branding (not internal 2ndHand icons)
        home_html = self.client.get(reverse("storefront:home")).content.decode("utf-8")
        self.assertIn("storefront/img/logo-rapido-pack-valencia.png", home_html)
        self.assertIn("storefront/img/favicon.ico", home_html)
        self.assertIn("storefront/img/apple-touch-icon.png", home_html)
        self.assertNotIn("inventory/icons/icon-192.png", home_html)
        self.assertNotIn("inventory/icons/apple-touch-icon.png", home_html)

        fav_resp = self.client.get(reverse("storefront:favicon"), follow=False)
        self.assertEqual(fav_resp.status_code, 301)
        self.assertIn("storefront/img/favicon.ico", fav_resp["Location"])

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

    def test_product_detail_breadcrumb_links_category_and_shows_product_name(self):
        product = self._create_published_product(
            title="Auriculares Sony WH-1000XM4 Negro",
            price=Decimal("145.00"),
            category=self.tech_cat,
        )
        detail_resp = self.client.get(product.get_public_url())
        self.assertEqual(detail_resp.status_code, 200)
        html = detail_resp.content.decode("utf-8")

        nav_match = re.search(r'<nav aria-label="Breadcrumb"[^>]*>(.*?)</nav>', html, re.S)
        self.assertIsNotNone(nav_match)
        breadcrumb_html = nav_match.group(1)

        cat_url = reverse("storefront:category", kwargs={"category_slug": self.tech_cat.slug})
        self.assertIn(reverse("storefront:home"), breadcrumb_html)
        self.assertIn(cat_url, breadcrumb_html)
        self.assertIn(escape(self.tech_cat.get_localized_name()), breadcrumb_html)
        self.assertIn(product.ai_title, breadcrumb_html)
        self.assertIn('aria-current="page"', breadcrumb_html)
        self.assertNotIn(product.public_reference, breadcrumb_html)

        # Inactive category falls back cleanly to filtered catalog URL (never links to 404)
        self.tech_cat.is_active = False
        self.tech_cat.save(update_fields=["is_active"])
        try:
            fallback_resp = self.client.get(product.get_public_url())
            self.assertEqual(fallback_resp.status_code, 200)
            fallback_nav = re.search(
                r'<nav aria-label="Breadcrumb"[^>]*>(.*?)</nav>',
                fallback_resp.content.decode("utf-8"),
                re.S,
            ).group(1)
            self.assertIn(f"{reverse('storefront:home')}?category={self.tech_cat.slug}", fallback_nav)
            self.assertNotIn(cat_url, fallback_nav)
        finally:
            self.tech_cat.is_active = True
            self.tech_cat.save(update_fields=["is_active"])

    def test_catalog_default_orders_featured_first_then_newest_descending(self):
        now = timezone.now()
        older_featured = self._create_published_product(
            title="Destacado Antiguo",
            price=Decimal("40.00"),
            is_featured=True,
        )
        newer_featured = self._create_published_product(
            title="Destacado Reciente",
            price=Decimal("45.00"),
            is_featured=True,
        )
        older_regular = self._create_published_product(
            title="Normal Antiguo",
            price=Decimal("30.00"),
            is_featured=False,
        )
        newest_regular = self._create_published_product(
            title="Normal Muy Reciente",
            price=Decimal("50.00"),
            is_featured=False,
        )
        sold_featured = self._create_published_product(
            title="Destacado Vendido",
            price=Decimal("60.00"),
            is_featured=True,
        )
        sold_featured.mark_as_sold(price=Decimal("60.00"))

        Product.objects.filter(pk=older_featured.pk).update(created_at=now - timedelta(days=5))
        Product.objects.filter(pk=newer_featured.pk).update(created_at=now - timedelta(days=2))
        Product.objects.filter(pk=newest_regular.pk).update(created_at=now - timedelta(hours=1))
        Product.objects.filter(pk=older_regular.pk).update(created_at=now - timedelta(days=3))
        Product.objects.filter(pk=sold_featured.pk).update(created_at=now - timedelta(minutes=30))

        expected_order = [
            newer_featured.pk,
            older_featured.pk,
            newest_regular.pk,
            older_regular.pk,
            sold_featured.pk,
        ]
        for route_name in ("storefront:home", "storefront:catalog"):
            resp = self.client.get(reverse(route_name))
            self.assertEqual(resp.status_code, 200)
            self.assertEqual([p.pk for p in resp.context["products"]], expected_order)

    def test_category_rail_shows_only_active_stock_by_default_with_show_all_toggle(self):
        # 1 available product in bicycles; 1 sold-only product in collectibles
        self._create_published_product(
            title="Bicicleta Disponible",
            price=Decimal("250.00"),
            category=self.bicycles_cat,
        )
        sold_collectible = self._create_published_product(
            title="Reloj Vendido",
            price=Decimal("80.00"),
            category=self.collectibles_cat,
        )
        sold_collectible.mark_as_sold(price=Decimal("80.00"))

        resp = self.client.get(reverse("storefront:home"))
        self.assertEqual(resp.status_code, 200)
        # Only 1 of 12 categories (bicicletas) has unsold available stock; 11 are hidden by default
        self.assertEqual(resp.context["hidden_categories_count"], 11)
        self.assertEqual(resp.context["categories"][0].slug, "bicicletas")

        html = resp.content.decode("utf-8")
        self.assertIn("rail.classList.toggle('flex-wrap', nextExpanded)", html)
        rail_html = re.search(r'<div[^>]*id="categoryRail"[^>]*>(.*?)</div>', html, re.S).group(1)

        self.assertIn('id="toggleAllCategoriesBtn"', rail_html)
        self.assertIn("+ Show all categories (11)", rail_html)
        self.assertIn("Show active only", rail_html)

        # Populated category chip stays visible (not marked data-empty-category)
        bike_chip = re.search(r'<a[^>]*href="/categoria/bicicletas/[^"]*"[^>]*>.*?</a>', rail_html, re.S).group(0)
        self.assertNotIn('data-empty-category="true"', bike_chip)
        self.assertIn("(1)", bike_chip)

        # Sold-only and empty categories stay hidden with data-empty-category="true" until toggled
        collectibles_chip = re.search(
            r'<a[^>]*href="/categoria/coleccionismo/[^"]*"[^>]*>.*?</a>', rail_html, re.S
        ).group(0)
        self.assertIn('data-empty-category="true"', collectibles_chip)
        self.assertIn("hidden ", collectibles_chip)

        # Direct visit to an empty category keeps that active category visible in the rail
        empty_cat_resp = self.client.get(reverse("storefront:category", kwargs={"category_slug": "coleccionismo"}))
        self.assertEqual(empty_cat_resp.status_code, 200)
        self.assertEqual(empty_cat_resp.context["hidden_categories_count"], 10)
        empty_rail = re.search(
            r'<div[^>]*id="categoryRail"[^>]*>(.*?)</div>', empty_cat_resp.content.decode("utf-8"), re.S
        ).group(1)
        active_collectibles = re.search(
            r'<a[^>]*href="/categoria/coleccionismo/[^"]*"[^>]*>.*?</a>', empty_rail, re.S
        ).group(0)
        self.assertNotIn('data-empty-category="true"', active_collectibles)
        self.assertNotIn("hidden ", active_collectibles)

    def test_product_detail_hides_other_stores_section_when_no_marketplace_links(self):
        store_only = Product.objects.create(
            raw_note="Exclusive item",
            ai_title="Mesa Exclusiva Alfafar",
            ai_description="Disponible exclusivamente en tienda.",
            sale_price=Decimal("120.00"),
            category=self.tech_cat,
            is_public=True,
            status=ProductStatus.PUBLISHED,
            created_by=self.staff_user,
        )
        resp = self.client.get(store_only.get_public_url())
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")
        self.assertNotIn("Other stores &amp; protected shipping:", html)
        self.assertNotIn("Other stores & protected shipping:", html)
        self.assertNotIn("Also available with protected shipping on:", html)
        self.assertNotIn(self.wallapop_site.base_url, html)

        # Adding an active link reveals the product-specific external links block
        link = ProductListingLink.objects.create(
            product=store_only,
            site=self.wallapop_site,
            url="https://es.wallapop.com/item/mesa-exclusiva-123",
            is_active=True,
        )
        linked_resp = self.client.get(store_only.get_public_url())
        self.assertEqual(linked_resp.status_code, 200)
        linked_html = linked_resp.content.decode("utf-8")
        self.assertIn("Also available with protected shipping on:", linked_html)
        self.assertIn(reverse("storefront:go_listing", kwargs={"link_pk": link.pk}), linked_html)

    def test_cookie_consent_banner_and_cross_subdomain_sync_state(self):
        from urllib.parse import quote

        from storefront.context_processors import _parse_rpv_cookie_consent

        # Unit parser verification for JSON, URL-encoded JSON, scalar tokens, and malformed payloads
        self.assertEqual(_parse_rpv_cookie_consent(None), (False, False))
        self.assertEqual(_parse_rpv_cookie_consent(""), (False, False))
        self.assertEqual(_parse_rpv_cookie_consent("accepted"), (True, True))
        self.assertEqual(_parse_rpv_cookie_consent("rejected"), (True, False))
        self.assertEqual(_parse_rpv_cookie_consent('{"essential":true,"analytics":true}'), (True, True))
        self.assertEqual(_parse_rpv_cookie_consent(quote('{"essential":true,"analytics":false}')), (True, False))
        self.assertEqual(_parse_rpv_cookie_consent('{"analytics_storage":"granted"}'), (True, True))
        self.assertEqual(_parse_rpv_cookie_consent("{broken-json"), (False, False))

        # 1. Fresh visitor without cookie sees undecided cookie banner & denied analytics default
        self.client.cookies.pop("rpv_cookie_consent", None)
        resp_fresh = self.client.get(reverse("storefront:home"))
        self.assertEqual(resp_fresh.status_code, 200)
        self.assertFalse(resp_fresh.context["cookie_consent_decided"])
        self.assertFalse(resp_fresh.context["cookie_analytics_granted"])
        html_fresh = resp_fresh.content.decode("utf-8")
        self.assertIn("GTM-PGBXBVXJ", html_fresh)
        self.assertIn("'analytics_storage': 'denied'", html_fresh)
        self.assertIn('id="footer-cookie-settings-btn"', html_fresh)
        self.assertIn('id="cookie-banner-container"', html_fresh)
        self.assertIn('id="cookie-accept-all-btn"', html_fresh)
        self.assertIn('id="cookie-reject-all-btn"', html_fresh)
        self.assertIn('id="cookie-save-settings-btn"', html_fresh)
        self.assertIn('id="cookie-toggle-settings-btn"', html_fresh)
        self.assertIn("Domain=.rapidopackvalencia.es", html_fresh)
        banner_tag_fresh = re.search(r'<div id="cookie-banner-container"[^>]*>', html_fresh).group(0)
        self.assertNotIn('aria-hidden="true"', banner_tag_fresh)

        # 2. Visitor arriving with cross-subdomain analytics-accepted cookie gets hidden banner & granted default
        for cookie_val in (quote('{"essential":true,"analytics":true,"version":1}'), "accepted"):
            self.client.cookies["rpv_cookie_consent"] = cookie_val
            resp_accepted = self.client.get(reverse("storefront:home"))
            self.assertEqual(resp_accepted.status_code, 200)
            self.assertTrue(resp_accepted.context["cookie_consent_decided"])
            self.assertTrue(resp_accepted.context["cookie_analytics_granted"])
            html_accepted = resp_accepted.content.decode("utf-8")
            self.assertIn("'analytics_storage': 'granted'", html_accepted)
            banner_tag = re.search(r'<div id="cookie-banner-container"[^>]*>', html_accepted).group(0)
            self.assertIn('aria-hidden="true"', banner_tag)
            toggle_tag = re.search(r'<input[^>]*id="cookie-analytics-toggle"[^>]*>', html_accepted).group(0)
            self.assertIn("checked", toggle_tag)

        # 3. Visitor arriving with rejected/essential-only cookie gets hidden banner & denied analytics
        for cookie_val in ("rejected", quote('{"essential":true,"analytics":false,"version":1}')):
            self.client.cookies["rpv_cookie_consent"] = cookie_val
            resp_rejected = self.client.get(reverse("storefront:home"))
            self.assertEqual(resp_rejected.status_code, 200)
            self.assertTrue(resp_rejected.context["cookie_consent_decided"])
            self.assertFalse(resp_rejected.context["cookie_analytics_granted"])
            html_rejected = resp_rejected.content.decode("utf-8")
            self.assertIn("'analytics_storage': 'denied'", html_rejected)
            banner_tag = re.search(r'<div id="cookie-banner-container"[^>]*>', html_rejected).group(0)
            self.assertIn('aria-hidden="true"', banner_tag)
            toggle_tag = re.search(r'<input[^>]*id="cookie-analytics-toggle"[^>]*>', html_rejected).group(0)
            self.assertNotIn("checked", toggle_tag)

        # 4. GTM <noscript>, dataLayer e-commerce/lead events, staff exclusion & override setting
        self.assertIn(
            '<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=GTM-PGBXBVXJ"',
            html_fresh,
        )
        self.assertIn("'traffic_type': 'public'", html_fresh)
        self.assertIn("event: 'view_item_list'", html_fresh)

        search_resp = self.client.get(f"{reverse('storefront:home')}?q=sony")
        search_html = search_resp.content.decode("utf-8")
        self.assertIn("event: 'search'", search_html)
        self.assertIn("search_term: 'sony'", search_html)

        detail_prod = self._create_published_product(
            title="Auriculares Sony GTM",
            price=Decimal("89.00"),
            category=self.tech_cat,
        )
        detail_html = self.client.get(detail_prod.get_public_url()).content.decode("utf-8")
        self.assertIn("event: 'view_item'", detail_html)
        self.assertIn('data-gtm-event="whatsapp_click"', detail_html)
        self.assertIn('data-gtm-event="marketplace_click"', detail_html)

        with override_settings(GTM_CONTAINER_ID="GTM-TEST999"):
            custom_html = self.client.get(reverse("storefront:home")).content.decode("utf-8")
            self.assertIn("GTM-TEST999", custom_html)

        # Logged-in staff members must not load GTM container scripts
        self.client.force_login(self.staff_user)
        staff_resp = self.client.get(reverse("storefront:home"))
        self.assertFalse(staff_resp.context["gtm_enabled"])
        staff_html = staff_resp.content.decode("utf-8")
        self.assertIn("'traffic_type': 'internal'", staff_html)
        self.assertNotIn("googletagmanager.com/ns.html", staff_html)
        self.assertNotIn("googletagmanager.com/gtm.js", staff_html)
