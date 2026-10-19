from contextvars import ContextVar

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

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        authenticated_user = user if (user and getattr(user, "is_authenticated", False)) else None
        token = _current_user.set(authenticated_user)
        try:
            response = self.get_response(request)
        finally:
            _current_user.reset(token)
        return response
