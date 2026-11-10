from django.db import migrations

from inventory.services.compliance_service import (
    DEFAULT_POLICY_CLAUSES_SEED,
    DEFAULT_POLICY_URL_MAP,
    compute_local_ngram_vector,
)


def seed_default_policy_clauses(apps, schema_editor):
    MarketplaceSite = apps.get_model("inventory", "MarketplaceSite")
    PolicyClause = apps.get_model("inventory", "PolicyClause")

    sites_by_slug = {s.slug: s for s in MarketplaceSite.objects.all()}
    for slug, url in DEFAULT_POLICY_URL_MAP.items():
        site = sites_by_slug.get(slug)
        if site and not (site.policy_url or "").strip():
            site.policy_url = url
            site.save(update_fields=["policy_url"])

    for item in DEFAULT_POLICY_CLAUSES_SEED:
        site_obj = sites_by_slug.get(item["site_slug"]) if item["site_slug"] else None
        seed_text = (
            f"{item['title_es']} {item['title_en']} "
            f"{item['description_es']} {item['description_en']} "
            f"{' '.join(item['hard_block_keywords'])}"
        )
        PolicyClause.objects.get_or_create(
            code=item["code"],
            defaults={
                "site": site_obj,
                "category": item["category"],
                "severity": item["severity"],
                "title_es": item["title_es"],
                "title_en": item["title_en"],
                "description_es": item["description_es"],
                "description_en": item["description_en"],
                "hard_block_keywords": list(item["hard_block_keywords"]),
                "embedding_vector": compute_local_ngram_vector(seed_text),
                "is_active": True,
            },
        )


def unseed_default_policy_clauses(apps, schema_editor):
    PolicyClause = apps.get_model("inventory", "PolicyClause")
    codes = [item["code"] for item in DEFAULT_POLICY_CLAUSES_SEED]
    PolicyClause.objects.filter(code__in=codes).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0025_marketplacesite_policy_content_hash_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_default_policy_clauses, unseed_default_policy_clauses),
    ]
