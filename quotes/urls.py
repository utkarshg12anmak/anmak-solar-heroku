from django.urls import path
from .views import create_quote_json
from .views import soft_delete_quote
from . import views
from .views import quotation_view
from .views import quotation_preview


app_name = "quotes"

urlpatterns = [
    path(
        "leads/<int:lead_id>/create/",
        create_quote_json,
        name="create_quote_json",

    ),
    path(
        "leads/<int:lead_id>/quotes/<int:quote_id>/delete/",
        soft_delete_quote,
        name="soft_delete_quote",
    ),
    path("approvals/", views.QuoteApprovalListView.as_view(), name="approval_list"),
    path("approvals/<int:pk>/approve/",  views.approve_quote,  name="approve_quote"),
    path("approvals/<int:pk>/decline/",  views.decline_quote,  name="decline_quote"),
    path("quotation/<int:pk>/", quotation_view, name="quotation_view"),    
    path(
        "preview-quote/<int:quote_pk>/",
        views.quotation_view,
        name="quotation_preview"
    ),
    path(
        "download-full-quote/<int:quote_pk>/",
        views.download_full_quote,
        name="download_full_quote",
    )
]

