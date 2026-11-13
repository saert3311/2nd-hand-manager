import re
import unicodedata
from datetime import datetime
from decimal import Decimal, InvalidOperation
from functools import lru_cache

from django.db.models import Exists, OuterRef, Q


def fold_search_text(text: str) -> str:
    """
    Case-folds Unicode text and strips all combining diacritical marks so
    Spanish/European accents (á, é, í, ó, ú, ü, ñ, Á, É, Í, Ó, Ú, Ü, Ñ)
    compare equal regardless of accentuation or uppercase/lowercase.
    """
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", str(text).casefold())
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


@lru_cache(maxsize=512)
def _compile_like_regex(pattern: str, escape: str) -> re.Pattern:
    parts: list[str] = ["^"]
    i = 0
    n = len(pattern)
    while i < n:
        ch = pattern[i]
        if escape and ch == escape and i + 1 < n:
            parts.append(re.escape(fold_search_text(pattern[i + 1])))
            i += 2
            continue
        if ch == "%":
            parts.append(".*")
        elif ch == "_":
            parts.append(".")
        else:
            parts.append(re.escape(fold_search_text(ch)))
        i += 1
    parts.append("$")
    return re.compile("".join(parts), re.DOTALL)


def sqlite_unaccent_like(pattern, value, escape=None) -> bool:
    """
    Deterministic replacement for SQLite's built-in 2-arg and 3-arg LIKE()
    scalar functions. Evaluates LIKE with full Unicode case-folding and
    diacritic stripping.
    """
    if pattern is None or value is None:
        return False
    pat_str = str(pattern)
    val_folded = fold_search_text(str(value))
    esc_str = str(escape) if escape else ""

    # Fast path for standard __icontains (%substring%) without inner wildcards
    if len(pat_str) >= 2 and pat_str.startswith("%") and pat_str.endswith("%"):
        inner = pat_str[1:-1]
        if "%" not in inner and "_" not in inner and (not esc_str or esc_str not in inner):
            return fold_search_text(inner) in val_folded

    regex = _compile_like_regex(pat_str, esc_str)
    return bool(regex.match(val_folded))


def register_sqlite_search_functions(connection) -> None:
    """
    Registers deterministic Unicode case- and accent-insensitive LIKE functions
    on a SQLite database connection.
    """
    if getattr(connection, "vendor", None) != "sqlite":
        return
    raw_conn = getattr(connection, "connection", None)
    if raw_conn is None:
        return
    try:
        raw_conn.create_function("like", 2, sqlite_unaccent_like, deterministic=True)
        raw_conn.create_function("like", 3, sqlite_unaccent_like, deterministic=True)
    except Exception:
        pass


_DATE_FORMATS = (
    "%Y-%m-%d",  # ISO: 2026-10-10
    "%d/%m/%Y",  # EU: 10/10/2026
    "%m/%d/%Y",  # US: 10/10/2026
    "%d-%m-%Y",  # 10-10-2026
    "%Y/%m/%d",  # 2026/10/10
    "%d.%m.%Y",  # 10.10.2026
)

_EXACT_REF_RE = re.compile(r"^(?:#|ref:)(\d+)$", re.IGNORECASE)
_PALLET_TOKEN_RE = re.compile(r"^(?:pallet|pal[eé]t?):(\d+)$", re.IGNORECASE)
_PRICE_RANGE_RE = re.compile(r"^(\d+(?:[.,]\d+)?)\s*(?:\.\.|-\s*(?=\d+(?:[.,]\d+)?\s*€))(\d+(?:[.,]\d+)?)\s*€?$")
_PRICE_CMP_RE = re.compile(r"^(<=|<|>=|>)\s*(\d+(?:[.,]\d+)?)\s*€?$")


def _parse_decimal_token(raw: str) -> Decimal | None:
    try:
        return Decimal(raw.replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def _build_date_query(token: str) -> Q:
    matched_date = None
    for fmt in _DATE_FORMATS:
        try:
            matched_date = datetime.strptime(token, fmt).date()
            break
        except ValueError:
            continue

    if matched_date:
        return Q(created_at__date=matched_date) | Q(sold_at__date=matched_date)

    ym_match = re.fullmatch(r"^(\d{4})[-/.](\d{1,2})$", token)
    if ym_match:
        year, month = int(ym_match.group(1)), int(ym_match.group(2))
        if 1 <= month <= 12:
            return (
                (Q(created_at__year=year) & Q(created_at__month=month))
                | (Q(sold_at__year=year) & Q(sold_at__month=month))
            )

    if re.fullmatch(r"^\d{4}$", token):
        year = int(token)
        if 1900 <= year <= 2100:
            return Q(created_at__year=year) | Q(sold_at__year=year)

    return Q()


def tokenize_search_query(query_str: str) -> list[str]:
    """
    Normalizes multi-word shorthand prefixes (e.g. 'Ref. #0042' -> 'ref:0042',
    'Pallet #5' -> 'pallet:5') and splits query_str into quoted phrases and
    whitespace-delimited tokens.
    """
    cleaned = (query_str or "").strip()
    if not cleaned:
        return []

    normalized = re.sub(
        r"(?:^|(?<=\s))ref\.?\s*#?(\d+)(?=\s|$)",
        r"ref:\1",
        cleaned,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        r"(?:^|(?<=\s))(?:pal[eé]t?|pallet)\s*(?:#|n[º°]?\.?|:)\s*(\d+)(?=\s|$)",
        r"pallet:\1",
        normalized,
        flags=re.IGNORECASE,
    )

    tokens: list[str] = []
    for match in re.finditer(r'"([^"]+)"|(\S+)', normalized):
        tok = (match.group(1) if match.group(1) is not None else match.group(2)).strip()
        if tok:
            tokens.append(tok)
    return tokens


def _build_token_query(token: str, scope: str) -> Q:
    from inventory.models import ProductClarification, ProductListingLink

    # 1. Exact Product ID / Reference (#42, ref:42, Ref. #0042)
    ref_match = _EXACT_REF_RE.fullmatch(token)
    if ref_match:
        return Q(pk=int(ref_match.group(1)))

    # 2. Exact Pallet Shorthand (pale:5, pallet:5 — internal scope only)
    if scope == "internal":
        pallet_match = _PALLET_TOKEN_RE.fullmatch(token)
        if pallet_match:
            return Q(pallet__number=int(pallet_match.group(1)))

    # 3. Price Range / Comparison Shorthands (<20, >=50, 15..50)
    range_match = _PRICE_RANGE_RE.fullmatch(token)
    if range_match:
        low = _parse_decimal_token(range_match.group(1))
        high = _parse_decimal_token(range_match.group(2))
        if low is not None and high is not None:
            if low > high:
                low, high = high, low
            return Q(sale_price__gte=low, sale_price__lte=high)

    cmp_match = _PRICE_CMP_RE.fullmatch(token)
    if cmp_match:
        op, val_str = cmp_match.group(1), cmp_match.group(2)
        val = _parse_decimal_token(val_str)
        if val is not None:
            if op == "<":
                return Q(sale_price__lt=val)
            if op == "<=":
                return Q(sale_price__lte=val)
            if op == ">":
                return Q(sale_price__gt=val)
            if op == ">=":
                return Q(sale_price__gte=val)

    # 4. Public Storefront Scope (strictly public fields — zero internal leakage)
    if scope == "public":
        pub_q = (
            Q(ai_title__icontains=token)
            | Q(ai_description__icontains=token)
            | Q(category__name__icontains=token)
            | Q(category__name_en__icontains=token)
        )
        if token.isdigit():
            pub_q |= Q(pk=int(token))
        return pub_q

    # 5. Internal Dashboard Scope (comprehensive staging, origin, clarification & date coverage)
    text_q = (
        Q(ai_title__icontains=token)
        | Q(raw_note__icontains=token)
        | Q(ai_description__icontains=token)
        | Q(provider__name__icontains=token)
        | Q(category__name__icontains=token)
        | Q(category__name_en__icontains=token)
        | Q(pallet__notes__icontains=token)
        | Q(sold_channel_notes__icontains=token)
        | Q(sold_marketplace__name__icontains=token)
        | Q(
            Exists(
                ProductClarification.objects.filter(product=OuterRef("pk")).filter(
                    Q(question__icontains=token) | Q(answer__icontains=token)
                )
            )
        )
        | Q(
            Exists(
                ProductListingLink.objects.filter(product=OuterRef("pk"), is_active=True).filter(
                    Q(site__name__icontains=token) | Q(url__icontains=token)
                )
            )
        )
    )

    if token.isdigit():
        num_val = int(token)
        text_q |= Q(pk=num_val) | Q(pallet__number=num_val)

    date_q = _build_date_query(token)
    if date_q:
        return text_q | date_q

    return text_q


def build_search_query(query_str: str, scope: str = "internal") -> Q:
    """
    Builds a Django ORM Q object for product search.
    - Combines multiple whitespace/quoted tokens with AND so words can match
      in any order across fields.
    - Supports scope="internal" (full staging/origin/clarifications/dates/shorthands)
      and scope="public" (strictly public storefront fields).
    """
    tokens = tokenize_search_query(query_str)
    if not tokens:
        return Q()

    combined_q = _build_token_query(tokens[0], scope=scope)
    for token in tokens[1:]:
        combined_q &= _build_token_query(token, scope=scope)
    return combined_q
