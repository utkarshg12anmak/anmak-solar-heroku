# reminders/admin.py

from django.contrib import admin
from .models import ReminderSettings, Reminder

@admin.register(ReminderSettings)
class ReminderSettingsAdmin(admin.ModelAdmin):
    list_display = ('default_ping_before_minutes',)
    # Ensure you cannot add a second row:
    def has_add_permission(self, request):
        # Only allow adding if no settings row exists
        if ReminderSettings.objects.exists():
            return False
        return super().has_add_permission(request)


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'owner',
        'content_type',
        'object_id',
        'reminder_time',
        'status',
        'priority',
        'ping_before_override',
        'created_at',
        'updated_at',
        'completed_at'
    )
    list_filter = ('status', 'priority', 'content_type')
    search_fields = ('message', 'owner__username', 'object_id')
    readonly_fields = ('created_at', 'updated_at', 'completed_at')

    fieldsets = (
        (
            "Core Reminder Info",
            {
                "fields": (
                    'content_type', 'object_id',
                    'owner', 'message',
                    'priority', 'status',
                )
            },
        ),
        (
            "Schedule",
            {
                "fields": (
                    'reminder_time', 'ping_before_override',
                )
            }
        ),
        (
            "Timestamps",
            {
                "fields": ('created_at', 'updated_at', 'completed_at'),
                'classes': ('collapse',),
            }
        ),
    )