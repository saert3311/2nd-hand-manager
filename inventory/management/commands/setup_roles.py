from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from inventory.permissions import ROLE_ASSISTANT, ROLE_MANAGER

User = get_user_model()


class Command(BaseCommand):
    help = "Initializes user groups (assistants, managers) and creates demo accounts for testing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-demo-users",
            action="store_true",
            help="Only create groups without creating demo accounts.",
        )

    def handle(self, *args, **options):
        # 1. Ensure Groups Exist
        assistant_group, _ = Group.objects.get_or_create(name=ROLE_ASSISTANT)
        manager_group, _ = Group.objects.get_or_create(name=ROLE_MANAGER)
        self.stdout.write(self.style.SUCCESS(f"Groups verified: '{ROLE_ASSISTANT}', '{ROLE_MANAGER}'"))

        if options["no_demo_users"]:
            return

        # 2. Create / Update Manager Demo Account
        manager_user, created_mgr = User.objects.get_or_create(
            username="manager",
            defaults={"is_staff": True, "email": "manager@example.com"}
        )
        manager_user.set_password("manager123")
        manager_user.is_staff = True
        manager_user.save()
        manager_user.groups.add(manager_group)
        self.stdout.write(
            self.style.SUCCESS("Manager account ready: username='manager', password='manager123' (staff/manager)")
        )

        # 3. Create / Update Assistant Demo Account
        asst_user, created_asst = User.objects.get_or_create(
            username="assistant",
            defaults={"email": "assistant@example.com"}
        )
        asst_user.set_password("assistant123")
        asst_user.is_staff = False
        asst_user.save()
        asst_user.groups.add(assistant_group)
        self.stdout.write(
            self.style.SUCCESS("Assistant account ready: username='assistant', password='assistant123' (assistant)")
        )
