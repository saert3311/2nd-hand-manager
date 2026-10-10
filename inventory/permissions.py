from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.utils.translation import gettext as _

ROLE_ASSISTANT = "assistants"
ROLE_MANAGER = "managers"


def is_manager(user) -> bool:
    """
    Returns True if user is superuser, staff, or in 'managers' group.
    """
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.is_staff or user.groups.filter(name=ROLE_MANAGER).exists()


def is_assistant(user) -> bool:
    """
    Returns True if user is in 'assistants' group.
    """
    if not user.is_authenticated:
        return False
    return user.groups.filter(name=ROLE_ASSISTANT).exists()


def manager_required(view_func):
    """
    Decorator requiring the user to have manager privileges.
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if not is_manager(request.user):
            raise PermissionDenied(_("Manager privileges required to access this action."))
        return view_func(request, *args, **kwargs)
    return _wrapped_view

