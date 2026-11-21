from contextvars import ContextVar

from django.conf import settings

_current_user: ContextVar = ContextVar("current_user", default=None)


def get_current_user():
    """
    Returns the authenticated user from the current request context, or None.
    Thread-safe and async-safe across concurrent requests.
    """
    return _current_user.get()


def set_current_user(user):
    """
    Explicitly sets the user for the current context (useful for tests or tasks).
    Returns a token that can be passed to reset_current_user.
    """
    return _current_user.set(user)


def reset_current_user(token):
    """Resets the context variable to the state before set_current_user was called."""
    _current_user.reset(token)


class CurrentUserMiddleware:
    """
    Middleware that captures the authenticated request user in a thread-safe contextvar,
    making it available across model saves, signals, and audit log handlers.
    """

    STATELESS_PWA_PATHS = ("/sw.js", "/manifest.json")
    STATELESS_EXACT_PATHS = (*STATELESS_PWA_PATHS, "/favicon.ico")

    def __init__(self, get_response):
        self.get_response = get_response

    @classmethod
    def _is_stateless_request(cls, path: str) -> bool:
        if path in cls.STATELESS_EXACT_PATHS:
            return True
        for prefix_attr in ("STATIC_URL", "MEDIA_URL"):
            prefix = getattr(settings, prefix_attr, "") or ""
            if prefix.startswith("/") and path.startswith(prefix):
                return True
        return False

    def __call__(self, request):
        if self._is_stateless_request(request.path):
            return self.get_response(request)
        user = getattr(request, "user", None)
        authenticated_user = user if (user and getattr(user, "is_authenticated", False)) else None
        token = _current_user.set(authenticated_user)
        try:
            response = self.get_response(request)
        finally:
            _current_user.reset(token)
        return response
