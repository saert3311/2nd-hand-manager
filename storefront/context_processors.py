from datetime import datetime
from zoneinfo import ZoneInfo

from django.urls import reverse
from django.utils.translation import gettext as _

from inventory.models import Category, MarketplaceSite, StorefrontConfiguration
from inventory.permissions import is_assistant, is_manager

ASTRO_LANDING_URL = "https://rapidopackvalencia.es"
STORE_PHONE_DISPLAY = "640 39 74 34"
STORE_PHONE_HREF = "tel:640397434"
STORE_TIMEZONE = ZoneInfo("Europe/Madrid")


def _compute_live_store_status() -> tuple[bool, str]:
    """
    Returns (is_open, localized_status_label) for the Alfafar physical store
    schedule in Europe/Madrid local time (Mon–Fri 09:30–20:00, Sat 10:00–15:00).
    """
    try:
        now = datetime.now(STORE_TIMEZONE)
    except Exception:
        return True, _("Mon–Fri 9:30–20:00 · Sat 10:00–15:00")

    weekday = now.weekday()
    hhmm = now.hour * 60 + now.minute
    if 0 <= weekday <= 4 and (9 * 60 + 30) <= hhmm < (20 * 60):
        return True, _("Open now · Until 20:00")
    if weekday == 5 and (10 * 60) <= hhmm < (15 * 60):
        return True, _("Open now · Until 15:00")
    return False, _("Closed now · Mon–Fri 9:30–20:00")


def storefront_config(request):
    """
    Injects the StorefrontConfiguration singleton, active navigation categories,
    active external marketplace storefronts, Astro landing base URL, live store
    status, and staff role flags into public storefront templates.
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

    store_is_open, store_live_status_label = _compute_live_store_status()

    return {
        "storefront": config,
        "store_config": config,
        "astro_landing_url": ASTRO_LANDING_URL,
        "store_phone_display": STORE_PHONE_DISPLAY,
        "store_phone_href": STORE_PHONE_HREF,
        "store_is_open": store_is_open,
        "store_live_status_label": store_live_status_label,
        "active_marketplace_sites": active_marketplace_sites,
        "storefront_whatsapp_url": whatsapp_url,
        "storefront_direct_wa_url": f"https://wa.me/{config.clean_whatsapp_number}",
        "nav_categories": categories,
        "is_staff_member": manager_flag or assistant_flag,
        "is_manager_user": manager_flag,
        "is_assistant_user": assistant_flag,
    }
