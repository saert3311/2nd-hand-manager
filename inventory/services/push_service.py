import json
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from pywebpush import WebPushException, webpush

from inventory.models import ClarificationStatus, ProductClarification, ProductStatus, PushSubscription
from inventory.permissions import ROLE_MANAGER

logger = logging.getLogger(__name__)


def is_push_configured() -> bool:
    """Return True if both VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY are configured."""
    pub = getattr(settings, "VAPID_PUBLIC_KEY", "").strip()
    priv = getattr(settings, "VAPID_PRIVATE_KEY", "").strip()
    return bool(pub and priv)


def _get_default_badge_count() -> int:
    """Return current count of unresolved clarification questions on active products."""
    try:
        return (
            ProductClarification.objects.filter(
                status=ClarificationStatus.PENDING,
                product__is_sold=False,
            )
            .exclude(product__status=ProductStatus.SOLD)
            .count()
        )
    except Exception:
        return 0


def send_push_to_subscription(
    subscription: PushSubscription,
    title: str,
    body: str,
    url: str = "/",
    tag: str = "",
    badge_count: int | None = None,
) -> bool:
    """
    Send an encrypted Web Push notification payload to a single PushSubscription.
    Automatically prunes the subscription record if the push service returns HTTP 404 or 410 Gone.
    """
    if not is_push_configured():
        logger.debug("Skipping push notification: VAPID keys are not configured.")
        return False

    if badge_count is None:
        badge_count = _get_default_badge_count()

    payload = {
        "title": title,
        "body": body,
        "url": url or "/",
        "tag": tag or "2ndhand-general",
        "icon": "/static/inventory/icons/icon-192.png",
        "badge": "/static/inventory/icons/icon-192.png",
        "badge_count": int(badge_count),
    }

    claims_email = getattr(settings, "VAPID_CLAIMS_EMAIL", "mailto:admin@localhost").strip()
    if claims_email and not claims_email.startswith("mailto:"):
        claims_email = f"mailto:{claims_email}"

    try:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {
                    "p256dh": subscription.p256dh,
                    "auth": subscription.auth,
                },
            },
            data=json.dumps(payload),
            vapid_private_key=settings.VAPID_PRIVATE_KEY.strip(),
            vapid_claims={"sub": claims_email or "mailto:admin@localhost"},
            timeout=5,
        )
        return True
    except WebPushException as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        if status_code in (404, 410):
            logger.info(
                "Pruning expired/revoked PushSubscription id=%s (HTTP %s).",
                subscription.pk,
                status_code,
            )
            subscription.delete()
        else:
            logger.warning(
                "WebPushException for subscription id=%s (HTTP %s): %s",
                subscription.pk,
                status_code,
                exc,
            )
        return False
    except Exception as exc:
        logger.warning("Unexpected error sending web push to subscription id=%s: %s", subscription.pk, exc)
        return False


def send_push_to_user(
    user,
    title: str,
    body: str,
    url: str = "/",
    tag: str = "",
    badge_count: int | None = None,
) -> int:
    """
    Send a Web Push notification to all active device subscriptions of a given user.
    Returns the number of successfully delivered notifications.
    """
    if not user or not getattr(user, "is_active", False) or not is_push_configured():
        return 0

    subscriptions = list(PushSubscription.objects.filter(user=user, is_active=True))
    sent_count = 0
    for sub in subscriptions:
        if send_push_to_subscription(
            subscription=sub,
            title=title,
            body=body,
            url=url,
            tag=tag,
            badge_count=badge_count,
        ):
            sent_count += 1
    return sent_count


def send_push_to_group(
    group_name: str,
    title: str,
    body: str,
    url: str = "/",
    tag: str = "",
    badge_count: int | None = None,
) -> int:
    """
    Send a Web Push notification to all active subscriptions of users belonging to `group_name`.
    For the managers group, also includes active staff and superuser accounts.
    Returns the number of successfully delivered notifications.
    """
    if not is_push_configured():
        return 0

    User = get_user_model()
    if group_name == ROLE_MANAGER:
        users = User.objects.filter(
            is_active=True,
        ).filter(Q(groups__name=group_name) | Q(is_staff=True) | Q(is_superuser=True)).distinct()
    else:
        users = User.objects.filter(
            is_active=True,
            groups__name=group_name,
        ).distinct()

    subscriptions = list(
        PushSubscription.objects.filter(
            user__in=users,
            is_active=True,
        ).select_related("user")
    )
    sent_count = 0
    for sub in subscriptions:
        if send_push_to_subscription(
            subscription=sub,
            title=title,
            body=body,
            url=url,
            tag=tag,
            badge_count=badge_count,
        ):
            sent_count += 1
    return sent_count
