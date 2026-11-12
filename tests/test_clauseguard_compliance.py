import time
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
    Category,
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
    compute_local_ngram_vector,
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

    def test_policy_clause_exposes_weak_keywords_and_exception_phrases(self):
        glb101 = PolicyClause.objects.get(code="GLB-101")
        glb103 = PolicyClause.objects.get(code="GLB-103")
        vt202 = PolicyClause.objects.get(code="VT-202")
        wp301 = PolicyClause.objects.get(code="WP-301")

        self.assertIn("arma de fuego", glb101.hard_block_keywords)
        self.assertIn("pistola", glb101.weak_keywords)
        self.assertIn("pistola de silicona", glb101.exception_phrases)

        self.assertIn("copia exacta", glb103.hard_block_keywords)
        self.assertIn("pirata", glb103.weak_keywords)
        self.assertIn("disfraz de pirata", glb103.exception_phrases)

        self.assertIn("llanta", vt202.weak_keywords)
        self.assertIn("llanta de bicicleta", vt202.exception_phrases)

        self.assertIn("whisky", wp301.weak_keywords)
        self.assertIn("vaso de whisky", wp301.exception_phrases)

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

    def test_stage1_matcher_cache_reuses_precompiled_rules_and_scales_under_5ms(self):
        from inventory.services import compliance_service

        self.assertEqual(len(compute_local_ngram_vector("Regla de prueba")), LOCAL_EMBEDDING_DIMS)
        self.assertFalse(hasattr(compliance_service, "cosine_similarity"))
        self.assertFalse(hasattr(compliance_service, "compute_embedding_vector"))

        # Create 300 active synced clauses with 12 keywords each (3,600 total keywords)
        vinted = MarketplaceSite.objects.get(slug="vinted")
        bulk_clauses = [
            PolicyClause(
                code=f"PERF-{idx:03d}",
                site=vinted,
                category="Performance Test",
                severity=PolicySeverity.MEDIUM,
                title_es=f"Regla sintética {idx}",
                title_en=f"Synthetic rule {idx}",
                description_es="Descripción sintética de prueba.",
                description_en="Synthetic test description.",
                hard_block_keywords=[f"synkw{idx}_{kw_idx}" for kw_idx in range(12)],
                is_active=True,
            )
            for idx in range(300)
        ]
        PolicyClause.objects.bulk_create(bulk_clauses)

        # First call builds/warms cache; subsequent calls hit cached matcher without rebuilding
        evaluate_stage1_local(title="Silla plegable de aluminio", language="es")

        from inventory.services import compliance_matcher as cm

        with patch.object(
            cm,
            "_compile_clause_entries",
            wraps=cm._compile_clause_entries,
        ) as spy_compile:
            t0 = time.perf_counter()
            for _ in range(10):
                res = evaluate_stage1_local(title="Silla plegable de aluminio con respaldo", language="es")
                self.assertEqual(res["verdict"], ComplianceVerdict.APPROVED)
            avg_ms = ((time.perf_counter() - t0) / 10.0) * 1000.0
            self.assertEqual(spy_compile.call_count, 0)
            self.assertLess(avg_ms, 5.0, f"Expected <5ms Stage 1 cached latency with 300 clauses, got {avg_ms:.2f}ms")

        # Creating/saving a PolicyClause invalidates the compiled cache automatically
        new_clause = PolicyClause.objects.get(code="PERF-001")
        new_clause.hard_block_keywords = ["sillaplasticoespecial"]
        new_clause.save()
        res_invalidated = evaluate_stage1_local(title="Item sillaplasticoespecial nuevo", language="es")
        self.assertEqual(res_invalidated["verdict"], ComplianceVerdict.MANUAL_REVIEW)

    def test_stage1_accuracy_corpus_zero_false_negatives_and_zero_false_positives(self):
        should_flag = [
            ("Pistolas de airsoft x2 con bolas", "GLB-101"),
            ("Lote de réplicas de bolsos Louis Vuitton", "GLB-103"),
            ("Medicamentos caducados varios", "GLB-102"),
            ("Baterías hinchadas de portátil", "GLB-105"),
            ("Perfumes abiertos al 80%", "VT-201"),
            ("Vapers desechables sabor fresa", "WP-301"),
            ("Esteroide anabolizante sin abrir", "GLB-102"),
            ("Navaja automática de bolsillo", "GLB-101"),
            ("Bolso imitación Gucci", "GLB-103"),
            ("Zapatillas Nike fake", "GLB-103"),
            ("Munición calibre 9mm", "GLB-101"),
            ("Cachorros de bulldog francés", "ML-501"),
            ("Taladros percutores Bosch lote", "VT-202"),
            ("Copia exacta de reloj Rolex", "GLB-103"),
            ("Cuchillo mariposa (balisong)", "GLB-101"),
            ("Revólver antiguo de colección", "GLB-101"),
            ("Cargador de móvil con pila abombada", "GLB-105"),
            ("Cargador que huele a quemado", "GLB-105"),
            ("Pintalabios usado una vez", "VT-201"),
        ]
        should_pass = [
            "Pistola de silicona caliente Bosch",
            "Pistola de masaje muscular percusión",
            "Pistola de agua Nerf para niños",
            "Pistola de pintura Wagner",
            "Chaqueta de cuero color tabaco",
            "Bolso 100% original, no es réplica ni falso",
            "Disfraz de pirata para niño talla 6",
            "Barco pirata LEGO 70413",
            "Transportín para mascota pequeña",
            "Cama para mascota lavable",
            "Vaso de whisky de cristal tallado",
            "Líquido sin nicotina para limpieza",
            "Pastillero semanal para medicamentos",
            "Nevera portátil para insulina",
            "Falso techo de escayola placas",
            "Llanta de bicicleta 29 pulgadas",
            "Funda para DNI y tarjetas",
            "Armario ropero de pino",
            "Silla de oficina ergonómica",
        ]

        for text, expected_code in should_flag:
            with self.subTest(flag_text=text):
                res = evaluate_stage1_local(title=text, language="es")
                self.assertIn(
                    res["verdict"],
                    (ComplianceVerdict.MANUAL_REVIEW, ComplianceVerdict.REJECTED),
                    f"False negative on {text!r}: verdict={res['verdict']}",
                )
                matched_codes = {m["code"] for m in res["report"]["matched_clauses"]}
                self.assertIn(
                    expected_code,
                    matched_codes,
                    f"Expected {expected_code} for {text!r}, got {matched_codes}",
                )

        for text in should_pass:
            with self.subTest(pass_text=text):
                res = evaluate_stage1_local(title=text, language="es")
                self.assertEqual(
                    res["verdict"],
                    ComplianceVerdict.APPROVED,
                    f"False positive on {text!r}: matched={res['report']['matched_clauses']}",
                )

    def test_stage1_weak_vs_strong_keyword_severity_and_top3_promotion(self):
        # Single ambiguous weak keyword ("pistola") triggers MANUAL_REVIEW (not REJECTED 92) and promotes GLB-101
        res_weak = evaluate_stage1_local(title="Pistola de juguete antigua sin marca", language="es")
        self.assertEqual(res_weak["verdict"], ComplianceVerdict.MANUAL_REVIEW)
        self.assertLess(res_weak["risk_score"], 85)
        self.assertIn("GLB-101", [c.code for c in res_weak["top_clauses"]])

        # Unambiguous strong CRITICAL keyword ("escopeta") triggers REJECTED (92)
        res_strong = evaluate_stage1_local(title="Escopeta de caza superpuesta", language="es")
        self.assertEqual(res_strong["verdict"], ComplianceVerdict.REJECTED)
        self.assertGreaterEqual(res_strong["risk_score"], 85)

    def test_stage1_category_signal_and_product_save_category_change_hook(self):
        appliances_cat, _ = Category.objects.get_or_create(
            slug="electrodomesticos",
            defaults={"name": "Electrodomésticos", "name_en": "Appliances"},
        )
        fashion_cat, _ = Category.objects.get_or_create(
            slug="moda-y-accesorios",
            defaults={"name": "Moda y accesorios", "name_en": "Fashion"},
        )

        # Neutral title + no category -> APPROVED
        product = Product.objects.create(
            raw_note="Aparato compacto blanco 1200W",
            created_by=self.assistant,
        )
        self.assertEqual(product.compliance_status, ComplianceVerdict.APPROVED)

        # Assigning category "electrodomesticos" triggers Stage 1 VT-202 for Vinted in Product.save()
        product.category = appliances_cat
        product.save()
        product.refresh_from_db()
        self.assertEqual(product.compliance_status, ComplianceVerdict.MANUAL_REVIEW)
        matrix = product.compliance_report["platform_matrix"]
        self.assertEqual(matrix["vinted"]["status"], ComplianceVerdict.MANUAL_REVIEW)
        self.assertIn("VT-202", matrix["vinted"]["clauses"])
        self.assertEqual(matrix["wallapop"]["status"], ComplianceVerdict.APPROVED)

        # Switching to safe fashion category restores APPROVED automatically
        product.category = fashion_cat
        product.save()
        product.refresh_from_db()
        self.assertEqual(product.compliance_status, ComplianceVerdict.APPROVED)

    @override_settings(GEMINI_API_KEY="test-key")
    @patch("inventory.services.compliance_service.genai.Client")
    def test_stage2_targeted_clearance_preserved_across_non_violating_category_edit(self, mock_client_cls):
        fashion_cat, _ = Category.objects.get_or_create(
            slug="moda-y-accesorios",
            defaults={"name": "Moda y accesorios", "name_en": "Fashion"},
        )
        appliances_cat, _ = Category.objects.get_or_create(
            slug="electrodomesticos",
            defaults={"name": "Electrodomésticos", "name_en": "Appliances"},
        )
        product = Product.objects.create(
            raw_note="Pistola antigua decorativa de metal",
            created_by=self.assistant,
        )
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_pass = MagicMock()
        mock_pass.usage_metadata = MagicMock(total_token_count=110)
        mock_pass.parsed = TargetedComplianceCheckSchema(passed=True, violated_clause_codes=[])
        mock_client.models.generate_content.return_value = mock_pass

        self.client.force_login(self.manager)
        self.client.post(reverse("inventory:product_verify_compliance", kwargs={"pk": product.pk}))
        product.refresh_from_db()
        self.assertEqual(product.compliance_stage, ComplianceStage.STAGE_2_TARGETED)
        self.assertEqual(product.compliance_status, ComplianceVerdict.APPROVED)

        # Assigning a non-violating category preserves STAGE_2_TARGETED clearance
        product.category = fashion_cat
        product.save()
        product.refresh_from_db()
        self.assertEqual(product.compliance_stage, ComplianceStage.STAGE_2_TARGETED)
        self.assertEqual(product.compliance_status, ComplianceVerdict.APPROVED)

        # Assigning a restricted category ("electrodomesticos" -> VT-202) flags VT-202
        product.category = appliances_cat
        product.save()
        product.refresh_from_db()
        self.assertEqual(product.compliance_status, ComplianceVerdict.MANUAL_REVIEW)
        self.assertIn("VT-202", [m["code"] for m in product.compliance_matched_clauses])

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

    def test_sanitize_extracted_keywords_strips_generic_stopwords_and_short_tokens(self):
        from inventory.services.policy_sync_service import sanitize_extracted_keywords

        raw = [
            "ropa",
            "Usado",
            "caja",
            "original",
            "gas",
            "oro",
            "DNI",
            "cbd",
            "tnt",
            "arma de fuego",
            "arma de fuego",
            "perfume abierto",
            "lote",
        ]
        cleaned = sanitize_extracted_keywords(raw)
        self.assertEqual(cleaned, ["dni", "cbd", "tnt", "arma de fuego", "perfume abierto"])

    @override_settings(GEMINI_API_KEY="test-key")
    @patch("inventory.services.policy_sync_service.genai.Client")
    def test_sync_site_policy_sanitizes_keywords_and_persists_weak_and_exceptions(self, mock_client_cls):
        vinted = MarketplaceSite.objects.get(slug="vinted")
        vinted.policy_raw_text = "Regla actualizada sobre cosméticos y artículos prohibidos."
        vinted.policy_content_hash = ""
        vinted.save()

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.parsed = ExtractedPolicyClausesSchema(
            clauses=[
                ExtractedClauseSchema(
                    code_suffix="990",
                    category="Hygiene",
                    severity="high",
                    title_es="Vinted: Higiene",
                    title_en="Vinted: Hygiene",
                    description_es="Cosméticos usados prohibidos.",
                    description_en="Used cosmetics prohibited.",
                    hard_block_keywords=["ropa", "usado", "cosmetico abierto", "dni"],
                    weak_keywords=["caja", "tester"],
                    exception_phrases=["nuevo precintado"],
                )
            ]
        )
        mock_client.models.generate_content.return_value = mock_resp

        res = sync_site_policy(vinted, use_api=True)
        self.assertEqual(res["status"], "synced")
        clause = PolicyClause.objects.get(code="VINT-990")
        self.assertEqual(clause.hard_block_keywords, ["cosmetico abierto", "dni"])
        self.assertEqual(clause.weak_keywords, ["tester"])
        self.assertEqual(clause.exception_phrases, ["nuevo precintado"])

    def test_audit_policy_keywords_command_reports_noisy_triggers(self):
        vinted = MarketplaceSite.objects.get(slug="vinted")
        PolicyClause.objects.create(
            code="NOISY-999",
            site=vinted,
            category="Audit Test",
            severity=PolicySeverity.MEDIUM,
            title_es="Regla ruidosa",
            title_en="Noisy rule",
            description_es="Regla de prueba",
            description_en="Test rule",
            hard_block_keywords=["camiseta"],
            is_active=True,
        )
        for i in range(4):
            Product.objects.create(
                raw_note=f"Camiseta básica algodón #{i}",
                created_by=self.assistant,
            )
        Product.objects.create(
            raw_note="Mesa auxiliar madera roble",
            created_by=self.assistant,
        )

        out = StringIO()
        call_command("audit_policy_keywords", threshold=0.05, stdout=out)
        output = out.getvalue()
        self.assertIn("NOISY-999", output)
        self.assertIn("camiseta", output)

    @override_settings(GEMINI_API_KEY="test-key")
    @patch("inventory.services.policy_sync_service.genai.Client")
    def test_sync_site_policy_no_ai_does_not_poison_content_hash(self, mock_client_cls):
        vinted = MarketplaceSite.objects.get(slug="vinted")
        vinted.policy_url = ""
        vinted.policy_raw_text = "Regla nueva sin haber sido extraída todavía por IA."
        vinted.policy_content_hash = "previous-hash"
        vinted.save()

        # Running with use_api=False must NOT stamp the new content hash, otherwise a subsequent AI run skips it
        res_no_ai = sync_site_policy(vinted, use_api=False)
        self.assertNotEqual(res_no_ai["status"], "synced")
        vinted.refresh_from_db()
        self.assertEqual(vinted.policy_content_hash, "previous-hash")

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.parsed = ExtractedPolicyClausesSchema(
            clauses=[
                ExtractedClauseSchema(
                    code_suffix="991",
                    category="Test",
                    severity="medium",
                    title_es="Regla extraída",
                    title_en="Extracted rule",
                    description_es="Descripción de prueba",
                    description_en="Test description",
                    hard_block_keywords=["artefacto prohibido"],
                )
            ]
        )
        mock_client.models.generate_content.return_value = mock_resp

        res_ai = sync_site_policy(vinted, use_api=True)
        self.assertEqual(res_ai["status"], "synced")
        mock_client.models.generate_content.assert_called_once()

    def test_dashboard_secondary_subfilters_preserve_compliance_filter(self):
        from inventory.models import ProductListingLink, SaleChannelType

        self.client.force_login(self.manager)
        wallapop = MarketplaceSite.objects.get(slug="wallapop")

        pub_flagged = Product.objects.create(
            ai_title="Pistola antigua decorativa",
            ai_description="Pieza vintage",
            sale_price="30.00",
            created_by=self.manager,
        )
        ProductListingLink.objects.create(
            product=pub_flagged,
            site=wallapop,
            url="https://es.wallapop.com/item/test-subfilter-1",
        )
        sold_flagged = Product.objects.create(
            ai_title="Navaja mariposa vintage",
            ai_description="Colección",
            sale_price="40.00",
            is_sold=True,
            sold_channel_type=SaleChannelType.IN_STORE,
            created_by=self.manager,
        )
        self.assertTrue(sold_flagged.is_compliance_flagged)

        resp_pub = self.client.get(
            f"{reverse('inventory:dashboard')}?status=published&sync=out_of_sync&compliance=flagged"
        )
        self.assertEqual(resp_pub.status_code, 200)
        html_pub = resp_pub.content.decode("utf-8")
        self.assertIn('href="?status=published&compliance=flagged"', html_pub)
        self.assertIn('href="?status=published&sync=out_of_sync&compliance=flagged"', html_pub)
        self.assertIn("sync=out_of_sync", html_pub.split('id="complianceFilterBtn"', 1)[1].split("</a>", 1)[0])

        resp_sold = self.client.get(
            f"{reverse('inventory:dashboard')}?status=sold&channel=in_store&compliance=flagged"
        )
        self.assertEqual(resp_sold.status_code, 200)
        html_sold = resp_sold.content.decode("utf-8")
        self.assertIn('href="?status=sold&compliance=flagged"', html_sold)
        self.assertIn('href="?status=sold&channel=in_store&compliance=flagged"', html_sold)
        self.assertIn("channel=in_store", html_sold.split('id="complianceFilterBtn"', 1)[1].split("</a>", 1)[0])

    def test_compliance_matcher_module_split_and_zero_percent_negation(self):
        from inventory.services import compliance_matcher, compliance_service

        # Dedicated matcher module must exist cleanly and dead _match_keyword must be gone
        self.assertTrue(hasattr(compliance_matcher, "stem_token"))
        self.assertTrue(hasattr(compliance_matcher, "stem_phrase"))
        self.assertFalse(hasattr(compliance_service, "_match_keyword"))

        # "0% nicotina" and "cero nicotina" must not trigger WP-301 false positive
        for clean_text in (
            "Líquido 0% nicotina para limpieza óptica",
            "Solución cero nicotina para cristal",
        ):
            res = evaluate_stage1_local(title=clean_text, description="")
            self.assertEqual(res["verdict"], ComplianceVerdict.APPROVED, msg=f"False positive on: {clean_text}")

        flagged = evaluate_stage1_local(title="E-liquid con 12mg nicotina para vaper", description="")
        self.assertNotEqual(flagged["verdict"], ComplianceVerdict.APPROVED)

    def test_policy_clause_normalizes_code_and_product_apply_compliance_result(self):
        vinted = MarketplaceSite.objects.get(slug="vinted")
        clause = PolicyClause.objects.create(
            code="  vt-custom-lower  ",
            site=vinted,
            category="Test",
            severity=PolicySeverity.MEDIUM,
            title_es="Regla minúscula",
            description_es="Texto",
        )
        self.assertEqual(clause.code, "VT-CUSTOM-LOWER")

        product = Product.objects.create(raw_note="Mesa madera maciza", created_by=self.assistant)
        sample = evaluate_stage1_local(title="Lote de réplicas de bolsos", raw_note="")
        product.apply_compliance_result(sample, commit=True)
        product.refresh_from_db()
        self.assertEqual(product.compliance_status, sample["verdict"])
        self.assertEqual(product.compliance_risk_score, sample["risk_score"])
        self.assertEqual(product.compliance_stage, sample["stage"])
        self.assertIsNotNone(product.compliance_checked_at)
