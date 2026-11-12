import hashlib
import json
import logging
import math
import re
from typing import Any, Optional

from django.conf import settings
from django.db import OperationalError, ProgrammingError
from django.utils.translation import get_language
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from inventory.models import (
    ComplianceStage,
    ComplianceVerdict,
    MarketplaceSite,
    PolicyClause,
    PolicySeverity,
)

from .compliance_matcher import (
    CATEGORY_BOOST_MAP,
    CATEGORY_FLAG_MAP,
    STOPWORDS,
    _masked_positions_for_exceptions,
    _matches_at_position,
    _tokenize_with_sentences,
    clause_embedding_text,
    collect_lexical_hits,
    get_compiled_clause_matcher,
    invalidate_clause_matcher_cache,
    normalize_text,
    stem_phrase,
    stem_token,
)
from .policy_clauses_seed import DEFAULT_POLICY_CLAUSES_SEED, DEFAULT_POLICY_URL_MAP

logger = logging.getLogger(__name__)

COMPLIANCE_CHECK_MODEL = getattr(settings, "GEMINI_COMPLIANCE_CHECK_MODEL_NAME", "gemini-flash-latest")
LOCAL_EMBEDDING_DIMS = 96

__all__ = [
    "CATEGORY_BOOST_MAP",
    "CATEGORY_FLAG_MAP",
    "COMPLIANCE_CHECK_MODEL",
    "DEFAULT_POLICY_CLAUSES_SEED",
    "DEFAULT_POLICY_URL_MAP",
    "LOCAL_EMBEDDING_DIMS",
    "TargetedComplianceCheckSchema",
    "_masked_positions_for_exceptions",
    "_matches_at_position",
    "_tokenize_with_sentences",
    "build_platform_matrix",
    "clause_embedding_text",
    "compute_local_ngram_vector",
    "ensure_default_policy_clauses",
    "evaluate_stage1_local",
    "evaluate_stage1_local_for_product",
    "format_top_clauses_prompt_block",
    "invalidate_clause_matcher_cache",
    "merge_stage2_compliance_result",
    "normalize_text",
    "parse_gemini_response_dict",
    "stem_phrase",
    "stem_token",
    "verify_product_compliance_ai",
]

_PRIMITIVE_FIELD_TYPES = (str, int, float, bool, list, dict, BaseModel, type(None))


def parse_gemini_response_dict(response: Any, schema_cls: Optional[type[BaseModel]] = None) -> dict[str, Any]:
    """Extracts a plain dictionary from a Gemini `GenerateContentResponse` (.parsed or .text)."""
    parsed = getattr(response, "parsed", None)
    if parsed is not None:
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, BaseModel):
            return parsed.model_dump()
        model_dump = getattr(parsed, "model_dump", None)
        if callable(model_dump):
            dumped = model_dump()
            if isinstance(dumped, dict):
                return dumped
        if schema_cls is not None:
            extracted: dict[str, Any] = {}
            for name, field_info in schema_cls.model_fields.items():
                val = getattr(parsed, name, None)
                extracted[name] = (
                    val
                    if isinstance(val, _PRIMITIVE_FIELD_TYPES)
                    else (None if field_info.is_required() else field_info.get_default(call_default_factory=True))
                )
            return extracted
        return dict(vars(parsed))
    raw_text = (getattr(response, "text", None) or "").strip()
    if not raw_text:
        return {}
    data = json.loads(raw_text)
    return data if isinstance(data, dict) else {}


def compute_local_ngram_vector(text: str, dims: int = LOCAL_EMBEDDING_DIMS) -> list[float]:
    """Retained for historical migration `0026_seed_default_policy_clauses` compatibility."""
    norm = normalize_text(text)
    if not norm:
        return [0.0] * dims
    vec = [0.0] * dims
    for tok in re.findall(r"[a-z0-9]{2,}", norm):
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
        vec[h % dims] += 2.0
        if len(tok) >= 4:
            for idx in range(len(tok) - 2):
                gram = tok[idx:idx + 3]
                gh = int(hashlib.md5(gram.encode("utf-8")).hexdigest(), 16)
                vec[gh % dims] += 0.6
    magnitude = math.sqrt(sum(v * v for v in vec))
    if magnitude > 0:
        vec = [round(v / magnitude, 6) for v in vec]
    return vec


def ensure_default_policy_clauses(use_api_embeddings: bool = False, sync_defaults: bool = False) -> int:
    """
    Idempotently seeds curated global and per-platform policy clauses (Wallapop, Vinted, eBay, Milanuncios).
    Also ensures default `policy_url` values are populated on known MarketplaceSite entries if blank.
    """
    del use_api_embeddings  # Historical signature compatibility
    sites_by_slug = {s.slug: s for s in MarketplaceSite.objects.all()}
    for slug, url in DEFAULT_POLICY_URL_MAP.items():
        site = sites_by_slug.get(slug)
        if site and not (site.policy_url or "").strip():
            site.policy_url = url
            site.save(update_fields=["policy_url", "updated_at"])

    created_count = 0
    for item in DEFAULT_POLICY_CLAUSES_SEED:
        site_obj = sites_by_slug.get(item["site_slug"]) if item["site_slug"] else None
        hard_kws = list(item.get("hard_block_keywords") or [])
        weak_kws = list(item.get("weak_keywords") or [])
        exc_phrases = list(item.get("exception_phrases") or [])
        defaults = {
            "site": site_obj,
            "category": item["category"],
            "severity": item["severity"],
            "title_es": item["title_es"],
            "title_en": item["title_en"],
            "description_es": item["description_es"],
            "description_en": item["description_en"],
            "hard_block_keywords": hard_kws,
            "weak_keywords": weak_kws,
            "exception_phrases": exc_phrases,
            "is_active": True,
        }
        obj, created = PolicyClause.objects.get_or_create(code=item["code"], defaults=defaults)
        if created:
            created_count += 1
        elif sync_defaults:
            changed_fields: list[str] = []
            if obj.hard_block_keywords != hard_kws:
                obj.hard_block_keywords = hard_kws
                changed_fields.append("hard_block_keywords")
            if obj.weak_keywords != weak_kws:
                obj.weak_keywords = weak_kws
                changed_fields.append("weak_keywords")
            if obj.exception_phrases != exc_phrases:
                obj.exception_phrases = exc_phrases
                changed_fields.append("exception_phrases")
            if changed_fields:
                changed_fields.append("updated_at")
                obj.save(update_fields=changed_fields)
    return created_count


def _compute_product_text_hash(title: str = "", description: str = "", raw_note: str = "") -> str:
    combined = normalize_text(f"{title}\n{description}\n{raw_note}")
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()[:16]


def _severity_score(severity: str, is_global: bool, match_strength: str = "strong") -> int:
    if severity == PolicySeverity.CRITICAL:
        base = 92 if is_global else 82
    elif severity == PolicySeverity.HIGH:
        base = 75 if is_global else 60
    else:
        base = 48 if is_global else 40
    if match_strength != "strong":
        return min(65 if is_global else 55, base)
    return base


def _is_hard_critical_entry(entry: dict[str, Any]) -> bool:
    return (
        not entry.get("site_slug")
        and entry.get("severity") == PolicySeverity.CRITICAL
        and entry.get("match_strength", "strong") == "strong"
    )


def build_platform_matrix(
    matched_clauses: list[dict[str, Any]],
    sites: Optional[list[MarketplaceSite]] = None,
) -> dict[str, dict[str, Any]]:
    """
    Constructs the per-platform compatibility matrix (`rapido-pack` Storefront + active MarketplaceSites).
    Global matches propagate to every platform; site-specific matches flag only that specific platform.
    """
    if sites is None:
        try:
            sites = list(MarketplaceSite.objects.filter(is_active=True).order_by("order", "name"))
        except (OperationalError, ProgrammingError):
            sites = []

    platforms: list[tuple[str, str]] = [("rapido-pack", "Rápido Pack")]
    seen_slugs = {"rapido-pack"}
    for site in sites:
        if site.slug and site.slug not in seen_slugs:
            platforms.append((site.slug, site.name))
            seen_slugs.add(site.slug)

    matrix: dict[str, dict[str, Any]] = {
        slug: {"slug": slug, "name": name, "status": ComplianceVerdict.APPROVED, "clauses": []}
        for slug, name in platforms
    }

    for clause in matched_clauses:
        clause_code = clause.get("code", "")
        severity = clause.get("severity", PolicySeverity.MEDIUM)
        site_slug = clause.get("site_slug") or ""
        is_strong = clause.get("match_strength", "strong") == "strong"
        target_status = (
            ComplianceVerdict.REJECTED
            if (severity == PolicySeverity.CRITICAL and is_strong)
            else ComplianceVerdict.MANUAL_REVIEW
        )

        if not site_slug:
            targets = list(matrix.values())
        else:
            if site_slug not in matrix:
                matrix[site_slug] = {
                    "slug": site_slug,
                    "name": clause.get("site_name") or site_slug.title(),
                    "status": ComplianceVerdict.APPROVED,
                    "clauses": [],
                }
            targets = [matrix[site_slug]]

        for entry in targets:
            if clause_code and clause_code not in entry["clauses"]:
                entry["clauses"].append(clause_code)
            if entry["status"] != ComplianceVerdict.REJECTED:
                entry["status"] = target_status

    return matrix


def _build_telemetry(top_k_sent: int, tokens_used: int, naive_baseline_tokens: int) -> dict[str, Any]:
    saved_pct = 0.0
    if naive_baseline_tokens > 0:
        saved_pct = max(0.0, round((1.0 - (tokens_used / naive_baseline_tokens)) * 100.0, 1))
    return {
        "top_k_clauses_sent": top_k_sent,
        "tokens_used": tokens_used,
        "naive_baseline_tokens": naive_baseline_tokens,
        "tokens_saved_percent": saved_pct,
    }


def evaluate_stage1_local(
    *,
    title: str = "",
    description: str = "",
    raw_note: str = "",
    category_name: str = "",
    category_slug: str = "",
    language: Optional[str] = None,
    top_k: int = 3,
) -> dict[str, Any]:
    """
    Stage 1 fast local policy filter (<5ms, 0 LLM tokens).
    Combines an inverted-index Spanish/English stemmed phrase matcher (strong vs. weak keywords,
    exception masking, 3-token negation window), deterministic category mapping, and
    stemmed content-token overlap for Top-K Stage 2 candidate selection.
    """
    lang = (language or get_language() or "es").lower()
    is_es = lang.startswith("es")
    combined_text = " ".join(part.strip() for part in (title, description, raw_note, category_name) if part and part.strip())
    norm_text = normalize_text(combined_text)
    cat_slug = (category_slug or "").strip().lower()
    text_hash = _compute_product_text_hash(title=title, description=description, raw_note=raw_note)

    try:
        sites = list(MarketplaceSite.objects.filter(is_active=True).order_by("order", "name"))
        matcher = get_compiled_clause_matcher(sites, seed_callback=ensure_default_policy_clauses)
    except (OperationalError, ProgrammingError):
        sites = []
        matcher = None

    naive_baseline = matcher.naive_baseline if matcher else 12000

    if matcher is None or not matcher.entries or (not norm_text and not cat_slug):
        matrix = build_platform_matrix([], sites=sites)
        empty_es = "No se detectaron palabras clave prohibidas ni señales de riesgo."
        empty_en = "No prohibited policy keywords or risk signals detected."
        return {
            "verdict": ComplianceVerdict.APPROVED,
            "risk_score": 0,
            "stage": ComplianceStage.STAGE_1_SAFE,
            "top_clauses": [],
            "report": {
                "text_hash": text_hash,
                "summary": empty_es if is_es else empty_en,
                "summary_es": empty_es,
                "summary_en": empty_en,
                "matched_clauses": [],
                "sanitized_actions": [],
                "platform_matrix": matrix,
                "telemetry": _build_telemetry(top_k_sent=0, tokens_used=0, naive_baseline_tokens=naive_baseline),
            },
        }

    tokens = _tokenize_with_sentences(combined_text)
    masked_cache: dict[int, set[int]] = {}
    strong_hits = collect_lexical_hits(tokens, matcher, matcher.strong_index, masked_cache)
    weak_hits = collect_lexical_hits(tokens, matcher, matcher.weak_index, masked_cache)

    flagged_codes = set(CATEGORY_FLAG_MAP.get(cat_slug, ()))
    boosted_codes = set(CATEGORY_BOOST_MAP.get(cat_slug, ())) | flagged_codes

    product_content_stems = {
        st for st, _raw, _sid in tokens if len(st) >= 3 and st not in STOPWORDS
    }

    scored_clauses: list[tuple[float, Any, list[str], list[str], bool, float]] = []
    for c_idx, entry in enumerate(matcher.entries):
        s_hits = strong_hits.get(c_idx, [])
        w_hits = weak_hits.get(c_idx, [])
        code_upper = entry.clause.code.upper()
        is_cat_flag = code_upper in flagged_codes
        is_cat_boost = code_upper in boosted_codes

        if product_content_stems and entry.content_stems:
            overlap = len(product_content_stems & entry.content_stems)
            sim = overlap / math.sqrt(len(product_content_stems) * len(entry.content_stems)) if overlap else 0.0
        else:
            sim = 0.0

        has_strong = bool(s_hits) or len(w_hits) >= 2
        has_any_signal = bool(s_hits or w_hits or is_cat_flag)
        rank_score = (
            sim
            + (3.0 if has_strong else (1.5 if has_any_signal else 0.0))
            + (1.2 if is_cat_boost else 0.0)
            + (0.15 * (len(s_hits) + len(w_hits)))
        )
        scored_clauses.append((rank_score, entry, s_hits, w_hits, is_cat_flag, sim))

    scored_clauses.sort(key=lambda item: item[0], reverse=True)
    top_entries = scored_clauses[:max(1, top_k)]
    top_clauses = [item[1].clause for item in top_entries]

    matched_clauses_data: list[dict[str, Any]] = []
    max_risk = 0
    has_global_critical = False
    has_lexical_hit = False

    for _rank, entry, s_hits, w_hits, is_cat_flag, sim in scored_clauses:
        if not (s_hits or w_hits or is_cat_flag):
            continue
        has_lexical_hit = True
        clause = entry.clause
        is_global = not entry.site_slug

        if s_hits or len(w_hits) >= 2:
            match_strength = "strong"
        elif w_hits:
            match_strength = "weak"
        else:
            match_strength = "category"

        entry_risk = _severity_score(clause.severity, is_global=is_global, match_strength=match_strength)
        max_risk = max(max_risk, entry_risk)

        combined_kws = list(s_hits)
        for wk in w_hits:
            if wk not in combined_kws:
                combined_kws.append(wk)
        excerpt = ", ".join(combined_kws) if combined_kws else f"category:{cat_slug}"

        matched_entry = {
            "code": clause.code,
            "site_slug": entry.site_slug,
            "site_name": clause.site.name if clause.site_id and clause.site else "Rápido Pack / Global",
            "title": clause.get_localized_title(lang),
            "title_es": clause.title_es,
            "title_en": clause.title_en,
            "severity": clause.severity,
            "match_strength": match_strength,
            "similarity": round(sim, 3),
            "matched_keywords": combined_kws,
            "excerpt": excerpt,
            "explanation": clause.get_localized_description(lang),
            "explanation_es": clause.description_es,
            "explanation_en": clause.description_en,
        }
        if _is_hard_critical_entry(matched_entry):
            has_global_critical = True
        matched_clauses_data.append(matched_entry)

    if has_global_critical:
        verdict = ComplianceVerdict.REJECTED
    elif matched_clauses_data:
        verdict = ComplianceVerdict.MANUAL_REVIEW
    else:
        verdict = ComplianceVerdict.APPROVED
        top_sim = top_entries[0][5] if top_entries else 0.0
        max_risk = min(20, int(round(top_sim * 25)))

    stage = ComplianceStage.STAGE_1_LEXICAL if has_lexical_hit else ComplianceStage.STAGE_1_SAFE
    matrix = build_platform_matrix(matched_clauses_data, sites=sites)

    if matched_clauses_data:
        summary_es = "; ".join(
            f"[{m['code']}] {m.get('title_es') or m['title']} ({m['excerpt']})" for m in matched_clauses_data[:3]
        )
        summary_en = "; ".join(
            f"[{m['code']}] {m.get('title_en') or m['title']} ({m['excerpt']})" for m in matched_clauses_data[:3]
        )
    else:
        summary_es = "Fase 1 aprobada sin incidencias — sin palabras clave prohibidas."
        summary_en = "Stage 1 clean pass — no prohibited keywords detected."

    return {
        "verdict": verdict,
        "risk_score": max_risk,
        "stage": stage,
        "top_clauses": top_clauses,
        "_sites": sites,
        "report": {
            "text_hash": text_hash,
            "summary": summary_es if is_es else summary_en,
            "summary_es": summary_es,
            "summary_en": summary_en,
            "matched_clauses": matched_clauses_data,
            "sanitized_actions": [],
            "platform_matrix": matrix,
            "telemetry": _build_telemetry(top_k_sent=0, tokens_used=0, naive_baseline_tokens=naive_baseline),
        },
    }


def evaluate_stage1_local_for_product(product: Any, language: Optional[str] = None, top_k: int = 3) -> dict[str, Any]:
    """Convenience wrapper running Stage 1 local compliance on a Product model instance."""
    cat_name = ""
    cat_slug = ""
    if getattr(product, "category_id", None) and getattr(product, "category", None):
        cat_name = product.category.name or ""
        cat_slug = product.category.slug or ""
    return evaluate_stage1_local(
        title=getattr(product, "ai_title", "") or "",
        description=getattr(product, "ai_description", "") or "",
        raw_note=getattr(product, "raw_note", "") or "",
        category_name=cat_name,
        category_slug=cat_slug,
        language=language,
        top_k=top_k,
    )


def format_top_clauses_prompt_block(clauses: list[PolicyClause], language: str = "es") -> str:
    """
    Formats ONLY the top-K (default 3) candidate clauses into a compact ~150-token prompt snippet
    for Stage 2 piggybacking, avoiding full Terms & Conditions upload.
    """
    if not clauses:
        return ""
    is_es = str(language).lower().startswith("es")
    header = (
        "REGLAS DE POLÍTICA RELEVANTES (TOP-3 CLAUSEGUARD):"
        if is_es
        else "RELEVANT POLICY CLAUSES (TOP-3 CLAUSEGUARD):"
    )
    lines = [header]
    for clause in clauses:
        scope = clause.site.name if clause.site_id and clause.site else "Global"
        title = clause.title_es if is_es else (clause.title_en or clause.title_es)
        desc = clause.description_es if is_es else (clause.description_en or clause.description_es)
        lines.append(f"- [{clause.code} | {scope} | {clause.severity}] {title}: {desc}")
    return "\n".join(lines)


def merge_stage2_compliance_result(
    *,
    stage1_result: dict[str, Any],
    ai_passed: Optional[bool] = None,
    violated_clause_codes: Optional[list[str]] = None,
    sanitized_note: str = "",
    stage: str = ComplianceStage.STAGE_2_PIGGYBACK,
    tokens_used: int = 150,
    language: Optional[str] = None,
) -> dict[str, Any]:
    """
    Merges Stage 1 deterministic hits with compact Stage 2 AI pass/fail adjudication.
    Looks up violated clause codes in the local PolicyClause database so Gemini never
    needs to spend output tokens generating explanations or reasons.
    """
    lang = (language or get_language() or "es").lower()
    is_es = lang.startswith("es")
    matched_by_code: dict[str, dict[str, Any]] = {
        str(m["code"]).upper(): dict(m) for m in (stage1_result.get("report", {}).get("matched_clauses") or [])
    }

    codes = [str(c).strip().upper() for c in (violated_clause_codes or []) if str(c).strip()]

    if stage == ComplianceStage.STAGE_2_TARGETED and ai_passed is not None:
        inspected_codes = {
            c.code.upper()
            for c in (stage1_result.get("top_clauses") or [])
            if getattr(c, "code", None)
        }
        for cleared_code in inspected_codes - set(codes):
            matched_by_code.pop(cleared_code, None)

    if codes:
        clauses_map = {
            c.code.upper(): c
            for c in PolicyClause.objects.filter(code__in=codes).select_related("site")
        }
        for code in codes:
            if code in matched_by_code:
                matched_by_code[code]["match_strength"] = "strong"
                continue
            if code in clauses_map:
                clause = clauses_map[code]
                matched_by_code[code] = {
                    "code": clause.code,
                    "site_slug": clause.site.slug if clause.site_id and clause.site else "",
                    "site_name": clause.site.name if clause.site_id and clause.site else "Rápido Pack / Global",
                    "title": clause.get_localized_title(lang),
                    "title_es": clause.title_es,
                    "title_en": clause.title_en,
                    "severity": clause.severity,
                    "match_strength": "strong",
                    "similarity": 1.0,
                    "matched_keywords": [],
                    "excerpt": "AI pass/fail check",
                    "explanation": clause.get_localized_description(lang),
                    "explanation_es": clause.description_es,
                    "explanation_en": clause.description_en,
                }
            else:
                matched_by_code[code] = {
                    "code": code,
                    "site_slug": "",
                    "site_name": "Rápido Pack / Global",
                    "title": f"Incidencia IA ({code})" if is_es else f"AI Compliance Flag ({code})",
                    "title_es": f"Incidencia IA ({code})",
                    "title_en": f"AI Compliance Flag ({code})",
                    "severity": PolicySeverity.HIGH,
                    "match_strength": "strong",
                    "similarity": 1.0,
                    "matched_keywords": [],
                    "excerpt": code,
                    "explanation": (
                        f"La verificación IA marcó el código {code} para revisión manual."
                        if is_es
                        else f"AI verification flagged clause {code} for manual review."
                    ),
                    "explanation_es": f"La verificación IA marcó el código {code} para revisión manual.",
                    "explanation_en": f"AI verification flagged clause {code} for manual review.",
                }

    if ai_passed is False and not matched_by_code:
        matched_by_code["AI-REVIEW"] = {
            "code": "AI-REVIEW",
            "site_slug": "",
            "site_name": "Rápido Pack / Global",
            "title": "Revisión manual sugerida por IA" if is_es else "AI Flagged for Manual Review",
            "title_es": "Revisión manual sugerida por IA",
            "title_en": "AI Flagged for Manual Review",
            "severity": PolicySeverity.HIGH,
            "match_strength": "strong",
            "similarity": 1.0,
            "matched_keywords": [],
            "excerpt": "AI pass=false",
            "explanation": (
                "La verificación IA detectó una posible incidencia de política."
                if is_es
                else "AI compliance verification detected a potential policy concern."
            ),
            "explanation_es": "La verificación IA detectó una posible incidencia de política.",
            "explanation_en": "AI compliance verification detected a potential policy concern.",
        }

    merged_matched = list(matched_by_code.values())

    has_global_critical = any(_is_hard_critical_entry(m) for m in merged_matched)
    computed_risk = 0
    for m in merged_matched:
        is_global = not m.get("site_slug")
        computed_risk = max(
            computed_risk,
            _severity_score(
                m.get("severity", PolicySeverity.HIGH),
                is_global=is_global,
                match_strength=m.get("match_strength", "strong"),
            ),
        )

    if has_global_critical:
        derived_verdict = ComplianceVerdict.REJECTED
    elif merged_matched or ai_passed is False:
        derived_verdict = ComplianceVerdict.MANUAL_REVIEW
        if not merged_matched:
            computed_risk = max(computed_risk, 55)
    else:
        derived_verdict = ComplianceVerdict.APPROVED

    if stage == ComplianceStage.STAGE_2_TARGETED:
        final_verdict = derived_verdict
        final_risk = computed_risk
    else:
        verdict_rank = {
            ComplianceVerdict.APPROVED: 0,
            ComplianceVerdict.MANUAL_REVIEW: 1,
            ComplianceVerdict.REJECTED: 2,
        }
        stage1_verdict = stage1_result.get("verdict", ComplianceVerdict.APPROVED)
        final_verdict = max((stage1_verdict, derived_verdict), key=lambda v: verdict_rank.get(v, 0))
        stage1_risk = int(stage1_result.get("risk_score", 0) or 0)
        final_risk = max(stage1_risk, computed_risk)

    sanitized_actions = list(stage1_result.get("report", {}).get("sanitized_actions") or [])
    if sanitized_note and sanitized_note.strip():
        sanitized_actions.append(sanitized_note.strip())

    matrix = build_platform_matrix(merged_matched, sites=stage1_result.get("_sites"))
    top_k_sent = len(stage1_result.get("top_clauses") or [])
    naive_baseline = (
        stage1_result.get("report", {})
        .get("telemetry", {})
        .get("naive_baseline_tokens", 12000)
    )

    if merged_matched:
        summary_es = "; ".join(f"[{m['code']}] {m.get('title_es') or m['title']}" for m in merged_matched[:3])
        summary_en = "; ".join(f"[{m['code']}] {m.get('title_en') or m['title']}" for m in merged_matched[:3])
    elif ai_passed is False:
        summary_es = "Verificación IA marcó revisión manual para este producto."
        summary_en = "AI check flagged this product for manual review."
    else:
        summary_es = "Aprobado en verificación IA — sin infracciones detectadas."
        summary_en = "Passed AI compliance check — no policy violations detected."

    text_hash = (stage1_result.get("report") or {}).get("text_hash", "")
    report_payload: dict[str, Any] = {
        "text_hash": text_hash,
        "summary": summary_es if is_es else summary_en,
        "summary_es": summary_es,
        "summary_en": summary_en,
        "matched_clauses": merged_matched,
        "sanitized_actions": sanitized_actions,
        "platform_matrix": matrix,
        "telemetry": _build_telemetry(
            top_k_sent=top_k_sent,
            tokens_used=max(0, int(tokens_used)),
            naive_baseline_tokens=naive_baseline,
        ),
    }
    if stage == ComplianceStage.STAGE_2_TARGETED and final_verdict == ComplianceVerdict.APPROVED and text_hash:
        report_payload["stage2_cleared_text_hash"] = text_hash

    return {
        "verdict": final_verdict,
        "risk_score": final_risk,
        "stage": stage,
        "report": report_payload,
    }


class TargetedComplianceCheckSchema(BaseModel):
    passed: bool = Field(
        description="True if the product passes all checked policy rules, False if any rule is violated",
    )
    violated_clause_codes: list[str] = Field(
        default_factory=list,
        description="Exact clause codes from the provided list that were violated, or [] if passed=True",
    )


def verify_product_compliance_ai(product: Any, language: Optional[str] = None) -> dict[str, Any]:
    """
    On-demand targeted Stage 1 -> Stage 2 verification for an existing product.
    Sends ONLY the top-3 matched clauses to Gemini and requests ONLY pass/fail + violated codes
    (zero explanation output tokens), resolving exact rules from local PolicyClause records.
    """
    lang = (language or get_language() or "es").lower()
    stage1 = evaluate_stage1_local_for_product(product, language=lang, top_k=3)
    top_clauses = stage1.get("top_clauses") or []
    clauses_block = format_top_clauses_prompt_block(top_clauses, language=lang)

    api_key = getattr(settings, "GEMINI_API_KEY", "") or ""
    if not api_key.strip() or not top_clauses:
        return stage1

    is_es = lang.startswith("es")
    prompt = (
        (
            "Verifica si este producto infringe alguna de las 3 cláusulas de política. "
            "NO generes explicaciones ni razones; responde únicamente `passed` (true/false) "
            "y los códigos exactos infringidos en `violated_clause_codes` (o `[]` si pasa).\n\n"
            if is_es
            else "Check whether this product violates any of the 3 policy clauses. "
            "Do NOT output explanations or reasons; return ONLY `passed` (true/false) "
            "and exact violated codes in `violated_clause_codes` (or `[]` if passed).\n\n"
        )
        + f"TITLE: {product.ai_title or ''}\n"
        + f"DESCRIPTION: {product.ai_description or ''}\n"
        + f"FIELD NOTES: {product.raw_note or ''}\n\n"
        + clauses_block
    )

    try:
        client = genai.Client(api_key=api_key.strip())
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=TargetedComplianceCheckSchema,
            temperature=0.0,
        )
        response = client.models.generate_content(
            model=COMPLIANCE_CHECK_MODEL,
            contents=[prompt],
            config=config,
        )
        usage = getattr(response, "usage_metadata", None)
        raw_total = getattr(usage, "total_token_count", None) if usage is not None else None
        tokens_used = (
            raw_total
            if isinstance(raw_total, int) and raw_total > 0
            else max(90, len(prompt) // 4 + 20)
        )

        data = parse_gemini_response_dict(response, TargetedComplianceCheckSchema)
        return merge_stage2_compliance_result(
            stage1_result=stage1,
            ai_passed=bool(data.get("passed", True)),
            violated_clause_codes=list(data.get("violated_clause_codes") or []),
            stage=ComplianceStage.STAGE_2_TARGETED,
            tokens_used=tokens_used,
            language=lang,
        )
    except Exception as exc:
        logger.warning("Targeted Stage 2 compliance check fallback to Stage 1: %s", exc)

    return stage1
