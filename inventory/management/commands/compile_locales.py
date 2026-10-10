from pathlib import Path

import polib
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Compiles all .po translation catalogs to binary .mo files across LOCALE_PATHS using polib (Windows-friendly)."

    def handle(self, *args, **options):
        locale_paths = getattr(settings, "LOCALE_PATHS", [])
        if not locale_paths:
            self.stdout.write(self.style.WARNING("No LOCALE_PATHS configured in settings."))
            return

        compiled_count = 0
        for locale_dir in locale_paths:
            locale_dir = Path(locale_dir)
            if not locale_dir.exists():
                continue

            for po_path in locale_dir.glob("**/django.po"):
                mo_path = po_path.with_suffix(".mo")
                po = polib.pofile(str(po_path))
                po.save_as_mofile(str(mo_path))
                self.stdout.write(self.style.SUCCESS(f"Compiled: {po_path.name} -> {mo_path.name} ({po_path.parent})"))
                compiled_count += 1

        if compiled_count == 0:
            self.stdout.write(self.style.NOTICE("No .po files found to compile."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Successfully compiled {compiled_count} catalog(s)."))
