from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from inventory.models import Product
from inventory.permissions import ROLE_ASSISTANT, ROLE_MANAGER

User = get_user_model()


class AdminAccessAndUserManagementTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.mgr_group, _ = Group.objects.get_or_create(name=ROLE_MANAGER)
        self.asst_group, _ = Group.objects.get_or_create(name=ROLE_ASSISTANT)

        # Superuser
        self.superuser = User.objects.create_superuser(
            username="super_admin", password="password123", email="super@example.com"
        )

        # Manager user
        self.manager = User.objects.create_user(
            username="shop_manager", password="password123", email="manager@example.com", is_staff=True
        )
        self.manager.groups.add(self.mgr_group)

        # Assistant user
        self.assistant = User.objects.create_user(
            username="intake_asst", password="password123", email="asst@example.com", is_staff=False
        )
        self.assistant.groups.add(self.asst_group)

        self.admin_url = reverse("admin:index")
        self.user_changelist_url = reverse("admin:auth_user_changelist")

    def test_manager_can_access_admin_portal(self):
        self.client.login(username="shop_manager", password="password123")
        resp = self.client.get(self.admin_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "2ndHand Staging")

    def test_superuser_can_access_admin_portal(self):
        self.client.login(username="super_admin", password="password123")
        resp = self.client.get(self.admin_url)
        self.assertEqual(resp.status_code, 200)

    def test_assistant_strictly_forbidden_from_admin_portal(self):
        self.client.login(username="intake_asst", password="password123")
        # Direct hit to /admin/ index
        resp = self.client.get(self.admin_url)
        self.assertEqual(resp.status_code, 403)

        # Direct hit to /admin/auth/user/
        resp_users = self.client.get(self.user_changelist_url)
        self.assertEqual(resp_users.status_code, 403)

    def test_anonymous_user_redirected_to_admin_login(self):
        resp = self.client.get(self.admin_url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/admin/login/", resp.url)

    def test_custom_user_admin_role_badges_and_catalog_counts(self):
        # Create products attributed to assistant
        for i in range(3):
            Product.objects.create(
                raw_note=f"Item {i}",
                sale_price=Decimal("20.00"),
                created_by=self.assistant
            )

        self.client.login(username="shop_manager", password="password123")
        resp = self.client.get(self.user_changelist_url)
        self.assertEqual(resp.status_code, 200)

        content = resp.content.decode("utf-8")
        # Check role badges rendered
        self.assertIn("Manager", content)
        self.assertIn("Assistant", content)
        self.assertIn("Superuser", content)

        # Check cataloged item count rendered for assistant
        self.assertIn(f"created_by__id__exact={self.assistant.id}", content)

    def test_role_list_filter(self):
        self.client.login(username="shop_manager", password="password123")

        # Filter Assistants
        resp_asst = self.client.get(self.user_changelist_url, {"role": "assistant"})
        self.assertEqual(resp_asst.status_code, 200)
        users = list(resp_asst.context["cl"].result_list)
        self.assertIn(self.assistant, users)
        self.assertNotIn(self.manager, users)
        self.assertNotIn(self.superuser, users)

        # Filter Managers
        resp_mgr = self.client.get(self.user_changelist_url, {"role": "manager"})
        self.assertEqual(resp_mgr.status_code, 200)
        users_mgr = list(resp_mgr.context["cl"].result_list)
        self.assertIn(self.manager, users_mgr)
        self.assertNotIn(self.assistant, users_mgr)

    def test_make_assistant_action(self):
        # Create a new staff user to convert to assistant
        user = User.objects.create_user(username="temp_staff", password="password123", is_staff=True)
        user.groups.add(self.mgr_group)

        self.client.login(username="super_admin", password="password123")
        post_data = {
            "action": "make_assistant",
            "_selected_action": [user.pk],
        }
        resp = self.client.post(self.user_changelist_url, post_data)
        self.assertEqual(resp.status_code, 302)

        user.refresh_from_db()
        self.assertFalse(user.is_staff)
        self.assertTrue(user.groups.filter(name=ROLE_ASSISTANT).exists())
        self.assertFalse(user.groups.filter(name=ROLE_MANAGER).exists())

    def test_make_manager_action(self):
        self.client.login(username="super_admin", password="password123")
        post_data = {
            "action": "make_manager",
            "_selected_action": [self.assistant.pk],
        }
        resp = self.client.post(self.user_changelist_url, post_data)
        self.assertEqual(resp.status_code, 302)

        self.assistant.refresh_from_db()
        self.assertTrue(self.assistant.is_staff)
        self.assertTrue(self.assistant.groups.filter(name=ROLE_MANAGER).exists())

    def test_deactivate_users_action_and_product_attribution_preservation(self):
        # Assistant catalogs product
        prod = Product.objects.create(raw_note="Vintage Jacket", created_by=self.assistant)

        self.client.login(username="shop_manager", password="password123")
        post_data = {
            "action": "deactivate_users",
            "_selected_action": [self.assistant.pk],
        }
        resp = self.client.post(self.user_changelist_url, post_data)
        self.assertEqual(resp.status_code, 302)

        self.assistant.refresh_from_db()
        self.assertFalse(self.assistant.is_active)

        # Attribution remains intact!
        prod.refresh_from_db()
        self.assertEqual(prod.created_by, self.assistant)

    def test_admin_spanish_localization(self):
        self.client.login(username="shop_manager", password="password123")
        resp = self.client.get(self.admin_url, HTTP_ACCEPT_LANGUAGE="es")
        self.assertEqual(resp.status_code, 200)

        content = resp.content.decode("utf-8")
        self.assertIn("Administración", content)
