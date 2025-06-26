# expenses/forms.py
from django import forms
from .models import Expense

class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = [
            "expense_type",
            "parent_category",
            "child_category",
            "amount",
            "expense_date",
            "start_date",
            "end_date",
            "remarks",
            "attachment",       # <-- our new file field
        ]
        widgets = {
            "expense_date": forms.DateInput(attrs={"type": "date"}),
            "start_date":   forms.DateInput(attrs={"type": "date"}),
            "end_date":     forms.DateInput(attrs={"type": "date"}),
        }