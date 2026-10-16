from django.db import migrations


def seed_default_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    for group_name in ['assistants', 'managers']:
        Group.objects.get_or_create(name=group_name)


def unseed_default_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name__in=['assistants', 'managers']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0009_databasebackuplog'),
    ]

    operations = [
        migrations.RunPython(seed_default_groups, unseed_default_groups),
    ]
