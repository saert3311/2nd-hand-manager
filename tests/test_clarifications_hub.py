from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from inventory.admin import ProductClarificationAdmin, ProductClarificationInline, manager_admin_site
from inventory.forms import ProductDirectClarificationForm
from inventory.models import (
    ClarificationCategory,
    ClarificationStatus,
    Product,
    ProductClarification,
    ProductStatus,
)
from inventory.permissions import ROLE_ASSISTANT, ROLE_MANAGER
from inventory.services.ai_service import generate_product_listing

User = get_user_model()


class ProductClarificationsHubTests(TestCase):
    def setUp(self):
        # Create user groups
        self.managers_group, _ = Group.objects.get_or_create(name=ROLE_MANAGER)
        self.assistants_group, _ = Group.objects.get_or_create(name=ROLE_ASSISTANT)

        # Create Manager
        self.manager = User.objects.create_user(
            username="manager_hub",
            password="password123",
            is_staff=True,
        )
        self.manager.groups.add(self.managers_group)

        # Create Assistant
        self.assistant = User.objects.create_user(
            username="assistant_hub",
            password="password123",
        )
        self.assistant.groups.add(self.assistants_group)

        # Create base test product
        self.product = Product.objects.create(
            raw_note="Vintage denim jacket with brass buttons",
            created_by=self.assistant,
            status=ProductStatus.DRAFT,
        )

        self.client = Client()

    def test_direct_clarification_model_creation(self):
        """Direct clarification note is saved in RESOLVED status with is_direct_note=True."""
        clarif = ProductClarification.objects.create(
            product=self.product,
            category=ClarificationCategory.MEASUREMENTS,
            is_direct_note=True,
            question="Direct Note",
            answer="Pit-to-pit: 56 cm, length: 72 cm",
            asked_by=self.assistant,
            answered_by=self.assistant,
            status=ClarificationStatus.RESOLVED,
            answered_at=timezone.now(),
        )
        self.assertTrue(clarif.is_direct_note)
        self.assertEqual(clarif.status, ClarificationStatus.RESOLVED)
        self.assertEqual(clarif.category, ClarificationCategory.MEASUREMENTS)
        self.assertEqual(clarif.answer, "Pit-to-pit: 56 cm, length: 72 cm")
        self.assertIsNotNone(clarif.answered_at)

    def test_direct_clarification_does_not_transition_product_to_awaiting_info(self):
        """Saving a direct clarification note preserves product status and does NOT set AWAITING_INFO."""
        self.product.status = ProductStatus.DRAFT
        self.product.save()

        ProductClarification.objects.create(
            product=self.product,
            category=ClarificationCategory.TAG_COMPOSITION,
            is_direct_note=True,
            question="Direct Note",
            answer="100% Selvedge Cotton Made in Japan",
            asked_by=self.assistant,
            answered_by=self.assistant,
            status=ClarificationStatus.RESOLVED,
            answered_at=timezone.now(),
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.status, ProductStatus.DRAFT)
        self.assertNotEqual(self.product.status, ProductStatus.AWAITING_INFO)

    def test_standard_manager_doubt_still_transitions_to_awaiting_info(self):
        """Standard manager doubt (is_direct_note=False, PENDING) transitions product to AWAITING_INFO."""
        self.product.status = ProductStatus.DRAFT
        self.product.save()

        ProductClarification.objects.create(
            product=self.product,
            category=ClarificationCategory.FLAWS_CONDITION,
            is_direct_note=False,
            question="Please verify if zipper works smoothly",
            asked_by=self.manager,
            status=ClarificationStatus.PENDING,
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.status, ProductStatus.AWAITING_INFO)

    def test_direct_clarification_form_validation(self):
        """ProductDirectClarificationForm requires non-empty note and valid category."""
        # Valid form
        form = ProductDirectClarificationForm(data={
            "category": ClarificationCategory.MEASUREMENTS,
            "note": "Chest: 54cm",
        })
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["note"], "Chest: 54cm")

        # Empty/whitespace note rejected
        invalid_form = ProductDirectClarificationForm(data={
            "category": ClarificationCategory.MEASUREMENTS,
            "note": "   \n  ",
        })
        self.assertFalse(invalid_form.is_valid())
        self.assertIn("note", invalid_form.errors)

    def test_assistant_can_add_direct_clarification_via_view(self):
        """Sourcing assistant can POST to add-note endpoint and create a resolved direct note."""
        self.client.force_login(self.assistant)
        url = reverse("inventory:add_direct_clarification", kwargs={"pk": self.product.pk})

        response = self.client.post(url, {
            "category": ClarificationCategory.MATERIAL_AUTHENTICITY,
            "note": "Genuine leather collar patch verified under magnifying loupe.",
        })

        self.assertRedirects(response, f"{reverse('inventory:product_detail', kwargs={'pk': self.product.pk})}#clarifications-section")

        clarif = ProductClarification.objects.filter(product=self.product, is_direct_note=True).first()
        self.assertIsNotNone(clarif)
        self.assertEqual(clarif.asked_by, self.assistant)
        self.assertEqual(clarif.answered_by, self.assistant)
        self.assertEqual(clarif.status, ClarificationStatus.RESOLVED)
        self.assertEqual(clarif.answer, "Genuine leather collar patch verified under magnifying loupe.")

        # Product status did NOT change to awaiting_info
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, ProductStatus.DRAFT)

    def test_manager_can_add_direct_clarification_via_view(self):
        """Store manager can POST to add-note endpoint and create a resolved direct note."""
        self.client.force_login(self.manager)
        url = reverse("inventory:add_direct_clarification", kwargs={"pk": self.product.pk})

        response = self.client.post(url, {
            "category": ClarificationCategory.MEASUREMENTS,
            "note": "Armpit-to-armpit: 52cm, Sleeve length: 64cm.",
        })

        self.assertRedirects(response, f"{reverse('inventory:product_detail', kwargs={'pk': self.product.pk})}#clarifications-section")
        clarif = ProductClarification.objects.filter(product=self.product, is_direct_note=True).first()
        self.assertIsNotNone(clarif)
        self.assertEqual(clarif.asked_by, self.manager)

    def test_assistant_cannot_create_pending_doubt(self):
        """Sourcing assistant cannot POST to standard add_clarification (manager doubt) endpoint."""
        self.client.force_login(self.assistant)
        url = reverse("inventory:add_clarification", kwargs={"pk": self.product.pk})

        response = self.client.post(url, {
            "category": ClarificationCategory.GENERAL,
            "question": "Can I ask this?",
        })

        # Redirects with error message, no pending doubt created
        self.assertRedirects(response, reverse("inventory:product_detail", kwargs={"pk": self.product.pk}))
        self.assertFalse(ProductClarification.objects.filter(product=self.product, is_direct_note=False).exists())

    def test_anonymous_user_redirected_to_login(self):
        """Unauthenticated user is redirected to login on POST to add-note."""
        url = reverse("inventory:add_direct_clarification", kwargs={"pk": self.product.pk})
        response = self.client.post(url, {
            "category": ClarificationCategory.GENERAL,
            "note": "Anonymous note",
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("inventory:login"), response.url)

    def test_deleted_product_assistant_rejected(self):
        """Assistant attempting to add note to soft-deleted product is safely blocked."""
        self.product.soft_delete(user=self.manager)
        self.client.force_login(self.assistant)

        url = reverse("inventory:add_direct_clarification", kwargs={"pk": self.product.pk})
        response = self.client.post(url, {
            "category": ClarificationCategory.GENERAL,
            "note": "Note on trash",
        })
        self.assertRedirects(response, reverse("inventory:dashboard"))
        self.assertFalse(ProductClarification.objects.filter(product=self.product).exists())

    def test_manager_can_delete_clarification_note(self):
        """Manager can delete any clarification note or doubt."""
        clarif = ProductClarification.objects.create(
            product=self.product,
            category=ClarificationCategory.GENERAL,
            is_direct_note=True,
            question="Direct Note",
            answer="Temporary note",
            asked_by=self.manager,
            status=ClarificationStatus.RESOLVED,
        )

        self.client.force_login(self.manager)
        url = reverse("inventory:delete_clarification", kwargs={"pk": self.product.pk, "clarification_pk": clarif.pk})
        response = self.client.post(url)
        self.assertRedirects(response, reverse("inventory:product_detail", kwargs={"pk": self.product.pk}))
        self.assertFalse(ProductClarification.objects.filter(pk=clarif.pk).exists())

    def test_ai_copywriting_prompt_formats_direct_notes(self):
        """generate_product_listing prompt includes direct notes formatted as Note / Nota."""
        ProductClarification.objects.create(
            product=self.product,
            category=ClarificationCategory.MEASUREMENTS,
            is_direct_note=True,
            question="Direct Note",
            answer="Chest: 56cm, Length: 70cm",
            asked_by=self.assistant,
            status=ClarificationStatus.RESOLVED,
        )

        # Mock Gemini client
        mock_response = MagicMock()
        mock_response.text = '{"title": "Vintage Jacket", "description": "Measurements: Chest 56cm"}'

        with patch("inventory.services.ai_service.genai.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_client.models.generate_content.return_value = mock_response

            # English prompt
            generate_product_listing(product=self.product, language="en")
            call_kwargs = mock_client.models.generate_content.call_args[1]
            contents = call_kwargs["contents"]
            prompt_str = contents[0]
            self.assertIn("CLARIFICATIONS AND ASSISTANT ANSWERS:", prompt_str)
            self.assertIn("- [Measurements / Sizing] Note: Chest: 56cm, Length: 70cm", prompt_str)

            # Spanish prompt
            generate_product_listing(product=self.product, language="es")
            call_kwargs_es = mock_client.models.generate_content.call_args[1]
            contents_es = call_kwargs_es["contents"]
            prompt_str_es = contents_es[0]
            self.assertIn("ACLARACIONES Y RESPUESTAS DEL ASISTENTE:", prompt_str_es)
            self.assertIn("Nota: Chest: 56cm, Length: 70cm", prompt_str_es)

    def test_product_detail_ui_rendering_manager_vs_assistant(self):
        """Product detail renders dual-mode tabs for manager and direct note form for assistant."""
        # 1. Manager view
        self.client.force_login(self.manager)
        response_mgr = self.client.get(reverse("inventory:product_detail", kwargs={"pk": self.product.pk}))
        self.assertEqual(response_mgr.status_code, 200)
        self.assertContains(response_mgr, "id=\"clarifications-section\"")
        self.assertContains(response_mgr, "id=\"tabBtnDirectNote\"")
        self.assertContains(response_mgr, "id=\"tabBtnAskDoubt\"")
        self.assertContains(response_mgr, "id=\"panelDirectNote\"")
        self.assertContains(response_mgr, "id=\"panelAskDoubt\"")

        # 2. Assistant view
        self.client.force_login(self.assistant)
        response_ast = self.client.get(reverse("inventory:product_detail", kwargs={"pk": self.product.pk}))
        self.assertEqual(response_ast.status_code, 200)
        self.assertContains(response_ast, "id=\"clarifications-section\"")
        self.assertNotContains(response_ast, "id=\"tabBtnDirectNote\"")
        self.assertNotContains(response_ast, "id=\"tabBtnAskDoubt\"")
        self.assertContains(response_ast, reverse("inventory:add_direct_clarification", kwargs={"pk": self.product.pk}))

    def test_spanish_localization_in_clarifications_hub(self):
        """Spanish Accept-Language header renders localized titles and buttons."""
        self.client.force_login(self.manager)
        response = self.client.get(
            reverse("inventory:product_detail", kwargs={"pk": self.product.pk}),
            HTTP_ACCEPT_LANGUAGE="es",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aclaraciones y notas del producto")
        self.assertContains(response, "Añadir nota directa")
        self.assertContains(response, "Guardar nota de aclaración")

    def test_admin_registration_includes_is_direct_note(self):
        """manager_admin_site displays is_direct_note in list_display and inline."""
        self.assertIn(ProductClarification, manager_admin_site._registry)
        admin_instance = manager_admin_site._registry[ProductClarification]
        self.assertIsInstance(admin_instance, ProductClarificationAdmin)
        self.assertIn("is_direct_note", admin_instance.list_display)
        self.assertIn("is_direct_note", admin_instance.list_filter)

        inline_classes = [inline.__class__ if not isinstance(inline, type) else inline for inline in manager_admin_site._registry[Product].inlines]
        self.assertIn(ProductClarificationInline, inline_classes)
        self.assertIn("is_direct_note", ProductClarificationInline.fields)
