from inventory.models import Category, StorefrontConfiguration
from inventory.permissions import is_assistant, is_manager


def storefront_config(request):
    """
    Injects the StorefrontConfiguration singleton, active navigation categories,
    and staff role flags into public storefront templates.
    """
    try:
        config = StorefrontConfiguration.get_solo()
    except Exception:
        config = StorefrontConfiguration()

    try:
        categories = list(Category.objects.filter(is_active=True).order_by("order", "name"))
    except Exception:
        categories = []

    user = getattr(request, "user", None)
    authenticated = bool(user and user.is_authenticated)
    manager_flag = bool(authenticated and is_manager(user))
    assistant_flag = bool(authenticated and is_assistant(user))

    return {
        "storefront": config,
        "store_config": config,
        "storefront_whatsapp_url": f"https://wa.me/{config.clean_whatsapp_number}",
        "nav_categories": categories,
        "is_staff_member": manager_flag or assistant_flag,
        "is_manager_user": manager_flag,
        "is_assistant_user": assistant_flag,
    }
