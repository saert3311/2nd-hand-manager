import io
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from PIL import Image

from inventory.forms import (
    ProductClarificationAnswerForm,
    ProductClarificationForm,
    ProductIntakeForm,
    ProductUpdateForm,
)
from inventory.models import (
    ClarificationCategory,
    MarketplaceSite,
    Product,
    ProductClarification,
    ProductListingLink,
)
from inventory.permissions import ROLE_ASSISTANT, ROLE_MANAGER
from inventory.services.image_service import process_and_convert_to_webp, validate_image_file


class SecurityAndXSSProtectionTests(TestCase):
    """
    Tests ensuring all user-entered inputs and LLM outputs are rendered safely without XSS.
    """

    def setUp(self):
        self.client = Client()
        self.assistant = User.objects.create_user(username="asst", password="password123")
        self.manager = User.objects.create_user(username="mgr", password="password123", is_staff=True)

        asst_group, _ = Group.objects.get_or_create(name=ROLE_ASSISTANT)
        mgr_group, _ = Group.objects.get_or_create(name=ROLE_MANAGER)
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

    def test_clarification_question_and_answer_xss_is_escaped(self):
        self.client.login(username="mgr", password="password123")
        product = Product.objects.create(raw_note="Jeans", created_by=self.assistant)
        clarif = ProductClarification.objects.create(
            product=product,
            category=ClarificationCategory.MEASUREMENTS,
            question="<script>alert('xss-question')</script>",
            asked_by=self.manager,
        )
        clarif.resolve(
            answer="<img src=x onerror=alert('xss-answer')>",
            answered_by=self.assistant,
        )

        response = self.client.get(reverse("inventory:product_detail", kwargs={"pk": product.pk}))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        # Unescaped payloads must not appear in HTML
        self.assertNotIn("<script>alert('xss-question')</script>", content)
        self.assertNotIn("<img src=x onerror=alert('xss-answer')>", content)

        # Escaped payloads must appear
        self.assertIn("&lt;script&gt;alert(&#x27;xss-question&#x27;)&lt;/script&gt;", content)
        self.assertIn("&lt;img src=x onerror=alert(&#x27;xss-answer&#x27;)&gt;", content)

    def test_marketplace_site_name_and_url_xss_is_escaped(self):
        self.client.login(username="mgr", password="password123")
        product = Product.objects.create(raw_note="Shoes", created_by=self.assistant)
        site = MarketplaceSite.objects.create(
            name="<b onmouseover=alert('site-xss')>EvilMarket</b>",
            base_url="https://evilmarket.example.com",
            order=1,
        )
        ProductListingLink.objects.create(
            product=product,
            site=site,
            url="https://evilmarket.example.com/items/123",
        )

        response = self.client.get(reverse("inventory:product_detail", kwargs={"pk": product.pk}))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        self.assertNotIn("<b onmouseover=alert('site-xss')>", content)
        self.assertIn("&lt;b onmouseover=alert(&#x27;site-xss&#x27;)&gt;EvilMarket&lt;/b&gt;", content)


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

    def test_product_listing_link_rejects_javascript_url_scheme(self):
        site = MarketplaceSite.objects.create(name="SiteA", base_url="https://sitea.example.com")
        prod = Product.objects.create(raw_note="Item")
        link = ProductListingLink(product=prod, site=site, url="javascript:alert('xss')")
        with self.assertRaises(ValidationError):
            link.full_clean()

    def test_marketplace_site_rejects_javascript_base_url(self):
        site = MarketplaceSite(name="BadSite", base_url="javascript:alert('evil')")
        with self.assertRaises(ValidationError):
            site.full_clean()

    def test_clarification_question_length_limit(self):
        form = ProductClarificationForm(data={
            "category": ClarificationCategory.MEASUREMENTS,
            "question": "Q" * 2001,
        })
        self.assertFalse(form.is_valid())
        self.assertIn("question", form.errors)

    def test_clarification_answer_length_limit(self):
        form = ProductClarificationAnswerForm(data={
            "answer": "A" * 3001,
        })
        self.assertFalse(form.is_valid())
        self.assertIn("answer", form.errors)

    def test_image_validation_rejects_zero_byte_empty_file(self):
        empty_file = SimpleUploadedFile("empty.jpg", b"", content_type="image/jpeg")
        with self.assertRaises(ValidationError) as ctx:
            validate_image_file(empty_file)
        self.assertIn("empty", str(ctx.exception).lower())

    def test_image_validation_rejects_corrupted_truncated_file(self):
        corrupted_file = SimpleUploadedFile("corrupted.jpg", b"\xff\xd8\xff\xe0\x00\x10JFIF\x00", content_type="image/jpeg")
        with self.assertRaises(ValidationError) as ctx:
            validate_image_file(corrupted_file)
        self.assertIn("not a valid or readable image", str(ctx.exception).lower())

    def test_image_validation_rejects_svg_file(self):
        svg_payload = b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>"
        svg_file = SimpleUploadedFile("vector.svg", svg_payload, content_type="image/svg+xml")
        with self.assertRaises(ValidationError) as ctx:
            validate_image_file(svg_file)
        self.assertIn("not a valid or readable image", str(ctx.exception).lower())

    def test_process_and_convert_to_webp_sanitizes_path_traversal_filename(self):
        buf = io.BytesIO()
        Image.new("RGB", (50, 50), color="red").save(buf, format="JPEG")
        buf.seek(0)
        traversal_file = SimpleUploadedFile("../../../etc/passwd.jpg", buf.getvalue(), content_type="image/jpeg")
        converted = process_and_convert_to_webp(traversal_file)
        self.assertNotIn("..", converted.name)
        self.assertNotIn("/", converted.name)
        self.assertNotIn("\\", converted.name)
        self.assertTrue(converted.name.endswith(".webp"))

    def test_generate_ai_view_clamps_oversized_title(self):
        mgr = User.objects.create_user(username="mgr_ai_clamp", password="password123", is_staff=True)
        mgr_group, _ = Group.objects.get_or_create(name=ROLE_MANAGER)
        mgr.groups.add(mgr_group)
        self.client.login(username="mgr_ai_clamp", password="password123")
        product = Product.objects.create(raw_note="Coat", created_by=mgr)

        with patch("inventory.services.ai_service.generate_product_listing") as mock_gen:
            mock_gen.return_value = {
                "title": "A" * 400,
                "description": "Safe description",
            }
            resp = self.client.post(reverse("inventory:generate_ai", kwargs={"pk": product.pk}))
            self.assertEqual(resp.status_code, 302)
            product.refresh_from_db()
            self.assertEqual(len(product.ai_title), 255)


class AccessControlAndSecurityHeadersTests(TestCase):
    """
    Tests checking authorization enforcement and security headers.
    """

    def setUp(self):
        self.client = Client()
        self.assistant = User.objects.create_user(username="asst_user", password="password123")
        self.manager = User.objects.create_user(username="mgr_user", password="password123", is_staff=True)

        asst_group, _ = Group.objects.get_or_create(name=ROLE_ASSISTANT)
        mgr_group, _ = Group.objects.get_or_create(name=ROLE_MANAGER)
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
