from django.conf import settings

from inventory.models import ClarificationStatus, ProductClarification


def notifications(request):
    """
    Global context processor providing count of unresolved clarification questions.
    Returns 0 for unauthenticated users.
    """
    if getattr(request, "user", None) and request.user.is_authenticated:
        count = ProductClarification.objects.filter(status=ClarificationStatus.PENDING).count()
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

