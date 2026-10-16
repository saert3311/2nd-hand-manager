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

