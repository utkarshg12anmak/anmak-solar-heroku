# reminders/forms.py

from django import forms
from django.contrib.contenttypes.models import ContentType
from .models import Reminder

class ReminderForm(forms.ModelForm):
    """
    Only the user‐editable fields appear here. We accept three extra kwargs:
      - app_label
      - model_name
      - object_id

    Then, on save(), we use those to set content_type/object_id, and owner.
    """

    class Meta:
        model = Reminder
        fields = [
            "message",
            "reminder_time",
            "priority",
            "ping_before_override",
        ]
        widgets = {
            # Render a native HTML5 datetime‐local picker
            "reminder_time": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }
        help_texts = {
            "ping_before_override": "Optional. If blank, we’ll use the default from ReminderSettings.",
            "message": "Brief description of what you need to do.",
        }
        labels = {
            "ping_before_override": "Ping Before (minutes)",
        }

    def __init__(self, *args, app_label=None, model_name=None, object_id=None, **kwargs):
        """
        We *must* receive app_label, model_name, object_id when constructing this form.
        If any of those is missing, we add a non‐field error on __all__.
        """
        super().__init__(*args, **kwargs)

        # Store those three values on the form instance so save() can see them.
        self.app_label = app_label
        self.model_name = model_name
        self.object_id = object_id

        # If any is missing, raise a non‐field error immediately
        if not (app_label and model_name and object_id):
            self.add_error(
                None,
                "Missing `app_label`, `model_name`, or `object_id` in form initialization."
            )

    def save(self, commit=True, owner_user=None):
        """
        Before saving the Reminder instance, set:
          - content_type  (via ContentType.lookup)
          - object_id     (already provided)
          - owner         (must be passed in as `owner_user`)
        """
        # Create a Reminder object but don’t hit the database yet
        reminder = super().save(commit=False)

        # 1) Find the ContentType for the target
        try:
            ct = ContentType.objects.get(
                app_label=self.app_label,
                model=self.model_name
            )
        except ContentType.DoesNotExist:
            # Should never happen if your view checked first—but just in case:
            raise forms.ValidationError(
                "Cannot attach reminder: invalid app_label/model_name."
            )

        reminder.content_type = ct
        reminder.object_id = self.object_id

        if owner_user is None:
            raise ValueError("You must call save(owner_user=some_user).")
        reminder.owner = owner_user

        if commit:
            reminder.save()
        return reminder