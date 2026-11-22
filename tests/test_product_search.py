from decimal import Decimal

from django.contrib.auth import get_user_model
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
from inventory.services.search_service import (
    build_search_query,
    fold_search_text,
    sqlite_unaccent_like,
    tokenize_search_query,
)
from tests.helpers import create_role_users

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

    def test_tokenize_search_query_handles_spaced_shorthands_and_currency(self):
        self.assertEqual(tokenize_search_query("<20 €"), ["<20"])
        self.assertEqual(tokenize_search_query("> 50"), [">50"])
        self.assertEqual(tokenize_search_query("<= 15,50 €"), ["<=15,50"])
        self.assertEqual(tokenize_search_query("15..50 €"), ["15..50"])
        self.assertEqual(tokenize_search_query("15 - 50€"), ["15-50€"])
        self.assertEqual(tokenize_search_query("15 - 50 €"), ["15-50€"])
        self.assertEqual(tokenize_search_query("Ref: 42"), ["ref:42"])
        self.assertEqual(tokenize_search_query("# 42"), ["#42"])
        self.assertEqual(tokenize_search_query("Pallet 5"), ["pallet:5"])
        self.assertEqual(tokenize_search_query("Palé 5"), ["pallet:5"])
        # Quoted phrases and year-month tokens must stay intact
        self.assertEqual(tokenize_search_query('"Ref: 42" Ref: 7'), ["Ref: 42", "ref:7"])
        self.assertEqual(tokenize_search_query("2026-10"), ["2026-10"])


class ProductSearchIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager, cls.assistant = create_role_users(prefix="search")
        cls.manager.is_staff = True
        cls.manager.save(update_fields=["is_staff"])

        cls.cat_tech, _ = Category.objects.get_or_create(
            slug="tecnologia-y-electronica",
            defaults={
                "name": "Tecnología y electrónica",
                "name_en": "Tech & Electronics",
                "is_active": True,
            },
        )
        cls.cat_kids, _ = Category.objects.get_or_create(
            slug="ninos-y-bebes",
            defaults={
                "name": "Niños y bebés",
                "name_en": "Kids & Babies",
                "is_active": True,
            },
        )

        cls.provider = Provider.objects.create(
            name="LiquiStock Camiones Valencia",
            provider_type=ProviderType.WHOLESALER,
        )
        cls.pallet = Pallet.objects.create(
            number=77,
            provider=cls.provider,
            notes="Lote especial herramientas eléctricas bricolaje",
        )
        cls.wallapop, _ = MarketplaceSite.objects.get_or_create(
            slug="wallapop",
            defaults={"name": "Wallapop", "base_url": "https://es.wallapop.com", "is_active": True},
        )

        cls.p_camera = Product.objects.create(
            ai_title="CÁMARA Réflex Canon EOS 2000D",
            ai_description="Cámara fotográfica con batería original y cargador.",
            raw_note="Número de serie SN-998877 impecable",
            sale_price=Decimal("240.00"),
            category=cls.cat_tech,
            is_public=True,
        )
        cls.p_drill = Product.objects.create(
            ai_title="Taladro percutor profesional Bosch 18V",
            ai_description="Incluye maletín y dos baterías de litio.",
            raw_note="Revisado en taller",
            sale_price=Decimal("45.00"),
            pallet=cls.pallet,
            category=cls.cat_tech,
            is_public=True,
        )
        cls.p_kids = Product.objects.create(
            ai_title="Carrito de paseo plegable para niño",
            ai_description="Silla ligera en muy buen estado.",
            raw_note="Capota azul marino",
            sale_price=Decimal("18.00"),
            category=cls.cat_kids,
            is_public=True,
        )

        ProductClarification.objects.create(
            product=cls.p_drill,
            category=ClarificationCategory.MEASUREMENTS,
            question="¿Qué voltaje y amperaje tiene?",
            answer="Batería de 4.0Ah comprobada",
            asked_by=cls.manager,
            answered_by=cls.manager,
            status=ClarificationStatus.RESOLVED,
        )
        ProductClarification.objects.create(
            product=cls.p_drill,
            category=ClarificationCategory.TAG_COMPOSITION,
            question="¿Referencia exacta del modelo?",
            answer="Modelo GSB-18V-21",
            asked_by=cls.manager,
            answered_by=cls.manager,
            status=ClarificationStatus.RESOLVED,
        )

        ProductListingLink.objects.create(
            product=cls.p_camera,
            site=cls.wallapop,
            url="https://es.wallapop.com/item/camara-canon-eos-991122",
            is_active=True,
        )

        cls.dashboard_url = reverse("inventory:dashboard")
        cls.storefront_url = reverse("storefront:catalog")

    def setUp(self):
        self.client.force_login(self.manager)

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

    def test_spaced_shorthands_end_to_end_matching(self):
        self.assertEqual(list(Product.objects.filter(build_search_query("<20 €"))), [self.p_kids])
        self.assertEqual(list(Product.objects.filter(build_search_query("> 200"))), [self.p_camera])
        self.assertEqual(list(Product.objects.filter(build_search_query("40..50 €"))), [self.p_drill])
        self.assertEqual(list(Product.objects.filter(build_search_query("40 - 50€"))), [self.p_drill])
        self.assertEqual(list(Product.objects.filter(build_search_query("40 - 50 €"))), [self.p_drill])
        self.assertEqual(list(Product.objects.filter(build_search_query(f"Ref: {self.p_camera.pk}"))), [self.p_camera])
        self.assertEqual(list(Product.objects.filter(build_search_query(f"# {self.p_camera.pk}"))), [self.p_camera])
        self.assertEqual(list(Product.objects.filter(build_search_query("Pallet 77"))), [self.p_drill])
        self.assertEqual(list(Product.objects.filter(build_search_query("Palé 77"))), [self.p_drill])

    def test_quoted_phrase_requires_contiguous_words(self):
        self.assertEqual(list(Product.objects.filter(build_search_query('"taladro percutor"'))), [self.p_drill])
        self.assertEqual(list(Product.objects.filter(build_search_query('"taladro bosch"'))), [])

    def test_four_digit_pk_matches_by_pk_without_date_collision(self):
        p_2025 = Product.objects.create(
            pk=2025,
            ai_title="Mesa roble macizo",
            ai_description="Mesa de comedor clásica.",
            raw_note="Nota mesa",
            sale_price=Decimal("120.00"),
            category=self.cat_tech,
        )
        self.assertIn(p_2025, Product.objects.filter(build_search_query("2025")))

    def test_inactive_marketplace_listing_link_excluded_from_search(self):
        ProductListingLink.objects.create(
            product=self.p_drill,
            site=self.wallapop,
            url="https://es.wallapop.com/item/inactive-link-887766",
            is_active=False,
        )
        self.assertEqual(list(Product.objects.filter(build_search_query("887766"))), [])

    def test_assistant_cross_tab_recovery_excludes_erased_tab(self):
        self.p_drill.soft_delete(user=self.manager)

        asst_client = Client()
        asst_client.force_login(self.assistant)
        resp = asst_client.get(self.dashboard_url, {"status": "all", "q": "taladro"})
        self.assertEqual(resp.status_code, 200)
        other_statuses = [t["status"] for t in resp.context["search_other_tabs"]]
        self.assertNotIn("erased", other_statuses)
        self.assertNotContains(resp, "status=erased")

    def test_cross_tab_recovery_pills_do_not_carry_compliance_filter(self):
        self.p_kids.is_sold = True
        self.p_kids.sold_channel_type = SaleChannelType.IN_STORE
        self.p_kids.save()

        resp = self.client.get(
            self.dashboard_url,
            {"status": "ready", "q": "nino", "compliance": "flagged"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="searchCrossTabRecovery"')
        content = resp.content.decode("utf-8")
        recovery_section = content.split('id="searchCrossTabRecovery"', 1)[1].split("</div>\n    </div>", 1)[0]
        self.assertNotIn("compliance=flagged", recovery_section)

    def test_strict_orm_lookups_preserve_accents_outside_search(self):
        # Standard Django __iexact and __icontains must NOT strip accents globally on SQLite
        self.assertFalse(Category.objects.filter(name__iexact="tecnologia y electronica").exists())
        self.assertFalse(Category.objects.filter(name__icontains="tecnologia").exists())
        # Scoped search lookup and build_search_query remain accent-insensitive
        self.assertTrue(Category.objects.filter(name__unaccent_icontains="tecnologia").exists())
        self.assertIn(self.p_camera, Product.objects.filter(build_search_query("tecnologia")))


class SearchServiceTests(TestCase):
    def test_empty_query_returns_empty_q(self):
        q = build_search_query("")
        self.assertEqual(len(q.children), 0)

        q_whitespace = build_search_query("   ")
        self.assertEqual(len(q_whitespace.children), 0)

    def test_text_query_structure(self):
        q = build_search_query("vintage denim")
        # Should contain ai_title, raw_note, ai_description unaccent_icontains lookups
        self.assertTrue(any("ai_title__unaccent_icontains" in str(child) for child in q.children))
        self.assertTrue(any("raw_note__unaccent_icontains" in str(child) for child in q.children))
        self.assertTrue(any("ai_description__unaccent_icontains" in str(child) for child in q.children))

    def test_iso_date_query_structure(self):
        q = build_search_query("2026-10-10")
        q_str = str(q)
        self.assertIn("created_at__date", q_str)
        self.assertIn("sold_at__date", q_str)

    def test_slashed_date_query_structure(self):
        q = build_search_query("10/10/2026")
        q_str = str(q)
        self.assertIn("created_at__date", q_str)
        self.assertIn("sold_at__date", q_str)

    def test_year_month_query_structure(self):
        q = build_search_query("2026-10")
        q_str = str(q)
        self.assertIn("created_at__year", q_str)
        self.assertIn("created_at__month", q_str)

    def test_four_digit_year_query_structure(self):
        q = build_search_query("2026")
        q_str = str(q)
        self.assertIn("created_at__year", q_str)
