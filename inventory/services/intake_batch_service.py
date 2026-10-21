import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from inventory.models import IntakeBatchSession, Product
from inventory.permissions import ROLE_MANAGER
from inventory.services import push_service

logger = logging.getLogger(__name__)


def get_debounce_minutes() -> int:
    """Return the configured sliding inactivity debounce window in minutes."""
    try:
        return int(getattr(settings, "INTAKE_SESSION_DEBOUNCE_MINUTES", 15))
    except (TypeError, ValueError):
        return 15


@transaction.atomic
def record_product_intake(product: Product, assistant=None) -> IntakeBatchSession | None:
    """
    Associate a newly cataloged draft product with an active IntakeBatchSession.
    If an open session exists for this assistant with activity within the debounce
    window, increments product_count and updates last_activity_at.
    Otherwise, initializes a fresh IntakeBatchSession.
    """
    user = assistant or product.created_by
    if not user:
        return None

    debounce_minutes = get_debounce_minutes()
    now = timezone.now()
    cutoff = now - timedelta(minutes=debounce_minutes)

    active_session = (
        IntakeBatchSession.objects.select_for_update()
        .filter(
            assistant=user,
            is_notified=False,
            last_activity_at__gte=cutoff,
        )
        .order_by("-last_activity_at")
        .first()
    )

    if active_session:
        active_session.product_count += 1
        active_session.last_activity_at = now
        active_session.save(update_fields=["product_count", "last_activity_at", "updated_at"])
    else:
        active_session = IntakeBatchSession.objects.create(
            assistant=user,
            started_at=now,
            last_activity_at=now,
            product_count=1,
            is_notified=False,
        )

    if product.batch_session_id != active_session.id:
        product.batch_session = active_session
        product.save(update_fields=["batch_session"])

    return active_session


def process_pending_intake_batches(
    debounce_minutes: int | None = None,
    dry_run: bool = False,
    notify_managers: bool = True,
) -> list[dict]:
    """
    Finds and processes open IntakeBatchSessions whose inactivity window has expired.
    Dispatches a single consolidated Web Push notification to store managers and
    marks each session as closed and notified.

    Returns a list of summary dicts for each processed batch session.
    """
    if debounce_minutes is None:
        debounce_minutes = get_debounce_minutes()

    now = timezone.now()
    cutoff = now - timedelta(minutes=debounce_minutes)

    # Query expired unnotified sessions
    expired_sessions = list(
        IntakeBatchSession.objects.filter(
            is_notified=False,
            last_activity_at__lte=cutoff,
        )
        .select_related("assistant")
        .order_by("last_activity_at")
    )

    results = []
    for session in expired_sessions:
        count = session.product_count
        assistant_name = session.assistant.get_full_name() or session.assistant.username

        title = str(_("📦 Lote completado: %(count)s nuevos productos") % {"count": count})
        body = str(_("Toca para revisar las prendas en el panel de staging."))
        url = "/dashboard/?status=draft"
        tag = f"intake-batch-{session.id}"

        sent_count = 0
        if not dry_run:
            if notify_managers:
                try:
                    sent_count = push_service.send_push_to_group(
                        group_name=ROLE_MANAGER,
                        title=title,
                        body=body,
                        url=url,
                        tag=tag,
                    )
                except Exception as exc:
                    logger.warning("Failed to dispatch push notification for intake batch %s: %s", session.id, exc)

            session.is_notified = True
            session.closed_at = now
            session.save(update_fields=["is_notified", "closed_at", "updated_at"])

        results.append({
            "session_id": session.id,
            "assistant": session.assistant.username,
            "assistant_display": assistant_name,
            "product_count": count,
            "is_dry_run": dry_run,
            "sent_notifications": sent_count,
            "last_activity_at": session.last_activity_at,
        })

    return results
