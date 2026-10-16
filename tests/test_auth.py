from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from inventory.permissions import (
    ROLE_ASSISTANT,
    ROLE_MANAGER,
    is_assistant,
    is_manager,
    manager_required,
)

User = get_user_model()


class AuthAndPermissionsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.assistant_group, _ = Group.objects.get_or_create(name=ROLE_ASSISTANT)
        self.manager_group, _ = Group.objects.get_or_create(name=ROLE_MANAGER)

        self.assistant_user = User.objects.create_user(
            username="assistant_joe", password="password123"
        )
        self.assistant_user.groups.add(self.assistant_group)

        self.manager_user = User.objects.create_user(
            username="manager_mary", password="password123", is_staff=True
        )

        self.regular_user = User.objects.create_user(
            username="regular_bob", password="password123"
        )

    def test_permission_helpers(self):
        self.assertTrue(is_assistant(self.assistant_user))
        self.assertFalse(is_manager(self.assistant_user))

        self.assertTrue(is_manager(self.manager_user))
        self.assertFalse(is_assistant(self.manager_user))

        self.assertFalse(is_manager(self.regular_user))
        self.assertFalse(is_assistant(self.regular_user))

    def test_manager_required_decorator(self):
        @manager_required
        def dummy_manager_view(request):
            return HttpResponse("Authorized")

        class DummyRequest:
            def __init__(self, user):
                self.user = user

        # Assistant should be denied
        with self.assertRaises(PermissionDenied):
            dummy_manager_view(DummyRequest(self.assistant_user))

        # Manager should succeed
        resp = dummy_manager_view(DummyRequest(self.manager_user))
        self.assertEqual(resp.status_code, 200)

    def test_root_redirect_unauthenticated(self):
        response = self.client.get(reverse("inventory:root"))
        self.assertRedirects(response, reverse("inventory:login"))

    def test_root_redirect_assistant(self):
        self.client.login(username="assistant_joe", password="password123")
        response = self.client.get(reverse("inventory:root"))
        self.assertRedirects(response, reverse("inventory:intake"))

    def test_root_redirect_manager(self):
        self.client.login(username="manager_mary", password="password123")
        response = self.client.get(reverse("inventory:root"))
        self.assertRedirects(response, reverse("inventory:dashboard"))

    @override_settings(TURNSTILE_ENABLED=False)
    def test_login_flow(self):
        response = self.client.post(
            reverse("inventory:login"),
            {"username": "assistant_joe", "password": "password123"}
        )
        self.assertRedirects(response, reverse("inventory:intake"))
