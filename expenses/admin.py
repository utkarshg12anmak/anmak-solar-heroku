from django.contrib import admin
from django.utils.html import format_html
from .models import ExpenseCategory, Expense, ExpenseRole

@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent")
    list_filter  = ("parent",)
    search_fields= ("name",)

@admin.register(ExpenseRole)
class ExpenseRoleAdmin(admin.ModelAdmin):
    list_display    = ("user", "role")
    list_editable  = ("role",)
    search_fields  = ("user__username", "user__email")


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = (
        "expense_type",
        "parent_category",
        "child_category",
        "amount",
        "expense_date",
        "start_date",
        "end_date",
        "attachment_link",  # add this
    )
    readonly_fields = ("attachment_link",)

    def attachment_link(self, obj):
        if obj.attachment:
            return format_html(
                '<a href="{}" target="_blank">Download</a>',
                obj.attachment.url
            )
        return "—"
    attachment_link.short_description = "Attachment"