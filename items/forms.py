# items/forms.py

from django import forms
from .models import PriceRule, PriceTier

class PriceRuleForm(forms.ModelForm):
    class Meta:
        model = PriceRule
        fields = [
            "price_book",
            "item",
            "base_price",
            "unit_type",
             'available',
        ]
        widgets = {
            "price_book": forms.Select(attrs={"class": "form-control"}),
            "item":       forms.Select(attrs={"class": "form-control"}),
            "base_price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "unit_type":  forms.Select(attrs={"class": "form-control"}),
        }


class PriceTierForm(forms.ModelForm):
    class Meta:
        model = PriceTier
        fields = [
            "price_rule",
            "min_quantity",
            "price",
        ]
        widgets = {
            "price_rule": forms.HiddenInput(),
            "min_quantity": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
            "price":        forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            'available': forms.RadioSelect(choices=[
                (True,  'Available'),
                (False, 'Not Available'),
            ]),
        }