from urllib.parse import quote

from django.shortcuts import redirect
from django.urls import reverse

from .pmo_session import get_pmo_role


class PmoPortalGateMiddleware:
    """
    Require PMO portal login (team/manager) for dashboard app routes.
    Exempt: admin, static, media, portal login/logout.
    """

    EXEMPT_PREFIXES = (
        "/admin/",
        "/portal/",
        "/project/static/",
        "/static/",
        "/media/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or ""
        if path == "/favicon.ico":
            return self.get_response(request)
        if any(path.startswith(p) for p in self.EXEMPT_PREFIXES):
            return self.get_response(request)
        if not get_pmo_role(request):
            login_url = reverse("dashboard:pmo_portal_login")
            if path not in ("/", ""):
                return redirect(f"{login_url}?next={quote(path, safe='/')}")
            return redirect(login_url)
        return self.get_response(request)
