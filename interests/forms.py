from django import forms
from .models import Interest
from django.core.validators import RegexValidator

class InterestForm(forms.ModelForm):
    phone_number = forms.RegexField(
        regex=r'^\d{10}$',
        error_messages={'invalid': "Enter exactly 10 digits."},
        widget=forms.TextInput(attrs={
            'type': 'tel',
            'maxlength': '10',
            'pattern': r'\d{10}',
            'inputmode': 'numeric',
            'placeholder': '10-digit number',
        })
    )
    class Meta:
        model = Interest
        fields = [
            'phone_number', 'remarks',
            'is_connected', 'status', 'source', 'mode',
        ]
        widgets = {
            'remarks': forms.Textarea(attrs={'rows': 3}),
        }