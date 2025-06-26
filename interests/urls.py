from django.urls import path
from .views import InterestListView, InterestCreateView, InterestUpdateView
from .views import InterestListView, adjust_dials, InterestCustomerCreateView

app_name = "interests"

urlpatterns = [
    path("", InterestListView.as_view(), name="list"),
    path("add/", InterestCreateView.as_view(), name="add"),
    path("<int:pk>/edit/", InterestUpdateView.as_view(), name="edit"),
    path('dials/<int:pk>/', adjust_dials, name='adjust_dials'),
    path(
    'create-customer/',
    InterestCustomerCreateView.as_view(),
    name='create-customer'
  ),

]