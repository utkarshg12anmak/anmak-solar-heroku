# customers/forms.py
from django import forms
from .models import Customer

class CustomerForm(forms.ModelForm):
    class Meta:
        model  = Customer
        fields = [
            "designation", "first_name", "last_name",
            "primary_phone", "secondary_phone",
            "address", "city", "source",
        ]

    def clean_primary_phone(self):
        phone = self.cleaned_data.get("primary_phone")
        if not phone:
            return phone  # let the “required” validator handle empties

        # look for any other customer with the same number
        qs = Customer.objects.filter(primary_phone=phone)
        if self.instance.pk:
            # if we’re editing, ignore ourselves
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            other = qs.first()
            raise forms.ValidationError(
                f"A customer with this number already exists (ID {other.pk})."
            )

        if self.instance and self.instance.pk:
            orig = Customer.objects.get(pk=self.instance.pk).primary_phone
            if phone != orig:
                raise forms.ValidationError("Primary phone cannot be changed once set.")    

        return phone

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove the empty choice
        self.fields['designation'].choices = [
            (val,label) for val,label in self.fields['designation'].choices if val
        ]
        # Default to “Mr.”
        self.fields['designation'].initial = 'Mr.'
