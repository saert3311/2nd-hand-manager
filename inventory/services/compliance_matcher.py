import re
import threading
import unicodedata
from dataclasses import dataclass
from typing import Any, Callable, Optional

from django.db.models import Count, Max

from inventory.models import MarketplaceSite, PolicyClause

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

STOPWORDS = frozenset({
    "a", "al", "con", "de", "del", "e", "el", "en", "es", "la", "las", "lo",
    "los", "o", "para", "por", "se", "sin", "su", "sus", "un", "una", "unas",
    "unos", "y", "and", "for", "from", "in", "of", "on", "or", "the", "to", "with",
    "articulo", "articulos", "producto", "productos", "venta", "vendo", "nuevo",
    "usado", "buen", "estado", "lote", "item", "items",
})

_NEGATION_WORDS = frozenset({
    "no", "ni", "sin", "nunca", "jamas", "nada", "tampoco",
    "not", "without", "never", "non", "0mg", "0%", "cero",
})

_NEGATION_BIGRAMS = frozenset({
    ("libre", "de"),
    ("free", "of"),
    ("exento", "de"),
})

_CLAUSE_BOUNDARY_CHARS = frozenset(".;:!?\n()[]{}")
_TOKEN_OR_BOUNDARY_RE = re.compile(r"[.;:!?\n()\[\]]|[a-z0-9]+(?:%|:[a-z0-9]+|\+)?")


def normalize_text(text: str) -> str:
    """Lowercase and strip diacritics for accent-insensitive Spanish/English matching."""
    raw = (text or "").strip().lower()
    nfkd = unicodedata.normalize("NFKD", raw)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


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
    Tokenizes text into `(stemmed_token, normalized_token, sentence_id)` tuples.
    Punctuation increments `sentence_id` so negations never bleed across sentence boundaries.
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


def clause_embedding_text(clause: Any) -> str:
    """Concatenates bilingual clause title, description, and trigger keywords for lexical indexing."""
    return (
        f"{clause.title_es} {clause.title_en} "
        f"{clause.description_es} {clause.description_en} "
        f"{' '.join(clause.hard_block_keywords or [])}"
    )


def estimate_naive_baseline_tokens(clauses: list[PolicyClause], sites: list[MarketplaceSite]) -> int:
    raw_policy_chars = sum(len((s.policy_raw_text or "").strip()) for s in sites)
    clause_chars = sum(
        len(c.title_es or "") + len(c.description_es or "") + len(c.title_en or "") + len(c.description_en or "")
        for c in clauses
    )
    estimated = (raw_policy_chars + clause_chars * 4) // 4
    return max(12000, estimated)


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
            if len(st) >= 3 and st not in STOPWORDS
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
        naive_baseline=estimate_naive_baseline_tokens(clauses, sites),
    )


def get_compiled_clause_matcher(
    sites: list[MarketplaceSite],
    seed_callback: Optional[Callable[[], Any]] = None,
) -> _CompiledClauseMatcher:
    global _COMPILED_MATCHER_CACHE
    stats = PolicyClause.objects.filter(is_active=True).aggregate(
        cnt=Count("id"),
        max_upd=Max("updated_at"),
    )
    cnt = int(stats.get("cnt") or 0)
    if cnt == 0 and seed_callback is not None:
        seed_callback()
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


def collect_lexical_hits(
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
