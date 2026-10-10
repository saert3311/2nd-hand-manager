from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from inventory.models import Product

User = get_user_model()


class DashboardViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testmanager", password="password123")
        self.url = reverse("inventory:dashboard")

        # Create sample products
        self.p1 = Product.objects.create(
            raw_note="Sony headphones wireless black",
            ai_title="Sony WH-1000XM4 Wireless Headphones",
            sale_price=Decimal("150.00"),
            is_sold=False
        )
        self.p2 = Product.objects.create(
            raw_note="Vintage trench coat beige",
            ai_title="Burberry Beige Trench Coat",
            sale_price=Decimal("220.00"),
            is_sold=True
        )
        self.p3 = Product.objects.create(
            raw_note="Leather boots size 42",
            is_sold=False
        )

    def test_dashboard_requires_login(self):
        resp = self.client.get(self.url)
        self.assertRedirects(resp, f"{reverse('inventory:login')}?next={self.url}")

    def test_dashboard_all_filter(self):
        self.client.login(username="testmanager", password="password123")
        resp = self.client.get(self.url, {"status": "all"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context["products"]), 3)
        self.assertEqual(resp.context["total_count"], 3)
        self.assertEqual(resp.context["active_count"], 2)
        self.assertEqual(resp.context["sold_count"], 1)

    def test_dashboard_active_filter(self):
        self.client.login(username="testmanager", password="password123")
        resp = self.client.get(self.url, {"status": "active"})
        self.assertEqual(resp.status_code, 200)
        products = list(resp.context["products"])
        self.assertEqual(len(products), 2)
        self.assertIn(self.p1, products)
        self.assertIn(self.p3, products)
        self.assertNotIn(self.p2, products)

    def test_dashboard_sold_filter(self):
        self.client.login(username="testmanager", password="password123")
        resp = self.client.get(self.url, {"status": "sold"})
        self.assertEqual(resp.status_code, 200)
        products = list(resp.context["products"])
        self.assertEqual(len(products), 1)
        self.assertIn(self.p2, products)

    def test_dashboard_search_query(self):
        self.client.login(username="testmanager", password="password123")
        resp = self.client.get(self.url, {"q": "Burberry"})
        self.assertEqual(resp.status_code, 200)
        products = list(resp.context["products"])
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0], self.p2)

        resp2 = self.client.get(self.url, {"q": "headphones"})
        self.assertEqual(len(resp2.context["products"]), 1)
        self.assertEqual(resp2.context["products"][0], self.p1)
