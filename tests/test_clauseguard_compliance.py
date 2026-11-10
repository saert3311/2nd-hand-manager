from io import StringIO
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from inventory.models import (
    ComplianceStage,
    ComplianceVerdict,
    MarketplaceSite,
    PolicyClause,
    PolicySeverity,
    Product,
    ProductStatus,
)
from inventory.permissions import ROLE_ASSISTANT, ROLE_MANAGER
from inventory.services.ai_service import (
    IntakePreflightSchema,
    ProductListingSchema,
    identify_intake_product,
)
from inventory.services.compliance_service import (
    ExtractedClauseSchema,
    ExtractedPolicyClausesSchema,
    TargetedComplianceCheckSchema,
    cosine_similarity,
    ensure_default_policy_clauses,
    evaluate_stage1_local,
    sync_site_policy,
)

User = get_user_model()


def _create_dummy_image_bytes() -> bytes:
    buf = __import__("io").BytesIO()
    img = Image.new("RGB", (120, 120), color="navy")
    img.save(buf, format="JPEG")
    return buf.getvalue()


class ClauseGuardComplianceTests(TestCase):
    def setUp(self):
        ensure_default_policy_clauses()
        self.mgr_group, _ = Group.objects.get_or_create(name=ROLE_MANAGER)
        self.asst_group, _ = Group.objects.get_or_create(name=ROLE_ASSISTANT)

        self.manager = User.objects.create_user(
            username="cg_manager",
            password="password123",
            is_staff=True,
        )
        self.manager.groups.add(self.mgr_group)

        self.assistant = User.objects.create_user(
            username="cg_assistant",
            password="password123",
        )
        self.assistant.groups.add(self.asst_group)

    def test_default_policy_clauses_seeded_with_vectors(self):
        self.assertGreaterEqual(PolicyClause.objects.count(), 12)
        glb = PolicyClause.objects.get(code="GLB-101")
        self.assertIsNone(glb.site)
        self.assertEqual(glb.severity, PolicySeverity.CRITICAL)
        self.assertTrue(len(glb.embedding_vector) > 0)

        vinted = MarketplaceSite.objects.get(slug="vinted")
        self.assertTrue(vinted.policy_url.startswith("https://"))
        self.assertTrue(PolicyClause.objects.filter(code="VT-202", site=vinted).exists())

    def test_stage1_safe_product_short_circuits_with_zero_tokens(self):
        res = evaluate_stage1_local(
            title="Chaqueta vaquera Levi's 501 talla M",
            description="Buen estado general, tejido denim resistente.",
            raw_note="Chaqueta denim clásica azul",
        )
        self.assertEqual(res["verdict"], ComplianceVerdict.APPROVED)
        self.assertEqual(res["stage"], ComplianceStage.STAGE_1_SAFE)
        self.assertLessEqual(len(res["top_clauses"]), 3)
        telemetry = res["report"]["telemetry"]
        self.assertEqual(telemetry["tokens_used"], 0)
        self.assertEqual(telemetry["tokens_saved_percent"], 100.0)
        self.assertGreaterEqual(telemetry["naive_baseline_tokens"], 12000)

    def test_stage1_global_critical_violation_blocks_all_platforms_advisory(self):
        product = Product.objects.create(
            raw_note="Bolso lujo réplica exacta calidad 1:1 sin caja",
            created_by=self.assistant,
        )
        self.assertEqual(product.compliance_status, ComplianceVerdict.REJECTED)
        self.assertEqual(product.compliance_stage, ComplianceStage.STAGE_1_LEXICAL)
        self.assertGreaterEqual(product.compliance_risk_score, 85)
        # Advisory only: Product.status remains DRAFT, not forcefully BLOCKED
        self.assertEqual(product.status, ProductStatus.DRAFT)
        codes = [m["code"] for m in product.compliance_matched_clauses]
        self.assertIn("GLB-103", codes)
        matrix = product.compliance_report["platform_matrix"]
        self.assertEqual(matrix["wallapop"]["status"], ComplianceVerdict.REJECTED)
        self.assertEqual(matrix["vinted"]["status"], ComplianceVerdict.REJECTED)
        self.assertEqual(matrix["rapido-pack"]["status"], ComplianceVerdict.REJECTED)

    def test_stage1_platform_specific_restriction_vinted_vs_wallapop(self):
        product = Product.objects.create(
            raw_note="Taladro percutor Bosch profesional 800W con maletín",
            created_by=self.assistant,
        )
        self.assertEqual(product.compliance_status, ComplianceVerdict.MANUAL_REVIEW)
        matrix = product.compliance_report["platform_matrix"]
        self.assertEqual(matrix["vinted"]["status"], ComplianceVerdict.MANUAL_REVIEW)
        self.assertIn("VT-202", matrix["vinted"]["clauses"])
        self.assertEqual(matrix["wallapop"]["status"], ComplianceVerdict.APPROVED)
        self.assertEqual(matrix["rapido-pack"]["status"], ComplianceVerdict.APPROVED)

    def test_manual_edit_re_evaluates_stage1_and_status_save_preserves_stage2(self):
        product = Product.objects.create(
            raw_note="Sudadera algodón azul marino",
            created_by=self.assistant,
        )
        self.assertEqual(product.compliance_status, ComplianceVerdict.APPROVED)

        # Manual edit introducing prohibited term automatically updates compliance
        product.ai_title = "Pistola airsoft eléctrica réplica M4"
        product.save()
        product.refresh_from_db()
        self.assertEqual(product.compliance_status, ComplianceVerdict.REJECTED)
        self.assertEqual(product.compliance_stage, ComplianceStage.STAGE_1_LEXICAL)

        # Simulate Stage 2 save + unrelated status update
        product.compliance_stage = ComplianceStage.STAGE_2_PIGGYBACK
        product.save(
            skip_auto_compliance=True,
            update_fields=["compliance_stage"],
        )
        product.status = ProductStatus.BLOCKED
        product.save(update_fields=["status"])
        product.refresh_from_db()
        self.assertEqual(product.compliance_stage, ComplianceStage.STAGE_2_PIGGYBACK)

    @override_settings(GEMINI_API_KEY="test-key")
    @patch("inventory.services.ai_service.genai.Client")
    def test_intake_identify_piggybacks_top3_clauses_and_visual_warnings(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.usage_metadata = MagicMock(total_token_count=210)
        mock_response.parsed = IntakePreflightSchema(
            identified_title="Crema facial abierta usada",
            category="Cosmética",
            detected_attributes=["Envase abierto sin precinto"],
            missing_or_recommended_info=[],
            suggested_note="Envase cosmético abierto.",
            compliance_verdict="manual_review",
            compliance_risk_score=62,
            compliance_flags=["Vinted prohíbe cosméticos abiertos o usados (VT-201)"],
        )
        mock_client.models.generate_content.return_value = mock_response

        res = identify_intake_product([_create_dummy_image_bytes()], raw_note="Crema facial", language="es")
        self.assertTrue(res["success"])
        self.assertEqual(res["compliance_verdict"], ComplianceVerdict.MANUAL_REVIEW)
        self.assertGreaterEqual(res["compliance_risk_score"], 62)
        self.assertIn("Vinted prohíbe cosméticos abiertos", res["compliance_flags"][0])

        # Verify ONLY top-3 clauses were injected into prompt (not all 12)
        prompt_sent = mock_client.models.generate_content.call_args.kwargs["contents"][0]
        self.assertIn("TOP-3 CLAUSEGUARD", prompt_sent)
        clause_lines = [line for line in prompt_sent.splitlines() if line.startswith("- [")]
        self.assertLessEqual(len(clause_lines), 3)

        # Verify intake_identify_view exposes compliance fields to UI
        self.client.force_login(self.assistant)
        upload = SimpleUploadedFile("cream.jpg", _create_dummy_image_bytes(), content_type="image/jpeg")
        resp = self.client.post(
            reverse("inventory:intake_identify"),
            {"images": upload, "raw_note": "Crema facial"},
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload["compliance_verdict"], "manual_review")
        self.assertEqual(payload["compliance_risk_score"], 62)

    @override_settings(GEMINI_API_KEY="test-key")
    @patch("inventory.services.ai_service.genai.Client")
    def test_generate_ai_listing_piggybacks_and_auto_sanitizes_copy(self, mock_client_cls):
        product = Product.objects.create(
            raw_note="Masajeador muscular eléctrico, cura el dolor de artritis al instante",
            created_by=self.assistant,
        )
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.usage_metadata = MagicMock(total_token_count=185)
        mock_response.parsed = ProductListingSchema(
            title="Masajeador Muscular Eléctrico Percusión",
            description="• Masajeador de percusión para relajación muscular tras el deporte\n• Incluye 4 cabezales",
            category_slug="deporte-y-ocio",
            condition="very_good",
            compliance_verdict="manual_review",
            compliance_risk_score=48,
            violated_clause_codes=["GLB-104"],
            compliance_explanation="Se evitó afirmar curación médica de artritis en la descripción.",
            sanitized_note="Eliminada afirmación terapéutica ('cura el dolor de artritis') según GLB-104.",
        )
        mock_client.models.generate_content.return_value = mock_response

        self.client.force_login(self.manager)
        resp = self.client.post(reverse("inventory:generate_ai", kwargs={"pk": product.pk}))
        self.assertEqual(resp.status_code, 302)

        product.refresh_from_db()
        self.assertEqual(product.ai_title, "Masajeador Muscular Eléctrico Percusión")
        self.assertEqual(product.compliance_stage, ComplianceStage.STAGE_2_PIGGYBACK)
        self.assertEqual(product.compliance_status, ComplianceVerdict.MANUAL_REVIEW)
        self.assertEqual(product.compliance_report["telemetry"]["tokens_used"], 185)
        self.assertTrue(
            any("GLB-104" in note for note in product.compliance_report.get("sanitized_actions", []))
        )

        # Verify Stage 2 prompt contains auto-sanitization instructions and <= 3 clauses
        prompt_sent = mock_client.models.generate_content.call_args.kwargs["contents"][0]
        self.assertIn("CLAUSEGUARD", prompt_sent)
        clause_lines = [line for line in prompt_sent.splitlines() if line.startswith("- [")]
        self.assertLessEqual(len(clause_lines), 3)

    @override_settings(GEMINI_API_KEY="test-key")
    @patch("inventory.services.ai_service.genai.Client")
    def test_verify_compliance_endpoint_permissions_and_preserves_custom_copy(self, mock_client_cls):
        product = Product.objects.create(
            raw_note="Cafetera espresso portátil",
            ai_title="Cafetera Espresso Manual Portátil",
            ai_description="Texto personalizado por el manager.",
            created_by=self.assistant,
        )

        # Assistant is blocked with 403
        self.client.force_login(self.assistant)
        resp_asst = self.client.post(
            reverse("inventory:product_verify_compliance", kwargs={"pk": product.pk})
        )
        self.assertEqual(resp_asst.status_code, 403)

        # Manager GET is rejected with 405
        self.client.force_login(self.manager)
        resp_get = self.client.get(
            reverse("inventory:product_verify_compliance", kwargs={"pk": product.pk})
        )
        self.assertEqual(resp_get.status_code, 405)

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.usage_metadata = MagicMock(total_token_count=160)
        mock_response.parsed = TargetedComplianceCheckSchema(
            compliance_verdict="approved",
            compliance_risk_score=10,
            violated_clause_codes=[],
            explanation="Producto apto para todas las plataformas.",
        )
        mock_client.models.generate_content.return_value = mock_response

        resp_post = self.client.post(
            reverse("inventory:product_verify_compliance", kwargs={"pk": product.pk})
        )
        self.assertEqual(resp_post.status_code, 302)

        product.refresh_from_db()
        # Custom title & description preserved untouched
        self.assertEqual(product.ai_title, "Cafetera Espresso Manual Portátil")
        self.assertEqual(product.ai_description, "Texto personalizado por el manager.")
        self.assertEqual(product.compliance_stage, ComplianceStage.STAGE_2_TARGETED)
        self.assertEqual(product.compliance_status, ComplianceVerdict.APPROVED)
        self.assertEqual(product.compliance_report["telemetry"]["tokens_used"], 160)

    @override_settings(GEMINI_API_KEY="test-key")
    @patch("inventory.services.compliance_service.genai.Client")
    @patch("inventory.services.compliance_service.fetch_policy_text_from_url")
    def test_hybrid_policy_sync_url_hash_dedup_and_antibot_fallback(self, mock_fetch, mock_client_cls):
        vinted = MarketplaceSite.objects.get(slug="vinted")
        vinted.policy_raw_text = "Regla de respaldo: Prohibida venta de drones comerciales y patinetes sin homologar."
        vinted.save()

        # 1. Anti-bot 403 on URL fetch -> falls back cleanly to policy_raw_text
        mock_fetch.return_value = ("", "HTTP 403 blocked/failed fetching https://www.vinted.es/catalog-rules")

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_extract_resp = MagicMock()
        mock_extract_resp.parsed = ExtractedPolicyClausesSchema(
            clauses=[
                ExtractedClauseSchema(
                    code_suffix="950",
                    category="Mobility",
                    severity="high",
                    title_es="Vinted: Drones y patinetes sin homologación",
                    title_en="Vinted: Uncertified Drones & Scooters",
                    description_es="Prohibida venta en Vinted.",
                    description_en="Prohibited on Vinted.",
                    hard_block_keywords=["dron comercial", "patinete sin homologar"],
                )
            ]
        )
        mock_client.models.generate_content.return_value = mock_extract_resp
        mock_embed_resp = MagicMock()
        mock_embed_resp.embeddings = [MagicMock(values=[0.1, 0.2, 0.3])]
        mock_client.models.embed_content.return_value = mock_embed_resp

        res1 = sync_site_policy(vinted)
        self.assertEqual(res1["status"], "synced")
        self.assertEqual(res1["source"], "raw_text")
        self.assertGreaterEqual(res1["clauses_updated"], 1)
        self.assertTrue(PolicyClause.objects.filter(code="VINT-950", site=vinted).exists())

        # 2. Second run with same content -> SHA-256 unchanged -> 0 Gemini calls!
        mock_client.models.generate_content.reset_mock()
        res2 = sync_site_policy(vinted)
        self.assertEqual(res2["status"], "unchanged")
        self.assertEqual(res2["clauses_updated"], 0)
        mock_client.models.generate_content.assert_not_called()

        # 3. Management command dry-run works cleanly
        out = StringIO()
        call_command("sync_marketplace_policies", "--site", "vinted", "--dry-run", "--no-ai", stdout=out)
        self.assertIn("vinted", out.getvalue().lower())

    def test_dashboard_compliance_filter_and_detail_ui_localization(self):
        safe_prod = Product.objects.create(
            raw_note="Libro de cocina mediterránea tapa dura",
            created_by=self.assistant,
        )
        flagged_prod = Product.objects.create(
            raw_note="Vaper recargable con nicotina sabor menta",
            created_by=self.assistant,
        )

        self.client.force_login(self.manager)
        resp_all = self.client.get(reverse("inventory:dashboard"))
        self.assertEqual(resp_all.status_code, 200)
        self.assertContains(resp_all, "complianceFilterBtn")
        self.assertContains(resp_all, "product-card-compliance-badge")

        resp_flagged = self.client.get(f"{reverse('inventory:dashboard')}?compliance=flagged")
        self.assertEqual(resp_flagged.status_code, 200)
        self.assertContains(resp_flagged, flagged_prod.display_title)
        self.assertNotContains(resp_flagged, safe_prod.display_title)

        # Product detail card renders ClauseGuard matrix, token savings & verify button for manager
        resp_detail = self.client.get(
            reverse("inventory:product_detail", kwargs={"pk": flagged_prod.pk}),
            HTTP_ACCEPT_LANGUAGE="es",
        )
        self.assertEqual(resp_detail.status_code, 200)
        self.assertContains(resp_detail, "clauseGuardCard")
        self.assertContains(resp_detail, "Cumplimiento de Políticas ClauseGuard")
        self.assertContains(resp_detail, "WP-301")
        self.assertContains(resp_detail, "verifyComplianceBtn")

        # Assistant sees ClauseGuard card read-only (no verifyComplianceBtn)
        self.client.force_login(self.assistant)
        resp_asst_detail = self.client.get(
            reverse("inventory:product_detail", kwargs={"pk": flagged_prod.pk}),
        )
        self.assertEqual(resp_asst_detail.status_code, 200)
        self.assertContains(resp_asst_detail, "clauseGuardCard")
        self.assertNotContains(resp_asst_detail, "verifyComplianceBtn")

        # Cosine similarity helper handles empty & mismatched lengths safely
        self.assertEqual(cosine_similarity([], [1.0, 2.0]), 0.0)
        self.assertEqual(cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0]), 0.0)
        self.assertEqual(cosine_similarity([1.0, 0.0], [1.0, 0.0]), 1.0)

    def test_admin_policy_clause_permissions(self):
        self.client.force_login(self.assistant)
        resp_asst = self.client.get("/admin/inventory/policyclause/")
        self.assertEqual(resp_asst.status_code, 403)

        self.client.force_login(self.manager)
        resp_mgr = self.client.get("/admin/inventory/policyclause/")
        self.assertEqual(resp_mgr.status_code, 200)
        self.assertContains(resp_mgr, "GLB-101")
