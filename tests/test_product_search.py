from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from inventory.models import (
    Category,
    ClarificationCategory,
    ClarificationStatus,
    MarketplaceSite,
    Pallet,
    Product,
    ProductClarification,
    ProductListingLink,
    Provider,
    ProviderType,
    SaleChannelType,
)
from inventory.permissions import ROLE_ASSISTANT, ROLE_MANAGER
from inventory.services.search_service import (
    build_search_query,
    fold_search_text,
    sqlite_unaccent_like,
    tokenize_search_query,
)

User = get_user_model()


class SearchServiceUnitTests(TestCase):
    def test_fold_search_text_handles_accents_and_unicode_case(self):
        self.assertEqual(fold_search_text("CÁMARA Réflex Niño Pingüino"), "camara reflex nino pinguino")
        self.assertEqual(fold_search_text("camara reflex nino pinguino"), "camara reflex nino pinguino")
        self.assertEqual(fold_search_text("ESPAÑA ÁÉÍÓÚÜÑ"), "espana aeiouun")

    def test_sqlite_unaccent_like_fast_and_wildcard_paths(self):
        self.assertTrue(sqlite_unaccent_like("%camara%", "CÁMARA Digital Sony", "\\"))
        self.assertTrue(sqlite_unaccent_like("%CÁMARA%", "cámara digital sony", "\\"))
        self.assertTrue(sqlite_unaccent_like("%nino%", "Bicicleta NIÑO 20", "\\"))
        self.assertTrue(sqlite_unaccent_like("camara_digital%", "Cámara-Digital", "\\"))
        self.assertTrue(sqlite_unaccent_like("%100\\% algodon%", "Camiseta 100% ALGODÓN orgánico", "\\"))
        self.assertFalse(sqlite_unaccent_like("%lavadora%", "Frigorífico Bosch", "\\"))

    def test_tokenize_search_query_normalizes_shorthands_and_quotes(self):
        self.assertEqual(tokenize_search_query("Ref. #0042"), ["ref:0042"])
        self.assertEqual(tokenize_search_query("Palé #7 bosch"), ["pallet:7", "bosch"])
        self.assertEqual(
            tokenize_search_query('taladro "percutor profesional" <50'),
            ["taladro", "percutor profesional", "<50"],
        )


class ProductSearchIntegrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.manager_group, _ = Group.objects.get_or_create(name=ROLE_MANAGER)
        self.asst_group, _ = Group.objects.get_or_create(name=ROLE_ASSISTANT)

        self.manager = User.objects.create_user(
            username="search_manager", password="password123", is_staff=True
        )
        self.manager.groups.add(self.manager_group)

        self.cat_tech, _ = Category.objects.get_or_create(
            slug="tecnologia-y-electronica",
            defaults={
                "name": "Tecnología y electrónica",
                "name_en": "Tech & Electronics",
                "is_active": True,
            },
        )
        self.cat_kids, _ = Category.objects.get_or_create(
            slug="ninos-y-bebes",
            defaults={
                "name": "Niños y bebés",
                "name_en": "Kids & Babies",
                "is_active": True,
            },
        )

        self.provider = Provider.objects.create(
            name="LiquiStock Camiones Valencia",
            provider_type=ProviderType.WHOLESALER,
        )
        self.pallet = Pallet.objects.create(
            number=77,
            provider=self.provider,
            notes="Lote especial herramientas eléctricas bricolaje",
        )
        self.wallapop, _ = MarketplaceSite.objects.get_or_create(
            slug="wallapop",
            defaults={"name": "Wallapop", "base_url": "https://es.wallapop.com", "is_active": True},
        )

        self.p_camera = Product.objects.create(
            ai_title="CÁMARA Réflex Canon EOS 2000D",
            ai_description="Cámara fotográfica con batería original y cargador.",
            raw_note="Número de serie SN-998877 impecable",
            sale_price=Decimal("240.00"),
            category=self.cat_tech,
            is_public=True,
        )
        self.p_drill = Product.objects.create(
            ai_title="Taladro percutor profesional Bosch 18V",
            ai_description="Incluye maletín y dos baterías de litio.",
            raw_note="Revisado en taller",
            sale_price=Decimal("45.00"),
            pallet=self.pallet,
            category=self.cat_tech,
            is_public=True,
        )
        self.p_kids = Product.objects.create(
            ai_title="Carrito de paseo plegable para niño",
            ai_description="Silla ligera en muy buen estado.",
            raw_note="Capota azul marino",
            sale_price=Decimal("18.00"),
            category=self.cat_kids,
            is_public=True,
        )

        # Attach multiple clarifications to p_drill to test 1-to-N Exists subquery and AND logic
        ProductClarification.objects.create(
            product=self.p_drill,
            category=ClarificationCategory.MEASUREMENTS,
            question="¿Qué voltaje y amperaje tiene?",
            answer="Batería de 4.0Ah comprobada",
            asked_by=self.manager,
            answered_by=self.manager,
            status=ClarificationStatus.RESOLVED,
        )
        ProductClarification.objects.create(
            product=self.p_drill,
            category=ClarificationCategory.TAG_COMPOSITION,
            question="¿Referencia exacta del modelo?",
            answer="Modelo GSB-18V-21",
            asked_by=self.manager,
            answered_by=self.manager,
            status=ClarificationStatus.RESOLVED,
        )

        # Attach marketplace link to p_camera
        ProductListingLink.objects.create(
            product=self.p_camera,
            site=self.wallapop,
            url="https://es.wallapop.com/item/camara-canon-eos-991122",
            is_active=True,
        )

        self.dashboard_url = reverse("inventory:dashboard")
        self.storefront_url = reverse("storefront:catalog")
        self.client.login(username="search_manager", password="password123")

    def test_spanish_accents_and_uppercase_lowercase_variants(self):
        for query in ["camara", "cámara", "CÁMARA", "CAMARA", "reflex", "RÉFLEX", "bateria", "BATERÍA"]:
            with self.subTest(query=query):
                qs = Product.objects.filter(build_search_query(query))
                self.assertIn(self.p_camera, qs)

        for nino_query in ["nino", "niño", "NIÑO", "NINO"]:
            with self.subTest(query=nino_query):
                qs = Product.objects.filter(build_search_query(nino_query))
                self.assertIn(self.p_kids, qs)

    def test_multi_word_out_of_order_and_cross_field_matching(self):
        # Non-adjacent words in title
        qs1 = Product.objects.filter(build_search_query("taladro bosch"))
        self.assertEqual(list(qs1), [self.p_drill])

        # Reversed word order
        qs2 = Product.objects.filter(build_search_query("18v bosch taladro"))
        self.assertEqual(list(qs2), [self.p_drill])

        # Cross-field match: one word in ai_title ("Canon"), one word in raw_note ("SN-998877")
        qs3 = Product.objects.filter(build_search_query("canon sn-998877"))
        self.assertEqual(list(qs3), [self.p_camera])

        # Cross-clarification match without row duplication
        qs4 = Product.objects.filter(build_search_query("4.0Ah GSB-18V-21"))
        self.assertEqual(list(qs4), [self.p_drill])
        self.assertEqual(qs4.count(), 1)

    def test_internal_field_coverage_and_smart_shorthands(self):
        # Exact ID / Reference shorthands
        for ref_q in [f"#{self.p_camera.pk}", f"ref:{self.p_camera.pk}", f"Ref. #{self.p_camera.pk:04d}"]:
            qs = Product.objects.filter(build_search_query(ref_q))
            self.assertEqual(list(qs), [self.p_camera])

        # Pallet shorthands and pallet notes
        for pal_q in ["pale:77", "pallet:77", "Pallet #77", "bricolaje"]:
            qs = Product.objects.filter(build_search_query(pal_q))
            self.assertEqual(list(qs), [self.p_drill])

        # Category name (ES & EN, accent-insensitive)
        self.assertIn(self.p_camera, Product.objects.filter(build_search_query("tecnologia")))
        self.assertIn(self.p_camera, Product.objects.filter(build_search_query("Electronics")))

        # Marketplace link URL / site name
        self.assertEqual(list(Product.objects.filter(build_search_query("991122"))), [self.p_camera])

        # Sold channel notes
        self.p_kids.is_sold = True
        self.p_kids.sold_channel_type = SaleChannelType.IN_STORE
        self.p_kids.sold_channel_notes = "Ticket #TCK-5544"
        self.p_kids.save()
        self.assertEqual(list(Product.objects.filter(build_search_query("TCK-5544"))), [self.p_kids])

        # Price shorthands
        self.assertEqual(list(Product.objects.filter(build_search_query("<20"))), [self.p_kids])
        self.assertEqual(list(Product.objects.filter(build_search_query("40..50"))), [self.p_drill])
        self.assertEqual(list(Product.objects.filter(build_search_query(">200"))), [self.p_camera])

    def test_dashboard_tab_counts_scoped_to_search_and_cross_tab_recovery(self):
        # Mark p_kids as sold and soft-delete p_drill
        self.p_kids.is_sold = True
        self.p_kids.sold_channel_type = SaleChannelType.IN_STORE
        self.p_kids.save()
        self.p_drill.soft_delete(user=self.manager)

        # Search for "nino" while on "ready" tab -> 0 results in ready, 1 in sold / all
        resp = self.client.get(self.dashboard_url, {"status": "ready", "q": "nino"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context["products"]), 0)
        self.assertEqual(resp.context["ready_count"], 0)
        self.assertEqual(resp.context["sold_count"], 1)
        self.assertEqual(resp.context["total_count"], 1)

        other_statuses = [t["status"] for t in resp.context["search_other_tabs"]]
        self.assertIn("all", other_statuses)
        self.assertIn("sold", other_statuses)
        self.assertContains(resp, 'id="searchCrossTabRecovery"')

        # Search for "taladro" on "all" tab -> 0 in active catalog, 1 in Trash ("erased")
        resp_trash = self.client.get(self.dashboard_url, {"status": "all", "q": "taladro"})
        self.assertEqual(resp_trash.status_code, 200)
        self.assertEqual(resp_trash.context["total_count"], 0)
        self.assertEqual(resp_trash.context["erased_count"], 1)
        trash_tabs = [t["status"] for t in resp_trash.context["search_other_tabs"]]
        self.assertIn("erased", trash_tabs)

    def test_public_storefront_search_forgiving_and_firewall_isolated(self):
        # Public search finds camera with unaccented multi-word out-of-order query
        resp = self.client.get(self.storefront_url, {"q": "canon camara"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn(self.p_camera, resp.context["products"])

        # Public search NEVER leaks internal fields (raw_note, provider, pallet, clarifications)
        for secret_query in [
            "SN-998877",               # raw_note
            "LiquiStock",              # provider__name
            "bricolaje",               # pallet__notes
            "pale:77",                 # pallet shorthand
            "GSB-18V-21",              # clarification answer
        ]:
            with self.subTest(secret_query=secret_query):
                resp_sec = self.client.get(self.storefront_url, {"q": secret_query})
                self.assertEqual(resp_sec.status_code, 200)
                self.assertEqual(len(resp_sec.context["products"]), 0)
