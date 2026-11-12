from django.db import migrations


def seed_default_walkin_provider(apps, schema_editor):
    Provider = apps.get_model("inventory", "Provider")
    Provider.objects.get_or_create(
        slug="compra-en-tienda-particular",
        defaults={
            "name": "Compra en Tienda / Particular",
            "provider_type": "walk_in",
            "notes": "Built-in origin for walk-in in-store individual buyouts (seller details recorded per item).",
            "is_active": True,
        },
    )


def unseed_default_walkin_provider(apps, schema_editor):
    Provider = apps.get_model("inventory", "Provider")
    Provider.objects.filter(slug="compra-en-tienda-particular").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0028_provider_and_product_origins"),
    ]

    operations = [
        migrations.RunPython(seed_default_walkin_provider, unseed_default_walkin_provider),
    ]
