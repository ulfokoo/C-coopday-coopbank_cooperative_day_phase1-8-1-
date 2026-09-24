from functools import wraps
from flask import abort, request
from flask_login import current_user


def user_has_permission(code):
    """Template/route-safe permission check. Anonymous users never pass."""
    if not current_user.is_authenticated:
        return False
    return current_user.has_permission(code)


def permission_required(code):
    """Route decorator: 403 if the logged-in user lacks this permission.
    SUPER ADMIN role always passes (see Role.has_permission)."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(403)
            if not current_user.has_permission(code):
                abort(403)
            return view_func(*args, **kwargs)

        return wrapped

    return decorator


def role_required(*role_names):
    """Route decorator: 403 unless the user's role name is in role_names
    (SUPER ADMIN always passes)."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(403)
            if current_user.is_super_admin:
                return view_func(*args, **kwargs)
            if not current_user.has_role(*role_names):
                abort(403)
            return view_func(*args, **kwargs)

        return wrapped

    return decorator
