from django.db import migrations


def sync_product_clarification_status(apps, schema_editor):
    Product = apps.get_model('inventory', 'Product')

    # Ensure any unsold product with pending clarifications has status 'awaiting_info'
    products_with_pending = Product.objects.filter(
        clarifications__status='pending',
        is_sold=False,
    ).exclude(status='sold')

    for p in products_with_pending:
        if p.status != 'awaiting_info':
            p.status = 'awaiting_info'
            p.save(update_fields=['status'])


def reverse_sync(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0010_seed_default_groups'),
    ]

    operations = [
        migrations.RunPython(sync_product_clarification_status, reverse_sync),
    ]
