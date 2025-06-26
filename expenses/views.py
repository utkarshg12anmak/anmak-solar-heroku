#expenses/views.py
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, DetailView, UpdateView
from .models import Expense, ExpenseRole
from django.core.exceptions import PermissionDenied
from .forms import ExpenseForm

from django.db.models import Q
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin

from .models import Expense
from profiles.models import DepartmentMembership

class ExpenseListView(ListView):
    model = Expense
    paginate_by = 10
    template_name = "expenses/expense_list.html"
    ordering = ['-updated_at'] 

    def get_queryset(self):
        me = self.request.user

        # Start with your own ID
        allowed_user_ids = {me.id}

        # Gather subordinates from *all* departments the user belongs to
        for mem in DepartmentMembership.objects.filter(user=me):
            dept = mem.department_id

            if mem.level == 1:
                # add all L2 & L3 in this department
                subs = DepartmentMembership.objects.filter(
                    department_id=dept,
                    level__in=[2, 3]
                ).values_list("user_id", flat=True)

            elif mem.level == 2:
                # add all L3 in this department
                subs = DepartmentMembership.objects.filter(
                    department_id=dept,
                    level=3
                ).values_list("user_id", flat=True)

            else:
                # Level 3: no subordinates
                subs = []

            allowed_user_ids.update(subs)

        # Now build one filter on created_by__in
        return Expense.objects.filter(
            created_by_id__in=allowed_user_ids
        ).order_by("-created_at")

class ExpenseCreateView(CreateView):
    model = Expense
    form_class = ExpenseForm
    success_url = reverse_lazy("expenses:list")
    template_name = "expenses/expense_form.html"

    def form_valid(self, form):
        expense = form.instance
        expense.created_by = self.request.user
        expense.updated_by = self.request.user
        return super().form_valid(form)

class ExpenseDetailView(DetailView):
    model = Expense
    template_name = "expenses/expense_detail.html"
    context_object_name = "expense"

class ExpenseUpdateView(UpdateView):
    model = Expense
    form_class = ExpenseForm
    success_url = reverse_lazy("expenses:list")
    template_name = "expenses/expense_form.html"

    def form_valid(self, form):
        expense = form.instance
        expense.updated_by = self.request.user
        return super().form_valid(form)

    def dispatch(self, request, *args, **kwargs):
        obj  = self.get_object()
        role = request.user.expense_role.role

        # SELF_SERVICE or GLOBAL_VIEWER may only edit their own
        if role != ExpenseRole.Role.GLOBAL_EDITOR and obj.created_by != request.user:
            raise PermissionDenied()
        return super().dispatch(request, *args, **kwargs)
