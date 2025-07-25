from django.contrib import admin
from .models import Lead, LeadStage

from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from .models import Lead  # adjust the import path if needed


@admin.register(LeadStage)
class LeadStageAdmin(admin.ModelAdmin):
    list_display = ('name','order')
    ordering     = ('order','name')
    search_fields= ('name',)

@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'system_size',
        'system_type',
        'stage',
        'lead_manager',
        'lead_quality',
        'grid_type',
        'total_amount',
        'interest',       # ← show the related Interest
        'created_by',
        'created_at',
    )
    list_filter = (
        'system_type',
        'lead_quality',
        'grid_type',
        'interest',       # ← filter by FK
    )
    search_fields = (
        'customer__primary_phone',
        'interest__pk',   # ← this lets you type the Interest ID into the search box
    )
    readonly_fields = ('created_by', 'updated_by', 'created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': (
                'customer','stage','lead_manager',
                'system_size','system_type','lead_quality','grid_type',
                'total_amount','remarks',
            )
        }),
        ('Meta', {
            'fields': ('created_by', 'created_at', 'updated_by', 'updated_at'),
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

class LeadAdmin(SimpleHistoryAdmin):
    # Optional: customize which columns show in the changelist
    list_display = ("id", "customer", "stage", "lead_manager", "updated_at")
    # Optional: add search/filter capabilities
    search_fields = ("customer__name", "lead_manager__username")
    list_filter = ("stage", "lead_quality")