import re
from datetime import datetime

from django.db.models import Q


def build_search_query(query_str: str) -> Q:
    """
    Builds a Django ORM Q object searching across:
    1. Title: ai_title
    2. Description & Notes: ai_description, raw_note
    3. Dates: created_at__date or sold_at__date when query matches a date pattern.
    """
    cleaned = query_str.strip()
    if not cleaned:
        return Q()

    # Base text condition: search title, notes, and AI description
    text_q = (
        Q(ai_title__icontains=cleaned)
        | Q(raw_note__icontains=cleaned)
        | Q(ai_description__icontains=cleaned)
    )

    date_q = Q()

    # Date formats to attempt parsing
    date_formats = [
        "%Y-%m-%d",  # ISO: 2026-10-10
        "%d/%m/%Y",  # EU: 10/10/2026
        "%m/%d/%Y",  # US: 10/10/2026
        "%d-%m-%Y",  # 10-10-2026
        "%Y/%m/%d",  # 2026/10/10
        "%d.%m.%Y",  # 10.10.2026
    ]

    matched_date = None
    for fmt in date_formats:
        try:
            matched_date = datetime.strptime(cleaned, fmt).date()
            break
        except ValueError:
            continue

    if matched_date:
        date_q = Q(created_at__date=matched_date) | Q(sold_at__date=matched_date)
    else:
        # Check Year-Month pattern: YYYY-MM or YYYY/MM
        ym_match = re.fullmatch(r"^(\d{4})[-/.](\d{1,2})$", cleaned)
        if ym_match:
            year, month = int(ym_match.group(1)), int(ym_match.group(2))
            if 1 <= month <= 12:
                date_q = (
                    (Q(created_at__year=year) & Q(created_at__month=month))
                    | (Q(sold_at__year=year) & Q(sold_at__month=month))
                )
        else:
            # Check 4-digit Year: YYYY
            if re.fullmatch(r"^\d{4}$", cleaned):
                year = int(cleaned)
                if 1900 <= year <= 2100:
                    date_q = Q(created_at__year=year) | Q(sold_at__year=year)

    if date_q:
        return text_q | date_q

    return text_q
