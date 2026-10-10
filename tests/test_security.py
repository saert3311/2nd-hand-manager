import io
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from PIL import Image

from inventory.forms import ProductIntakeForm, ProductUpdateForm
from inventory.models import Product
from inventory.permissions import ROLE_ASSISTANT, ROLE_MANAGER
from inventory.services.image_service import validate_image_file


class SecurityAndXSSProtectionTests(TestCase):
    """
    Tests ensuring all user-entered inputs and LLM outputs are rendered safely without XSS.
    """

    def setUp(self):
        self.client = Client()
        self.assistant = User.objects.create_user(username="asst", password="password123")
        self.manager = User.objects.create_user(username="mgr", password="password123", is_staff=True)

        asst_group = Group.objects.create(name=ROLE_ASSISTANT)
        mgr_group = Group.objects.create(name=ROLE_MANAGER)
        self.assistant.groups.add(asst_group)
        self.manager.groups.add(mgr_group)

    def test_raw_note_xss_payload_is_escaped_on_staging_detail(self):
        self.client.login(username="mgr", password="password123")
        xss_payload = "<script>alert('xss-in-raw-note')</script>"
        product = Product.objects.create(raw_note=xss_payload, created_by=self.assistant)

        response = self.client.get(reverse("inventory:product_detail", kwargs={"pk": product.pk}))
        self.assertEqual(response.status_code, 200)

        content = response.content.decode("utf-8")
        # Ensure unescaped script tag is NOT in the response HTML
        self.assertNotIn("<script>alert('xss-in-raw-note')</script>", content)
        # Ensure escaped script tag IS present
        self.assertIn("&lt;script&gt;alert(&#x27;xss-in-raw-note&#x27;)&lt;/script&gt;", content)

    def test_ai_title_and_description_xss_is_escaped(self):
        self.client.login(username="mgr", password="password123")
        malicious_title = '<img src=x onerror="alert(\'xss-title\')">'
        malicious_desc = '<a href="javascript:alert(\'xss-link\')">Click me</a>'
        product = Product.objects.create(
            raw_note="Normal note",
            ai_title=malicious_title,
            ai_description=malicious_desc,
            created_by=self.assistant,
        )

        response = self.client.get(reverse("inventory:product_detail", kwargs={"pk": product.pk}))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        self.assertNotIn('<img src=x onerror="alert(\'xss-title\')">', content)
        self.assertNotIn('<a href="javascript:alert(\'xss-link\')">', content)
        self.assertIn('&lt;img src=x onerror=&quot;alert(&#x27;xss-title&#x27;)&quot;&gt;', content)

    def test_dashboard_search_query_xss_is_escaped(self):
        self.client.login(username="mgr", password="password123")
        xss_query = '"><script>alert("search-xss")</script>'

        response = self.client.get(reverse("inventory:dashboard"), {"q": xss_query})
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        # Must not have raw injected script tag
        self.assertNotIn('<script>alert("search-xss")</script>', content)
        self.assertIn('&quot;&gt;&lt;script&gt;alert(&quot;search-xss&quot;)&lt;/script&gt;', content)


class InputValidationAndBoundaryTests(TestCase):
    """
    Tests ensuring input boundaries and data models reject malicious or invalid data.
    """

    def test_sale_price_cannot_be_negative(self):
        form = ProductUpdateForm(data={
            "ai_title": "Vintage Cap",
            "ai_description": "Clean condition",
            "sale_price": "-10.00",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("sale_price", form.errors)

    def test_sale_price_cannot_exceed_maximum(self):
        form = ProductUpdateForm(data={
            "ai_title": "Vintage Cap",
            "ai_description": "Clean condition",
            "sale_price": "99999999999.00",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("sale_price", form.errors)

    def test_model_validates_negative_sale_price(self):
        product = Product(raw_note="Cap", sale_price=Decimal("-5.00"))
        with self.assertRaises(ValidationError):
            product.full_clean()

    def test_raw_note_length_limit(self):
        huge_note = "A" * 5001
        form = ProductIntakeForm(data={"raw_note": huge_note})
        self.assertFalse(form.is_valid())
        self.assertIn("raw_note", form.errors)

    def test_image_validation_rejects_fake_image_file(self):
        fake_file = SimpleUploadedFile("malicious.jpg", b"<?php echo 'hacked'; ?>", content_type="image/jpeg")
        with self.assertRaises(ValidationError) as ctx:
            validate_image_file(fake_file)
        self.assertIn("not a valid or readable image", str(ctx.exception))

    def test_image_validation_accepts_valid_jpeg(self):
        buf = io.BytesIO()
        Image.new("RGB", (50, 50), color="blue").save(buf, format="JPEG")
        buf.seek(0)
        valid_file = SimpleUploadedFile("item.jpg", buf.getvalue(), content_type="image/jpeg")
        # Should not raise
        validate_image_file(valid_file)


class AccessControlAndSecurityHeadersTests(TestCase):
    """
    Tests checking authorization enforcement and security headers.
    """

    def setUp(self):
        self.client = Client()
        self.assistant = User.objects.create_user(username="asst_user", password="password123")
        self.manager = User.objects.create_user(username="mgr_user", password="password123", is_staff=True)

        asst_group = Group.objects.create(name=ROLE_ASSISTANT)
        mgr_group = Group.objects.create(name=ROLE_MANAGER)
        self.assistant.groups.add(asst_group)
        self.manager.groups.add(mgr_group)

        self.product = Product.objects.create(raw_note="Test Item", created_by=self.assistant)

    def test_assistant_cannot_update_product_staging_details(self):
        self.client.login(username="asst_user", password="password123")
        detail_url = reverse("inventory:product_detail", kwargs={"pk": self.product.pk})
        response = self.client.post(
            detail_url,
            {
                "ai_title": "Unauthorized Title",
                "sale_price": "50.00",
                "is_sold": "on",
            },
        )
        self.assertRedirects(response, detail_url)
        self.product.refresh_from_db()
        self.assertNotEqual(self.product.ai_title, "Unauthorized Title")

    def test_assistant_cannot_trigger_ai_generation(self):
        self.client.login(username="asst_user", password="password123")
        response = self.client.post(reverse("inventory:generate_ai", kwargs={"pk": self.product.pk}))
        # Must return 403 Forbidden due to manager_required
        self.assertEqual(response.status_code, 403)

    def test_ai_generation_redirects_non_post_requests(self):
        self.client.login(username="mgr_user", password="password123")
        detail_url = reverse("inventory:product_detail", kwargs={"pk": self.product.pk})
        response = self.client.get(reverse("inventory:generate_ai", kwargs={"pk": self.product.pk}))
        self.assertRedirects(response, detail_url)

    def test_security_headers_present_in_responses(self):
        self.client.login(username="mgr_user", password="password123")
        response = self.client.get(reverse("inventory:dashboard"))
        self.assertEqual(response.status_code, 200)

        # X-Frame-Options clickjacking protection
        self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")
        # X-Content-Type-Options MIME sniffing protection
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
