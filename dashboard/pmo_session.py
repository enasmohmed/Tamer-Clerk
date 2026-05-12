"""PMO portal role (team vs manager) stored in session — not Django auth users."""

from django.utils import timezone

SESSION_ROLE_KEY = "pmo_role"
SESSION_STARTED_KEY = "pmo_portal_started_at"

ROLE_TEAM = "team"
ROLE_MANAGER = "manager"


def get_pmo_role(request):
    return (request.session.get(SESSION_ROLE_KEY) or "").strip().lower()


def is_pmo_manager(request):
    return get_pmo_role(request) == ROLE_MANAGER


def is_pmo_team(request):
    return get_pmo_role(request) == ROLE_TEAM


def set_pmo_session(request, role: str):
    request.session[SESSION_ROLE_KEY] = role
    request.session[SESSION_STARTED_KEY] = timezone.now().isoformat()
    request.session.save()


def clear_pmo_session(request):
    request.session.pop(SESSION_ROLE_KEY, None)
    request.session.pop(SESSION_STARTED_KEY, None)
    request.session.save()


def pmo_template_context(request):
    role = get_pmo_role(request)
    return {
        "pmo_role": role,
        "pmo_is_manager": role == ROLE_MANAGER,
        "pmo_is_team": role == ROLE_TEAM,
    }


def pmo_actor_label(request):
    """Human label for Active Alerts / audit (PMO portal roles)."""
    if is_pmo_manager(request):
        return "PMO Manager"
    if is_pmo_team(request):
        return "PMO Team member"
    return "User"
