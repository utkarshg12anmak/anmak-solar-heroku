# profiles/admin.py

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import UserProfile, OnDutyChangeLog
from .models import Department, DepartmentType, DepartmentRegion, DepartmentCategory, DepartmentMembership, UserProfile, OnDutyChangeLog

from .models import ApprovalLimit
from django.utils.html import format_html 

User = get_user_model()

# 1) Unregister the built-in User admin so we can re-register with our inline
admin.site.unregister(User)

@admin.register(DepartmentCategory)
class DepartmentCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


# 2) Define an inline for our new profile model
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = "Profile"

# 3) Re-register User with the inline attached
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)

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

# (OPTIONAL) If you still want a standalone UserProfile listing, you can
# also register it by itself below. But you don’t need to if you only need
# the inline on the User page.

# @admin.register(UserProfile)
# class UserProfileAdmin(admin.ModelAdmin):
#     list_display = ("user", "is_on_duty")
#     list_editable = ("is_on_duty",)
#     search_fields = ("user__username", "user__first_name", "user__last_name")

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
    list_display = ('name', 'parent', 'dept_type', 'region', 'category','draft_quotation_link')
    list_filter  = ('dept_type', 'region', 'category')
    search_fields = ('name',)
    inlines      = (DepartmentMembershipInline,)
   
    readonly_fields = ('draft_quotation_link',)
    # include all the ones you actually want editors to be able to set:
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
            url = obj.draft_quotation.url
            return format_html('<a href="{}" target="_blank">View PDF</a>', url)
        return '-'
    draft_quotation_link.short_description = 'Current Draft'    

    def indented_name(self, obj):
        return obj.__str__()
    indented_name.short_description = "Department"

    def get_parent_name(self, obj):
        return obj.parent.name if obj.parent else '-'
    get_parent_name.short_description = "Parent Dept"

@admin.register(DepartmentMembership)
class DepartmentMembershipAdmin(admin.ModelAdmin):
    list_display = ('user','department','level')
    list_filter  = ('level','department')
    autocomplete_fields = ('user','department')

@admin.register(ApprovalLimit)
class ApprovalLimitAdmin(admin.ModelAdmin):
    list_display   = ('department', 'level', 'max_amount')
    list_filter    = ('department', 'level')
    ordering       = ('department__name', '-level')
    search_fields  = ('department__name',)

