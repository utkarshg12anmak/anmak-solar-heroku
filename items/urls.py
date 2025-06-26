# items/urls.py
from django.urls import path
from . import views

app_name = "items"

urlpatterns = [
    # ──────────── Items / Lookups ────────────
    path("", views.ItemListView.as_view(), name="list"),
    path("manage-brands/", views.ManageBrandsView.as_view(), name="manage_brands"),
    path("manage-uoms/",   views.ManageUOMsView.as_view(),   name="manage_uoms"),
    path("manage-l1-categories/", views.ManageL1CategoriesView.as_view(), name="manage_l1_categories"),
    path("manage-l2-categories/", views.ManageL2CategoriesView.as_view(), name="manage_l2_categories"),
    path("update-item/<int:pk>/", views.UpdateItemView.as_view(),   name="update_item"),
    path("create-item/",          views.CreateItemView.as_view(),   name="create_item"),

    # ──────────── PriceTier AJAX fragment ────────────
    # (must come before the static /rules/ route)
    path(
        "price-settings/rules/<int:rule_pk>/tiers/",
        views.PriceTierManageView.as_view(),
        name="price_tiers_manage",
    ),

    # ──────────── PriceTier CRUD (non-AJAX fallbacks) ────────────
    path("price-settings/tiers/add/",    views.PriceTierCreateView.as_view(), name="tier_add"),
    path("price-settings/tiers/<int:pk>/edit/",   views.PriceTierUpdateView.as_view(), name="tier_edit"),
    path("price-settings/tiers/<int:pk>/delete/", views.PriceTierDeleteView.as_view(), name="tier_delete"),

    # ──────────── PriceRule CRUD ────────────
    path("price-settings/rules/create/", views.PriceRuleCreateView.as_view(), name="price_rule_create"),
    path("price-settings/rules/<int:pk>/edit/",   views.PriceRuleUpdateView.as_view(), name="price_rule_edit"),
    path("price-settings/rules/<int:pk>/delete/", views.PriceRuleDeleteView.as_view(), name="price_rule_delete"),

    # ──────────── PriceRule List ────────────
    path("price-settings/rules/", views.PriceRuleListView.as_view(), name="price_rules_list"),

    path(
        'price-rules/<int:pk>/toggle-availability/',
        views.toggle_price_rule_availability,
        name='price_rule_toggle_availability'
    ),


]

