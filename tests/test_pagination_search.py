import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from inventory.models import Product, ProductImage, ProductStatus
from inventory.permissions import ROLE_ASSISTANT, ROLE_MANAGER
from inventory.services.search_service import build_search_query

User = get_user_model()


class SearchServiceTests(TestCase):
    def test_empty_query_returns_empty_q(self):
        q = build_search_query("")
        self.assertEqual(len(q.children), 0)

        q_whitespace = build_search_query("   ")
        self.assertEqual(len(q_whitespace.children), 0)

    def test_text_query_structure(self):
        q = build_search_query("vintage denim")
        # Should contain ai_title, raw_note, ai_description unaccent_icontains lookups
        self.assertTrue(any("ai_title__unaccent_icontains" in str(child) for child in q.children))
        self.assertTrue(any("raw_note__unaccent_icontains" in str(child) for child in q.children))
        self.assertTrue(any("ai_description__unaccent_icontains" in str(child) for child in q.children))

    def test_iso_date_query_structure(self):
        q = build_search_query("2026-10-10")
        q_str = str(q)
        self.assertIn("created_at__date", q_str)
        self.assertIn("sold_at__date", q_str)

    def test_slashed_date_query_structure(self):
        q = build_search_query("10/10/2026")
        q_str = str(q)
        self.assertIn("created_at__date", q_str)
        self.assertIn("sold_at__date", q_str)

    def test_year_month_query_structure(self):
        q = build_search_query("2026-10")
        q_str = str(q)
        self.assertIn("created_at__year", q_str)
        self.assertIn("created_at__month", q_str)

    def test_four_digit_year_query_structure(self):
        q = build_search_query("2026")
        q_str = str(q)
        self.assertIn("created_at__year", q_str)


class DashboardPaginationAndSearchTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.manager_group, _ = Group.objects.get_or_create(name=ROLE_MANAGER)
        self.asst_group, _ = Group.objects.get_or_create(name=ROLE_ASSISTANT)

        self.manager = User.objects.create_user(
            username="manager_user", password="password123", is_staff=True
        )
        self.manager.groups.add(self.manager_group)

        self.dashboard_url = reverse("inventory:dashboard")
        self.client.login(username="manager_user", password="password123")

    def test_pagination_caps_at_20_items_per_page(self):
        # Create 45 products
        products = [
            Product(raw_note=f"Item {i}", sale_price=Decimal("15.00"))
            for i in range(1, 46)
        ]
        Product.objects.bulk_create(products)

        # Page 1
        resp = self.client.get(self.dashboard_url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context["products"]), 20)
        self.assertEqual(resp.context["page_obj"].number, 1)
        self.assertEqual(resp.context["paginator"].num_pages, 3)
        self.assertTrue(resp.context["page_obj"].has_next())
        self.assertFalse(resp.context["page_obj"].has_previous())

        # Page 2
        resp2 = self.client.get(self.dashboard_url, {"page": "2"})
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(len(resp2.context["products"]), 20)
        self.assertEqual(resp2.context["page_obj"].number, 2)
        self.assertTrue(resp2.context["page_obj"].has_next())
        self.assertTrue(resp2.context["page_obj"].has_previous())

        # Page 3
        resp3 = self.client.get(self.dashboard_url, {"page": "3"})
        self.assertEqual(resp3.status_code, 200)
        self.assertEqual(len(resp3.context["products"]), 5)
        self.assertEqual(resp3.context["page_obj"].number, 3)
        self.assertFalse(resp3.context["page_obj"].has_next())
        self.assertTrue(resp3.context["page_obj"].has_previous())

    def test_invalid_page_handles_gracefully(self):
        Product.objects.bulk_create([
            Product(raw_note=f"Item {i}") for i in range(1, 25)
        ])

        # Non-integer page returns first page
        resp_abc = self.client.get(self.dashboard_url, {"page": "invalid_page"})
        self.assertEqual(resp_abc.status_code, 200)
        self.assertEqual(resp_abc.context["page_obj"].number, 1)

        # Out of bounds page returns last page
        resp_999 = self.client.get(self.dashboard_url, {"page": "999"})
        self.assertEqual(resp_999.status_code, 200)
        self.assertEqual(resp_999.context["page_obj"].number, 2)

    def test_query_string_preserved_in_pagination(self):
        # Create 25 products with 'jacket'
        Product.objects.bulk_create([
            Product(raw_note=f"Leather jacket {i}", is_sold=False) for i in range(1, 26)
        ])

        resp = self.client.get(self.dashboard_url, {"q": "jacket", "status": "active", "page": "1"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("status=active", resp.context["query_string"])
        self.assertIn("q=jacket", resp.context["query_string"])
        self.assertNotIn("page=", resp.context["query_string"])

        # Check pagination links in HTML output
        content = resp.content.decode("utf-8")
        self.assertIn("page=2", content)
        self.assertIn("q=jacket", content)
        self.assertIn("status=active", content)

    def test_search_by_title_description_and_notes(self):
        p1 = Product.objects.create(ai_title="Vintage Carhartt Chore Coat", raw_note="heavy canvas")
        p2 = Product.objects.create(ai_title="Levis Denim Pants", ai_description="Stone washed 501 jeans")
        p3 = Product.objects.create(raw_note="Woolrich flannel shirt with plaid pattern")

        # Search title
        resp = self.client.get(self.dashboard_url, {"q": "Carhartt"})
        p_ids = [p.id for p in resp.context["products"]]
        self.assertIn(p1.id, p_ids)
        self.assertNotIn(p2.id, p_ids)
        self.assertNotIn(p3.id, p_ids)

        # Search description
        resp2 = self.client.get(self.dashboard_url, {"q": "Stone washed"})
        p_ids2 = [p.id for p in resp2.context["products"]]
        self.assertIn(p2.id, p_ids2)
        self.assertNotIn(p1.id, p_ids2)

        # Search raw note
        resp3 = self.client.get(self.dashboard_url, {"q": "Woolrich"})
        p_ids3 = [p.id for p in resp3.context["products"]]
        self.assertIn(p3.id, p_ids3)
        self.assertNotIn(p1.id, p_ids3)

    def test_search_by_date(self):
        p_today = Product.objects.create(raw_note="Cataloged today")
        p_target = Product.objects.create(raw_note="Cataloged on specific date")

        # Update created_at directly in DB to bypass auto_now_add
        target_datetime = timezone.make_aware(datetime.datetime(2026, 5, 20, 14, 30))
        Product.objects.filter(id=p_target.id).update(created_at=target_datetime)

        # Search by exact ISO date
        resp_iso = self.client.get(self.dashboard_url, {"q": "2026-05-20"})
        p_ids = [p.id for p in resp_iso.context["products"]]
        self.assertIn(p_target.id, p_ids)
        self.assertNotIn(p_today.id, p_ids)

        # Search by EU slashed date
        resp_eu = self.client.get(self.dashboard_url, {"q": "20/05/2026"})
        p_ids_eu = [p.id for p in resp_eu.context["products"]]
        self.assertIn(p_target.id, p_ids_eu)
        self.assertNotIn(p_today.id, p_ids_eu)

        # Search by Year-Month
        resp_ym = self.client.get(self.dashboard_url, {"q": "2026-05"})
        p_ids_ym = [p.id for p in resp_ym.context["products"]]
        self.assertIn(p_target.id, p_ids_ym)
        self.assertNotIn(p_today.id, p_ids_ym)

    def test_pagination_spanish_localization(self):
        Product.objects.bulk_create([
            Product(raw_note=f"Item {i}") for i in range(1, 25)
        ])

        resp = self.client.get(self.dashboard_url, HTTP_ACCEPT_LANGUAGE="es")
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")

        self.assertIn("Mostrando", content)
        self.assertIn("productos", content)
        self.assertIn("Siguiente", content)
        self.assertIn("Anterior", content)
        self.assertIn("Buscar título, nota o fecha", content)

    def test_intake_recent_uploads_remain_unpaginated(self):
        # Sourcing assistant intake view
        asst = User.objects.create_user(username="asst_user", password="password123")
        asst.groups.add(self.asst_group)
        self.client.login(username="asst_user", password="password123")

        # Create 10 items by assistant
        for i in range(10):
            Product.objects.create(raw_note=f"Upload {i}", created_by=asst)

        resp = self.client.get(reverse("inventory:intake"))
        self.assertEqual(resp.status_code, 200)
        # Should strictly show recent 5 items, not paginated
        self.assertEqual(len(resp.context["recent_products"]), 5)

    def test_page_size_selector_20_50_100(self):
        Product.objects.bulk_create([Product(raw_note=f"Batch Item {i}") for i in range(1, 106)])

        # Default 20 items across 6 pages
        resp_default = self.client.get(self.dashboard_url)
        self.assertEqual(resp_default.status_code, 200)
        self.assertEqual(resp_default.context["per_page"], 20)
        self.assertEqual(len(resp_default.context["products"]), 20)
        self.assertEqual(resp_default.context["paginator"].num_pages, 6)
        self.assertContains(resp_default, 'id="dashboardResultsBar"')
        self.assertContains(resp_default, 'id="perPageSelector"')
        self.assertContains(resp_default, 'href="?per_page=20"')
        self.assertContains(resp_default, 'href="?per_page=50"')
        self.assertContains(resp_default, 'href="?per_page=100"')

        # Switch to 50 items across 3 pages
        resp_50 = self.client.get(self.dashboard_url, {"per_page": "50"})
        self.assertEqual(resp_50.status_code, 200)
        self.assertEqual(resp_50.context["per_page"], 50)
        self.assertEqual(len(resp_50.context["products"]), 50)
        self.assertEqual(resp_50.context["paginator"].num_pages, 3)
        resp_50_p3 = self.client.get(self.dashboard_url, {"per_page": "50", "page": "3"})
        self.assertEqual(len(resp_50_p3.context["products"]), 5)

        # Switch to 100 items across 2 pages
        resp_100 = self.client.get(self.dashboard_url, {"per_page": "100"})
        self.assertEqual(resp_100.status_code, 200)
        self.assertEqual(resp_100.context["per_page"], 100)
        self.assertEqual(len(resp_100.context["products"]), 100)
        self.assertEqual(resp_100.context["paginator"].num_pages, 2)
        resp_100_p2 = self.client.get(self.dashboard_url, {"per_page": "100", "page": "2"})
        self.assertEqual(len(resp_100_p2.context["products"]), 5)

    def test_page_size_session_persistence_and_reset_to_20(self):
        Product.objects.bulk_create([Product(raw_note=f"Session Item {i}") for i in range(1, 61)])

        # Select 50 items per page
        resp_50 = self.client.get(self.dashboard_url, {"per_page": "50"})
        self.assertEqual(len(resp_50.context["products"]), 50)
        self.assertEqual(self.client.session.get("dashboard_per_page"), 50)

        # Returning to /dashboard/ without per_page remembers 50
        resp_remembered = self.client.get(self.dashboard_url)
        self.assertEqual(resp_remembered.context["per_page"], 50)
        self.assertEqual(len(resp_remembered.context["products"]), 50)

        # Clicking 20 explicitly resets session preference back to 20
        resp_20 = self.client.get(self.dashboard_url, {"per_page": "20"})
        self.assertEqual(resp_20.context["per_page"], 20)
        self.assertEqual(len(resp_20.context["products"]), 20)
        self.assertEqual(self.client.session.get("dashboard_per_page"), 20)

        resp_after_reset = self.client.get(self.dashboard_url)
        self.assertEqual(resp_after_reset.context["per_page"], 20)
        self.assertEqual(len(resp_after_reset.context["products"]), 20)

    def test_invalid_page_size_falls_back_cleanly_without_propagating(self):
        Product.objects.bulk_create([Product(raw_note=f"Invalid Param Item {i}") for i in range(1, 61)])

        for bad_value in ("abc", "0", "-10", "999"):
            resp = self.client.get(self.dashboard_url, {"per_page": bad_value})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.context["per_page"], 20)
            self.assertEqual(len(resp.context["products"]), 20)
            self.assertNotIn("per_page=", resp.context["query_string"])
            self.assertNotIn(bad_value, resp.context["query_string"])

        # When session already holds 50, invalid query value keeps 50 and does not overwrite session
        self.client.get(self.dashboard_url, {"per_page": "50"})
        resp_bad_with_session = self.client.get(self.dashboard_url, {"per_page": "999"})
        self.assertEqual(resp_bad_with_session.status_code, 200)
        self.assertEqual(resp_bad_with_session.context["per_page"], 50)
        self.assertEqual(self.client.session.get("dashboard_per_page"), 50)
        self.assertIn("per_page=50", resp_bad_with_session.context["query_string"])
        self.assertNotIn("999", resp_bad_with_session.context["query_string"])

    def test_page_size_preserves_filters_resets_page_and_survives_clear_filters(self):
        Product.objects.bulk_create(
            [
                Product(
                    ai_title=f"Ready Jacket {i}",
                    ai_description="Staged description ready for listing.",
                    raw_note="jacket",
                    sale_price=Decimal("35.00"),
                    status=ProductStatus.READY,
                    is_sold=False,
                )
                for i in range(1, 26)
            ]
        )

        # Non-default per_page alone should NOT render "Clear filters"
        resp_only_per_page = self.client.get(self.dashboard_url, {"per_page": "50"})
        self.assertNotContains(resp_only_per_page, "Clear filters")

        # Active filters + page=2 + per_page=50: base_query preserves status & q while resetting page
        resp_filtered = self.client.get(
            self.dashboard_url,
            {"status": "ready", "q": "jacket", "page": "2", "per_page": "50"},
        )
        self.assertEqual(resp_filtered.status_code, 200)
        base_q = resp_filtered.context["per_page_base_query"]
        self.assertIn("status=ready", base_q)
        self.assertIn("q=jacket", base_q)
        self.assertNotIn("page=", base_q)
        self.assertNotIn("per_page=", base_q)
        content = resp_filtered.content.decode("utf-8")
        self.assertIn('href="?status=ready&per_page=50"', content)
        self.assertIn('<input type="hidden" name="per_page" value="50">', content)

    def test_results_bar_visible_on_single_page_and_hidden_when_empty(self):
        # Empty catalog hides the results bar
        resp_empty = self.client.get(self.dashboard_url)
        self.assertEqual(resp_empty.status_code, 200)
        self.assertNotContains(resp_empty, 'id="dashboardResultsBar"')

        # 35 items at 50/page fits on 1 page -> results bar stays visible, bottom pagination omitted
        Product.objects.bulk_create([Product(raw_note=f"Single Page Item {i}") for i in range(1, 36)])
        resp_single = self.client.get(self.dashboard_url, {"per_page": "50"})
        self.assertEqual(resp_single.status_code, 200)
        self.assertFalse(resp_single.context["page_obj"].has_other_pages())
        self.assertContains(resp_single, 'id="dashboardResultsBar"')
        self.assertContains(resp_single, 'id="perPageSelector"')
        self.assertNotContains(resp_single, 'aria-label="Pagination"')

    def test_assistant_can_use_page_size_selector(self):
        asst = User.objects.create_user(username="asst_paginator", password="password123")
        asst.groups.add(self.asst_group)
        self.client.force_login(asst)
        Product.objects.bulk_create([Product(raw_note=f"Asst Item {i}", created_by=asst) for i in range(1, 56)])

        resp = self.client.get(self.dashboard_url, {"per_page": "50"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["per_page"], 50)
        self.assertEqual(len(resp.context["products"]), 50)

        resp_next = self.client.get(self.dashboard_url)
        self.assertEqual(resp_next.context["per_page"], 50)
        self.assertEqual(len(resp_next.context["products"]), 50)

    def test_dashboard_constant_query_count_and_lazy_images_across_20_and_100_products(self):
        products = Product.objects.bulk_create(
            [Product(ai_title=f"Perf Item {i}", sale_price=Decimal("25.00")) for i in range(1, 101)]
        )
        ProductImage.objects.bulk_create(
            [
                ProductImage(product=p, image=f"products/2026/11/item_{p.pk}_{idx}.webp", order=idx)
                for p in products
                for idx in (0, 1)
            ]
        )

        # Warm session & baseline query count for 20 products
        self.client.get(self.dashboard_url, {"per_page": "20"})
        with CaptureQueriesContext(connection) as ctx_20:
            resp_20 = self.client.get(self.dashboard_url, {"per_page": "20"})
        self.assertEqual(resp_20.status_code, 200)
        self.assertEqual(len(resp_20.context["products"]), 20)

        # Measure query count for 100 products with 2 images each
        self.client.get(self.dashboard_url, {"per_page": "100"})
        with CaptureQueriesContext(connection) as ctx_100:
            resp_100 = self.client.get(self.dashboard_url, {"per_page": "100"})
        self.assertEqual(resp_100.status_code, 200)
        self.assertEqual(len(resp_100.context["products"]), 100)
        self.assertEqual(
            len(ctx_100),
            len(ctx_20),
            f"Expected constant O(1) SQL queries across 20 and 100 products, got {len(ctx_20)} vs {len(ctx_100)}",
        )

        # Verify LCP image priority (card 1) and lazy-loading (cards 5..100)
        html = resp_100.content.decode("utf-8")
        self.assertEqual(html.count('fetchpriority="high"'), 1)
        self.assertEqual(html.count('loading="lazy"'), 96)
        self.assertEqual(html.count('decoding="async"'), 100)

    def test_page_size_selector_spanish_localization(self):
        Product.objects.create(raw_note="Artículo de prueba")
        resp = self.client.get(self.dashboard_url, HTTP_ACCEPT_LANGUAGE="es")
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self.assertIn("Mostrando", content)
        self.assertIn("Por página:", content)
        self.assertIn('aria-label="Productos por página"', content)
        self.assertIn('aria-label="Mostrar 50 productos por página"', content)

    def test_public_storefront_keeps_fixed_20_page_size(self):
        Product.objects.bulk_create(
            [
                Product(
                    ai_title=f"Public Outlet Product {i}",
                    ai_description="Public storefront item description.",
                    sale_price=Decimal("19.90"),
                    status=ProductStatus.READY,
                    is_public=True,
                    is_sold=False,
                )
                for i in range(1, 26)
            ]
        )
        resp = self.client.get(reverse("storefront:catalog"), {"per_page": "100"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context["products"]), 20)
