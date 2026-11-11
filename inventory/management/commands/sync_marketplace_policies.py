from django.core.management.base import BaseCommand

from inventory.models import MarketplaceSite
from inventory.services.compliance_service import ensure_default_policy_clauses
from inventory.services.policy_sync_service import sync_site_policy


class Command(BaseCommand):
    help = (
        "Synchronizes marketplace Terms & Conditions from configured policy_url (or policy_raw_text fallback), "
        "skips unchanged content via SHA-256 hash comparison, and indexes atomic PolicyClause vectors."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--site",
            type=str,
            default="",
            help="Optional MarketplaceSite slug to sync (e.g. wallapop, vinted).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force re-extraction and embedding refresh even if content hash has not changed.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview sync actions without writing changes to the database.",
        )
        parser.add_argument(
            "--no-ai",
            action="store_true",
            help="Skip external Gemini API calls and use deterministic local vectors only.",
        )

    def handle(self, *args, **options):
        site_slug = (options.get("site") or "").strip().lower()
        force = bool(options.get("force", False))
        dry_run = bool(options.get("dry_run", False))
        use_api = not bool(options.get("no_ai", False))

        prefix = "[DRY RUN] " if dry_run else ""

        if not dry_run:
            seeded = ensure_default_policy_clauses(use_api_embeddings=False)
            if seeded:
                self.stdout.write(self.style.SUCCESS(f"Seeded {seeded} default policy clause(s)."))

        qs = MarketplaceSite.objects.filter(is_active=True).order_by("order", "name")
        if site_slug:
            qs = qs.filter(slug=site_slug)

        sites = list(qs)
        if not sites:
            self.stdout.write(self.style.WARNING(f"{prefix}No matching active MarketplaceSite records found."))
            return

        for site in sites:
            res = sync_site_policy(site, force=force, dry_run=dry_run, use_api=use_api)
            status = res.get("status")
            source = res.get("source")
            updated = res.get("clauses_updated", 0)
            if status == "synced":
                self.stdout.write(
                    self.style.SUCCESS(
                        f"{prefix}{site.name} ({site.slug}): SYNCED via {source} ({updated} clauses updated)"
                    )
                )
            elif status == "unchanged":
                self.stdout.write(
                    f"{prefix}{site.name} ({site.slug}): UNCHANGED (SHA-256 matched via {source}; 0 tokens spent)"
                )
            elif status == "would_sync":
                self.stdout.write(
                    self.style.NOTICE(
                        f"{prefix}{site.name} ({site.slug}): WOULD SYNC via {source}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"{prefix}{site.name} ({site.slug}): SKIPPED ({res.get('error', 'no content')})"
                    )
                )
