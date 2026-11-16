from django.urls import reverse

from inventory.models import Category, MarketplaceSite, StorefrontConfiguration
from inventory.permissions import is_assistant, is_manager

ASTRO_LANDING_URL = "https://rapidopackvalencia.es"


def storefront_config(request):
    """
    Injects the StorefrontConfiguration singleton, active navigation categories,
    active external marketplace storefronts, Astro landing base URL, and staff role
    flags into public storefront templates.
    """
    try:
        config = StorefrontConfiguration.get_solo()
    except Exception:
        config = StorefrontConfiguration()

    try:
        categories = list(Category.objects.filter(is_active=True).order_by("order", "name"))
    except Exception:
        categories = []

    try:
        active_marketplace_sites = list(
            MarketplaceSite.objects.filter(is_active=True)
            .exclude(base_url="")
            .order_by("order", "name")
        )
    except Exception:
        active_marketplace_sites = []

    user = getattr(request, "user", None)
    authenticated = bool(user and user.is_authenticated)
    manager_flag = bool(authenticated and is_manager(user))
    assistant_flag = bool(authenticated and is_assistant(user))

    try:
        whatsapp_url = reverse("storefront:go_whatsapp")
    except Exception:
        whatsapp_url = f"https://wa.me/{config.clean_whatsapp_number}"

    return {
        "storefront": config,
        "store_config": config,
        "astro_landing_url": ASTRO_LANDING_URL,
        "active_marketplace_sites": active_marketplace_sites,
        "storefront_whatsapp_url": whatsapp_url,
        "storefront_direct_wa_url": f"https://wa.me/{config.clean_whatsapp_number}",
        "nav_categories": categories,
        "is_staff_member": manager_flag or assistant_flag,
        "is_manager_user": manager_flag,
        "is_assistant_user": assistant_flag,
    }
