# customers/admin.py
from django.contrib import admin
from .models import City, CustomerSource, Designation, Customer

@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    filter_horizontal = ("view_only_users", "view_edit_users")
    fieldsets = (
      (None, {
        "fields": ("name",)
      }),
      ("Access Control", {
        "classes": ("collapse",),
        "fields": ("view_only_users", "view_edit_users"),
      }),
    )
    
@admin.register(CustomerSource)
class SourceAdmin(admin.ModelAdmin): 
    list_display = ("name", "color")
    search_fields = ("name",)
    # Allow editing the hex color right from the change form
    fields = ("name", "color")

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display    = ("first_name", "last_name", "primary_phone", "designation", "city", "created_at")
    search_fields   = ("first_name", "last_name", "primary_phone")
    list_filter     = ("designation", "city", "source")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
      (None, {
        "fields": (
          ("first_name", "last_name"),
          "designation",
          ("primary_phone", "secondary_phone"),
          "address",
          ("city", "source"),
        )
      }),
      ("Timestamps", {
        "classes": ("collapse",),
        "fields": ("created_at", "updated_at"),
      }),
    )


@admin.register(Designation)
class DesignationAdmin(admin.ModelAdmin):
    list_display = ("title",)
    search_fields = ("title",)





