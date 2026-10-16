from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from inventory.forms import ProductUpdateForm
from inventory.models import Product


class InternationalizationTests(TestCase):
    def setUp(self):
        self.assistant_group, _ = Group.objects.get_or_create(name="assistants")
        self.manager_group, _ = Group.objects.get_or_create(name="managers")

        self.assistant_user = User.objects.create_user(
            username="assistant_jane",
            password="testpassword123",
        )
        self.assistant_user.groups.add(self.assistant_group)

        self.manager_user = User.objects.create_user(
            username="manager_alex",
            password="testpassword123",
        )
        self.manager_user.groups.add(self.manager_group)

        self.product = Product.objects.create(
            raw_note="Original 1994 Pink Floyd tour tee, size XL",
            ai_title="Vintage Tour T-Shirt",
            ai_description="1994 Pink Floyd vintage t-shirt in great condition.",
            sale_price="45.00",
            is_sold=False,
        )

        self.client = Client()

    def test_login_page_renders_in_spanish_with_accept_language_header(self):
        response = self.client.get(reverse("inventory:login"), headers={"accept-language": "es"})
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Iniciar Sesión", content)
        self.assertIn("Inicia sesión en tu cuenta", content)
        self.assertIn("Usuario", content)
        self.assertIn("Contraseña", content)

    def test_login_page_renders_in_english_by_default_and_with_en_header(self):
        response = self.client.get(reverse("inventory:login"), headers={"accept-language": "en-US,en;q=0.9"})
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Sign In", content)
        self.assertIn("Sign in to your account", content)
        self.assertIn("Username", content)
        self.assertIn("Password", content)

    def test_unsupported_language_falls_back_to_english(self):
        response = self.client.get(reverse("inventory:login"), headers={"accept-language": "fr-FR,fr;q=0.8"})
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Sign In", content)
        self.assertIn("Sign in to your account", content)

    def test_intake_page_renders_in_spanish(self):
        self.client.force_login(self.assistant_user)
        response = self.client.get(reverse("inventory:intake"), headers={"accept-language": "es"})
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Nueva Entrada de Producto", content)
        self.assertIn("Fotos (Obligatorio)", content)
        self.assertIn("Notas de Campo / Descripción Breve", content)
        self.assertIn("Guardar y Catalogar Siguiente Artículo", content)

    def test_dashboard_renders_in_spanish(self):
        self.client.force_login(self.manager_user)
        response = self.client.get(reverse("inventory:dashboard"), headers={"accept-language": "es-ES,es;q=0.9"})
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Panel de Control", content)
        self.assertIn("Catálogo de Inventario", content)
        self.assertIn("Todos", content)
        self.assertIn("Activo", content)
        self.assertIn("Vendido", content)
        self.assertIn("Nueva Entrada", content)

    def test_product_detail_renders_in_spanish_and_preserves_raw_notes(self):
        self.client.force_login(self.manager_user)
        response = self.client.get(
            reverse("inventory:product_detail", kwargs={"pk": self.product.pk}),
            headers={"accept-language": "es"},
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Volver al Panel", content)
        self.assertIn("Notas de Entrada Preservadas", content)
        self.assertIn("Generar Publicación con IA", content)
        self.assertIn("Guardar Cambios de Publicación", content)
        # Verify raw note is preserved unchanged
        self.assertIn("Original 1994 Pink Floyd tour tee, size XL", content)
        # Verify price badge is rendered and price input has valid unlocalized dot value
        self.assertIn("product-price-badge", content)
        self.assertIn("45", content)
        self.assertIn('value="45.00"', content)
        self.assertNotIn('value="45,00"', content)

    def test_manual_language_switch_sets_cookie_and_overrides_header(self):
        setlang_url = reverse("set_language")
        # Post to set language to Spanish
        response = self.client.post(
            setlang_url,
            data={"language": "es", "next": reverse("inventory:login")},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("django_language", response.cookies)
        self.assertEqual(response.cookies["django_language"].value, "es")

        # Following request with accept-language='en', but cookie='es'
        self.client.cookies["django_language"] = "es"
        response = self.client.get(reverse("inventory:login"), headers={"accept-language": "en-US,en;q=0.9"})
        content = response.content.decode("utf-8")
        self.assertIn("Iniciar Sesión", content)

        # Switch back to English
        response = self.client.post(
            setlang_url,
            data={"language": "en", "next": reverse("inventory:login")},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.cookies["django_language"].value, "en")

        self.client.cookies["django_language"] = "en"
        response = self.client.get(reverse("inventory:login"), headers={"accept-language": "es"})
        content = response.content.decode("utf-8")
        self.assertIn("Sign In", content)

    def test_navbar_language_switcher_links_rendered(self):
        response = self.client.get(reverse("inventory:login"))
        content = response.content.decode("utf-8")
        self.assertIn('name="language" value="en"', content)
        self.assertIn('name="language" value="es"', content)
        self.assertIn("EN", content)
        self.assertIn("ES", content)

    @patch("inventory.services.ai_service.generate_product_listing")
    def test_generate_ai_listing_passes_active_spanish_language(self, mock_generate):
        mock_generate.return_value = {
            "title": "Camiseta de Gira Vintage Pink Floyd 1994",
            "description": "• Camiseta auténtica de la gira The Division Bell\n• Talla XL",
        }
        self.client.force_login(self.manager_user)
        self.client.cookies["django_language"] = "es"

        url = reverse("inventory:generate_ai", kwargs={"pk": self.product.pk})
        response = self.client.post(url, follow=True)

        self.assertEqual(response.status_code, 200)
        mock_generate.assert_called_once()
        _, kwargs = mock_generate.call_args
        self.assertEqual(kwargs.get("language"), "es")

        self.product.refresh_from_db()
        self.assertEqual(self.product.ai_title, "Camiseta de Gira Vintage Pink Floyd 1994")
        self.assertIn("The Division Bell", self.product.ai_description)

    def test_localized_form_validation_messages(self):
        from django.utils import translation

        with translation.override("es"):
            form = ProductUpdateForm(data={"sale_price": "invalid-price"})
            self.assertFalse(form.is_valid())
            errors = form.errors.as_text()
            # Django's DecimalField invalid error in Spanish
            self.assertTrue(
                "Introduzca un número" in errors or "número" in errors.lower(),
                f"Expected Spanish validation error, got: {errors}"
            )
