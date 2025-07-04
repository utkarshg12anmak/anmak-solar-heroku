# core/middleware.py

from django.conf import settings
from django.shortcuts import redirect
from django.urls import resolve

class LoginRequiredMiddleware:
    """
    Redirect any anonymous user to LOGIN_URL unless:
      • they’re already hitting an exempt URL name
      • or the URL path starts with /admin/ (Django’s admin)
    """
    EXEMPT_NAMES = {
        'login',         # your login view
        'logout',        # your logout view
        # (you can add more by-name exemptions here)
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1) Always allow admin URLs through
        if request.path.startswith('/admin/'):
            return self.get_response(request)

        # 2) If user is not authenticated, and this URL isn’t exempt…
        if not request.user.is_authenticated:
            match = resolve(request.path_info)
            if match.url_name not in self.EXEMPT_NAMES:
                # redirect to LOGIN_URL with next=…
                return redirect(f"{settings.LOGIN_URL}?next={request.path}")

        return self.get_response(request)
