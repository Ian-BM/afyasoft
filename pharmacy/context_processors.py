from .models import UserProfile


def pharmacy_roles(request):
    if not request.user.is_authenticated:
        return {
            "pharmacy_is_admin": False,
            "pharmacy_role": None,
        }
    try:
        role = request.user.pharmacy_profile.role
    except UserProfile.DoesNotExist:
        role = UserProfile.Role.WORKER
    return {
        "pharmacy_is_admin": role == UserProfile.Role.ADMIN,
        "pharmacy_role": role,
    }
