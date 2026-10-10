from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from inventory.models import Product
from inventory.permissions import ROLE_ASSISTANT

User = get_user_model()


class GenerateAIViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.manager = User.objects.create_user(username="manager_ai", password="password123", is_staff=True)
        self.assistant = User.objects.create_user(username="asst_ai", password="password123")
        asst_group = Group.objects.create(name=ROLE_ASSISTANT)
        self.assistant.groups.add(asst_group)

        self.product = Product.objects.create(
            raw_note="Vintage 90s Carhartt jacket dark brown",
            created_by=self.assistant
        )
        self.ai_url = reverse("inventory:generate_ai", kwargs={"pk": self.product.pk})

    @patch("inventory.services.ai_service.generate_product_listing")
    def test_manager_can_trigger_ai_generation(self, mock_generate):
        mock_generate.return_value = {
            "title": "Vintage 1990s Carhartt Detroit Jacket - Dark Brown",
            "description": "• Heavyweight canvas\n• Authentic workwear patina\n• Clean lining"
        }

        self.client.login(username="manager_ai", password="password123")
        resp = self.client.post(self.ai_url)

        self.assertRedirects(resp, reverse("inventory:product_detail", kwargs={"pk": self.product.pk}))
        self.product.refresh_from_db()
        self.assertEqual(self.product.ai_title, "Vintage 1990s Carhartt Detroit Jacket - Dark Brown")
        self.assertEqual(self.product.ai_description, "• Heavyweight canvas\n• Authentic workwear patina\n• Clean lining")
        # Ensure raw_note is strictly preserved!
        self.assertEqual(self.product.raw_note, "Vintage 90s Carhartt jacket dark brown")

    def test_assistant_cannot_trigger_ai(self):
        self.client.login(username="asst_ai", password="password123")
        # Expect permission denied (HTTP 403)
        resp = self.client.post(self.ai_url)
        self.assertEqual(resp.status_code, 403)

    def test_get_request_redirects_to_detail(self):
        self.client.login(username="manager_ai", password="password123")
        resp = self.client.get(self.ai_url)
        self.assertRedirects(resp, reverse("inventory:product_detail", kwargs={"pk": self.product.pk}))
