from .models import UserProfile


def pharmacy_roles(request):
    if not request.user.is_authenticated:
        return {
            "pharmacy_is_admin": False,
            "pharmacy_is_manager": False,
            "pharmacy_can_manage_staff": False,
            "pharmacy_can_add_medicine": False,
            "pharmacy_role": None,
            "pharmacy_display_name": "",
            "pharmacy_name": "Afya Soft",
            "pharmacy_days_remaining": 0,
        }
    try:
        profile = request.user.pharmacy_profile
        role = profile.role
    except UserProfile.DoesNotExist:
        profile = None
        role = UserProfile.Role.WORKER
    return {
        "pharmacy_is_admin": role == UserProfile.Role.ADMIN,
        "pharmacy_is_manager": role == UserProfile.Role.MANAGER,
        "pharmacy_can_manage_staff": role in {UserProfile.Role.ADMIN, UserProfile.Role.MANAGER},
        "pharmacy_can_add_medicine": role in {
            UserProfile.Role.ADMIN,
            UserProfile.Role.MANAGER,
            UserProfile.Role.WORKER,
        },
        "pharmacy_role": role,
        "pharmacy_display_name": (
            profile.client_name.strip()
            if profile and profile.client_name
            else request.user.get_full_name() or request.user.username
        ),
        "pharmacy_name": (
            profile.pharmacy_name.strip()
            if profile and profile.pharmacy_name
            else "Afya Soft"
        ),
        "pharmacy_days_remaining": (
            profile.subscription_days_remaining
            if profile
            else 0
        ),
    }
