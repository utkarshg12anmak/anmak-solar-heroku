# interests/views.py

import json
import logging
from datetime import date, timedelta

from django.db.models import Q, Subquery
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse, Http404
from django.shortcuts import render, get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import ListView, CreateView, UpdateView

from .models import Interest, AuthorizedInterestUser
from .forms import InterestForm
from customers.forms import CustomerForm
from customers.models import Customer
from profiles.models import DepartmentMembership
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q


from .models import (
    Interest,
    AuthorizedInterestUser,
    InterestStatus,
    InterestSource,
    ModeOfContact,
)

logger = logging.getLogger(__name__)


# --- Mixin for Department-Based Access Control (403 for non-members) ---
class DepartmentAccessMixin:
    dept_type     = 'Customer Support'
    category_name = 'Lead Qualification Team'

    def dispatch(self, request, *args, **kwargs):
        user = request.user

        membership = DepartmentMembership.objects.filter(
            user=user,
            department__dept_type__name=self.dept_type,
            department__category__name=self.category_name
        ).first()

        if not membership:
            raise PermissionDenied()

        self.department = membership.department
        self.user_level = membership.level
        return super().dispatch(request, *args, **kwargs)


@require_POST
def adjust_dials(request, pk):
    if not request.user.is_authenticated:
        raise Http404()
    try:
        payload = json.loads(request.body)
        delta   = int(payload.get('delta', 0))
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({'error': 'invalid payload'}, status=400)

    new_count = max(0, Interest.objects.get(pk=pk).dials + delta)
    Interest.objects.filter(pk=pk).update(
        dials=new_count,
        updated_by=request.user
    )
    return JsonResponse({'dials': new_count})


class InterestListView(DepartmentAccessMixin, LoginRequiredMixin, ListView):
    model         = Interest
    template_name = "interests/interest_list.html"
    paginate_by   = 10
    ordering      = ['-updated_at']

    def get_queryset(self):
        req = self.request
        user = req.user

        membership = req.session.get("active_membership")
        if not membership:
            raise PermissionDenied()

        dept_id     = membership['department_id']
        user_level  = membership['level']
        dept_map    = req.session.get("department_user_map", {})
         # Normalize level_map keys to strings early
        level_map = {str(k): v for k, v in dept_map.get(str(dept_id), {}).items()}

        filters = Q()
        q = req.GET.get('q','').strip()
        if q:
            filters &= Q(phone_number__icontains=q)

        start_str = req.GET.get('start')
        end_str   = req.GET.get('end')
        if start_str and end_str:
            try:
                sd = date.fromisoformat(start_str)
                ed = date.fromisoformat(end_str)
                filters &= Q(created_at__date__range=(sd, ed))
            except ValueError:
                pass
        else:
            today = timezone.localdate()
            filters &= Q(created_at__date=today)                        
        conn = req.GET.get('connected')
        if conn in ('0', '1'):
            filters &= Q(is_connected=(conn == '1'))

        if user_level == 3:
            filters &= Q(created_by_id=user.id)
        elif user_level == 2:
            allowed_users = set(level_map.get('2', [])) | set(level_map.get('3', []))
            filters &= Q(created_by_id__in=allowed_users)        
        elif user_level == 1:
            all_users = set()
            for lv in ('1', '2', '3'):
                all_users |= set(level_map.get(lv, []))
            filters &= Q(created_by_id__in=all_users)
        else:
            raise PermissionDenied()

        #print("User:", user.id, user.get_full_name())
        #print("User Level:", user_level)
        #print("Level Map:", level_map)
        #print("All Interest creator IDs:", list(Interest.objects.values_list("created_by_id", flat=True).distinct()))

        #if user_level == 2:
            #allowed_users = set(level_map.get(2, [])) | set(level_map.get(3, [])) | {user.id}
            #print("→ L2 allowed_users:", allowed_users)

        #elif user_level == 1:
            #all_users = {user.id}
            f#or lv in (1, 2, 3):
                #all_users |= set(level_map.get(lv, []))
            #print("→ L1 all_users:", all_users)


        return (
            Interest.objects
            .filter(filters)
            .select_related(
                'created_by', 'updated_by',
                'lead', 'lead__customer', 'lead__customer__city',
                'status', 'source', 'mode',
            )
            .order_by(*self.ordering)
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Reconstruct the *un‐paginated* filtered queryset:
        qs = self.get_queryset().order_by()  # drop ordering if you like

        # Use a single aggregate call for all three counts
        counts = qs.aggregate(
            total=Count('pk'),
            connected=Count('pk', filter=Q(is_connected=True)),
            interested=Count('pk', filter=Q(status__name='Interested')),
        )

        context['total_records']   = counts['total']
        context['connected_count'] = counts['connected']
        context['interested_count']= counts['interested']
        return context


class InterestCreateView(DepartmentAccessMixin, LoginRequiredMixin, CreateView):
    model         = Interest
    form_class    = InterestForm
    template_name = "interests/interest_form.html"
    success_url   = reverse_lazy("interests:list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        return super().form_valid(form)


class InterestCustomerCreateView(DepartmentAccessMixin, LoginRequiredMixin, CreateView):
    model         = Customer
    form_class    = CustomerForm
    template_name = "interests/interest_create_from_interest.html"

    def get_initial(self):
        initial     = super().get_initial()
        interest_pk = self.request.GET.get("from_interest")
        phone       = self.request.GET.get("phone")
        source_pk   = self.request.GET.get("source")

        if interest_pk:
            initial["interest"]     = interest_pk
        if phone:
            initial["primary_phone"] = phone
        if source_pk:
            initial["source"]       = source_pk

        return initial

    def form_valid(self, form):
        interest_pk = self.request.GET.get("from_interest")
        if interest_pk:
            form.instance.linked_interest = get_object_or_404(Interest, pk=interest_pk)
        return super().form_valid(form)

    def get_success_url(self):
        interest_pk = self.request.GET.get("from_interest")
        return reverse_lazy("interests:edit", args=[interest_pk])


class InterestUpdateView(DepartmentAccessMixin, LoginRequiredMixin, UpdateView):
    model         = Interest
    form_class    = InterestForm
    template_name = "interests/interest_form.html"
    success_url   = reverse_lazy("interests:list")

    def get_queryset(self):
        # Join in every FK your template touches in one SQL
        return Interest.objects.select_related(
            'created_by',
            'updated_by',
            'status',
            'source',
            'mode',
            'lead__lead_manager',
            'customer',
        )

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        user = self.request.user

        # 1) If they have an explicit 'supervisor' record, OK
        auth = AuthorizedInterestUser.objects.filter(user=user, role_type='supervisor').exists()

        # 2) Or they're the original creator
        creator = (obj.created_by_id == user.id)

        # 3) Or they are in this department at Level 1 or 2
        membership = DepartmentMembership.objects.filter(
            user=user,
            department=self.department,
            level__in=[1,2,3]
        ).exists()

        if not (auth or creator or membership):
            raise PermissionDenied

        return obj

    def get_form(self, form_class=None):
        # Build the form instance (won't re-query the Interest)
        form = super().get_form(form_class)

        # Load these three tables exactly once
        statuses = list(InterestStatus.objects.all())
        sources  = list(InterestSource.objects.all())
        modes    = list(ModeOfContact.objects.all())

        # Override the dropdown choices (avoids count+SELECT)
        form.fields['status'].choices = [(s.pk, str(s)) for s in statuses]
        form.fields['source'].choices = [(s.pk, str(s)) for s in sources]
        form.fields['mode'].choices   = [(m.pk, str(m)) for m in modes]

        # If it’s tied to a Lead, make everything read-only
        if getattr(self.object, 'lead', None):
            for field in form.fields.values():
                field.disabled = True
            messages.info(
                self.request,
                "This interest is tied to a Lead, so fields are read-only."
            )

        return form

    def form_valid(self, form):
        # Preserve read-only if tied to a Lead
        if getattr(self.object, 'lead', None):
            return self.render_to_response(self.get_context_data(form=form))
        form.instance.updated_by = self.request.user
        return super().form_valid(form)


