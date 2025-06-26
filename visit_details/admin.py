# visit_details/admin.py

from django.contrib import admin
from .models import VisitDetail, VisitImage

class VisitImageInline(admin.TabularInline):
    model = VisitDetail.images.through  # since images is a M2M through VisitImage
    extra = 1
    verbose_name = "Site Image"
    verbose_name_plural = "Site Images"
    readonly_fields = ("visitimage_image_tag",)
    
    def visitimage_image_tag(self, obj):
        # show thumbnail if you like
        if obj.visitimage.image:
            return format_html(
                '<img src="{}" style="max-height:100px;max-width:100px;" />',
                obj.visitimage.image.url
            )
        return "-"
    visitimage_image_tag.short_description = "Preview"

@admin.register(VisitDetail)
class VisitDetailAdmin(admin.ModelAdmin):
    list_display = ("id", "lead", "visit_date", "start_time", "end_time", "created_at", "created_by")
    list_filter = ("visit_date", "lead")
    search_fields = ("lead__customer__first_name", "lead__customer__last_name", "lead__pk")
    inlines = [VisitImageInline]
    readonly_fields = ("created_at", "updated_at")
    
    fieldsets = (
        (None, {
            "fields": ("lead", "visit_date", ("start_time", "end_time"), "inspection_report")
        }),
        ("Meta", {
            "classes": ("collapse",),
            "fields": ("created_at", "created_by", "updated_at", "updated_by"),
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(VisitImage)
class VisitImageAdmin(admin.ModelAdmin):
    list_display = ("id", "visitimage_image_tag", "uploaded_at")
    readonly_fields = ("visitimage_image_tag", "uploaded_at")
    
    def visitimage_image_tag(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height:100px;max-width:100px;" />',
                obj.image.url
            )
        return "-"
    visitimage_image_tag.short_description = "Preview"