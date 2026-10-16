from django.apps import AppConfig
from django.db.models.signals import post_migrate


def ensure_default_role_groups(sender, **kwargs):
    if sender.name == "inventory":
        from django.contrib.auth.models import Group

        from .permissions import ROLE_ASSISTANT, ROLE_MANAGER
        Group.objects.get_or_create(name=ROLE_ASSISTANT)
        Group.objects.get_or_create(name=ROLE_MANAGER)


class InventoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'inventory'

    def ready(self):
        post_migrate.connect(ensure_default_role_groups, sender=self)

