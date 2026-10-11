from django.db import migrations


def seed_default_marketplace_sites(apps, schema_editor):
    MarketplaceSite = apps.get_model('inventory', 'MarketplaceSite')

    platforms = [
        {
            "name": "Wallapop",
            "slug": "wallapop",
            "base_url": "https://es.wallapop.com",
            "order": 1,
            "is_active": True,
        },
        {
            "name": "Vinted",
            "slug": "vinted",
            "base_url": "https://www.vinted.es",
            "order": 2,
            "is_active": True,
        },
        {
            "name": "Milanuncios",
            "slug": "milanuncios",
            "base_url": "https://www.milanuncios.com",
            "order": 3,
            "is_active": True,
        },
        {
            "name": "eBay",
            "slug": "ebay",
            "base_url": "https://www.ebay.es",
            "order": 4,
            "is_active": True,
        },
    ]

    for p in platforms:
        MarketplaceSite.objects.get_or_create(
            slug=p["slug"],
            defaults={
                "name": p["name"],
                "base_url": p["base_url"],
                "order": p["order"],
                "is_active": p["is_active"],
            }
        )


def unseed_default_marketplace_sites(apps, schema_editor):
    MarketplaceSite = apps.get_model('inventory', 'MarketplaceSite')
    MarketplaceSite.objects.filter(slug__in=["wallapop", "vinted", "milanuncios", "ebay"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0005_marketplacesite_productlistinglink'),
    ]

    operations = [
        migrations.RunPython(seed_default_marketplace_sites, unseed_default_marketplace_sites),
    ]
