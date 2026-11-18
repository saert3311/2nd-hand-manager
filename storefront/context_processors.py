import json
from urllib.parse import unquote

from django.conf import settings
from django.urls import reverse

from inventory.models import StorefrontConfiguration
from inventory.permissions import is_assistant, is_manager

ASTRO_LANDING_URL = "https://rapidopackvalencia.es"
STORE_PHONE_DISPLAY = "640 39 74 34"
STORE_PHONE_HREF = "tel:640397434"
GTM_CONTAINER_ID = "GTM-PGBXBVXJ"
COOKIE_CONSENT_NAME = "rpv_cookie_consent"

_CONSENT_GRANTED_VALUES = frozenset({"accepted", "accept_all", "all", "granted", "true", "1", "analytics"})
_CONSENT_DENIED_VALUES = frozenset(
    {"rejected", "reject_all", "essential", "necessary", "denied", "false", "0", "technical"}
)


def _parse_rpv_cookie_consent(raw_value: str | None) -> tuple[bool, bool]:
    """
    Parse shared ``rpv_cookie_consent`` cookie (JSON or scalar token) into
    ``(has_decided, analytics_granted)`` while ignoring malformed values.
    """
    if not raw_value or not isinstance(raw_value, str):
        return False, False

    decoded = unquote(raw_value.strip())
    if not decoded:
        return False, False

    if decoded.startswith("{"):
        try:
            payload = json.loads(decoded)
        except (TypeError, ValueError):
            return False, False
        if not isinstance(payload, dict):
            return False, False

        for key in ("analytics", "analytics_storage", "status", "choice"):
            if key not in payload:
                continue
            val = payload[key]
            if isinstance(val, bool):
                return True, val
            if isinstance(val, str):
                norm = val.strip().lower()
                if norm in _CONSENT_GRANTED_VALUES:
                    return True, True
                if norm in _CONSENT_DENIED_VALUES:
                    return True, False
        if "essential" in payload or "necessary" in payload:
            return True, False
        return False, False

    normalized = decoded.lower()
    if normalized in _CONSENT_GRANTED_VALUES:
        return True, True
    if normalized in _CONSENT_DENIED_VALUES:
        return True, False
    return False, False


def get_request_storefront_config(request) -> StorefrontConfiguration:
    """Return the StorefrontConfiguration singleton, cached once per HTTP request."""
    cached = getattr(request, "_storefront_config_cache", None) if request is not None else None
    if cached is not None:
        return cached
    try:
        config = StorefrontConfiguration.get_solo()
    except Exception:
        config = StorefrontConfiguration()
    if request is not None:
        try:
            request._storefront_config_cache = config
        except Exception:
            pass
    return config


def storefront_config(request):
    """
    Injects the StorefrontConfiguration singleton, Astro landing base URL, canonical URL,
    GTM & cookie consent flags, live store status, and staff role flags into public templates.
    """
    config = get_request_storefront_config(request)

    user = getattr(request, "user", None)
    authenticated = bool(user and user.is_authenticated)
    manager_flag = bool(authenticated and is_manager(user))
    assistant_flag = bool(authenticated and is_assistant(user))
    staff_member = bool(
        manager_flag
        or assistant_flag
        or (authenticated and (getattr(user, "is_staff", False) or getattr(user, "is_superuser", False)))
    )
    gtm_container_id = getattr(settings, "GTM_CONTAINER_ID", GTM_CONTAINER_ID)
    gtm_enabled = bool(gtm_container_id and not staff_member)

    try:
        whatsapp_url = reverse("storefront:go_whatsapp")
    except Exception:
        whatsapp_url = f"https://wa.me/{config.clean_whatsapp_number}"

    raw_consent = request.COOKIES.get(COOKIE_CONSENT_NAME) if hasattr(request, "COOKIES") else None
    cookie_consent_decided, cookie_analytics_granted = _parse_rpv_cookie_consent(raw_consent)
    try:
        default_canonical_url = request.build_absolute_uri(request.path)
    except Exception:
        default_canonical_url = ""

    return {
        "storefront": config,
        "store_config": config,
        "astro_landing_url": ASTRO_LANDING_URL,
        "default_canonical_url": default_canonical_url,
        "gtm_container_id": gtm_container_id,
        "gtm_enabled": gtm_enabled,
        "cookie_consent_name": COOKIE_CONSENT_NAME,
        "cookie_consent_decided": cookie_consent_decided,
        "cookie_analytics_granted": cookie_analytics_granted,
        "store_phone_display": STORE_PHONE_DISPLAY,
        "store_phone_href": STORE_PHONE_HREF,
        "storefront_whatsapp_url": whatsapp_url,
        "is_staff_member": staff_member,
        "is_manager_user": manager_flag,
        "is_assistant_user": assistant_flag,
    }
