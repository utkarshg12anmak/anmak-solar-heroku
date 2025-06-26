# reminders/views.py

import json
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse

from .forms import ReminderForm
from .models import Reminder

from django.utils import timezone

@login_required
def add_reminder(request, app_label, model_name, object_id):
    # 0) Look up the ContentType (fail with 404 if invalid)
    try:
        ct = ContentType.objects.get(app_label=app_label, model=model_name)
    except ContentType.DoesNotExist:
        raise Http404("Invalid app_label or model_name for reminder.")

    # 1) Confirm the “target” object truly exists
    ct.get_object_for_this_type(pk=object_id)  # 404 if not found

    if request.method == "GET":
        # Just render the partial “popup_reminder.html” (no layout). Our JS expects JSON.
        form = ReminderForm(
            app_label=app_label,
            model_name=model_name,
            object_id=object_id
        )
        rendered = render(
            request,
            "reminders/popup_reminder.html",
            {
                "form": form,
                "app_label": app_label,
                "model_name": model_name,
                "object_id": object_id,
            },
        )

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            # Send back JSON so our JS can inject it into a <div>.
            return JsonResponse({"html": rendered.content.decode("utf-8")})

        # If someone browses directly (not via AJAX), just return the full page
        return rendered

    # ─── If POST: try to create a new reminder ───
    form = ReminderForm(
        request.POST,
        app_label=app_label,
        model_name=model_name,
        object_id=object_id
    )

    if form.is_valid():
        # Pass request.user into save() as owner_user
        reminder = form.save(commit=True, owner_user=request.user)

        # If AJAX, return a simple success JSON
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": True})

        # Otherwise (non-AJAX), redirect back to the “thing’s” detail page
        return redirect(reverse(f"{app_label}:edit", args=[object_id]))

    # If form is invalid, return JSON containing form.errors
    errors = {field: [str(e) for e in err_list] for field, err_list in form.errors.items()}
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"success": False, "errors": errors}, status=400)

    # If someone POSTed non‐AJAX (rare case), re‐render the partial with errors:
    return render(
        request,
        "reminders/popup_reminder.html",
        {
            "form": form,
            "app_label": app_label,
            "model_name": model_name,
            "object_id": object_id,
        },
        status=400,
    )

@login_required
def mark_complete(request, pk):
    """
    AJAX endpoint: POST to /reminders/<pk>/complete/
    Will mark reminder pk as COMPLETED (if not already) and return JSON.
    """
    if request.method != "POST" or not request.headers.get("x-requested-with"):
        raise Http404

    reminder = get_object_or_404(Reminder, pk=pk)

    # … (permission check, status‐toggle, save) …

    reminder.status = "COMPLETED"
# <—– Suddenly right here the next lines are your reminders/urls.py copy-pasted INSIDE this function
#    path("add/<str:app_label>/<str:model_name>/<int:object_id>/",
#         views.add_reminder,
#         name="add_reminder"),
#    path("<int:pk>/complete/",
#         views.mark_complete,             # ← This function does not exist
#         name="mark_completed"),
#    # … (other URLs) …
# ]

    from django.utils import timezone
    reminder.completed_at = timezone.now()
    reminder.save()

    return JsonResponse({"success": True})