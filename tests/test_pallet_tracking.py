import datetime
import io
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import translation
from PIL import Image

from inventory.forms import PalletForm, ProductIntakeForm
from inventory.models import Pallet, Product, ProductStatus
from inventory.permissions import ROLE_ASSISTANT, ROLE_MANAGER

User = get_user_model()


def create_dummy_image():
    file_obj = io.BytesIO()
    image = Image.new("RGB", (100, 100), color="blue")
    image.save(file_obj, format="JPEG")
    file_obj.seek(0)
    return SimpleUploadedFile("test_sample.jpg", file_obj.read(), content_type="image/jpeg")


class PalletTrackingTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.assistant_group, _ = Group.objects.get_or_create(name=ROLE_ASSISTANT)
        self.manager_group, _ = Group.objects.get_or_create(name=ROLE_MANAGER)

        self.manager = User.objects.create_user(
            username="manager_ana",
            password="password123",
            is_staff=True,
        )
        self.manager.groups.add(self.manager_group)

        self.assistant = User.objects.create_user(
            username="assistant_carlos",
            password="password123",
        )
        self.assistant.groups.add(self.assistant_group)

        self.pallet1 = Pallet.objects.create(
            number=1,
            received_date=datetime.date(2026, 10, 15),
            purchase_price=Decimal("450.00"),
            estimated_value=Decimal("1200.00"),
            notes="Amazon returns pallet #A1",
            created_by=self.manager,
        )

    def test_pallet_model_str_and_properties(self):
        self.assertEqual(str(self.pallet1), "Pallet #1 (2026-10-15)")
        self.assertEqual(self.pallet1.number, 1)
        self.assertEqual(self.pallet1.purchase_price, Decimal("450.00"))
        self.assertEqual(self.pallet1.estimated_value, Decimal("1200.00"))

    def test_pallet_number_unique_constraint(self):
        with self.assertRaises(IntegrityError):
            Pallet.objects.create(
                number=1,
                received_date=datetime.date(2026, 10, 16),
            )

    def test_product_pallet_cascade_set_null(self):
        product = Product.objects.create(
            raw_note="Gaming keyboard",
            ai_title="Mechanical Gaming Keyboard RGB",
            sale_price=Decimal("45.00"),
            status=ProductStatus.READY,
            pallet=self.pallet1,
            created_by=self.assistant,
        )
        self.assertEqual(product.pallet, self.pallet1)
        self.assertEqual(self.pallet1.products.count(), 1)

        # Deleting pallet must NOT delete the product; it should set pallet to None
        self.pallet1.delete()
        product.refresh_from_db()
        self.assertIsNone(product.pallet)
        self.assertTrue(Product.objects.filter(pk=product.pk).exists())

    def test_pallet_form_validation(self):
        # Valid form
        form = PalletForm(data={
            "number": 2,
            "received_date": "2026-10-31",
            "purchase_price": "300.50",
            "estimated_value": "900.00",
            "notes": "Costco overstock",
        })
        self.assertTrue(form.is_valid(), form.errors)

        # Negative number invalid
        form_invalid_num = PalletForm(data={
            "number": 0,
            "received_date": "2026-10-31",
        })
        self.assertFalse(form_invalid_num.is_valid())
        self.assertIn("number", form_invalid_num.errors)

        # Negative price invalid
        form_invalid_price = PalletForm(data={
            "number": 3,
            "received_date": "2026-10-31",
            "purchase_price": "-10.00",
        })
        self.assertFalse(form_invalid_price.is_valid())
        self.assertIn("purchase_price", form_invalid_price.errors)

    def test_manager_pallets_view_and_creation(self):
        self.client.login(username="manager_ana", password="password123")
        response = self.client.get(reverse("inventory:pallets"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pallet #1")
        self.assertContains(response, "450.00")
        self.assertContains(response, "1200.00")

        # Auto-numbered initial form should have number = 2
        form_in_ctx = response.context["form"]
        self.assertEqual(form_in_ctx.initial["number"], 2)

        # Create new pallet via POST
        post_response = self.client.post(
            reverse("inventory:pallets"),
            data={
                "number": 2,
                "received_date": "2026-10-31",
                "purchase_price": "600.00",
                "estimated_value": "1500.00",
                "notes": "Target liquidation",
            },
        )
        self.assertRedirects(post_response, reverse("inventory:pallets"))
        self.assertTrue(Pallet.objects.filter(number=2).exists())
        pallet2 = Pallet.objects.get(number=2)
        self.assertEqual(pallet2.created_by, self.manager)

    def test_manager_pallet_edit_view(self):
        self.client.login(username="manager_ana", password="password123")
        edit_url = reverse("inventory:pallet_edit", args=[self.pallet1.pk])
        response = self.client.get(edit_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Amazon returns pallet #A1")

        post_response = self.client.post(
            edit_url,
            data={
                "number": 1,
                "received_date": "2026-10-15",
                "purchase_price": "475.00",
                "estimated_value": "1300.00",
                "notes": "Updated notes",
            },
        )
        self.assertRedirects(post_response, reverse("inventory:pallets"))
        self.pallet1.refresh_from_db()
        self.assertEqual(self.pallet1.purchase_price, Decimal("475.00"))
        self.assertEqual(self.pallet1.notes, "Updated notes")

    def test_manager_pallet_delete_view(self):
        self.client.login(username="manager_ana", password="password123")
        product = Product.objects.create(
            raw_note="Headphones",
            ai_title="Wireless Headphones",
            pallet=self.pallet1,
            created_by=self.manager,
        )

        delete_url = reverse("inventory:pallet_delete", args=[self.pallet1.pk])
        response = self.client.post(delete_url)
        self.assertRedirects(response, reverse("inventory:pallets"))
        self.assertFalse(Pallet.objects.filter(pk=self.pallet1.pk).exists())

        product.refresh_from_db()
        self.assertIsNone(product.pallet)

    def test_assistant_cannot_access_pallets_view(self):
        self.client.login(username="assistant_carlos", password="password123")
        response = self.client.get(reverse("inventory:pallets"))
        self.assertEqual(response.status_code, 403)

        edit_response = self.client.get(reverse("inventory:pallet_edit", args=[self.pallet1.pk]))
        self.assertEqual(edit_response.status_code, 403)

        delete_response = self.client.post(reverse("inventory:pallet_delete", args=[self.pallet1.pk]))
        self.assertEqual(delete_response.status_code, 403)

    def test_unauthenticated_redirects_to_login(self):
        response = self.client.get(reverse("inventory:pallets"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("inventory:login"), response.url)

    def test_sticky_intake_session_persistence(self):
        self.client.login(username="assistant_carlos", password="password123")

        # 1. Initial GET on /intake/ with no session: pre-selects pallet1 (highest number)
        response1 = self.client.get(reverse("inventory:intake"))
        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response1.context["form"].initial.get("pallet"), self.pallet1.pk)

        # 2. Assistant catalogs item with pallet1
        img1 = create_dummy_image()
        post_response = self.client.post(
            reverse("inventory:intake"),
            data={
                "pallet": self.pallet1.pk,
                "raw_note": "Sony speaker in box",
                "images": [img1],
                "ai_title": "Sony Bluetooth Speaker",
                "estimated_retail_price": "120.00",
                "estimated_resale_price": "60.00",
            },
        )
        self.assertRedirects(post_response, reverse("inventory:intake"))
        created_prod1 = Product.objects.filter(raw_note="Sony speaker in box").first()
        self.assertIsNotNone(created_prod1)
        self.assertEqual(created_prod1.pallet, self.pallet1)

        # Verify session has sticky pallet
        session = self.client.session
        self.assertEqual(session.get("last_intake_pallet_id"), self.pallet1.pk)

        # 3. Next GET on /intake/: initial form has pallet1 preselected
        response2 = self.client.get(reverse("inventory:intake"))
        self.assertEqual(response2.context["form"].initial.get("pallet"), self.pallet1.pk)

        # 4. Assistant catalogs standalone walk-in item without pallet ("none")
        img2 = create_dummy_image()
        post_response2 = self.client.post(
            reverse("inventory:intake"),
            data={
                "pallet": "",  # Empty choice
                "raw_note": "Walk-in vintage lamp",
                "images": [img2],
                "ai_title": "Vintage Brass Desk Lamp",
                "estimated_retail_price": "80.00",
                "estimated_resale_price": "35.00",
            },
        )
        self.assertRedirects(post_response2, reverse("inventory:intake"))
        created_prod2 = Product.objects.filter(raw_note="Walk-in vintage lamp").first()
        self.assertIsNotNone(created_prod2)
        self.assertIsNone(created_prod2.pallet)

        # Verify session remembered "none"
        session2 = self.client.session
        self.assertEqual(session2.get("last_intake_pallet_id"), "none")

        # 5. Subsequent GET to /intake/ preserves "no pallet"
        response3 = self.client.get(reverse("inventory:intake"))
        self.assertIsNone(response3.context["form"].initial.get("pallet"))

    def test_assistant_choice_field_does_not_expose_financials(self):
        form = ProductIntakeForm()
        choices = list(form.fields["pallet"].choices)
        # Should have empty label + pallet1
        self.assertGreaterEqual(len(choices), 2)
        empty_val, empty_label = choices[0]
        self.assertEqual(empty_val, "")
        self.assertIn("No Pallet", str(empty_label))

        pallet_val, pallet_label = choices[1]
        self.assertEqual(pallet_val, self.pallet1.pk)
        # Must show Pallet #1 (YYYY-MM-DD)
        self.assertIn("Pallet #1", str(pallet_label))
        # Must NEVER leak purchase price or estimated value
        self.assertNotIn("450", str(pallet_label))
        self.assertNotIn("1200", str(pallet_label))

    def test_product_detail_pallet_display_and_manager_update(self):
        product = Product.objects.create(
            raw_note="Office chair",
            ai_title="Ergonomic Mesh Chair",
            sale_price=Decimal("85.00"),
            status=ProductStatus.READY,
            pallet=self.pallet1,
            created_by=self.assistant,
        )

        pallet2 = Pallet.objects.create(
            number=2,
            received_date=datetime.date(2026, 10, 20),
            created_by=self.manager,
        )

        self.client.login(username="manager_ana", password="password123")
        detail_url = reverse("inventory:product_detail", args=[product.pk])
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pallet #1")

        # Manager updates pallet to pallet2
        post_response = self.client.post(
            detail_url,
            data={
                "pallet": pallet2.pk,
                "ai_title": "Ergonomic Mesh Chair Pro",
                "ai_description": "High quality chair",
                "sale_price": "90.00",
                "status": ProductStatus.READY,
            },
        )
        self.assertRedirects(post_response, detail_url)
        product.refresh_from_db()
        self.assertEqual(product.pallet, pallet2)
        self.assertEqual(product.ai_title, "Ergonomic Mesh Chair Pro")

    def test_spanish_translations(self):
        with translation.override("es"):
            from django.utils.translation import gettext as _

            self.assertEqual(_("Pallet Attribution"), "Atribución de Pallet")
            self.assertEqual(_("Liquidation Pallets"), "Pallets de liquidación")
            self.assertEqual(_("Register New Pallet"), "Registrar Nuevo Pallet")
            self.assertEqual(_("Received Date"), "Fecha de recepción")
            self.assertEqual(_("Create Pallet"), "Crear Pallet")

        self.client.login(username="manager_ana", password="password123")
        self.client.cookies["django_language"] = "es"
        response = self.client.get(reverse("inventory:pallets"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Pallets de liquidación", content)
        self.assertIn("Registrar Nuevo Pallet", content)
        self.assertIn("Fecha de recepción", content)
        self.assertIn("Crear Pallet", content)
