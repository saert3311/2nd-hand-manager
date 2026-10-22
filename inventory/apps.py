from django.apps import AppConfig
from django.db.backends.signals import connection_created
from django.db.models.signals import post_migrate


def ensure_default_role_groups(sender, **kwargs):
    if sender.name == "inventory":
        from django.contrib.auth.models import Group

        from .permissions import ROLE_ASSISTANT, ROLE_MANAGER
        Group.objects.get_or_create(name=ROLE_ASSISTANT)
        Group.objects.get_or_create(name=ROLE_MANAGER)


def configure_sqlite_wal(sender, connection, **kwargs):
    if connection.vendor == "sqlite":
        db_name = str(connection.settings_dict.get("NAME", ""))
        if db_name and db_name != ":memory:" and "memorydb" not in db_name:
            try:
                with connection.cursor() as cursor:
                    cursor.execute("PRAGMA journal_mode=WAL;")
                    cursor.execute("PRAGMA synchronous=NORMAL;")
            except Exception:
                pass


class InventoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'inventory'

    def ready(self):
        post_migrate.connect(ensure_default_role_groups, sender=self)
        connection_created.connect(configure_sqlite_wal, dispatch_uid="inventory.sqlite_wal")
