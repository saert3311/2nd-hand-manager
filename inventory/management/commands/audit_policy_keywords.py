from collections import Counter

from django.core.management.base import BaseCommand

from inventory.models import PolicyClause, Product
from inventory.services.compliance_service import (
    _masked_positions_for_exceptions,
    _matches_at_position,
    _tokenize_with_sentences,
    ensure_default_policy_clauses,
    stem_phrase,
)


class Command(BaseCommand):
    help = (
        "Scans non-deleted catalog products against active PolicyClause keywords "
        "and reports noisy triggers matching above the configured threshold."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--threshold",
            type=float,
            default=0.05,
            help="Catalog match-rate threshold (0.0-1.0) above which a keyword is flagged as noisy (default: 0.05).",
        )

    def handle(self, *args, **options):
        threshold = max(0.0, min(1.0, float(options["threshold"])))
        ensure_default_policy_clauses(use_api_embeddings=False)

        products = list(
            Product.objects.filter(is_deleted=False)
            .select_related("category")
            .only("id", "ai_title", "ai_description", "raw_note", "category__name")
        )
        total = len(products)
        clauses = list(PolicyClause.objects.filter(is_active=True).order_by("code"))

        if total == 0:
            self.stdout.write(self.style.WARNING("No non-deleted products found in catalog to audit."))
            return

        tokenized_products = []
        for product in products:
            cat_name = product.category.name if product.category_id and product.category else ""
            combined = " ".join(
                part.strip()
                for part in (product.ai_title, product.ai_description, product.raw_note, cat_name)
                if part and part.strip()
            )
            tokenized_products.append(_tokenize_with_sentences(combined))

        noisy_findings = []
        for clause in clauses:
            exceptions = tuple(
                s for e in (clause.exception_phrases or []) if (s := stem_phrase(str(e)))
            )
            kw_defs: list[tuple[str, str, tuple[str, ...]]] = []
            for kw in (clause.hard_block_keywords or []):
                stems = stem_phrase(str(kw))
                if stems:
                    kw_defs.append(("strong", str(kw), stems))
            for kw in (clause.weak_keywords or []):
                stems = stem_phrase(str(kw))
                if stems:
                    kw_defs.append(("weak", str(kw), stems))

            kw_counts: Counter[tuple[str, str]] = Counter()
            for tokens in tokenized_products:
                masked = _masked_positions_for_exceptions(tokens, exceptions)
                matched_in_product: set[tuple[str, str]] = set()
                for kind, raw_kw, kw_stems in kw_defs:
                    first = kw_stems[0]
                    for idx, tok in enumerate(tokens):
                        if tok[0] == first and _matches_at_position(tokens, idx, kw_stems, masked):
                            matched_in_product.add((kind, raw_kw))
                            break
                for pair in matched_in_product:
                    kw_counts[pair] += 1

            for (kind, raw_kw), cnt in kw_counts.most_common():
                rate = cnt / total
                if rate > threshold:
                    noisy_findings.append((rate, cnt, clause.code, kind, raw_kw))

        noisy_findings.sort(reverse=True)
        self.stdout.write(
            f"Audited {len(clauses)} active policy clause(s) across {total} non-deleted product(s) "
            f"(threshold={threshold:.0%}):"
        )
        if not noisy_findings:
            self.stdout.write(self.style.SUCCESS("OK — 0 noisy keywords exceeded the match threshold."))
            return

        for rate, cnt, code, kind, raw_kw in noisy_findings:
            self.stdout.write(
                self.style.WARNING(
                    f"  NOISY [{code}] ({kind}) {raw_kw!r}: {cnt}/{total} ({rate:.1%})"
                )
            )
