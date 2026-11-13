import datetime
import io
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import translation
from PIL import Image

from inventory.forms import ProductIntakeForm
from inventory.models import (
    Pallet,
    Product,
    ProductStatus,
    Provider,
    ProviderType,
    StorefrontConfiguration,
)
from inventory.services.origin_service import (
    build_intake_origin_choices,
    get_providers_with_roi_stats,
    parse_origin_token,
)

User = get_user_model()


def _make_test_image_file(name="test.jpg"):
    buf = io.BytesIO()
    Image.new("RGB", (120, 120), color=(40, 140, 90)).save(buf, format="JPEG")
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type="image/jpeg")


class ProviderModelAndGoldenSyncTests(TestCase):
    """Tests Provider model defaults, seeded walk-in provider, and Golden Sync Invariant."""

    def test_seeded_walkin_provider_exists(self):
        walkin = Provider.objects.get(slug="compra-en-tienda-particular")
        self.assertEqual(walkin.name, "Compra en Tienda / Particular")
        self.assertEqual(walkin.provider_type, ProviderType.WALK_IN)
        self.assertTrue(walkin.is_active)

    def test_unique_slug_generation_and_type_icons(self):
        p1 = Provider.objects.create(name="LiquiStock Valencia", provider_type=ProviderType.WHOLESALER)
        p2 = Provider.objects.create(name="LiquiStock Valencia!", provider_type=ProviderType.OTHER)
        self.assertEqual(p1.slug, "liquistock-valencia")
        self.assertEqual(p2.slug, "liquistock-valencia-2")
        self.assertEqual(p1.type_icon, "🏢")
        self.assertEqual(p2.type_icon, "🏷️")

        walkin = Provider.objects.get(slug="compra-en-tienda-particular")
        self.assertEqual(walkin.type_icon, "🏪")

    def test_golden_sync_product_inherits_pallet_provider(self):
        wholesaler = Provider.objects.create(name="EuroLots", provider_type=ProviderType.WHOLESALER)
        other = Provider.objects.create(name="FleaMarket", provider_type=ProviderType.OTHER)
        pallet = Pallet.objects.create(
            number=101,
            received_date=datetime.date(2026, 10, 1),
            provider=wholesaler,
        )

        # Even if caller passes a conflicting provider alongside pallet, Golden Sync enforces pallet.provider
        product = Product.objects.create(
            raw_note="Sony headphones",
            pallet=pallet,
            provider=other,
        )
        self.assertEqual(product.provider, wholesaler)

    def test_golden_sync_pallet_provider_cascade_updates_products(self):
        p1 = Provider.objects.create(name="Provider A", provider_type=ProviderType.WHOLESALER)
        p2 = Provider.objects.create(name="Provider B", provider_type=ProviderType.WHOLESALER)
        pallet = Pallet.objects.create(number=202, received_date=datetime.date(2026, 10, 2), provider=p1)
        prod = Product.objects.create(raw_note="Coffee maker", pallet=pallet)
        self.assertEqual(prod.provider, p1)

        # Update pallet provider -> linked products update automatically
        pallet.provider = p2
        pallet.save()
        prod.refresh_from_db()
        self.assertEqual(prod.provider, p2)

        # Clearing pallet provider clears derived product provider
        pallet.provider = None
        pallet.save()
        prod.refresh_from_db()
        self.assertIsNone(prod.provider)

    def test_soft_set_null_on_delete_and_origin_display(self):
        p = Provider.objects.create(name="Direct Supplier", provider_type=ProviderType.OTHER)
        pallet = Pallet.objects.create(number=303, received_date=datetime.date(2026, 10, 3), provider=p)
        prod_pallet = Product.objects.create(raw_note="Item A", pallet=pallet)
        prod_direct = Product.objects.create(raw_note="Item B", provider=p)
        prod_none = Product.objects.create(raw_note="Item C")

        self.assertEqual(prod_pallet.origin_display, "Pallet #303 · Direct Supplier")
        self.assertEqual(prod_direct.origin_display, "Direct Supplier")
        self.assertEqual(prod_none.origin_display, "")

        # Deleting provider keeps pallet and products intact (SET_NULL)
        p.delete()
        pallet.refresh_from_db()
        prod_pallet.refresh_from_db()
        prod_direct.refresh_from_db()
        self.assertIsNone(pallet.provider)
        self.assertIsNone(prod_pallet.provider)
        self.assertIsNone(prod_direct.provider)
        self.assertEqual(prod_pallet.origin_display, "Pallet #303")

        # Deleting pallet keeps product intact
        pallet.delete()
        prod_pallet.refresh_from_db()
        self.assertIsNone(prod_pallet.pallet)


class OriginServiceAndROITests(TestCase):
    """Tests origin_service choices, token parser, and zero-double-counting ROI."""

    def test_build_intake_origin_choices_excludes_financials(self):
        provider = Provider.objects.create(name="SecretLot", provider_type=ProviderType.WHOLESALER)
        Pallet.objects.create(
            number=50,
            received_date=datetime.date(2026, 10, 5),
            purchase_price=Decimal("1234.56"),
            estimated_value=Decimal("4321.00"),
            provider=provider,
        )
        choices = build_intake_origin_choices()
        serialized = repr(choices)
        self.assertIn("pallet:", serialized)
        self.assertIn("provider:", serialized)
        self.assertIn("SecretLot", serialized)
        self.assertNotIn("1234.56", serialized)
        self.assertNotIn("4321.00", serialized)

    def test_parse_origin_token_variants(self):
        active_prov = Provider.objects.create(name="ActiveProv", is_active=True)
        inactive_prov = Provider.objects.create(name="InactiveProv", is_active=False)
        pallet = Pallet.objects.create(number=60, received_date=datetime.date(2026, 10, 6), provider=active_prov)

        self.assertEqual(parse_origin_token(""), (None, None))
        self.assertEqual(parse_origin_token("none"), (None, None))
        self.assertEqual(parse_origin_token(f"pallet:{pallet.pk}"), (pallet, active_prov))
        self.assertEqual(parse_origin_token(f"provider:{active_prov.pk}"), (None, active_prov))

        with self.assertRaises(ValidationError):
            parse_origin_token(f"provider:{inactive_prov.pk}")
        with self.assertRaises(ValidationError):
            parse_origin_token("pallet:999999")
        with self.assertRaises(ValidationError):
            parse_origin_token("garbage")

    def test_provider_roi_no_double_counting(self):
        provider = Provider.objects.create(name="LiquiROI", provider_type=ProviderType.WHOLESALER)
        pallet = Pallet.objects.create(
            number=70,
            received_date=datetime.date(2026, 10, 7),
            purchase_price=Decimal("500.00"),
            provider=provider,
        )
        # Palletized products (even if acquisition_cost has a lingering value, MUST NOT double count!)
        Product.objects.create(
            ai_title="Pallet Item Sold",
            ai_description="Desc",
            sale_price=Decimal("700.00"),
            acquisition_cost=Decimal("100.00"),
            is_sold=True,
            sold_channel_type="in_store",
            pallet=pallet,
        )
        Product.objects.create(
            ai_title="Pallet Item Active",
            ai_description="Desc",
            sale_price=Decimal("250.00"),
            pallet=pallet,
        )
        # Non-pallet direct product (counts acquisition_cost)
        Product.objects.create(
            ai_title="Direct Item Sold",
            ai_description="Desc",
            sale_price=Decimal("200.00"),
            acquisition_cost=Decimal("120.00"),
            is_sold=True,
            sold_channel_type="in_store",
            provider=provider,
        )
        # Soft-deleted direct product (MUST NOT count toward ROI stats or active stock)
        Product.objects.create(
            ai_title="Deleted Direct Item",
            ai_description="Desc",
            sale_price=Decimal("999.00"),
            acquisition_cost=Decimal("50.00"),
            is_deleted=True,
            provider=provider,
        )

        stats = {row["provider"].pk: row for row in get_providers_with_roi_stats()}[provider.pk]
        self.assertEqual(stats["pallets_count"], 1)
        self.assertEqual(stats["total_products_count"], 3)
        self.assertEqual(stats["active_products_count"], 1)
        self.assertEqual(stats["sold_products_count"], 2)
        self.assertEqual(stats["pallet_cost_total"], Decimal("500.00"))
        self.assertEqual(stats["standalone_cost_total"], Decimal("120.00"))
        self.assertEqual(stats["total_cost"], Decimal("620.00"))
        self.assertEqual(stats["realized_revenue"], Decimal("900.00"))
        self.assertEqual(stats["active_stock_value"], Decimal("250.00"))
        self.assertEqual(stats["net_margin"], Decimal("280.00"))
        self.assertEqual(stats["roi_pct"], Decimal("45.2"))


@override_settings(TURNSTILE_ENABLED=False)
class OriginIntakeAndPermissionsViewsTests(TestCase):
    """Tests /intake/ origin picker, session stickiness, and manager-only acquisition_cost."""

    def setUp(self):
        self.managers_group, _created = Group.objects.get_or_create(name="managers")
        self.assistants_group, _created = Group.objects.get_or_create(name="assistants")

        self.manager = User.objects.create_user(username="mgr_origin", password="pw")
        self.manager.groups.add(self.managers_group)

        self.assistant = User.objects.create_user(username="asst_origin", password="pw")
        self.assistant.groups.add(self.assistants_group)

        self.wholesaler = Provider.objects.create(name="EuroWholesale", provider_type=ProviderType.WHOLESALER)
        self.walkin = Provider.objects.get(slug="compra-en-tienda-particular")
        self.pallet = Pallet.objects.create(
            number=1,
            received_date=datetime.date(2026, 10, 10),
            purchase_price=Decimal("888.88"),
            provider=self.wholesaler,
        )

    def test_intake_unified_origin_and_stickiness(self):
        self.client.force_login(self.assistant)

        resp_get = self.client.get(reverse("inventory:intake"))
        self.assertEqual(resp_get.status_code, 200)
        self.assertContains(resp_get, 'name="origin"')
        self.assertContains(resp_get, f'value="pallet:{self.pallet.pk}"')
        self.assertContains(resp_get, f'value="provider:{self.walkin.pk}"')
        self.assertNotContains(resp_get, "888.88")
        self.assertNotContains(resp_get, 'name="acquisition_cost"')

        # Step 1: Select a pallet origin -> product gets pallet + derived provider + sticky session
        resp_post1 = self.client.post(
            reverse("inventory:intake"),
            {
                "origin": f"pallet:{self.pallet.pk}",
                "raw_note": "Sony TV pallet unit",
                "images": _make_test_image_file("tv.jpg"),
            },
        )
        self.assertEqual(resp_post1.status_code, 302)
        p1 = Product.objects.get(raw_note="Sony TV pallet unit")
        self.assertEqual(p1.pallet, self.pallet)
        self.assertEqual(p1.provider, self.wholesaler)
        self.assertEqual(self.client.session.get("last_intake_origin"), f"pallet:{self.pallet.pk}")
        self.assertEqual(self.client.session.get("last_intake_pallet_id"), self.pallet.pk)

        # Next GET pre-selects pallet:<id>
        form = ProductIntakeForm(initial={"origin": self.client.session.get("last_intake_origin")})
        self.assertEqual(form.initial["origin"], f"pallet:{self.pallet.pk}")

        # Step 2: Switch to direct walk-in provider -> clears pallet, stores walk-in, clears sticky pallet id
        resp_post2 = self.client.post(
            reverse("inventory:intake"),
            {
                "origin": f"provider:{self.walkin.pk}",
                "raw_note": "Walk-in acoustic guitar",
                "images": _make_test_image_file("guitar.jpg"),
            },
        )
        self.assertEqual(resp_post2.status_code, 302)
        p2 = Product.objects.get(raw_note="Walk-in acoustic guitar")
        self.assertIsNone(p2.pallet)
        self.assertEqual(p2.provider, self.walkin)
        self.assertEqual(self.client.session.get("last_intake_origin"), f"provider:{self.walkin.pk}")
        self.assertEqual(self.client.session.get("last_intake_pallet_id"), "none")

    def test_acquisition_cost_strictly_manager_only(self):
        product = Product.objects.create(
            ai_title="Vintage Synth",
            ai_description="Clean synth",
            sale_price=Decimal("300.00"),
            acquisition_cost=Decimal("95.50"),
            provider=self.walkin,
        )

        # Assistant never sees acquisition_cost field or value in HTML, and cannot mutate via POST
        self.client.force_login(self.assistant)
        resp_asst = self.client.get(reverse("inventory:product_detail", kwargs={"pk": product.pk}))
        self.assertEqual(resp_asst.status_code, 200)
        self.assertNotContains(resp_asst, 'name="acquisition_cost"')
        self.assertNotContains(resp_asst, "95.50")
        self.assertNotContains(resp_asst, "95,50")

        resp_asst_post = self.client.post(
            reverse("inventory:product_detail", kwargs={"pk": product.pk}),
            {
                "ai_title": "Hacked",
                "acquisition_cost": "1.00",
                "provider": str(self.wholesaler.pk),
            },
        )
        self.assertEqual(resp_asst_post.status_code, 302)
        product.refresh_from_db()
        self.assertEqual(product.ai_title, "Vintage Synth")
        self.assertEqual(product.acquisition_cost, Decimal("95.50"))
        self.assertEqual(product.provider, self.walkin)

        # Manager sees and edits acquisition_cost cleanly
        self.client.force_login(self.manager)
        resp_mgr = self.client.get(reverse("inventory:product_detail", kwargs={"pk": product.pk}))
        self.assertEqual(resp_mgr.status_code, 200)
        self.assertContains(resp_mgr, 'name="acquisition_cost"')
        self.assertContains(resp_mgr, "95.50")

        resp_mgr_post = self.client.post(
            reverse("inventory:product_detail", kwargs={"pk": product.pk}),
            {
                "ai_title": "Vintage Synth",
                "ai_description": "Clean synth",
                "sale_price": "300.00",
                "acquisition_cost": "110.25",
                "provider": str(self.walkin.pk),
                "pallet": "",
            },
        )
        self.assertEqual(resp_mgr_post.status_code, 302)
        product.refresh_from_db()
        self.assertEqual(product.acquisition_cost, Decimal("110.25"))


@override_settings(TURNSTILE_ENABLED=False)
class ProvidersHubAndDashboardFilterTests(TestCase):
    """Tests Providers Hub CRUD, dashboard filtering, search, storefront firewall, and i18n."""

    def setUp(self):
        self.managers_group, _created = Group.objects.get_or_create(name="managers")
        self.assistants_group, _created = Group.objects.get_or_create(name="assistants")
        self.manager = User.objects.create_user(username="mgr_hub", password="pw")
        self.manager.groups.add(self.managers_group)
        self.assistant = User.objects.create_user(username="asst_hub", password="pw")
        self.assistant.groups.add(self.assistants_group)

        self.walkin = Provider.objects.get(slug="compra-en-tienda-particular")
        self.supplier = Provider.objects.create(name="IberiaLiquida", provider_type=ProviderType.WHOLESALER)
        self.pallet = Pallet.objects.create(
            number=10,
            received_date=datetime.date(2026, 10, 10),
            purchase_price=Decimal("400.00"),
            provider=self.supplier,
        )
        self.prod_pallet = Product.objects.create(
            ai_title="Pallet Monitor",
            ai_description="27 inch",
            sale_price=Decimal("180.00"),
            pallet=self.pallet,
        )
        self.prod_walkin = Product.objects.create(
            ai_title="Walkin Watch",
            ai_description="Automatic",
            sale_price=Decimal("150.00"),
            acquisition_cost=Decimal("65.00"),
            provider=self.walkin,
        )
        self.prod_none = Product.objects.create(
            ai_title="Unknown Origin Lamp",
            ai_description="Desk lamp",
            sale_price=Decimal("25.00"),
        )

    def test_assistant_blocked_from_provider_crud_and_hub(self):
        self.client.force_login(self.assistant)
        self.assertEqual(self.client.get(reverse("inventory:pallets")).status_code, 403)
        self.assertEqual(
            self.client.post(
                reverse("inventory:provider_create"),
                {"name": "Illegal", "provider_type": "other"},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                reverse("inventory:provider_edit", kwargs={"pk": self.supplier.pk}),
                {"name": "Hack", "provider_type": "other"},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(reverse("inventory:provider_delete", kwargs={"pk": self.supplier.pk})).status_code,
            403,
        )

    def test_manager_provider_hub_crud_flow(self):
        self.client.force_login(self.manager)

        resp = self.client.get(f"{reverse('inventory:pallets')}?tab=providers")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "IberiaLiquida")
        self.assertContains(resp, "Compra en Tienda / Particular")

        # Create provider
        resp_create = self.client.post(
            reverse("inventory:provider_create"),
            {
                "name": "Madrid Surplus",
                "provider_type": ProviderType.WHOLESALER,
                "contact_info": "ops@madridsurplus.example",
                "notes": "Net 30",
                "is_active": "on",
            },
        )
        self.assertRedirects(resp_create, f"{reverse('inventory:pallets')}?tab=providers")
        created = Provider.objects.get(name="Madrid Surplus")

        # Edit provider
        resp_edit = self.client.post(
            reverse("inventory:provider_edit", kwargs={"pk": created.pk}),
            {
                "name": "Madrid Surplus SL",
                "provider_type": ProviderType.OTHER,
                "contact_info": "hello@madridsurplus.example",
                "notes": "Updated notes",
                "is_active": "on",
            },
        )
        self.assertRedirects(resp_edit, f"{reverse('inventory:pallets')}?tab=providers")
        created.refresh_from_db()
        self.assertEqual(created.name, "Madrid Surplus SL")
        self.assertEqual(created.provider_type, ProviderType.OTHER)

        # GET on delete endpoint rejected (POST required)
        self.assertEqual(
            self.client.get(reverse("inventory:provider_delete", kwargs={"pk": created.pk})).status_code,
            405,
        )

        # Delete provider
        resp_del = self.client.post(reverse("inventory:provider_delete", kwargs={"pk": created.pk}))
        self.assertRedirects(resp_del, f"{reverse('inventory:pallets')}?tab=providers")
        self.assertFalse(Provider.objects.filter(pk=created.pk).exists())

    def test_dashboard_provider_filter_search_and_zero_cost_leak(self):
        self.client.force_login(self.assistant)

        # Filter by supplier -> shows only Pallet Monitor
        resp_sup = self.client.get(f"{reverse('inventory:dashboard')}?provider={self.supplier.pk}")
        self.assertEqual(resp_sup.status_code, 200)
        self.assertContains(resp_sup, "Pallet Monitor")
        self.assertNotContains(resp_sup, "Walkin Watch")
        self.assertNotContains(resp_sup, "Unknown Origin Lamp")
        self.assertContains(resp_sup, "product-card-provider-badge")
        self.assertNotContains(resp_sup, "400.00")

        # Filter by none -> shows Unknown Origin Lamp
        resp_none = self.client.get(f"{reverse('inventory:dashboard')}?provider=none")
        self.assertContains(resp_none, "Unknown Origin Lamp")
        self.assertNotContains(resp_none, "Pallet Monitor")
        self.assertNotContains(resp_none, "Walkin Watch")

        # Filter by walk-in provider -> zero acquisition_cost leaked
        resp_walkin = self.client.get(f"{reverse('inventory:dashboard')}?provider={self.walkin.pk}")
        self.assertContains(resp_walkin, "Walkin Watch")
        self.assertNotContains(resp_walkin, "65.00")

        # Global search matches provider name
        resp_q = self.client.get(f"{reverse('inventory:dashboard')}?q=IberiaLiquida")
        self.assertContains(resp_q, "Pallet Monitor")
        self.assertNotContains(resp_q, "Walkin Watch")

        # Composable ?pallet=10&provider=<walkin.pk> yields empty cleanly
        resp_combo = self.client.get(
            f"{reverse('inventory:dashboard')}?pallet={self.pallet.pk}&provider={self.walkin.pk}"
        )
        self.assertNotContains(resp_combo, "Pallet Monitor")
        self.assertNotContains(resp_combo, "Walkin Watch")

    def test_storefront_firewall_never_exposes_provider_pallet_or_cost(self):
        cfg = StorefrontConfiguration.get_solo()
        cfg.storefront_enabled = True
        cfg.save()
        self.prod_walkin.status = ProductStatus.READY
        self.prod_walkin.save()

        resp_list = self.client.get(reverse("storefront:catalog"))
        self.assertEqual(resp_list.status_code, 200)
        self.assertContains(resp_list, "Walkin Watch")
        self.assertNotContains(resp_list, "Compra en Tienda / Particular")
        self.assertNotContains(resp_list, "65.00")

        resp_detail = self.client.get(
            reverse(
                "storefront:product_detail",
                kwargs={"slug": "walkin-watch", "pk": self.prod_walkin.pk},
            ),
            follow=True,
        )
        self.assertEqual(resp_detail.status_code, 200)
        self.assertNotContains(resp_detail, "Compra en Tienda / Particular")
        self.assertNotContains(resp_detail, "65.00")

    def test_bilingual_spanish_translations(self):
        self.client.force_login(self.manager)
        self.client.cookies["django_language"] = "es"
        with translation.override("es"):
            resp_hub = self.client.get(
                f"{reverse('inventory:pallets')}?tab=providers",
                headers={"Accept-Language": "es"},
            )
            self.assertContains(resp_hub, "Proveedores")
            self.assertContains(resp_hub, "Registrar Nuevo Proveedor")

            resp_intake = self.client.get(reverse("inventory:intake"), headers={"Accept-Language": "es"})
            self.assertContains(resp_intake, "Origen del producto")
            self.assertContains(resp_intake, "Orígenes Directos (Sin Palet)")

            resp_dash = self.client.get(reverse("inventory:dashboard"), headers={"Accept-Language": "es"})
            self.assertContains(resp_dash, "Todos los proveedores")
