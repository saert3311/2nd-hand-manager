from django.core.management.base import BaseCommand
from django.db.models import Q

from inventory.models import Category, Product, ProductCondition
from inventory.services.ai_service import (
    AIServiceError,
    generate_product_listing,
    infer_taxonomy_heuristically,
)


class Command(BaseCommand):
    help = (
        "Classifies products into the 12 official Rápido Pack categories and 4 condition states "
        "using deterministic keyword heuristics or Gemini Multimodal Vision (--use-ai)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Re-classify all products, including those that already have a category and condition.",
        )
        parser.add_argument(
            "--use-ai",
            action="store_true",
            help="Use Gemini Multimodal Vision API when GEMINI_API_KEY is configured, falling back to heuristics.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview classifications without saving changes to the database.",
        )

    def handle(self, *args, **options):
        reclassify_all = options.get("all", False)
        use_ai = options.get("use_ai", False)
        dry_run = options.get("dry_run", False)

        categories_by_slug = {c.slug: c for c in Category.objects.all()}
        valid_conditions = set(dict(ProductCondition.choices).keys())

        qs = Product.objects.select_related("category").prefetch_related("images").order_by("id")
        if not reclassify_all:
            qs = qs.filter(Q(category__isnull=True) | Q(condition=""))

        products = list(qs)
        prefix = "[DRY RUN] " if dry_run else ""

        if not products:
            self.stdout.write(self.style.SUCCESS(f"{prefix}No products require taxonomy classification."))
            return

        updated_count = 0
        for product in products:
            cat_slug = ""
            cond_code = ""

            if use_ai:
                try:
                    ai_data = generate_product_listing(product, language="es")
                    cat_slug = (ai_data.get("category_slug") or "").strip()
                    cond_code = (ai_data.get("condition") or "").strip()
                except AIServiceError:
                    pass

            if not cat_slug or not cond_code:
                combined_text = f"{product.ai_title} {product.ai_description} {product.raw_note}"
                heur_cat, heur_cond = infer_taxonomy_heuristically(combined_text)
                cat_slug = cat_slug or heur_cat
                cond_code = cond_code or heur_cond

            target_category = categories_by_slug.get(cat_slug)
            target_condition = cond_code if cond_code in valid_conditions else ProductCondition.GOOD

            changed = False
            update_fields = []
            if (reclassify_all or not product.category_id) and target_category:
                product.category = target_category
                update_fields.append("category")
                changed = True
            if (reclassify_all or not product.condition) and target_condition:
                product.condition = target_condition
                update_fields.append("condition")
                changed = True

            if changed:
                updated_count += 1
                if not dry_run:
                    product.save(update_fields=[*update_fields, "updated_at"])
                cat_label = product.category.slug if product.category else "none"
                self.stdout.write(
                    f"  {prefix}Product #{product.pk} ({product.display_title[:45]}): "
                    f"category={cat_label}, condition={product.condition}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}Classified {updated_count} of {len(products)} inspected product(s)."
            )
        )
