# customers/urls.py
from django.urls import path
from . import views
from .views import CustomerListView, CustomerCreateView, CustomerUpdateView, CustomerLeadCreateView, api_customer_exists

app_name = "customers"

urlpatterns = [
    path("",    CustomerListView.as_view(),   name="list"),
    path("add/", CustomerCreateView.as_view(), name="add"),
    path("<int:pk>/edit/", CustomerUpdateView.as_view(), name="edit"),
    path("add-with-lead/",CustomerLeadCreateView.as_view(),name="customer_leads_add"),
    path('api/exists/', api_customer_exists, name='api_customer_exists'),
    path("create-with-lead/",CustomerLeadCreateView.as_view(),name="create_with_lead",)
]
