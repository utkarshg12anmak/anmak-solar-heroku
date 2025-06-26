# core/views.py

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "index.html"
    login_url = "login"
    redirect_field_name = "next"

# core/views.py  (or anywhere you prefer)
from django.conf import settings
from django.http import HttpResponse

def show_debug(request):
    return HttpResponse(f"DEBUG is currently: {settings.DEBUG}")

def what_is_debug(request):
    return HttpResponse(f"DEBUG is currently: {settings.DEBUG}")