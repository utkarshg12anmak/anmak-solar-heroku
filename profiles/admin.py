from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.sessions.models import Session
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    UserProfile,
    OnDutyChangeLog,
    Department,
    DepartmentType,
    DepartmentRegion,
    DepartmentCategory,
    DepartmentMembership,
    ApprovalLimit,
)

User = get_user_model()

# 1) Unregister the default User admin BEFORE registering anything
admin.site.unregister(User)


# Inline for UserProfile
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = "Profile"


# 2) Re-register User just once, extending BaseUserAdmin
@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'is_active', 'is_staff')
    actions = ['logout_everywhere']

    def logout_everywhere(self, request, queryset):
        """Admin action to delete all sessions for selected users."""
        now = timezone.now()
        deleted = 0
        user_pks = {str(u.pk) for u in queryset}
        for session in Session.objects.filter(expire_date__gte=now):
            data = session.get_decoded()
            if data.get('_auth_user_id') in user_pks:
                session.delete()
                deleted += 1
        self.message_user(request, f"Cleared {deleted} session(s).")
    logout_everywhere.short_description = "Log selected users out of all devices"


# 3) Everything else in this file stays the same, but make sure
#    there are no other @admin.register(User) lines below.


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "is_on_duty")
    list_editable = ("is_on_duty",)
    search_fields = ("user__username", "user__first_name", "user__last_name")


@admin.register(OnDutyChangeLog)
class OnDutyChangeLogAdmin(admin.ModelAdmin):
    list_display = ("who_changed", "target_profile", "old_value", "new_value", "timestamp")
    readonly_fields = ("who_changed", "target_profile", "old_value", "new_value", "timestamp")
    list_filter = ("who_changed", "new_value", "timestamp")
    search_fields = ("who_changed__username", "target_profile__user__username")
    date_hierarchy = "timestamp"


@admin.register(DepartmentCategory)
class DepartmentCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(DepartmentType)
class DepartmentTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(DepartmentRegion)
class DepartmentRegionAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


class DepartmentMembershipInline(admin.TabularInline):
    model = DepartmentMembership
    extra = 1
    autocomplete_fields = ('user',)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'dept_type', 'region', 'category', 'draft_quotation_link')
    list_filter  = ('dept_type', 'region', 'category')
    search_fields = ('name',)
    inlines      = (DepartmentMembershipInline,)
    readonly_fields = ('draft_quotation_link',)
    fields = (
        'name',
        'parent',
        'dept_type',
        'region',
        'category',
        'draft_quotation',
        'draft_quotation_link',
    )

    def draft_quotation_link(self, obj):
        if obj.draft_quotation:
            return format_html(
                '<a href="{}" target="_blank">View DOCX</a>',
                obj.draft_quotation.url
            )
        return '-'
    draft_quotation_link.short_description = 'Current Draft'


@admin.register(DepartmentMembership)
class DepartmentMembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'department', 'level')
    list_filter  = ('level', 'department')
    autocomplete_fields = ('user', 'department')


@admin.register(ApprovalLimit)
class ApprovalLimitAdmin(admin.ModelAdmin):
    list_display  = ('department', 'level', 'max_amount')
    list_filter   = ('department', 'level')
    ordering      = ('department__name', '-level')
    search_fields = ('department__name',)
