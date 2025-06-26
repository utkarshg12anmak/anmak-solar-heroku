# leads/forms.py

from django import forms
from .models import Lead
from customers.models import Customer
from profiles.models import Department

class CustomerSelectionForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['primary_phone']  # we’ll lookup by phone; could add more if you want to pre-fill

class CustomerCreateForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['designation','first_name','last_name','primary_phone','secondary_phone','address','city','source']


class LeadForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = [
            'system_size',
            'system_type',
            'lead_quality',
            'grid_type',
            'total_amount',
            'remarks',
            "department",
        ]
        widgets = {
            'total_amount': forms.NumberInput(attrs={
                'step': '0.01',
                'min': '0'
            }),
            'customer': forms.Select(),
            "department": forms.Select(attrs={"class":"form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['total_amount'].required = False
        # make system_type mandatory
        self.fields['system_type'].required = True
        # add the HTML5 required attribute so browser blocks blank submits too
        self.fields['system_type'].widget.attrs['required'] = 'required'
        # only Sales departments:
        self.fields["department"].queryset = Department.objects.filter(
            dept_type__name="Sales"
        )

