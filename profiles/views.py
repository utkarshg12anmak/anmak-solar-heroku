# profiles/views.py

from django.shortcuts import redirect, get_object_or_404, render
from django.views.generic import TemplateView
from django.core.paginator import Paginator
from profiles.models import UserProfile, OnDutyChangeLog, DepartmentMembership

class OnDutyView(TemplateView):
    template_name = "profiles/on_duty.html"

    allowed_dept_types = ["Sales", "Customer Support"]

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        # Get all department memberships of this user
        memberships = DepartmentMembership.objects.select_related(
            "department__dept_type"
        ).filter(user=user)

        allowed = any(
            m.department.dept_type.name in self.allowed_dept_types
            for m in memberships
        )

        if not allowed:
            return render(request, "403.html", status=403)

        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        pid = request.POST.get("profile_id")
        new_status = request.POST.get("new_status") == "on"
        profile = get_object_or_404(UserProfile, id=pid)

        old = profile.is_on_duty
        profile.is_on_duty = new_status
        profile.save()

        OnDutyChangeLog.objects.create(
            who_changed=request.user,
            target_profile=profile,
            old_value=old,
            new_value=new_status
        )
        return redirect("profiles:on_duty")

    def get_context_data(self, **ctx):
        ctx = super().get_context_data(**ctx)
        ctx["profiles"] = UserProfile.objects.select_related("user")

        all_logs = OnDutyChangeLog.objects.select_related(
            "who_changed", "target_profile__user"
        ).order_by("-timestamp")
        paginator = Paginator(all_logs, 10)
        page = self.request.GET.get("log_page") or 1
        ctx["log_page_obj"] = paginator.get_page(page)
        return ctx