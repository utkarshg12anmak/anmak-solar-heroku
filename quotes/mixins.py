# quotes/mixins.py
from django.db.models import Q
from django.contrib.auth.mixins import LoginRequiredMixin
from profiles.models import DepartmentMembership
from leads.models import Lead

class LeadAccessMixin(LoginRequiredMixin):
    def get_allowed_leads(self):
        me = self.request.user

        # Base Lead qs
        qs = Lead.objects.all()

        # 2) Grab only your Sales‐dept memberships
        my_mems = DepartmentMembership.objects.filter(
            user=me,
            department__dept_type__name="Sales"
        )

        # 3) Build allowed_q exactly as in LeadListView
        allowed_q = Q(lead_manager=me)
        for mem in my_mems:
            dept = mem.department
            if mem.level == 1:
                mgr_ids = DepartmentMembership.objects.filter(
                    department=dept,
                    level__in=[2,3]
                ).values_list("user_id", flat=True)
                allowed_q |= Q(department=dept, lead_manager_id__in=mgr_ids)
            elif mem.level == 2:
                mgr_ids = DepartmentMembership.objects.filter(
                    department=dept,
                    level=3
                ).values_list("user_id", flat=True)
                allowed_q |= Q(department=dept, lead_manager_id__in=mgr_ids)
            # level 3 grants only own leads

        return qs.filter(allowed_q)