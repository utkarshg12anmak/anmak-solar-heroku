# interests/admin.py
from django.contrib import admin
from django import forms
from django.db import models
from .models import (
    InterestStatus, ModeOfContact, InterestSource,
    AuthorizedInterestUser, Interest
)
from django.core.exceptions import ObjectDoesNotExist



@admin.register(InterestStatus)
class InterestStatusAdmin(admin.ModelAdmin):
    list_display = ("name",)

@admin.register(ModeOfContact)
class ModeOfContactAdmin(admin.ModelAdmin):
    list_display = ("name",)

@admin.register(InterestSource)
class InterestSourceAdmin(admin.ModelAdmin):
    list_display = ("name",)

@admin.register(AuthorizedInterestUser)
class AuthorizedInterestUserAdmin(admin.ModelAdmin):
    list_display  = ('user', 'role_type')
    list_filter   = ('role_type',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name')

class InterestAdminForm(forms.ModelForm):
    class Meta:
        model = Interest
        fields = "__all__"
        widgets = {
            # turn all IntegerFields into a nice up/down spinner
            models.IntegerField: forms.NumberInput(attrs={'step': 1, 'min': 0, 'style': 'width: 5em;'}),
        }

@admin.register(Interest)
class InterestAdmin(admin.ModelAdmin):
    list_display    = (
        "phone_number", "attempted_times", "is_connected",
        "status", "source", "mode",'dials',
        "created_by", "updated_by", "created_at",'lead',
    )
    list_editable = ('dials',) 

    list_filter     = ("is_connected", "status", "source", "mode")
    search_fields   = ("phone_number", "remarks")

    # make these fields read-only in the form
    readonly_fields = (
        "attempted_times",
        "created_by", "updated_by",
        "created_at", "updated_at",
    )

    # only these fields are editable:
    fields = (
        "phone_number",
        "remarks", "is_connected", "status", "source", "mode",
        # the read-only ones will still render below
        "attempted_times",
        "created_by", "updated_by",
        "created_at", "updated_at",
    )

    def _interest_has_lead(self, obj):
        try:
            return obj and obj.lead is not None
        except ObjectDoesNotExist:
            return False

    def get_readonly_fields(self, request, obj=None):
        if self._interest_has_lead(obj):
            return [f.name for f in self.model._meta.fields]
        return super().get_readonly_fields(request, obj)

    def has_delete_permission(self, request, obj=None):
        if self._interest_has_lead(obj):
            return False
        return super().has_delete_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        if self._interest_has_lead(obj):
            # allow viewing (GET) but not saving (POST)
            return request.method in ('GET', 'HEAD')
        return super().has_change_permission(request, obj)