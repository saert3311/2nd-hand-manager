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
    LOCAL_EMBEDDING_DIMS,
    TargetedComplianceCheckSchema,
    compute_embedding_vector,
    cosine_similarity,
    ensure_default_policy_clauses,
    evaluate_stage1_local,
    merge_stage2_compliance_result,
    verify_product_compliance_ai,
)
from inventory.services.policy_sync_service import (
    ExtractedClauseSchema,
    ExtractedPolicyClausesSchema,
    _SafeRedirectHandler,
    fetch_policy_text_from_url,
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
            compliance_passed=False,
            violated_clause_codes=["VT-201"],
        )
        mock_client.models.generate_content.return_value = mock_response

        res = identify_intake_product([_create_dummy_image_bytes()], raw_note="Crema facial", language="es")
        self.assertTrue(res["success"])
        self.assertEqual(res["compliance_verdict"], ComplianceVerdict.MANUAL_REVIEW)
        self.assertGreater(res["compliance_risk_score"], 0)
        self.assertIn("VT-201", res["compliance_flags"][0])

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
        self.assertEqual(payload["compliance_risk_score"], res["compliance_risk_score"])

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
            compliance_passed=False,
            violated_clause_codes=["GLB-104"],
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
        self.assertIn("GLB-104", product.compliance_report.get("summary", ""))
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
    @patch("inventory.services.compliance_service.genai.Client")
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
            passed=True,
            violated_clause_codes=[],
        )
        mock_client.models.generate_content.return_value = mock_response

        resp_post = self.client.post(
            reverse("inventory:product_verify_compliance", kwargs={"pk": product.pk})
        )
        self.assertEqual(resp_post.status_code, 302)

        call_kwargs = mock_client.models.generate_content.call_args.kwargs
        self.assertEqual(call_kwargs["model"], "gemini-flash-latest")
        verify_prompt = call_kwargs["contents"][0]
        self.assertIn("Do NOT output explanations or reasons", verify_prompt)

        product.refresh_from_db()
        # Custom title & description preserved untouched
        self.assertEqual(product.ai_title, "Cafetera Espresso Manual Portátil")
        self.assertEqual(product.ai_description, "Texto personalizado por el manager.")
        self.assertEqual(product.compliance_stage, ComplianceStage.STAGE_2_TARGETED)
        self.assertEqual(product.compliance_status, ComplianceVerdict.APPROVED)
        self.assertEqual(product.compliance_report["telemetry"]["tokens_used"], 160)

        # When AI returns passed=False + violated code, local PolicyClause supplies exact rule details
        mock_fail_response = MagicMock()
        mock_fail_response.usage_metadata = MagicMock(total_token_count=145)
        mock_fail_response.parsed = TargetedComplianceCheckSchema(
            passed=False,
            violated_clause_codes=["VT-202"],
        )
        mock_client.models.generate_content.return_value = mock_fail_response

        resp_fail = self.client.post(
            reverse("inventory:product_verify_compliance", kwargs={"pk": product.pk})
        )
        self.assertEqual(resp_fail.status_code, 302)
        product.refresh_from_db()
        self.assertEqual(product.compliance_status, ComplianceVerdict.MANUAL_REVIEW)
        self.assertGreater(product.compliance_risk_score, 0)
        self.assertIn("VT-202", product.compliance_report.get("summary", ""))
        matched_codes = [c["code"] for c in product.compliance_report.get("matched_clauses", [])]
        self.assertIn("VT-202", matched_codes)

    @override_settings(GEMINI_API_KEY="test-key")
    @patch("inventory.services.policy_sync_service.genai.Client")
    @patch("inventory.services.policy_sync_service.fetch_policy_text_from_url")
    def test_hybrid_policy_sync_url_hash_dedup_and_antibot_fallback(self, mock_fetch, mock_client_cls):
        vinted = MarketplaceSite.objects.get(slug="vinted")
        vinted.policy_raw_text = "Regla de respaldo: Prohibida venta de drones comerciales y patinetes sin homologar."
        vinted.save()

        # 1. Anti-bot 403 on URL fetch -> falls back cleanly to policy_raw_text
        mock_fetch.return_value = ("", "HTTP 403 blocked/failed fetching https://www.vinted.es/catalog-rules")

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_extract_resp = MagicMock()
        # Return > 8 granular clauses (10 total) to verify the 8-rule cap was removed
        granular_clauses = [
            ExtractedClauseSchema(
                code_suffix=str(950 + i),
                category="Mobility" if i == 0 else f"Granular Category {i}",
                severity="high",
                title_es=(
                    "Vinted: Drones y patinetes sin homologación"
                    if i == 0
                    else f"Vinted: Regla granular {i}"
                ),
                title_en=(
                    "Vinted: Uncertified Drones & Scooters"
                    if i == 0
                    else f"Vinted: Granular Rule {i}"
                ),
                description_es=f"Descripción detallada de la regla {i} en Vinted.",
                description_en=f"Detailed rule {i} description on Vinted.",
                hard_block_keywords=(
                    ["dron comercial", "patinete sin homologar"]
                    if i == 0
                    else [f"termino bloqueado {i}"]
                ),
            )
            for i in range(10)
        ]
        mock_extract_resp.parsed = ExtractedPolicyClausesSchema(clauses=granular_clauses)
        mock_client.models.generate_content.return_value = mock_extract_resp

        res1 = sync_site_policy(vinted)
        self.assertEqual(res1["status"], "synced")
        self.assertEqual(res1["source"], "raw_text")
        self.assertEqual(res1["clauses_updated"], 10)
        self.assertEqual(PolicyClause.objects.filter(site=vinted, code__startswith="VINT-95").count(), 10)
        self.assertTrue(PolicyClause.objects.filter(code="VINT-950", site=vinted).exists())

        sync_call_kwargs = mock_client.models.generate_content.call_args.kwargs
        self.assertEqual(sync_call_kwargs["model"], "gemini-flash-latest")
        sync_prompt = sync_call_kwargs["contents"][0]
        self.assertIn("ALL distinct, granular", sync_prompt)
        self.assertNotIn("up to 8", sync_prompt)

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

    @override_settings(GEMINI_API_KEY="test-key")
    @patch("inventory.services.policy_sync_service.genai.Client")
    def test_sync_site_policy_preserves_hash_on_ai_extraction_failure(self, mock_client_cls):
        vinted = MarketplaceSite.objects.get(slug="vinted")
        vinted.policy_url = ""
        vinted.policy_raw_text = "Nueva política de prueba Vinted con cambios."
        vinted.policy_content_hash = "previous-hash-value"
        vinted.save()

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.side_effect = RuntimeError("Gemini 429 quota exceeded")

        res_fail = sync_site_policy(vinted, use_api=True)
        self.assertEqual(res_fail["status"], "extraction_failed")
        vinted.refresh_from_db()
        self.assertEqual(vinted.policy_content_hash, "previous-hash-value")

        # Subsequent sync once Gemini recovers still runs extraction without needing --force
        mock_client.models.generate_content.side_effect = None
        mock_resp = MagicMock()
        mock_resp.parsed = ExtractedPolicyClausesSchema(
            clauses=[
                ExtractedClauseSchema(
                    code_suffix="971",
                    category="Test Rule",
                    severity="medium",
                    title_es="Vinted: Regla recuperada",
                    title_en="Vinted: Recovered rule",
                    description_es="Descripción recuperada.",
                    description_en="Recovered description.",
                    hard_block_keywords=["termino recuperado"],
                )
            ]
        )
        mock_client.models.generate_content.return_value = mock_resp

        res_ok = sync_site_policy(vinted, use_api=True)
        self.assertEqual(res_ok["status"], "synced")
        self.assertEqual(res_ok["clauses_updated"], 1)
        self.assertTrue(PolicyClause.objects.filter(code="VINT-971", site=vinted, is_active=True).exists())

    @override_settings(GEMINI_API_KEY="test-key")
    @patch("inventory.services.policy_sync_service.genai.Client")
    def test_sync_site_policy_deactivates_removed_clauses_and_dedupes_codes(self, mock_client_cls):
        vinted = MarketplaceSite.objects.get(slug="vinted")
        vinted.policy_url = ""
        vinted.policy_raw_text = "Política V1 con dos reglas duplicadas de sufijo y una tercera."
        vinted.save()

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        first_resp = MagicMock()
        first_resp.parsed = ExtractedPolicyClausesSchema(
            clauses=[
                ExtractedClauseSchema(
                    code_suffix="960",
                    category="Cat A",
                    severity="high",
                    title_es="Vinted: Regla 960 A",
                    title_en="Vinted: Rule 960 A",
                    description_es="Desc A",
                    description_en="Desc A",
                    hard_block_keywords=["alfa"],
                ),
                ExtractedClauseSchema(
                    code_suffix="960",
                    category="Cat B",
                    severity="medium",
                    title_es="Vinted: Regla 960 B colisión",
                    title_en="Vinted: Rule 960 B collision",
                    description_es="Desc B",
                    description_en="Desc B",
                    hard_block_keywords=["beta"],
                ),
                ExtractedClauseSchema(
                    code_suffix="961",
                    category="Cat C",
                    severity="high",
                    title_es="Vinted: Regla 961",
                    title_en="Vinted: Rule 961",
                    description_es="Desc C",
                    description_en="Desc C",
                    hard_block_keywords=["gamma"],
                ),
            ]
        )
        mock_client.models.generate_content.return_value = first_resp

        res1 = sync_site_policy(vinted, use_api=True)
        self.assertEqual(res1["clauses_updated"], 3)
        self.assertTrue(PolicyClause.objects.filter(code="VINT-960", is_active=True).exists())
        self.assertTrue(PolicyClause.objects.filter(code="VINT-960-2", is_active=True).exists())
        self.assertTrue(PolicyClause.objects.filter(code="VINT-961", is_active=True).exists())

        # Re-sync with updated T&C keeping only 960 -> 960-2 & 961 deactivated, seeded VT-201 stays active
        vinted.policy_raw_text = "Política V2 simplificada."
        vinted.save()
        second_resp = MagicMock()
        second_resp.parsed = ExtractedPolicyClausesSchema(
            clauses=[
                ExtractedClauseSchema(
                    code_suffix="960",
                    category="Cat A",
                    severity="high",
                    title_es="Vinted: Regla 960 vigente",
                    title_en="Vinted: Active rule 960",
                    description_es="Desc vigente",
                    description_en="Active desc",
                    hard_block_keywords=["alfa"],
                )
            ]
        )
        mock_client.models.generate_content.return_value = second_resp

        sync_site_policy(vinted, use_api=True)
        self.assertTrue(PolicyClause.objects.get(code="VINT-960").is_active)
        self.assertFalse(PolicyClause.objects.get(code="VINT-960-2").is_active)
        self.assertFalse(PolicyClause.objects.get(code="VINT-961").is_active)
        self.assertTrue(PolicyClause.objects.get(code="VT-201").is_active)

    def test_merge_stage2_normalizes_lowercase_codes_and_handles_unknown_code(self):
        clean_stage1 = evaluate_stage1_local(title="Jersey lana merino", language="es")

        merged_lower = merge_stage2_compliance_result(
            stage1_result=clean_stage1,
            ai_passed=False,
            violated_clause_codes=["vt-202"],
            stage=ComplianceStage.STAGE_2_TARGETED,
            tokens_used=120,
            language="es",
        )
        self.assertEqual(merged_lower["verdict"], ComplianceVerdict.MANUAL_REVIEW)
        self.assertEqual([c["code"] for c in merged_lower["report"]["matched_clauses"]], ["VT-202"])
        self.assertEqual(
            merged_lower["report"]["platform_matrix"]["vinted"]["status"],
            ComplianceVerdict.MANUAL_REVIEW,
        )

        merged_unknown = merge_stage2_compliance_result(
            stage1_result=clean_stage1,
            ai_passed=False,
            violated_clause_codes=["UNKNOWN-999"],
            stage=ComplianceStage.STAGE_2_TARGETED,
            tokens_used=120,
            language="es",
        )
        self.assertEqual(merged_unknown["verdict"], ComplianceVerdict.MANUAL_REVIEW)
        self.assertGreaterEqual(len(merged_unknown["report"]["matched_clauses"]), 1)
        self.assertIn("UNKNOWN-999", merged_unknown["report"]["summary"])

    @override_settings(GEMINI_API_KEY="test-key")
    @patch("inventory.services.compliance_service.genai.Client")
    def test_targeted_verify_clears_stage1_false_positive_and_supports_json_text_fallback(self, mock_client_cls):
        # Stage 1 keyword "pistola" triggers GLB-101 falsely on a history book
        false_positive = Product.objects.create(
            raw_note="Libro de historia sobre pistola antigua del siglo XVIII",
            ai_title="Libro Ilustrado Historia Armas Antiguas",
            created_by=self.assistant,
        )
        self.assertEqual(false_positive.compliance_status, ComplianceVerdict.REJECTED)

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_pass_resp = MagicMock()
        mock_pass_resp.usage_metadata = MagicMock(total_token_count=130)
        mock_pass_resp.parsed = TargetedComplianceCheckSchema(passed=True, violated_clause_codes=[])
        mock_client.models.generate_content.return_value = mock_pass_resp

        self.client.force_login(self.manager)
        resp = self.client.post(
            reverse("inventory:product_verify_compliance", kwargs={"pk": false_positive.pk})
        )
        self.assertEqual(resp.status_code, 302)

        false_positive.refresh_from_db()
        self.assertEqual(false_positive.compliance_status, ComplianceVerdict.APPROVED)
        self.assertLessEqual(false_positive.compliance_risk_score, 20)
        self.assertEqual(false_positive.compliance_matched_clauses, [])
        self.assertEqual(
            false_positive.compliance_report["platform_matrix"]["wallapop"]["status"],
            ComplianceVerdict.APPROVED,
        )

        # JSON text fallback when response.parsed is None
        clean_prod = Product.objects.create(
            raw_note="Abrigo largo beige talla L",
            created_by=self.assistant,
        )
        mock_fallback_resp = MagicMock()
        mock_fallback_resp.usage_metadata = MagicMock(total_token_count=140)
        mock_fallback_resp.parsed = None
        mock_fallback_resp.text = '{"passed": false, "violated_clause_codes": ["vt-202"]}'
        mock_client.models.generate_content.return_value = mock_fallback_resp

        res_json = verify_product_compliance_ai(clean_prod, language="es")
        self.assertEqual(res_json["verdict"], ComplianceVerdict.MANUAL_REVIEW)
        self.assertEqual([c["code"] for c in res_json["report"]["matched_clauses"]], ["VT-202"])

    @patch("inventory.services.policy_sync_service.urllib.request.OpenerDirector.open")
    def test_fetch_policy_text_blocks_ssrf_and_non_text_responses(self, mock_open):
        text_meta, err_meta = fetch_policy_text_from_url("http://169.254.169.254/latest/meta-data/")
        self.assertEqual(text_meta, "")
        self.assertIn("blocked", (err_meta or "").lower())
        mock_open.assert_not_called()

        text_loop, err_loop = fetch_policy_text_from_url("http://127.0.0.1:8000/admin/")
        self.assertEqual(text_loop, "")
        self.assertIn("blocked", (err_loop or "").lower())
        mock_open.assert_not_called()

        with patch(
            "inventory.services.policy_sync_service.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("10.0.0.5", 443))],
        ):
            text_priv, err_priv = fetch_policy_text_from_url("https://internal.corp.example/terms")
            self.assertEqual(text_priv, "")
            self.assertIn("blocked", (err_priv or "").lower())
            mock_open.assert_not_called()

        handler = _SafeRedirectHandler()
        with self.assertRaises(ValueError):
            handler.redirect_request(
                MagicMock(),
                MagicMock(),
                302,
                "Found",
                {},
                "http://169.254.169.254/latest/meta-data/",
            )

        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False
        mock_resp.status = 200
        mock_resp.headers = MagicMock()
        mock_resp.headers.get_content_type.return_value = "application/pdf"
        mock_resp.headers.get.return_value = "application/pdf"
        mock_open.return_value = mock_resp
        with patch(
            "inventory.services.policy_sync_service.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("93.184.216.34", 443))],
        ):
            text_pdf, err_pdf = fetch_policy_text_from_url("https://example.com/terms.pdf")
            self.assertEqual(text_pdf, "")
            self.assertIn("unsupported", (err_pdf or "").lower())

    def test_stage1_reuses_cached_local_vectors_without_recomputing_per_clause(self):
        self.assertEqual(len(compute_embedding_vector("Regla de prueba", use_api=True)), LOCAL_EMBEDDING_DIMS)

        from inventory.services import compliance_service as cs

        with patch.object(
            cs,
            "compute_local_ngram_vector",
            wraps=cs.compute_local_ngram_vector,
        ) as spy_vec:
            evaluate_stage1_local(title="Silla plegable de aluminio", language="es")
            self.assertEqual(spy_vec.call_count, 1)

    def test_stage1_clean_pass_summary_localized_in_spanish(self):
        res_non_empty = evaluate_stage1_local(title="Silla de madera maciza", language="es")
        self.assertNotIn("Stage 1 clean pass", res_non_empty["report"]["summary"])
        self.assertIn("Fase 1", res_non_empty["report"]["summary"])

        res_empty = evaluate_stage1_local(title="", language="es")
        self.assertNotIn("No prohibited", res_empty["report"]["summary"])
        self.assertIn("No se detectaron", res_empty["report"]["summary"])

        clean_prod = Product.objects.create(
            raw_note="Silla de madera maciza",
            created_by=self.assistant,
        )
        self.client.force_login(self.manager)
        resp = self.client.get(
            reverse("inventory:product_detail", kwargs={"pk": clean_prod.pk}),
            HTTP_ACCEPT_LANGUAGE="es",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "Stage 1 clean pass")
        self.assertContains(resp, "Fase 1")
