#leads/urls.py
from django.urls import path
from . import views
from .views import LeadListView, LeadCreateView, LeadUpdateView,LeadCreateWithCustomer, LeadEditFormView
  

app_name = "leads"
urlpatterns = [
    path("",          LeadListView.as_view(),   name="list"),
    path("add/",      LeadCreateView.as_view(), name="add"),
    path("add-with-customer/",LeadCreateWithCustomer.as_view(),
         name="add_with_customer"),
    path(
        'api/customer/lookup/<str:phone>/',
        views.customer_lookup,
        name='customer_lookup'
    ),
    path('<int:pk>/next_stage/',  views.LeadNextStageView.as_view(), name='next_stage'),
    path('<int:pk>/prev_stage/',  views.LeadPrevStageView.as_view(), name='prev_stage'),
    path("<int:pk>/edit/", LeadUpdateView.as_view(), name="edit"),
    path("<int:pk>/edit/form/", LeadEditFormView.as_view(), name="edit_form"),


]

# If DEBUG=True, this block will let Django serve media files from MEDIA_ROOT
from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)