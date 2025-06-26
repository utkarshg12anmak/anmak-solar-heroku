# leads/api_urls.py
from django.urls import path
from .views import customer_lookup

urlpatterns = [
    path(
        "lookup/<str:phone>/",
        customer_lookup,
        name="customer_lookup"
    ),
]
