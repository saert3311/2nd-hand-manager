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
            ai_description="Premium wireless noise cancelling headphones.",
            sale_price=Decimal("150.00"),
            is_sold=False,
        )
        self.p2 = Product.objects.create(
            raw_note="Vintage trench coat beige",
            ai_title="Burberry Beige Trench Coat",
            ai_description="Classic trench coat in good vintage condition.",
            sale_price=Decimal("220.00"),
            is_sold=True,
        )
        self.p3 = Product.objects.create(
            raw_note="Leather boots size 42",
            is_sold=False,
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
        self.assertEqual(resp.context["ready_count"], 1)
        self.assertEqual(resp.context["active_count"], 2)
        self.assertEqual(resp.context["sold_count"], 1)

    def test_dashboard_ready_filter(self):
        self.client.login(username="testmanager", password="password123")
        resp = self.client.get(self.url, {"status": "ready"})
        self.assertEqual(resp.status_code, 200)
        products = list(resp.context["products"])
        self.assertEqual(len(products), 1)
        self.assertIn(self.p1, products)
        self.assertNotIn(self.p2, products)
        self.assertNotIn(self.p3, products)
        self.assertContains(resp, "Ready to Publish")
        self.assertContains(resp, "(1)")

    def test_dashboard_active_filter(self):
        self.client.login(username="testmanager", password="password123")
        resp = self.client.get(self.url, {"status": "active"})
        self.assertEqual(resp.status_code, 200)
        products = list(resp.context["products"])
        self.assertEqual(len(products), 2)
        self.assertIn(self.p1, products)
        self.assertIn(self.p3, products)
        self.assertNotIn(self.p2, products)

    def test_dashboard_ready_tab_spanish_localization(self):
        self.client.login(username="testmanager", password="password123")
        resp = self.client.get(self.url, {"status": "ready"}, HTTP_ACCEPT_LANGUAGE="es")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Listo para Publicar")

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

    def test_dashboard_price_pending_filter_and_count(self):
        self.client.login(username="testmanager", password="password123")
        # Product with title and description, but no price -> PRICE_PENDING
        p_pending = Product.objects.create(
            raw_note="Denim jacket vintage",
            ai_title="Levi's Vintage Denim Jacket",
            ai_description="Classic blue denim jacket in good vintage condition.",
            sale_price=None,
        )
        self.assertEqual(p_pending.status, "price_pending")

        resp = self.client.get(self.url, {"status": "price_pending"})
        self.assertEqual(resp.status_code, 200)
        products = list(resp.context["products"])
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0], p_pending)
        self.assertEqual(resp.context["price_pending_count"], 1)
        self.assertContains(resp, "Price Pending")
        self.assertContains(resp, "(1)")

    def test_product_detail_renders_price_pending_badge(self):
        self.client.login(username="testmanager", password="password123")
        p_pending = Product.objects.create(
            raw_note="Vintage watch",
            ai_title="Omega Seamaster Vintage Watch",
            ai_description="Authentic automatic movement, light cosmetic wear.",
            sale_price=Decimal("0.00"),
        )
        self.assertEqual(p_pending.status, "price_pending")

        resp = self.client.get(reverse("inventory:product_detail", kwargs={"pk": p_pending.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "product-status-badge")
        self.assertContains(resp, "Price Pending")
