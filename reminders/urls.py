from django.urls import path
from . import views

app_name = "reminders"

urlpatterns = [
    path(
        "add/<str:app_label>/<str:model_name>/<int:object_id>/",
        views.add_reminder,
        name="add_reminder",
    ),
    path(
        "<int:pk>/complete/",
        views.mark_complete,
        name="mark_completed",
    ),
    # …any other reminder-related URLs…
]