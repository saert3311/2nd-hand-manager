import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from inventory.models import Product
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
        # Should contain ai_title, raw_note, ai_description lookups
        self.assertTrue(any("ai_title__icontains" in str(child) for child in q.children))
        self.assertTrue(any("raw_note__icontains" in str(child) for child in q.children))
        self.assertTrue(any("ai_description__icontains" in str(child) for child in q.children))

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
