import io
import json
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from PIL import Image
from pywebpush import WebPushException

from inventory.admin import PushSubscriptionAdmin, manager_admin_site
from inventory.management.commands.generate_vapid_keys import generate_vapid_keypair
from inventory.models import (
    ClarificationCategory,
    Product,
    ProductClarification,
    ProductStatus,
    PushSubscription,
)
from inventory.permissions import ROLE_ASSISTANT, ROLE_MANAGER
from inventory.services.push_service import (
    is_push_configured,
    send_push_to_group,
    send_push_to_subscription,
    send_push_to_user,
)
from tests.helpers import goto_authenticated, login_in_browser, open_browser_page, start_shared_browser

User = get_user_model()


class PWAManifestAndServiceWorkerTests(TestCase):
    def setUp(self):
        self.assistant_group, _ = Group.objects.get_or_create(name=ROLE_ASSISTANT)
        self.manager_group, _ = Group.objects.get_or_create(name=ROLE_MANAGER)

        self.user = User.objects.create_user(username="assistant_pwa", password="password123")
        self.user.groups.add(self.assistant_group)

        self.manager = User.objects.create_user(
            username="manager_pwa", password="password123", is_staff=True
        )
        self.manager.groups.add(self.manager_group)

    def test_manifest_json_endpoint(self):
        response = self.client.get(reverse("inventory:manifest"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/manifest+json")

        data = json.loads(response.content.decode("utf-8"))
        self.assertEqual(data["id"], "/dashboard/")
        self.assertEqual(data["short_name"], "2ndHand")
        self.assertEqual(data["display"], "standalone")
        self.assertEqual(data["scope"], "/")
        self.assertEqual(data["start_url"], "/dashboard/")
        self.assertEqual(data["theme_color"], "#059669")
        self.assertGreaterEqual(len(data["icons"]), 4)
        purposes = {icon["purpose"] for icon in data["icons"]}
        self.assertIn("any", purposes)
        self.assertIn("maskable", purposes)
        self.assertGreaterEqual(len(data["shortcuts"]), 3)

    def test_service_worker_endpoint_headers_and_content(self):
        response = self.client.get(reverse("inventory:service_worker"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/javascript", response["Content-Type"])
        self.assertEqual(response["Service-Worker-Allowed"], "/")
        self.assertEqual(response["Cache-Control"], "no-cache, no-store, must-revalidate")

        body = response.content.decode("utf-8")
        self.assertIn("self.addEventListener('fetch'", body)
        self.assertIn("self.addEventListener('push'", body)
        self.assertIn("self.addEventListener('notificationclick'", body)
        self.assertIn("self.registration.showNotification", body)
        self.assertIn("url: '/dashboard/'", body)
        self.assertIn("payload.url || '/dashboard/'", body)
        self.assertIn(": '/dashboard/';", body)
        self.assertNotIn("url: '/'", body)

    def test_manifest_and_service_worker_execute_zero_db_queries(self):
        self.client.force_login(self.manager)
        with self.assertNumQueries(0):
            manifest_resp = self.client.get(reverse("inventory:manifest"))
        self.assertEqual(manifest_resp.status_code, 200)
        with self.assertNumQueries(0):
            sw_resp = self.client.get(reverse("inventory:service_worker"))
        self.assertEqual(sw_resp.status_code, 200)

    def test_pwa_static_icons_exist_and_dimensions(self):
        icons_dir = Path(settings.BASE_DIR) / "inventory" / "static" / "inventory" / "icons"
        expected = {
            "icon-192.png": (192, 192),
            "icon-512.png": (512, 512),
            "apple-touch-icon.png": (180, 180),
        }
        for filename, dims in expected.items():
            icon_path = icons_dir / filename
            self.assertTrue(icon_path.exists(), f"Missing PWA icon {filename}")
            with Image.open(icon_path) as img:
                self.assertEqual(img.format, "PNG")
                self.assertEqual(img.size, dims)

    def test_dashboard_renders_pwa_manifest_for_manager_and_assistant(self):
        storefront_href = reverse("storefront:catalog")
        for account in (self.manager, self.user):
            self.client.force_login(account)
            response = self.client.get(reverse("inventory:dashboard"))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, '<link rel="manifest" href="/manifest.json">')
            self.assertContains(response, '<meta name="apple-mobile-web-app-capable" content="yes">')
            self.assertContains(response, 'name="theme-color" content="#059669"')
            self.assertContains(response, "apple-touch-icon.png")
            self.assertContains(response, "navigator.serviceWorker.register")
            self.assertContains(response, 'id="push-toggle-btn"')
            self.assertContains(response, 'id="mobile-push-toggle-btn"')

            html = response.content.decode("utf-8")
            storefront_anchors = re.findall(
                rf'<a[^>]*href="{re.escape(storefront_href)}"[^>]*>',
                html,
                flags=re.DOTALL,
            )
            self.assertEqual(len(storefront_anchors), 2)
            for anchor in storefront_anchors:
                self.assertIn('target="_blank"', anchor)
                self.assertIn('rel="noopener noreferrer"', anchor)

    def test_non_dashboard_backend_pages_omit_manifest_but_keep_service_worker(self):
        product = Product.objects.create(
            raw_note="PWA non-dashboard check",
            ai_title="Vintage Lamp",
            created_by=self.user,
        )
        targets = [
            (self.user, reverse("inventory:intake")),
            (self.user, reverse("inventory:product_detail", kwargs={"pk": product.pk})),
            (self.manager, reverse("inventory:intake")),
            (self.manager, reverse("inventory:product_detail", kwargs={"pk": product.pk})),
            (self.manager, reverse("inventory:pallets")),
        ]
        for account, url in targets:
            self.client.force_login(account)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, 'rel="manifest"')
            self.assertNotContains(response, "apple-mobile-web-app-capable")
            self.assertContains(response, 'name="theme-color" content="#059669"')
            self.assertContains(response, "apple-touch-icon.png")
            self.assertContains(response, "navigator.serviceWorker.register")
            self.assertContains(response, 'id="push-toggle-btn"')
            self.assertContains(response, 'id="mobile-push-toggle-btn"')

    def test_login_page_omits_manifest_and_service_worker(self):
        self.client.logout()
        response = self.client.get(reverse("inventory:login"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'rel="manifest"')
        self.assertNotContains(response, "apple-mobile-web-app-capable")
        self.assertNotContains(response, "navigator.serviceWorker.register")

    def test_public_storefront_omits_manifest_and_service_worker_for_anonymous_and_staff(self):
        public_urls = [
            reverse("storefront:home"),
            reverse("storefront:catalog"),
            reverse("storefront:how_to_buy"),
        ]
        for account in (None, self.manager, self.user):
            if account is None:
                self.client.logout()
            else:
                self.client.force_login(account)
            for url in public_urls:
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, 'rel="manifest"')
                self.assertNotContains(response, "apple-mobile-web-app-capable")
                self.assertNotContains(response, "navigator.serviceWorker.register")
                self.assertNotContains(response, "/manifest.json")
                self.assertNotContains(response, "/sw.js")


class VAPIDCommandAndPushServiceTests(TestCase):
    def setUp(self):
        self.pub_key, self.priv_key = generate_vapid_keypair()
        self.assistant_group, _ = Group.objects.get_or_create(name=ROLE_ASSISTANT)
        self.manager_group, _ = Group.objects.get_or_create(name=ROLE_MANAGER)

        self.assistant = User.objects.create_user(username="asst_push", password="password123")
        self.assistant.groups.add(self.assistant_group)

        self.manager = User.objects.create_user(
            username="mgr_push", password="password123", is_staff=True
        )
        self.manager.groups.add(self.manager_group)

        self.sub_assistant = PushSubscription.objects.create(
            user=self.assistant,
            endpoint="https://fcm.googleapis.com/fcm/send/sub-assistant-1",
            p256dh="BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM",
            auth="tBHItJI5svbpez7KI4CCXg",
            user_agent="Mozilla/5.0 Android",
        )
        self.sub_manager = PushSubscription.objects.create(
            user=self.manager,
            endpoint="https://fcm.googleapis.com/fcm/send/sub-manager-1",
            p256dh="BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM",
            auth="tBHItJI5svbpez7KI4CCXg",
            user_agent="Mozilla/5.0 Desktop",
        )

    def test_generate_vapid_keys_command(self):
        out = io.StringIO()
        call_command("generate_vapid_keys", stdout=out)
        output = out.getvalue()
        self.assertIn("VAPID_PUBLIC_KEY=", output)
        self.assertIn("VAPID_PRIVATE_KEY=", output)
        self.assertIn("VAPID_CLAIMS_EMAIL=", output)
        self.assertEqual(len(self.pub_key), 87)
        self.assertTrue(self.pub_key.startswith("B"))
        self.assertEqual(len(self.priv_key), 43)

    @override_settings(VAPID_PUBLIC_KEY="", VAPID_PRIVATE_KEY="")
    def test_push_skipped_when_vapid_unconfigured(self):
        self.assertFalse(is_push_configured())
        result = send_push_to_subscription(
            self.sub_assistant, title="Test", body="Body", url="/intake/"
        )
        self.assertFalse(result)

    @patch("inventory.services.push_service.webpush")
    def test_send_push_to_user_and_group(self, mock_webpush):
        with override_settings(
            VAPID_PUBLIC_KEY=self.pub_key,
            VAPID_PRIVATE_KEY=self.priv_key,
            VAPID_CLAIMS_EMAIL="mailto:ops@example.com",
        ):
            self.assertTrue(is_push_configured())
            sent = send_push_to_user(
                self.assistant,
                title="Hello Assistant",
                body="Please check item #1",
                url="/products/1/",
                tag="test-tag",
                badge_count=3,
            )
            self.assertEqual(sent, 1)
            mock_webpush.assert_called_once()
            call_kwargs = mock_webpush.call_args.kwargs
            self.assertEqual(
                call_kwargs["subscription_info"]["endpoint"],
                self.sub_assistant.endpoint,
            )
            payload = json.loads(call_kwargs["data"])
            self.assertEqual(payload["title"], "Hello Assistant")
            self.assertEqual(payload["url"], "/products/1/")
            self.assertEqual(payload["badge_count"], 3)

            mock_webpush.reset_mock()
            mgr_sent = send_push_to_group(
                ROLE_MANAGER,
                title="Manager Alert",
                body="Item ready",
                url="/dashboard/",
            )
            self.assertEqual(mgr_sent, 1)
            mock_webpush.assert_called_once()

    @patch("inventory.services.push_service.webpush")
    def test_push_default_fallback_url_is_dashboard(self, mock_webpush):
        with override_settings(
            VAPID_PUBLIC_KEY=self.pub_key,
            VAPID_PRIVATE_KEY=self.priv_key,
        ):
            send_push_to_subscription(
                self.sub_assistant,
                title="Default Sub",
                body="No url arg",
            )
            send_push_to_subscription(
                self.sub_assistant,
                title="Empty Sub",
                body="Empty url arg",
                url="",
            )
            send_push_to_user(
                self.assistant,
                title="Default User",
                body="No url arg",
            )
            send_push_to_group(
                ROLE_MANAGER,
                title="Default Group",
                body="No url arg",
            )

        self.assertEqual(mock_webpush.call_count, 4)
        for call in mock_webpush.call_args_list:
            payload = json.loads(call.kwargs["data"])
            self.assertEqual(payload["url"], "/dashboard/")

    @patch("inventory.services.push_service.webpush")
    def test_expired_subscription_pruned_on_410_and_404(self, mock_webpush):
        mock_response = MagicMock()
        mock_response.status_code = 410
        mock_webpush.side_effect = WebPushException("410 Gone", response=mock_response)

        with override_settings(
            VAPID_PUBLIC_KEY=self.pub_key,
            VAPID_PRIVATE_KEY=self.priv_key,
        ):
            ok = send_push_to_subscription(
                self.sub_assistant, title="Expired", body="Should prune"
            )
            self.assertFalse(ok)
            self.assertFalse(
                PushSubscription.objects.filter(pk=self.sub_assistant.pk).exists()
            )

    @patch("inventory.services.push_service.webpush")
    def test_admin_registration_and_send_test_push_action(self, mock_webpush):
        self.assertIn(PushSubscription, manager_admin_site._registry)
        model_admin = manager_admin_site._registry[PushSubscription]
        self.assertIsInstance(model_admin, PushSubscriptionAdmin)

        factory = RequestFactory()
        request = factory.post("/admin/inventory/pushsubscription/")
        request.user = self.manager
        request._messages = MagicMock()

        with override_settings(
            VAPID_PUBLIC_KEY=self.pub_key,
            VAPID_PRIVATE_KEY=self.priv_key,
        ):
            qs = PushSubscription.objects.filter(pk=self.sub_manager.pk)
            model_admin.send_test_push_action(request, qs)
            mock_webpush.assert_called_once()


class PushSubscriptionAPIEndpointsTests(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username="user1_api", password="password123")
        self.user2 = User.objects.create_user(username="user2_api", password="password123")
        self.pub_key, self.priv_key = generate_vapid_keypair()

    def test_endpoints_require_authentication(self):
        for url_name in ("inventory:push_subscribe", "inventory:push_unsubscribe", "inventory:push_test"):
            resp = self.client.post(reverse(url_name), data="{}", content_type="application/json")
            self.assertEqual(resp.status_code, 302)

    def test_subscribe_and_upsert_idempotency(self):
        self.client.login(username="user1_api", password="password123")
        payload = {
            "endpoint": "https://fcm.googleapis.com/fcm/send/device-xyz",
            "keys": {
                "p256dh": "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM",
                "auth": "tBHItJI5svbpez7KI4CCXg",
            },
        }
        resp1 = self.client.post(
            reverse("inventory:push_subscribe"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(PushSubscription.objects.filter(user=self.user1).count(), 1)

        # Second call with same endpoint updates existing record without duplicating
        payload["keys"]["auth"] = "updatedAuthSecret12345"
        resp2 = self.client.post(
            reverse("inventory:push_subscribe"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(PushSubscription.objects.count(), 1)
        sub = PushSubscription.objects.first()
        self.assertEqual(sub.auth, "updatedAuthSecret12345")

    def test_subscribe_validation_errors(self):
        self.client.login(username="user1_api", password="password123")
        # Missing fields
        resp = self.client.post(
            reverse("inventory:push_subscribe"),
            data=json.dumps({"endpoint": "https://fcm.googleapis.com/send/1"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

        # Invalid URL scheme
        resp_bad_url = self.client.post(
            reverse("inventory:push_subscribe"),
            data=json.dumps({
                "endpoint": "ftp://bad-scheme.example.com/push",
                "keys": {"p256dh": "key1", "auth": "auth1"},
            }),
            content_type="application/json",
        )
        self.assertEqual(resp_bad_url.status_code, 400)

    def test_unsubscribe_isolates_user_subscriptions(self):
        sub1 = PushSubscription.objects.create(
            user=self.user1,
            endpoint="https://fcm.googleapis.com/fcm/send/u1",
            p256dh="k1",
            auth="a1",
        )
        sub2 = PushSubscription.objects.create(
            user=self.user2,
            endpoint="https://fcm.googleapis.com/fcm/send/u2",
            p256dh="k2",
            auth="a2",
        )

        self.client.login(username="user1_api", password="password123")
        # Attempting to delete user2's endpoint does not delete user2's subscription
        self.client.post(
            reverse("inventory:push_unsubscribe"),
            data=json.dumps({"endpoint": sub2.endpoint}),
            content_type="application/json",
        )
        self.assertTrue(PushSubscription.objects.filter(pk=sub2.pk).exists())

        # Deleting user1's own endpoint succeeds
        resp = self.client.post(
            reverse("inventory:push_unsubscribe"),
            data=json.dumps({"endpoint": sub1.endpoint}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(PushSubscription.objects.filter(pk=sub1.pk).exists())

    @patch("inventory.services.push_service.webpush")
    def test_push_test_endpoint(self, mock_webpush):
        PushSubscription.objects.create(
            user=self.user1,
            endpoint="https://fcm.googleapis.com/fcm/send/u1-test",
            p256dh="k1",
            auth="a1",
        )
        self.client.login(username="user1_api", password="password123")
        with override_settings(
            VAPID_PUBLIC_KEY=self.pub_key,
            VAPID_PRIVATE_KEY=self.priv_key,
        ):
            resp = self.client.post(
                reverse("inventory:push_test"),
                data="{}",
                content_type="application/json",
            )
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(json.loads(resp.content)["sent"], 1)
            mock_webpush.assert_called_once()


class LivePushWorkflowSignalsTests(TestCase):
    def setUp(self):
        self.assistant_group, _ = Group.objects.get_or_create(name=ROLE_ASSISTANT)
        self.manager_group, _ = Group.objects.get_or_create(name=ROLE_MANAGER)
        self.assistant = User.objects.create_user(username="sig_assistant", password="password123")
        self.assistant.groups.add(self.assistant_group)
        self.manager = User.objects.create_user(
            username="sig_manager", password="password123", is_staff=True
        )
        self.manager.groups.add(self.manager_group)

    @patch("inventory.services.push_service.send_push_to_group")
    @override_settings(PUSH_NOTIFICATIONS_LIVE_SIGNALS=False)
    def test_signals_do_not_fire_when_env_flag_disabled(self, mock_send_group):
        product = Product.objects.create(raw_note="Draft item", created_by=self.assistant)
        product.ai_title = "Identified Coat"
        product.ai_description = "Full description"
        product.save()

        clarification = ProductClarification.objects.create(
            product=product,
            category=ClarificationCategory.MEASUREMENTS,
            question="Sleeve length?",
            asked_by=self.manager,
        )
        clarification.resolve(answer="62 cm", answered_by=self.assistant)
        mock_send_group.assert_not_called()

    @patch("inventory.services.push_service.send_push_to_group")
    @override_settings(PUSH_NOTIFICATIONS_LIVE_SIGNALS=True)
    def test_signals_fire_for_doubts_and_lifecycle_when_enabled(self, mock_send_group):
        # 1. New DRAFT product -> debounced into IntakeBatchSession without immediate push spam
        product = Product.objects.create(
            raw_note="Vintage leather bag",
            ai_title="Vintage Leather Crossbody Bag",
            created_by=self.assistant,
        )
        self.assertEqual(product.status, ProductStatus.DRAFT)
        mock_send_group.assert_not_called()
        self.assertIsNotNone(product.batch_session)
        self.assertEqual(product.batch_session.product_count, 1)
        self.assertEqual(product.batch_session.assistant, self.assistant)

        # 2. Adding description without price transitions to PRICE_PENDING -> notifies managers
        mock_send_group.reset_mock()
        product.ai_description = "Genuine leather crossbody bag with brass buckle."
        product.save()
        self.assertEqual(product.status, ProductStatus.PRICE_PENDING)
        mock_send_group.assert_called_once()
        self.assertEqual(mock_send_group.call_args.kwargs["group_name"], ROLE_MANAGER)
        self.assertEqual(
            mock_send_group.call_args.kwargs["tag"], f"product-price-pending-{product.pk}"
        )

        # 3. Manager creates PENDING clarification doubt -> notifies assistants
        mock_send_group.reset_mock()
        clarification = ProductClarification.objects.create(
            product=product,
            category=ClarificationCategory.FLAWS_CONDITION,
            question="Are there any scratches on the base?",
            asked_by=self.manager,
        )
        mock_send_group.assert_called_once()
        self.assertEqual(mock_send_group.call_args.kwargs["group_name"], ROLE_ASSISTANT)
        self.assertEqual(
            mock_send_group.call_args.kwargs["tag"], f"clarification-product-{product.pk}"
        )

        # 4. Assistant resolves clarification doubt -> notifies managers
        mock_send_group.reset_mock()
        clarification.resolve(answer="No scratches, base is clean.", answered_by=self.assistant)
        # Note: resolving the last clarification also transitions Product back to PRICE_PENDING,
        # so send_push_to_group is called for clarification-resolved (and price-pending if transitioned).
        called_tags = [c.kwargs["tag"] for c in mock_send_group.call_args_list]
        self.assertIn(f"clarification-resolved-{product.pk}", called_tags)


@override_settings(TURNSTILE_ENABLED=False)
class BrowserPWAServiceWorkerAndPushTests(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._browser = start_shared_browser(cls)

    def setUp(self):
        self.manager = User.objects.create_user(
            username="browser_pwa_mgr", password="password123", is_staff=True
        )

    def test_browser_service_worker_registration_and_manifest(self):
        with open_browser_page(
            self._browser,
            self,
            block_service_workers=False,
            viewport={"width": 1280, "height": 800},
        ) as (context, page):
            # 1. Anonymous public storefront has zero manifest, standalone meta, or SW registrations
            page.goto(f"{self.live_server_url}/")
            self.assertEqual(page.locator('link[rel="manifest"]').count(), 0)
            self.assertEqual(page.locator('meta[name="apple-mobile-web-app-capable"]').count(), 0)
            public_sw_count = page.evaluate(
                """async () => {
                    if (!('serviceWorker' in navigator)) return 0;
                    const regs = await navigator.serviceWorker.getRegistrations();
                    return regs.length;
                }"""
            )
            self.assertEqual(public_sw_count, 0)

            # 2. Anonymous /login/ also has zero manifest, standalone meta, or SW registrations
            page.goto(f"{self.live_server_url}/login/")
            self.assertEqual(page.locator('link[rel="manifest"]').count(), 0)
            self.assertEqual(page.locator('meta[name="apple-mobile-web-app-capable"]').count(), 0)
            login_sw_count = page.evaluate(
                """async () => {
                    if (!('serviceWorker' in navigator)) return 0;
                    const regs = await navigator.serviceWorker.getRegistrations();
                    return regs.length;
                }"""
            )
            self.assertEqual(login_sw_count, 0)

            # 3. Sign in as manager -> lands on /dashboard/ with manifest, SW, and new-tab storefront link
            login_in_browser(
                page,
                self.live_server_url,
                "browser_pwa_mgr",
                "password123",
                navigate_to_login=False,
                wait_until="load",
            )

            self.assertIn("/dashboard/", page.url)
            manifest_href = page.get_attribute('link[rel="manifest"]', "href")
            self.assertEqual(manifest_href, "/manifest.json")
            self.assertEqual(
                page.get_attribute('meta[name="apple-mobile-web-app-capable"]', "content"),
                "yes",
            )

            manifest_payload = page.evaluate(
                """async () => {
                    const resp = await fetch('/manifest.json');
                    return await resp.json();
                }"""
            )
            self.assertEqual(manifest_payload["id"], "/dashboard/")
            self.assertEqual(manifest_payload["start_url"], "/dashboard/")
            self.assertEqual(manifest_payload["scope"], "/")

            sw_scope = page.evaluate(
                """async () => {
                    if (!('serviceWorker' in navigator)) return null;
                    const reg = await navigator.serviceWorker.ready;
                    return reg ? reg.scope : null;
                }"""
            )
            self.assertEqual(sw_scope, f"{self.live_server_url}/")

            toggle_btn = page.locator("#push-toggle-btn")
            self.assertTrue(toggle_btn.is_visible())
            self.assertEqual(toggle_btn.get_attribute("data-subscribed"), "false")

            storefront_link = page.locator('#desktop-nav a[href="/tienda/"]')
            self.assertEqual(storefront_link.get_attribute("target"), "_blank")
            rel_tokens = set((storefront_link.get_attribute("rel") or "").split())
            self.assertTrue({"noopener", "noreferrer"}.issubset(rel_tokens))

            # 4. Authenticated /intake/ omits manifest/standalone tags while keeping SW & push toggle
            goto_authenticated(page, f"{self.live_server_url}/intake/", wait_until="load")
            self.assertEqual(page.locator('link[rel="manifest"]').count(), 0)
            self.assertEqual(page.locator('meta[name="apple-mobile-web-app-capable"]').count(), 0)
            intake_sw_scope = page.evaluate(
                """async () => {
                    if (!('serviceWorker' in navigator)) return null;
                    const reg = await navigator.serviceWorker.ready;
                    return reg ? reg.scope : null;
                }"""
            )
            self.assertEqual(intake_sw_scope, f"{self.live_server_url}/")
            self.assertTrue(page.locator("#push-toggle-btn").is_visible())

            # 5. Authenticated staff visiting public storefront / sees zero manifest or standalone tags
            page.goto(f"{self.live_server_url}/")
            self.assertEqual(page.locator('link[rel="manifest"]').count(), 0)
            self.assertEqual(page.locator('meta[name="apple-mobile-web-app-capable"]').count(), 0)

