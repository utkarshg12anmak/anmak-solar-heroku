from django.urls import path
from . import views

app_name = "expenses"

urlpatterns = [
    path("", views.ExpenseListView.as_view(), name="list"),
    path("add/", views.ExpenseCreateView.as_view(), name="add"),
    path("<int:pk>/", views.ExpenseDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.ExpenseUpdateView.as_view(), name="edit"),
]