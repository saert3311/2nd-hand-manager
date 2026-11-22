import hashlib
import json
import logging
import math
import re
from typing import Any, Optional

from django.conf import settings
from django.core.cache import cache
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

DEFAULT_GEMINI_MODEL = "gemini-4-hydrogen"
DEFAULT_THINKING_LEVEL = "low"
FALLBACK_MODEL_CHAIN: tuple[str, ...] = (
    "gemini-4-hydrogen",
    "gemini-3.8-flash",
    "gemini-flash-latest",
)
COMPLIANCE_CHECK_MODEL = getattr(settings, "GEMINI_COMPLIANCE_CHECK_MODEL_NAME", DEFAULT_GEMINI_MODEL)
GEMINI_API_VERSION = getattr(settings, "GEMINI_API_VERSION", "v1beta")
GEMINI_MODELS_CACHE_KEY = "gemini_available_models_v1"
GEMINI_MODELS_CACHE_TTL = 3600
LOCAL_EMBEDDING_DIMS = 96

STATIC_FALLBACK_MODELS: tuple[tuple[str, str], ...] = (
    ("gemini-4-hydrogen", "Gemini 4 Hydrogen (gemini-4-hydrogen)"),
    ("gemini-4-argon", "Gemini 4 Argon (gemini-4-argon)"),
    ("gemini-4-carbon", "Gemini 4 Carbon (gemini-4-carbon)"),
    ("gemini-3.8-flash", "Gemini 3.8 Flash (gemini-3.8-flash)"),
    ("gemini-3.6-flash", "Gemini 3.6 Flash (gemini-3.6-flash)"),
    ("gemini-3.5-flash-lite", "Gemini 3.5 Flash-Lite (gemini-3.5-flash-lite)"),
    ("gemini-3.1-flash-lite", "Gemini 3.1 Flash-Lite (gemini-3.1-flash-lite)"),
    ("gemini-flash-latest", "Gemini Flash Latest (gemini-flash-latest)"),
    ("gemini-flash-lite-latest", "Gemini Flash-Lite Latest (gemini-flash-lite-latest)"),
    ("gemini-2.5-flash", "Gemini 2.5 Flash (gemini-2.5-flash)"),
    ("gemini-2.5-pro", "Gemini 2.5 Pro (gemini-2.5-pro)"),
)

_MINIMAL_THINKING_SUPPORTED_PREFIXES = (
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3-flash-preview",
)

_INCOMPATIBLE_MODEL_TOKENS = (
    "-tts",
    "-image",
    "transcribe",
    "-live",
    "robotics",
    "computer-use",
    "embedding",
    "customtools",
    "omni",
    "nano-banana",
    "lyria",
    "veo",
    "imagen",
    "aqa",
    "learnlm",
)

_PREFERRED_MODEL_ORDER = (
    "gemini-4-hydrogen",
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-4-argon",
    "gemini-4-carbon",
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
)

__all__ = [
    "CATEGORY_BOOST_MAP",
    "CATEGORY_FLAG_MAP",
    "COMPLIANCE_CHECK_MODEL",
    "DEFAULT_GEMINI_MODEL",
    "DEFAULT_POLICY_CLAUSES_SEED",
    "DEFAULT_POLICY_URL_MAP",
    "DEFAULT_THINKING_LEVEL",
    "FALLBACK_MODEL_CHAIN",
    "GEMINI_API_VERSION",
    "GEMINI_MODELS_CACHE_KEY",
    "LOCAL_EMBEDDING_DIMS",
    "STATIC_FALLBACK_MODELS",
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
    "fetch_available_gemini_models",
    "format_top_clauses_prompt_block",
    "generate_content_with_fallback",
    "get_gemini_http_options",
    "invalidate_clause_matcher_cache",
    "is_compatible_gemini_model",
    "is_recoverable_model_error",
    "merge_stage2_compliance_result",
    "normalize_text",
    "parse_gemini_response_dict",
    "resolve_task_model_and_thinking",
    "resolve_thinking_config",
    "stem_phrase",
    "stem_token",
    "verify_product_compliance_ai",
]


def get_gemini_http_options() -> types.HttpOptions:
    """
    Returns explicit HttpOptions pinning the Gemini Developer API version (`v1beta`).

    `google-genai >= 3.0.0` defaults to `v1`, which rejects `-latest` model aliases
    (e.g. `gemini-flash-latest`) with 404 NOT_FOUND and disables JSON mode
    (`response_mime_type="application/json"`).
    """
    api_version = (getattr(settings, "GEMINI_API_VERSION", GEMINI_API_VERSION) or "v1beta").strip()
    return types.HttpOptions(api_version=api_version)


def is_compatible_gemini_model(
    model_name: str,
    supported_actions: Optional[list[str]] = None,
) -> bool:
    """
    Returns True when `model_name` is a multimodal text/JSON-capable Gemini model
    suitable for structured output (`generateContent`), excluding TTS, image-gen,
    audio/video-only, live voice, robotics, and non-Gemini models.
    """
    clean_id = (model_name or "").strip().lower().removeprefix("models/")
    if not clean_id.startswith("gemini-"):
        return False
    if supported_actions is not None and "generateContent" not in supported_actions:
        return False
    return not any(tok in clean_id for tok in _INCOMPATIBLE_MODEL_TOKENS)


def fetch_available_gemini_models(
    *,
    force_refresh: bool = False,
    client_cls: Any = None,
) -> list[tuple[str, str]]:
    """
    Fetches and caches compatible `generateContent` Gemini models from `client.models.list()`.
    Always returns a non-empty list of `(model_id, display_label)` tuples, falling back to
    `STATIC_FALLBACK_MODELS` when offline or when `GEMINI_API_KEY` is unconfigured.
    """
    if not force_refresh:
        cached = cache.get(GEMINI_MODELS_CACHE_KEY)
        if isinstance(cached, list) and cached:
            return list(cached)

    api_key = (getattr(settings, "GEMINI_API_KEY", "") or "").strip()
    if not api_key:
        return list(STATIC_FALLBACK_MODELS)

    try:
        cls = client_cls or genai.Client
        client = cls(api_key=api_key, http_options=get_gemini_http_options())
        discovered: dict[str, str] = {}
        for m in client.models.list():
            raw_name = str(getattr(m, "name", "") or "").strip()
            actions = list(getattr(m, "supported_actions", None) or [])
            if not is_compatible_gemini_model(raw_name, actions if actions else None):
                continue
            model_id = raw_name.removeprefix("models/")
            display_name = str(getattr(m, "display_name", "") or "").strip()
            label = f"{display_name} ({model_id})" if display_name and model_id not in display_name else model_id
            discovered[model_id] = label

        if not discovered:
            return list(STATIC_FALLBACK_MODELS)

        for fb_id, fb_label in STATIC_FALLBACK_MODELS:
            discovered.setdefault(fb_id, fb_label)

        order_index = {m_id: idx for idx, m_id in enumerate(_PREFERRED_MODEL_ORDER)}
        sorted_choices = sorted(
            discovered.items(),
            key=lambda item: (order_index.get(item[0], 999), item[0]),
        )
        cache.set(GEMINI_MODELS_CACHE_KEY, sorted_choices, GEMINI_MODELS_CACHE_TTL)
        return sorted_choices
    except Exception as exc:
        logger.warning("Could not fetch live Gemini models list from API: %s. Using static fallback.", exc)
        return list(STATIC_FALLBACK_MODELS)


def resolve_thinking_config(
    model_name: str,
    thinking_level: Optional[str] = DEFAULT_THINKING_LEVEL,
) -> types.ThinkingConfig:
    """
    Resolves a model-compatible `types.ThinkingConfig` to prevent overthinking and
    excess output token spend while avoiding `400 INVALID_ARGUMENT` on models
    that do not support `MINIMAL` (such as `gemini-4-hydrogen` and `gemini-3.8-flash`).
    """
    clean_model = (model_name or DEFAULT_GEMINI_MODEL).strip().lower().removeprefix("models/")
    raw_level = (thinking_level or DEFAULT_THINKING_LEVEL).strip().lower()

    if raw_level == "minimal":
        if clean_model.startswith(_MINIMAL_THINKING_SUPPORTED_PREFIXES):
            effective_level = "MINIMAL"
        else:
            effective_level = "LOW"
    elif raw_level in ("low", "medium", "high"):
        effective_level = raw_level.upper()
    else:
        effective_level = "LOW"

    return types.ThinkingConfig(thinking_level=effective_level)


def resolve_task_model_and_thinking(
    task: str = "copywriting",
    language: str = "es",
    explicit_model: Optional[str] = None,
) -> tuple[str, str]:
    """
    Resolves `(model_name, thinking_level)` for a given AI task ('copywriting', 'intake',
    'compliance', 'policy_sync') from the active `AIPromptConfiguration`, falling back
    to `DEFAULT_GEMINI_MODEL` ('gemini-4-hydrogen') and `DEFAULT_THINKING_LEVEL` ('low').
    """
    lang_code = "es" if str(language or "es").lower().startswith("es") else "en"
    config = None
    try:
        from inventory.models import AIPromptConfiguration

        config = AIPromptConfiguration.objects.filter(language=lang_code, is_active=True).first()
        if config is None:
            config = AIPromptConfiguration.objects.filter(is_active=True).first()
    except Exception as exc:
        logger.warning("Could not retrieve AIPromptConfiguration for task '%s': %s", task, exc)

    if explicit_model and explicit_model.strip():
        resolved_model = explicit_model.strip()
    elif config is not None:
        resolved_model = config.get_model_for_task(task)
    else:
        resolved_model = DEFAULT_GEMINI_MODEL

    if task == "compliance":
        resolved_thinking = "minimal"
    elif config is not None and getattr(config, "thinking_level", None):
        resolved_thinking = str(config.thinking_level).strip().lower()
    else:
        resolved_thinking = DEFAULT_THINKING_LEVEL

    return resolved_model, resolved_thinking


def is_recoverable_model_error(exc: Exception) -> bool:
    """
    Returns True strictly when `exc` indicates a missing/deprecated model (404 NOT_FOUND)
    or an unsupported model/parameter error (400 INVALID_ARGUMENT), never for quota (429),
    authentication (401/403), or network timeout errors.
    """
    msg = str(exc or "").lower()
    if any(
        tok in msg
        for tok in (
            "429",
            "resource_exhausted",
            "quota",
            "401",
            "403",
            "unauthenticated",
            "permission_denied",
            "timeout",
            "timed out",
        )
    ):
        return False
    return any(
        tok in msg
        for tok in (
            "404",
            "not_found",
            "not found",
            "400",
            "invalid_argument",
            "is not supported",
        )
    )


_is_recoverable_model_error = is_recoverable_model_error


def _is_config_or_tool_error(exc: Exception) -> bool:
    """
    Returns True strictly when `exc` indicates a 400 / invalid_argument / unsupported feature error
    (e.g., rejecting `tools` combined with JSON MIME mode, or unsupported `seed`), never for `404` or fatal quota/auth errors.
    """
    if not is_recoverable_model_error(exc):
        return False
    msg = str(exc or "").lower()
    return any(tok in msg for tok in ("400", "invalid_argument", "is not supported"))


def _build_json_schema_prompt_appendix(response_schema: type[BaseModel]) -> str:
    """Builds a compact JSON-only formatting instruction for models rejecting JSON MIME mode alongside tools."""
    schema_json = json.dumps(response_schema.model_json_schema(), ensure_ascii=False)
    return (
        "\n\nOUTPUT FORMAT REQUIREMENT:\n"
        "Return ONLY a single valid JSON object (no surrounding markdown prose) conforming to this JSON Schema:\n"
        f"{schema_json}"
    )


def generate_content_with_fallback(
    client: Any,
    *,
    model: str,
    contents: list[Any],
    response_schema: type[BaseModel],
    temperature: float = 0.2,
    thinking_level: Optional[str] = DEFAULT_THINKING_LEVEL,
    fallback_models: tuple[str, ...] = FALLBACK_MODEL_CHAIN,
    use_web_search: bool = False,
    fallback_state: Optional[dict[str, Any]] = None,
    system_instruction: Optional[str] = None,
    seed: Optional[int] = None,
    allow_ungrounded_fallback: bool = True,
) -> Any:
    """
    Executes `client.models.generate_content(...)` with model-clamped `ThinkingConfig`
    and self-heals on `404 NOT_FOUND` or `400 INVALID_ARGUMENT` by retrying down
    `fallback_models` (`gemini-4-hydrogen` -> `gemini-3.8-flash` -> `gemini-flash-latest`).

    Supports native `system_instruction` and deterministic `seed` (stripping `seed` on the
    same model if rejected with `400 INVALID_ARGUMENT`). When `use_web_search=True`, attaches
    Gemini's built-in Google Search Grounding tool, retries with prompt-enforced JSON on
    `400 INVALID_ARGUMENT` tool/MIME conflicts, and optionally falls back to un-grounded vision
    (or raises when `allow_ungrounded_fallback=False`) while recording `fallback_state`.
    """
    primary = (model or DEFAULT_GEMINI_MODEL).strip()
    candidates: list[str] = [primary]
    for fb in fallback_models:
        fb_clean = (fb or "").strip()
        if fb_clean and fb_clean not in candidates:
            candidates.append(fb_clean)

    search_tools = [types.Tool(google_search=types.GoogleSearch())] if use_web_search else None
    clean_sys_inst = (system_instruction or "").strip() or None

    last_exc: Optional[Exception] = None
    for idx, candidate_model in enumerate(candidates):
        thinking_cfg = resolve_thinking_config(candidate_model, thinking_level)
        config_kwargs: dict[str, Any] = {
            "response_mime_type": "application/json",
            "response_schema": response_schema,
            "temperature": temperature,
            "thinking_config": thinking_cfg,
        }
        if clean_sys_inst:
            config_kwargs["system_instruction"] = clean_sys_inst
        if seed is not None:
            config_kwargs["seed"] = int(seed)
        if use_web_search:
            config_kwargs["tools"] = search_tools
        config = types.GenerateContentConfig(**config_kwargs)

        try:
            return client.models.generate_content(
                model=candidate_model,
                contents=contents,
                config=config,
            )
        except Exception as exc:
            last_exc = exc
            if not is_recoverable_model_error(exc):
                raise

            if use_web_search and _is_config_or_tool_error(exc):
                logger.warning(
                    "Gemini grounded structured JSON failed on '%s' (%s); retrying with prompt-enforced JSON + Search.",
                    candidate_model,
                    exc,
                )
                prompt_fallback_contents = list(contents) + [_build_json_schema_prompt_appendix(response_schema)]
                prompt_fallback_kwargs: dict[str, Any] = {
                    "temperature": temperature,
                    "thinking_config": thinking_cfg,
                    "tools": search_tools,
                }
                if clean_sys_inst:
                    prompt_fallback_kwargs["system_instruction"] = clean_sys_inst
                try:
                    return client.models.generate_content(
                        model=candidate_model,
                        contents=prompt_fallback_contents,
                        config=types.GenerateContentConfig(**prompt_fallback_kwargs),
                    )
                except Exception as exc2:
                    last_exc = exc2
                    if not is_recoverable_model_error(exc2):
                        raise
            elif not use_web_search and seed is not None and _is_config_or_tool_error(exc):
                logger.warning(
                    "Gemini model '%s' rejected seed or config parameter (%s); retrying without seed.",
                    candidate_model,
                    exc,
                )
                no_seed_kwargs = {k: v for k, v in config_kwargs.items() if k != "seed"}
                try:
                    return client.models.generate_content(
                        model=candidate_model,
                        contents=contents,
                        config=types.GenerateContentConfig(**no_seed_kwargs),
                    )
                except Exception as exc2:
                    last_exc = exc2
                    if not is_recoverable_model_error(exc2):
                        raise

            if idx < len(candidates) - 1:
                logger.warning(
                    "Gemini model '%s' failed with recoverable error (%s); falling back to '%s'.",
                    candidate_model,
                    last_exc,
                    candidates[idx + 1],
                )
                continue

    if use_web_search and last_exc is not None and is_recoverable_model_error(last_exc):
        if fallback_state is not None:
            fallback_state["fell_back_to_ungrounded"] = True
        if allow_ungrounded_fallback:
            logger.warning(
                "All grounded Gemini candidates failed with recoverable tool errors (%s); "
                "falling back to standard un-grounded vision.",
                last_exc,
            )
            return generate_content_with_fallback(
                client,
                model=model,
                contents=contents,
                response_schema=response_schema,
                temperature=temperature,
                thinking_level=thinking_level,
                fallback_models=fallback_models,
                use_web_search=False,
                system_instruction=system_instruction,
                seed=seed,
            )
        raise last_exc

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("No candidate Gemini models configured.")

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
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw_text, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end > start:
            data = json.loads(cleaned[start:end + 1])
        else:
            raise
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
        active_model, thinking_level = resolve_task_model_and_thinking("compliance", language=lang)
        client = genai.Client(api_key=api_key.strip(), http_options=get_gemini_http_options())
        response = generate_content_with_fallback(
            client,
            model=active_model,
            contents=[prompt],
            response_schema=TargetedComplianceCheckSchema,
            temperature=0.0,
            thinking_level=thinking_level,
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
