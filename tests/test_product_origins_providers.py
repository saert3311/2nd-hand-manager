import datetime
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import translation
from playwright.sync_api import expect

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
from tests.helpers import (
    create_user_with_group,
    goto_authenticated,
    login_in_browser,
    make_test_image_file,
    open_browser_page,
    start_shared_browser,
)

User = get_user_model()


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

    def test_pallet_save_update_fields_without_provider_does_not_cascade(self):
        p1 = Provider.objects.create(name="OrigSup", provider_type=ProviderType.WHOLESALER)
        p2 = Provider.objects.create(name="OtherSup", provider_type=ProviderType.WHOLESALER)
        pallet = Pallet.objects.create(number=404, received_date=datetime.date(2026, 10, 4), provider=p1)
        prod = Product.objects.create(raw_note="Pallet unit", pallet=pallet)

        pallet.provider = p2
        pallet.purchase_price = Decimal("150.00")
        pallet.save(update_fields=["purchase_price"])

        pallet.refresh_from_db()
        prod.refresh_from_db()
        self.assertEqual(pallet.provider, p1)
        self.assertEqual(prod.provider, p1)

    def test_pallet_save_cascade_is_atomic_on_db_failure(self):
        p1 = Provider.objects.create(name="AtomicSup1", provider_type=ProviderType.WHOLESALER)
        p2 = Provider.objects.create(name="AtomicSup2", provider_type=ProviderType.WHOLESALER)
        pallet = Pallet.objects.create(number=405, received_date=datetime.date(2026, 10, 4), provider=p1)
        prod = Product.objects.create(raw_note="Atomic item", pallet=pallet)

        pallet.provider = p2
        with patch("django.db.models.query.QuerySet.update", side_effect=DatabaseError("Simulated update failure")):
            with self.assertRaises(DatabaseError):
                pallet.save()

        pallet.refresh_from_db()
        prod.refresh_from_db()
        self.assertEqual(pallet.provider, p1)
        self.assertEqual(prod.provider, p1)

    def test_product_save_unrelated_update_fields_skips_pallet_query(self):
        sup = Provider.objects.create(name="QuerySup", provider_type=ProviderType.WHOLESALER)
        pallet = Pallet.objects.create(number=406, received_date=datetime.date(2026, 10, 4), provider=sup)
        created = Product.objects.create(ai_title="Sync item", pallet=pallet)

        fresh = Product.objects.get(pk=created.pk)
        fresh.needs_platform_sync = True
        with CaptureQueriesContext(connection) as ctx:
            fresh.save(update_fields=["needs_platform_sync"], skip_auto_compliance=True)

        sql_statements = " ".join(q["sql"].lower() for q in ctx.captured_queries)
        self.assertNotIn("inventory_pallet", sql_statements)


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
        self.assertNotIn("pallet_est_value_total", stats)


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
                "images": make_test_image_file("tv.jpg", color=(40, 140, 90)),
            },
        )
        self.assertEqual(resp_post1.status_code, 302)
        p1 = Product.objects.get(raw_note="Sony TV pallet unit")
        self.assertEqual(p1.pallet, self.pallet)
        self.assertEqual(p1.provider, self.wholesaler)
        self.assertEqual(self.client.session.get("last_intake_origin"), f"pallet:{self.pallet.pk}")
        self.assertNotIn("last_intake_pallet_id", self.client.session)

        # Next GET pre-selects pallet:<id>
        form = ProductIntakeForm(initial={"origin": self.client.session.get("last_intake_origin")})
        self.assertEqual(form.initial["origin"], f"pallet:{self.pallet.pk}")

        # Step 2: Switch to direct walk-in provider -> clears pallet, updates sticky origin
        resp_post2 = self.client.post(
            reverse("inventory:intake"),
            {
                "origin": f"provider:{self.walkin.pk}",
                "raw_note": "Walk-in acoustic guitar",
                "images": make_test_image_file("guitar.jpg", color=(40, 140, 90)),
            },
        )
        self.assertEqual(resp_post2.status_code, 302)
        p2 = Product.objects.get(raw_note="Walk-in acoustic guitar")
        self.assertIsNone(p2.pallet)
        self.assertEqual(p2.provider, self.walkin)
        self.assertEqual(self.client.session.get("last_intake_origin"), f"provider:{self.walkin.pk}")
        self.assertNotIn("last_intake_pallet_id", self.client.session)

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

    def test_product_detail_post_assigns_pallet_and_syncs_provider(self):
        standalone = Product.objects.create(
            ai_title="Monitor Standalone",
            ai_description="24 inch",
            sale_price=Decimal("120.00"),
            provider=self.walkin,
        )
        self.client.force_login(self.manager)
        # Simulates disabled #id_provider (omitted from POST) when pallet is selected
        resp = self.client.post(
            reverse("inventory:product_detail", kwargs={"pk": standalone.pk}),
            {
                "ai_title": "Monitor Standalone",
                "ai_description": "24 inch",
                "sale_price": "120.00",
                "pallet": str(self.pallet.pk),
            },
        )
        self.assertEqual(resp.status_code, 302)
        standalone.refresh_from_db()
        self.assertEqual(standalone.pallet, self.pallet)
        self.assertEqual(standalone.provider, self.wholesaler)


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

    def test_provider_create_invalid_post_stays_on_providers_tab(self):
        self.client.force_login(self.manager)
        resp = self.client.post(
            reverse("inventory:provider_create"),
            {"name": "IberiaLiquida", "provider_type": ProviderType.WHOLESALER},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["active_tab"], "providers")
        self.assertTrue(resp.context["provider_form"].errors)
        self.assertContains(resp, 'role="alert"')

    def test_pallet_edit_post_cascades_provider_to_products(self):
        new_sup = Provider.objects.create(name="CascadePostSup", provider_type=ProviderType.WHOLESALER)
        self.client.force_login(self.manager)
        resp = self.client.post(
            reverse("inventory:pallet_edit", kwargs={"pk": self.pallet.pk}),
            {
                "number": str(self.pallet.number),
                "provider": str(new_sup.pk),
                "received_date": "2026-10-10",
                "purchase_price": "400.00",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.prod_pallet.refresh_from_db()
        self.assertEqual(self.prod_pallet.provider, new_sup)

    def test_sanitize_public_product_clears_prefetched_fields_cache(self):
        from storefront.views import _sanitize_public_product

        fetched = Product.objects.select_related("provider", "pallet").get(pk=self.prod_pallet.pk)
        sanitized = _sanitize_public_product(fetched)
        self.assertIsNone(sanitized.provider_id)
        self.assertIsNone(sanitized.pallet_id)
        self.assertIsNone(sanitized.provider)
        self.assertIsNone(sanitized.pallet)
        self.assertIsNone(sanitized.acquisition_cost)

    def test_dashboard_tab_counts_match_scoped_provider_filter(self):
        self.client.force_login(self.manager)
        resp = self.client.get(f"{reverse('inventory:dashboard')}?provider={self.supplier.pk}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["total_count"], 1)
        self.assertEqual(resp.context["ready_count"], 1)


@override_settings(TURNSTILE_ENABLED=False)
class OriginInteractiveBrowserTests(StaticLiveServerTestCase):
    """Browser TDD tests for Origin Provider locking on /products/<pk>/ and shared delete modal on /pallets/."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._browser = start_shared_browser(cls)

    def setUp(self):
        self.manager = create_user_with_group("mgr_browser_origin", password="pw", group_name="managers")
        self.supplier = Provider.objects.create(name="BrowserSup", provider_type=ProviderType.WHOLESALER)
        self.pallet = Pallet.objects.create(
            number=77,
            received_date=datetime.date(2026, 10, 10),
            purchase_price=Decimal("300.00"),
            provider=self.supplier,
        )
        self.pallet_product = Product.objects.create(
            ai_title="Browser Pallet Camera",
            ai_description="Clean lens",
            sale_price=Decimal("90.00"),
            pallet=self.pallet,
        )

    def test_product_detail_locks_provider_while_pallet_selected_and_unlocks_on_clear(self):
        with open_browser_page(self._browser, self) as (_context, page):
            login_in_browser(page, self.live_server_url, "mgr_browser_origin", "pw")
            goto_authenticated(
                page,
                f"{self.live_server_url}{reverse('inventory:product_detail', kwargs={'pk': self.pallet_product.pk})}",
            )
            expect(page.locator("#id_provider")).to_be_visible()

            provider_select = page.locator("#id_provider")
            pallet_select = page.locator("#id_pallet")
            self.assertTrue(provider_select.is_disabled())

            # Clearing pallet unlocks provider selector
            pallet_select.select_option("")
            self.assertFalse(provider_select.is_disabled())

            # Selecting pallet again locks provider and syncs its value
            pallet_select.select_option(str(self.pallet.pk))
            self.assertTrue(provider_select.is_disabled())
            self.assertEqual(provider_select.input_value(), str(self.supplier.pk))

    def test_pallets_hub_shared_delete_modal_works_for_pallet_and_provider(self):
        with open_browser_page(self._browser, self) as (_context, page):
            login_in_browser(page, self.live_server_url, "mgr_browser_origin", "pw")
            goto_authenticated(page, f"{self.live_server_url}{reverse('inventory:pallets')}")
            expect(page.locator(f"#pallet-card-{self.pallet.pk}")).to_be_visible()

            page.locator(f"#pallet-card-{self.pallet.pk} button").first.click()
            modal = page.locator("#deleteOriginModal")
            self.assertTrue(modal.is_visible())
            self.assertIn("Pallet #77", page.locator("#deleteOriginModalWarning").inner_text())
            page.locator("#deleteOriginModal button:has-text('Cancel')").first.click()
            self.assertFalse(modal.is_visible())

            page.locator("#tabBtnProviders").click()
            page.locator(f"#provider-card-{self.supplier.pk} button").first.click()
            self.assertTrue(modal.is_visible())
            self.assertIn("BrowserSup", page.locator("#deleteOriginModalWarning").inner_text())
            page.locator("#deleteOriginModal button:has-text('Cancel')").first.click()
            self.assertFalse(modal.is_visible())
