# items/forms.py

from django import forms
from django.core.exceptions import ValidationError

from .models import PriceRule, PriceTier


class PriceRuleForm(forms.ModelForm):
    class Meta:
        model = PriceRule
        fields = ['price_book', 'item', 'base_price', 'unit_type', 'available']

    def clean(self):
        cleaned_data = super().clean()
        price_book = cleaned_data.get('price_book')
        item = cleaned_data.get('item')
        if price_book and item:
            qs = PriceRule.objects.filter(price_book=price_book, item=item)
            # Exclude current instance on update
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError(
                    "A price rule for this item already exists in this price book."
                )
        return cleaned_data


class PriceTierForm(forms.ModelForm):
    class Meta:
        model = PriceTier
        fields = ['price_rule', 'min_quantity', 'price']

    def clean_min_quantity(self):
        min_q = self.cleaned_data.get('min_quantity')
        if min_q is not None and min_q < 0:
            raise ValidationError("Tier min_quantity cannot be negative.")
        return min_q

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price is not None and price < 0:
            raise ValidationError("Tier price cannot be negative.")
        return price
