# profiles/mixins.py

from django.shortcuts import render
from django.core.exceptions import PermissionDenied
from profiles.models import DepartmentMembership

class SalesDepartmentRequiredMixin:
    """
    Blocks any user who isn't in a Sales department.
    """
    def dispatch(self, request, *args, **kwargs):
        in_sales = DepartmentMembership.objects.filter(
            user=request.user,
            department__dept_type__name="Sales"
        ).exists()
        if not in_sales:
            # render your standalone 403.html with a 403 status
            return render(request, "403.html", status=403)
        return super().dispatch(request, *args, **kwargs)