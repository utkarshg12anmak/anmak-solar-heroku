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
from profiles.models import Department, DepartmentMembership

logger = logging.getLogger(__name__)


# --- Mixin for Department-Based Access Control ---
class DepartmentAccessMixin:
    dept_type = 'Customer Support'
    region_name = 'Meerut'
    category_name = 'Lead Qualification Team'

    def dispatch(self, request, *args, **kwargs):
        self.department = get_object_or_404(
            Department.objects.select_related('dept_type', 'region', 'category'),
            dept_type__name=self.dept_type,
            region__name=self.region_name,
            category__name=self.category_name
        )
        membership = get_object_or_404(
            DepartmentMembership,
            user=request.user,
            department=self.department
        )
        self.user_level = membership.level
        return super().dispatch(request, *args, **kwargs)


@require_POST
def adjust_dials(request, pk):
    if not request.user.is_authenticated:
        raise Http404()
    try:
        payload = json.loads(request.body)
        delta = int(payload.get('delta', 0))
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({'error': 'invalid payload'}, status=400)

    new_count = max(0, Interest.objects.get(pk=pk).dials + delta)
    Interest.objects.filter(pk=pk).update(
        dials=new_count,
        updated_by=request.user
    )
    return JsonResponse({'dials': new_count})


class InterestListView(DepartmentAccessMixin, LoginRequiredMixin, ListView):
    model = Interest
    template_name = "interests/interest_list.html"
    paginate_by = 10
    ordering = ['-updated_at']

    def get_queryset(self):
        qs = Interest.objects.select_related('created_by')
        req = self.request
        filters = Q()

        if not req.GET.get('range'):
            today = timezone.localdate()
            filters &= Q(created_at__date=today)

        q = req.GET.get('q', '').strip()
        if q:
            filters &= Q(phone_number__icontains=q)

        range_str = req.GET.get('range')
        if range_str:
            try:
                start_str, end_str = (d.strip() for d in range_str.split(' to ', 1))
                start_date = date.fromisoformat(start_str)
                end_date = date.fromisoformat(end_str)
            except ValueError:
                end_date = timezone.localdate()
                start_date = end_date - timedelta(days=7)
            filters &= Q(created_at__date__range=(start_date, end_date))

        conn = req.GET.get('connected')
        if conn in ('0', '1'):
            filters &= Q(is_connected=(conn == '1'))

        user_id = req.user.id
        if self.user_level == 3:
            filters &= Q(created_by_id=user_id)
        else:
            if self.user_level == 2:
                subq = Subquery(
                    DepartmentMembership.objects.filter(
                        department=self.department, level=3
                    ).values('user_id')
                )
                filters &= Q(created_by_id__in=subq) | Q(created_by_id=user_id)
            elif self.user_level == 1:
                subq = Subquery(
                    DepartmentMembership.objects.filter(
                        department=self.department, level__in=[1,2,3]
                    ).values('user_id')
                )
                filters &= Q(created_by_id__in=subq)
            else:
                return Interest.objects.none()

        return qs.filter(filters).order_by(*self.ordering)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({
            'q': self.request.GET.get('q', ''),
            'range': self.request.GET.get('range', ''),
            'connected': self.request.GET.get('connected', ''),
            'department': self.department,
            'user_level': self.user_level,
        })
        return ctx


class InterestCreateView(DepartmentAccessMixin, LoginRequiredMixin, CreateView):
    model = Interest
    form_class = InterestForm
    template_name = "interests/interest_form.html"
    success_url = reverse_lazy("interests:list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        return super().form_valid(form)


class InterestCustomerCreateView(DepartmentAccessMixin, LoginRequiredMixin, CreateView):
    model = Customer
    form_class = CustomerForm
    template_name = "interests/interest_create_from_interest.html"

    def get_initial(self):
        initial = super().get_initial()
        interest_pk = self.request.GET.get("from_interest")
        phone = self.request.GET.get("phone")
        source_pk = self.request.GET.get("source")
        if interest_pk:
            initial["interest"] = interest_pk
        if phone:
            initial["primary_phone"] = phone
        if source_pk:
            initial["source"] = source_pk
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
    model = Interest
    form_class = InterestForm
    template_name = "interests/interest_form.html"
    success_url = reverse_lazy("interests:list")

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        user = request.user

        auth = AuthorizedInterestUser.objects.filter(user=user).first()
        dept_access = DepartmentMembership.objects.filter(
            user=user,
            department__dept_type__name='Customer Support',
            department__category__name='Lead Qualification Team'
        ).exists()
        permitted = bool(dept_access) or (auth and (auth.role_type != 'member' or obj.created_by == user))
        if not permitted:
            return render(request, "interests/interest_list.html", {"has_access": False})
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if getattr(self.get_object(), 'lead', None) is not None:
            for f in form.fields.values():
                f.disabled = True
            messages.info(self.request, "This interest is tied to a Lead, so fields are read-only.")
        return form

    def form_valid(self, form):
        if getattr(self.get_object(), 'lead', None) is not None:
            return self.render_to_response(self.get_context_data(form=form))
        form.instance.updated_by = self.request.user
        return super().form_valid(form)
