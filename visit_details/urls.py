# visit_details/urls.py

from django.urls import path
from . import views

app_name = "visit_details"

urlpatterns = [
    
    
    # Create a new visit for a lead
    path("leads/<int:lead_pk>/visits/add/", views.VisitCreateView.as_view(), name="visit_add"),

    # Edit / delete an existing visit
    path("visits/<int:pk>/edit/", views.VisitUpdateView.as_view(), name="visit_edit"),
    path("visits/<int:pk>/delete/", views.VisitDeleteView.as_view(), name="visit_delete"),

    # Preview IR first (so it catches /preview/ before your add/edit)
    path("visits/<int:pk>/preview/",
         views.inspection_report_preview,
         name="visit_preview"),
]

