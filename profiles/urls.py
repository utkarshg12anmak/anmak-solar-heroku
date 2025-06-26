# profiles/urls.py
from django.urls import path
from .views import OnDutyView

app_name = "profiles"

urlpatterns = [
    path("on-duty/", OnDutyView.as_view(), name="on_duty"),
]