from django.conf import settings

from inventory.models import ClarificationStatus, ProductClarification, ProductStatus


def notifications(request):
    """
    Global context processor providing count of unresolved clarification questions.
    Returns 0 for unauthenticated users. Excludes sold products.
    """
    if getattr(request, "user", None) and request.user.is_authenticated:
        count = (
            ProductClarification.objects.filter(
                status=ClarificationStatus.PENDING,
                product__is_sold=False,
            )
            .exclude(product__status=ProductStatus.SOLD)
            .count()
        )
        return {"pending_clarifications_count": count}
    return {"pending_clarifications_count": 0}


def turnstile(request):
    """
    Global context processor injecting Cloudflare Turnstile settings into templates.
    """
    return {
        "TURNSTILE_SITE_KEY": getattr(settings, "TURNSTILE_SITE_KEY", ""),
        "TURNSTILE_ENABLED": getattr(settings, "TURNSTILE_ENABLED", False),
    }


def pwa_push(request):
    """
    Global context processor exposing VAPID public key, push configuration status,
    and whether the authenticated user has at least one active PushSubscription.
    """
    from inventory.models import PushSubscription
    from inventory.services.push_service import is_push_configured

    vapid_public_key = getattr(settings, "VAPID_PUBLIC_KEY", "").strip()
    push_configured = is_push_configured()
    has_sub = False
    if getattr(request, "user", None) and request.user.is_authenticated:
        has_sub = PushSubscription.objects.filter(user=request.user, is_active=True).exists()
    return {
        "VAPID_PUBLIC_KEY": vapid_public_key,
        "PUSH_CONFIGURED": push_configured,
        "user_has_push_subscription": has_sub,
    }


def build_info(request):
    """
    Global context processor injecting compilation timestamp, Git commit SHA,
    application version, and environment metadata into templates.
    """
    from inventory.services.version_service import get_build_info

    return {"build_info": get_build_info()}


