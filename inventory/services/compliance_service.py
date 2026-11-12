import hashlib
import json
import logging
import math
import re
import threading
import unicodedata
from dataclasses import dataclass
from typing import Any, Optional

from django.conf import settings
from django.db import OperationalError, ProgrammingError
from django.db.models import Count, Max
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

from .policy_clauses_seed import DEFAULT_POLICY_CLAUSES_SEED, DEFAULT_POLICY_URL_MAP

logger = logging.getLogger(__name__)

COMPLIANCE_CHECK_MODEL = getattr(settings, "GEMINI_COMPLIANCE_CHECK_MODEL_NAME", "gemini-flash-latest")
LOCAL_EMBEDDING_DIMS = 96

# Deterministic category-slug mappings for Stage 1 local compliance
CATEGORY_FLAG_MAP: dict[str, tuple[str, ...]] = {
    "electrodomesticos": ("VT-202",),
    "construccion-y-reformas": ("VT-202",),
    "motor-y-accesorios": ("VT-202",),
}

CATEGORY_BOOST_MAP: dict[str, tuple[str, ...]] = {
    "motor-y-accesorios": ("VT-202", "EB-401"),
    "electrodomesticos": ("VT-202",),
    "construccion-y-reformas": ("VT-202",),
    "tecnologia-y-electronica": ("GLB-105", "GLB-106", "GLB-107"),
    "industria-y-agricultura": ("ML-501", "VT-202"),
    "moda-y-accesorios": ("GLB-103", "VT-201"),
}

_INVARIANT_STEMS = frozenset({
    "gas", "gris", "pais", "seis", "tres", "dos", "mas", "plus",
    "tenis", "chasis", "crisis", "dosis", "tesis", "lunes", "martes",
    "jueves", "viernes", "virus", "bonus", "campus", "focus", "status",
})

_PLURAL_ES_SUFFIXES = (
    "ares", "eres", "ires", "ores", "ures",
    "ales", "eles", "iles", "oles", "ules",
    "anes", "enes", "ines", "ones", "unes",
    "ades", "edes", "ides", "odes", "udes",
    "ojes", "ajes", "ejes", "ises",
)

_STOPWORDS = frozenset({
    "a", "al", "con", "de", "del", "e", "el", "en", "es", "la", "las", "lo",
    "los", "o", "para", "por", "se", "sin", "su", "sus", "un", "una", "unas",
    "unos", "y", "and", "for", "from", "in", "of", "on", "or", "the", "to", "with",
    "articulo", "articulos", "producto", "productos", "venta", "vendo", "nuevo",
    "usado", "buen", "estado", "lote", "item", "items",
})

_NEGATION_WORDS = frozenset({
    "no", "ni", "sin", "nunca", "jamas", "nada", "tampoco",
    "not", "without", "never", "non", "0mg",
})

_NEGATION_BIGRAMS = frozenset({
    ("libre", "de"),
    ("free", "of"),
    ("exento", "de"),
})

_CLAUSE_BOUNDARY_CHARS = frozenset(".;:!?\n()[]{}")

__all__ = [
    "CATEGORY_BOOST_MAP",
    "CATEGORY_FLAG_MAP",
    "COMPLIANCE_CHECK_MODEL",
    "DEFAULT_POLICY_CLAUSES_SEED",
    "DEFAULT_POLICY_URL_MAP",
    "LOCAL_EMBEDDING_DIMS",
    "TargetedComplianceCheckSchema",
    "build_platform_matrix",
    "clause_embedding_text",
    "compute_embedding_vector",
    "compute_local_ngram_vector",
    "cosine_similarity",
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


def clause_embedding_text(clause: Any) -> str:
    """Concatenates bilingual clause title, description, and trigger keywords for local vectorization."""
    return (
        f"{clause.title_es} {clause.title_en} "
        f"{clause.description_es} {clause.description_en} "
        f"{' '.join(clause.hard_block_keywords or [])}"
    )


def normalize_text(text: str) -> str:
    """Lowercase and strip diacritics for accent-insensitive Spanish/English matching."""
    raw = (text or "").strip().lower()
    nfkd = unicodedata.normalize("NFKD", raw)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


_TOKEN_OR_BOUNDARY_RE = re.compile(r"[.;:!?\n()\[\]]|[a-z0-9]+(?::[a-z0-9]+|\+)?")


def stem_token(token: str) -> str:
    """Lightweight accent-normalized Spanish/English plural stemmer with invariant allowlist."""
    tok = normalize_text(token)
    if not tok or len(tok) < 4 or tok in _INVARIANT_STEMS:
        return tok
    if tok.endswith("ces") and len(tok) > 4:
        return tok[:-3] + "z"
    if len(tok) >= 5 and tok.endswith(_PLURAL_ES_SUFFIXES):
        return tok[:-2]
    if tok.endswith("s") and not tok.endswith("ss"):
        return tok[:-1]
    return tok


def _tokenize_with_sentences(text: str) -> list[tuple[str, str, int]]:
    """
    Tokenizes text into (stemmed_token, normalized_token, sentence_id) tuples.
    Punctuation increments sentence_id so negations never bleed across sentence boundaries.
    """
    norm = normalize_text(text)
    if not norm:
        return []
    tokens: list[tuple[str, str, int]] = []
    sent_id = 0
    for match in _TOKEN_OR_BOUNDARY_RE.finditer(norm):
        raw = match.group(0)
        if len(raw) == 1 and raw in _CLAUSE_BOUNDARY_CHARS:
            sent_id += 1
            continue
        tokens.append((stem_token(raw), raw, sent_id))
    return tokens


def stem_phrase(phrase: str) -> tuple[str, ...]:
    """Converts a keyword/exception phrase into a tuple of stemmed tokens."""
    norm = normalize_text(phrase)
    if not norm:
        return ()
    parts: list[str] = []
    for match in _TOKEN_OR_BOUNDARY_RE.finditer(norm):
        raw = match.group(0)
        if len(raw) == 1 and raw in _CLAUSE_BOUNDARY_CHARS:
            continue
        parts.append(stem_token(raw))
    return tuple(parts)


def _tokenize(text: str) -> list[str]:
    norm = normalize_text(text)
    return re.findall(r"[a-z0-9]{2,}", norm)


@dataclass(frozen=True)
class _CompiledClauseEntry:
    clause: PolicyClause
    site_slug: str
    exceptions: tuple[tuple[str, ...], ...]
    content_stems: frozenset[str]


@dataclass(frozen=True)
class _CompiledClauseMatcher:
    signature: tuple[int, Any, int]
    entries: tuple[_CompiledClauseEntry, ...]
    by_code_idx: dict[str, int]
    strong_index: dict[str, tuple[tuple[int, str, tuple[str, ...]], ...]]
    weak_index: dict[str, tuple[tuple[int, str, tuple[str, ...]], ...]]
    naive_baseline: int


_CACHE_LOCK = threading.Lock()
_CACHE_GENERATION = 0
_COMPILED_MATCHER_CACHE: Optional[_CompiledClauseMatcher] = None


def invalidate_clause_matcher_cache() -> None:
    """Invalidates the in-memory compiled Stage 1 PolicyClause matcher cache."""
    global _CACHE_GENERATION, _COMPILED_MATCHER_CACHE
    with _CACHE_LOCK:
        _CACHE_GENERATION += 1
        _COMPILED_MATCHER_CACHE = None


def _compile_clause_entries(
    clauses: list[PolicyClause],
    sites: list[MarketplaceSite],
    signature: tuple[int, Any, int],
) -> _CompiledClauseMatcher:
    entries: list[_CompiledClauseEntry] = []
    by_code_idx: dict[str, int] = {}
    strong_tmp: dict[str, list[tuple[int, str, tuple[str, ...]]]] = {}
    weak_tmp: dict[str, list[tuple[int, str, tuple[str, ...]]]] = {}

    for c_idx, clause in enumerate(clauses):
        site_slug = clause.site.slug if clause.site_id and clause.site else ""
        exc_list = []
        for phrase in (getattr(clause, "exception_phrases", None) or []):
            stemmed = stem_phrase(str(phrase))
            if stemmed:
                exc_list.append(stemmed)

        for kw in (clause.hard_block_keywords or []):
            stemmed = stem_phrase(str(kw))
            if stemmed:
                strong_tmp.setdefault(stemmed[0], []).append((c_idx, str(kw), stemmed))

        for kw in (getattr(clause, "weak_keywords", None) or []):
            stemmed = stem_phrase(str(kw))
            if stemmed:
                weak_tmp.setdefault(stemmed[0], []).append((c_idx, str(kw), stemmed))

        full_text = clause_embedding_text(clause)
        c_stems = frozenset(
            st
            for st, _raw, _sid in _tokenize_with_sentences(full_text)
            if len(st) >= 3 and st not in _STOPWORDS
        )
        entries.append(
            _CompiledClauseEntry(
                clause=clause,
                site_slug=site_slug,
                exceptions=tuple(exc_list),
                content_stems=c_stems,
            )
        )
        by_code_idx[clause.code.upper()] = c_idx

    return _CompiledClauseMatcher(
        signature=signature,
        entries=tuple(entries),
        by_code_idx=by_code_idx,
        strong_index={k: tuple(v) for k, v in strong_tmp.items()},
        weak_index={k: tuple(v) for k, v in weak_tmp.items()},
        naive_baseline=_estimate_naive_baseline_tokens(clauses, sites),
    )


def _get_compiled_clause_matcher(sites: list[MarketplaceSite]) -> _CompiledClauseMatcher:
    global _COMPILED_MATCHER_CACHE
    stats = PolicyClause.objects.filter(is_active=True).aggregate(
        cnt=Count("id"),
        max_upd=Max("updated_at"),
    )
    cnt = int(stats.get("cnt") or 0)
    if cnt == 0:
        ensure_default_policy_clauses(use_api_embeddings=False)
        stats = PolicyClause.objects.filter(is_active=True).aggregate(
            cnt=Count("id"),
            max_upd=Max("updated_at"),
        )
        cnt = int(stats.get("cnt") or 0)

    signature = (cnt, stats.get("max_upd"), _CACHE_GENERATION)
    cached = _COMPILED_MATCHER_CACHE
    if cached is not None and cached.signature == signature:
        return cached

    with _CACHE_LOCK:
        cached = _COMPILED_MATCHER_CACHE
        if cached is not None and cached.signature == signature:
            return cached
        clauses = list(PolicyClause.objects.filter(is_active=True).select_related("site").order_by("code"))
        compiled = _compile_clause_entries(clauses, sites, signature)
        _COMPILED_MATCHER_CACHE = compiled
        return compiled


def _masked_positions_for_exceptions(
    tokens: list[tuple[str, str, int]],
    exceptions: tuple[tuple[str, ...], ...],
) -> set[int]:
    if not exceptions or not tokens:
        return set()
    masked: set[int] = set()
    n = len(tokens)
    for exc in exceptions:
        m = len(exc)
        if m == 0 or m > n:
            continue
        first_exc = exc[0]
        for idx in range(n - m + 1):
            if tokens[idx][0] != first_exc:
                continue
            sid = tokens[idx][2]
            if all(tokens[idx + j][0] == exc[j] and tokens[idx + j][2] == sid for j in range(1, m)):
                masked.update(range(idx, idx + m))
    return masked


def _has_pre_hit_negation(tokens: list[tuple[str, str, int]], hit_idx: int) -> bool:
    if hit_idx <= 0:
        return False
    sid = tokens[hit_idx][2]
    start = max(0, hit_idx - 3)
    prev_raw = [tokens[p][1] for p in range(start, hit_idx) if tokens[p][2] == sid]
    if not prev_raw:
        return False
    if any(tok in _NEGATION_WORDS for tok in prev_raw):
        return True
    for i in range(len(prev_raw) - 1):
        if (prev_raw[i], prev_raw[i + 1]) in _NEGATION_BIGRAMS:
            return True
    return False


def _matches_at_position(
    tokens: list[tuple[str, str, int]],
    idx: int,
    kw_stems: tuple[str, ...],
    masked: set[int],
) -> bool:
    m = len(kw_stems)
    if idx + m > len(tokens):
        return False
    sid = tokens[idx][2]
    for offset in range(m):
        pos = idx + offset
        if pos in masked:
            return False
        if tokens[pos][0] != kw_stems[offset] or tokens[pos][2] != sid:
            return False
    return not _has_pre_hit_negation(tokens, idx)


def _compute_product_text_hash(title: str = "", description: str = "", raw_note: str = "") -> str:
    combined = normalize_text(f"{title}\n{description}\n{raw_note}")
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()[:16]


def compute_local_ngram_vector(text: str, dims: int = LOCAL_EMBEDDING_DIMS) -> list[float]:
    """
    Deterministic lightweight hashed char-trigram + word-token embedding vector.
    Provides fast (<1ms) offline semantic similarity in SQLite without external APIs.
    """
    norm = normalize_text(text)
    if not norm:
        return [0.0] * dims

    vec = [0.0] * dims
    tokens = _tokenize(norm)
    for tok in tokens:
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


def compute_embedding_vector(text: str, use_api: bool = False) -> list[float]:
    """
    Computes the fixed 96-dim local hashed n-gram vector used by Stage 1 scoring.
    Kept synchronous and zero-API-cost so stored vectors always match runtime Stage 1 dimensions.
    """
    clean_text = (text or "").strip()
    if not clean_text:
        return [0.0] * LOCAL_EMBEDDING_DIMS
    return compute_local_ngram_vector(clean_text)


def cosine_similarity(vec_a: list[float] | tuple[float, ...], vec_b: list[float] | tuple[float, ...]) -> float:
    """Computes cosine similarity in [0.0, 1.0] safely, returning 0.0 on empty or mismatched dimensions."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a <= 0 or norm_b <= 0:
        return 0.0
    return max(0.0, min(1.0, round(dot / (norm_a * norm_b), 4)))


def ensure_default_policy_clauses(use_api_embeddings: bool = False, sync_defaults: bool = False) -> int:
    """
    Idempotently seeds curated global and per-platform policy clauses (Wallapop, Vinted, eBay, Milanuncios).
    Also ensures default `policy_url` values are populated on known MarketplaceSite entries if blank.
    """
    sites_by_slug = {s.slug: s for s in MarketplaceSite.objects.all()}
    for slug, url in DEFAULT_POLICY_URL_MAP.items():
        site = sites_by_slug.get(slug)
        if site and not (site.policy_url or "").strip():
            site.policy_url = url
            site.save(update_fields=["policy_url", "updated_at"])

    created_count = 0
    for item in DEFAULT_POLICY_CLAUSES_SEED:
        site_obj = sites_by_slug.get(item["site_slug"]) if item["site_slug"] else None
        seed_text = (
            f"{item['title_es']} {item['title_en']} "
            f"{item['description_es']} {item['description_en']} "
            f"{' '.join(item['hard_block_keywords'])}"
        )
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
            "embedding_vector": compute_embedding_vector(seed_text, use_api=use_api_embeddings),
            "is_active": True,
        }
        obj, created = PolicyClause.objects.get_or_create(code=item["code"], defaults=defaults)
        if created:
            created_count += 1
        else:
            changed_fields: list[str] = []
            if not obj.embedding_vector or len(obj.embedding_vector) != LOCAL_EMBEDDING_DIMS:
                obj.embedding_vector = compute_embedding_vector(seed_text, use_api=False)
                changed_fields.append("embedding_vector")
            if sync_defaults:
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


def _match_keyword(normalized_haystack: str, keyword: str) -> bool:
    """Stem-aware, negation-aware phrase matcher on arbitrary text."""
    kw_stems = stem_phrase(keyword)
    if not kw_stems:
        return False
    tokens = _tokenize_with_sentences(normalized_haystack)
    if not tokens:
        return False
    first = kw_stems[0]
    empty_masked: set[int] = set()
    return any(
        tok[0] == first and _matches_at_position(tokens, idx, kw_stems, empty_masked)
        for idx, tok in enumerate(tokens)
    )


def _estimate_naive_baseline_tokens(clauses: list[PolicyClause], sites: list[MarketplaceSite]) -> int:
    raw_policy_chars = sum(len((s.policy_raw_text or "").strip()) for s in sites)
    clause_chars = sum(
        len(c.title_es or "") + len(c.description_es or "") + len(c.title_en or "") + len(c.description_en or "")
        for c in clauses
    )
    estimated = (raw_policy_chars + clause_chars * 4) // 4
    return max(12000, estimated)


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


def _collect_lexical_hits(
    tokens: list[tuple[str, str, int]],
    matcher: _CompiledClauseMatcher,
    index_map: dict[str, tuple[tuple[int, str, tuple[str, ...]], ...]],
    masked_cache: dict[int, set[int]],
) -> dict[int, list[str]]:
    """Evaluates an inverted-index keyword dictionary against product tokens in O(len(tokens))."""
    hits: dict[int, list[str]] = {}
    seen_pairs: set[tuple[int, str]] = set()
    entries = matcher.entries
    for idx, (stem, _raw, _sid) in enumerate(tokens):
        candidates = index_map.get(stem)
        if not candidates:
            continue
        for c_idx, raw_kw, kw_stems in candidates:
            masked = masked_cache.get(c_idx)
            if masked is None:
                masked = _masked_positions_for_exceptions(tokens, entries[c_idx].exceptions)
                masked_cache[c_idx] = masked
            if _matches_at_position(tokens, idx, kw_stems, masked):
                pair = (c_idx, raw_kw)
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    hits.setdefault(c_idx, []).append(raw_kw)
    return hits


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
        matcher = _get_compiled_clause_matcher(sites)
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
    strong_hits = _collect_lexical_hits(tokens, matcher, matcher.strong_index, masked_cache)
    weak_hits = _collect_lexical_hits(tokens, matcher, matcher.weak_index, masked_cache)

    flagged_codes = set(CATEGORY_FLAG_MAP.get(cat_slug, ()))
    boosted_codes = set(CATEGORY_BOOST_MAP.get(cat_slug, ())) | flagged_codes

    product_content_stems = {
        st for st, _raw, _sid in tokens if len(st) >= 3 and st not in _STOPWORDS
    }

    scored_clauses: list[tuple[float, _CompiledClauseEntry, list[str], list[str], bool, float]] = []
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

        # Strong hit OR 2+ weak hits escalate to full clause severity; single weak hit or category stays cautious
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
        if combined_kws:
            excerpt = ", ".join(combined_kws)
        else:
            excerpt = f"category:{cat_slug}"

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

    # In targeted AI verification, clear Stage 1 keyword false-positives for clauses that were
    # explicitly sent to Gemini and adjudicated safe by the model.
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

    matrix = build_platform_matrix(merged_matched)
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
