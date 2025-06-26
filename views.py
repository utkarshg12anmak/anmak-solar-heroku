# core/views.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.contrib.auth.views import LogoutView
from django.contrib import messages

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "index.html"
    # If you hit this view while not logged in, go here:
    login_url = "login"
    # After login, redirect back to the page you originally wanted:
    redirect_field_name = "next"

# core/views.py


class CustomLogoutView(LogoutView):
    next_page = "login"

    def dispatch(self, request, *args, **kwargs):
        messages.success(request, "You have successfully logged out.")
        return super().dispatch(request, *args, **kwargs)