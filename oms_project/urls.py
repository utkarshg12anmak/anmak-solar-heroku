# oms_project/urls.py
import debug_toolbar
from django.contrib import admin
from django.urls import path, include
from core.views import DashboardView
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from core.views import what_is_debug   # ← Import the debug‐check view here


urlpatterns = [
    path("__debug__/", include(debug_toolbar.urls)),
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", DashboardView.as_view(), name="dashboard"),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="accounts/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),
    path("profiles/", include("profiles.urls", namespace="profiles")),
    path("", DashboardView.as_view(), name="dashboard"),
    path("expenses/", include("expenses.urls", namespace="expenses")),
    path("leads/", include("leads.urls", namespace="leads")),
    path("interests/", include(("interests.urls","interests"), namespace="interests")),
    path("sales/customers/", include("customers.urls", namespace="customers")),
    path('leads/', include('leads.urls')), 
    path('api/', include('leads.urls')),
    path("api/customer/", include("leads.api_urls")),
    path("items/", include("items.urls")),
    path("what-is-debug/", what_is_debug, name="what_is_debug"),
    path("reminders/", include(("reminders.urls", "reminders"), namespace="reminders")),
    path('quotes/', include('quotes.urls', namespace='quotes')),
    path("visits/", include("visit_details.urls", namespace="visit_details")),



]

# Serve media files in DEBUG mode:
#from django.conf import settings
#from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns