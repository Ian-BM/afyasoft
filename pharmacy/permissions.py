from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from .models import UserProfile


def is_pharmacy_admin(user):
    if not user.is_authenticated:
        return False
    try:
        return user.pharmacy_profile.role == UserProfile.Role.ADMIN
    except UserProfile.DoesNotExist:
        return False


def is_pharmacy_manager(user):
    if not user.is_authenticated:
        return False
    try:
        return user.pharmacy_profile.role == UserProfile.Role.MANAGER
    except UserProfile.DoesNotExist:
        return False


def is_pharmacy_admin_or_manager(user):
    return is_pharmacy_admin(user) or is_pharmacy_manager(user)


def pharmacy_admin_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not is_pharmacy_admin(request.user):
            messages.error(
                request,
                "You do not have permission for that. Only admin can manage these features.",
            )
            return redirect("dashboard")
        return view_func(request, *args, **kwargs)

    return _wrapped


def pharmacy_staff_manager_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not is_pharmacy_admin_or_manager(request.user):
            messages.error(
                request,
                "You do not have permission for that. Only admin or manager can manage workers.",
            )
            return redirect("dashboard")
        return view_func(request, *args, **kwargs)

    return _wrapped
