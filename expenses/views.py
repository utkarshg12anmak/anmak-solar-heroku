#expenses/views.py
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, DetailView, UpdateView
from .models import Expense, ExpenseRole
from django.core.exceptions import PermissionDenied
from .forms import ExpenseForm


from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin

from .models import Expense
from profiles.models import DepartmentMembership
from django.db.models import Q, Prefetch


class ExpenseListView(ListView):
    model = Expense
    paginate_by = 10
    template_name = "expenses/expense_list.html"
    ordering = ['-updated_at']

    def get_queryset(self):
        user = self.request.user
        # pulled from your middleware/login flow
        am = self.request.session.get('active_membership', {})
        dept_id = am.get('department_id')
        level   = am.get('level')

        # Figure out which subordinate levels to include
        if level == 1:
            sub_levels = [2, 3]
        elif level == 2:
            sub_levels = [3]
        else:  # level 3 or missing data
            sub_levels = []

        # Base filter: always allow your own expenses
        q = Q(created_by=user)

        # If you have subs, OR in those levels in the same department
        if sub_levels and dept_id is not None:
            q |= Q(
                created_by__departmentmembership__department_id=dept_id,
                created_by__departmentmembership__level__in=sub_levels
            )

        # One database hit, plus a single JOIN on departmentmembership
        return (
            Expense.objects
                   .filter(q)
                   .select_related("created_by", "updated_by")
                   .order_by("-created_at")
                   .distinct()
        )

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
