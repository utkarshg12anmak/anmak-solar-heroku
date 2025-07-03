# leads/views.py

import logging
from django.db.models import Sum, Q, Prefetch
from django.utils import timezone
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied
from django.urls import reverse_lazy
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, TemplateView

from .models import (
    Lead, LeadStage,
    SYSTEM_TYPE_CHOICES, LEAD_QUALITY_CHOICES, GRID_TYPE_CHOICES,
)
from .forms import CustomerSelectionForm, CustomerCreateForm, LeadForm

from customers.models import Customer, City
from profiles.models import Department, DepartmentMembership
from profiles.mixins import SalesDepartmentRequiredMixin
from items.models import PriceRule
from visit_details.models import VisitDetail
from reminders.models import Reminder

from collections import defaultdict




# module-level constants & logger
IST = ZoneInfo("Asia/Kolkata")
logger = logging.getLogger(__name__)
User = get_user_model()

class LeadCreateWithCustomer(View):
    template_name = "leads/lead_with_customer_form.html"

    def get(self, request):
        return render(request, self.template_name, {
            'customer_select_form': CustomerSelectionForm(),
            'customer_create_form': CustomerCreateForm(),
            'lead_form': LeadForm(),
        })

    def post(self, request):
        # 1) Try to bind & validate the “select existing” form
        sel = CustomerSelectionForm(request.POST)
        if sel.is_valid() and sel.cleaned_data['primary_phone']:
            # see if there’s an existing customer
            phone = sel.cleaned_data['primary_phone']
            try:
                customer = Customer.objects.get(primary_phone=phone)
            except Customer.DoesNotExist:
                # no such customer; fall through to creation
                customer = None
        else:
            customer = None

        # 2) If no existing customer, try to create one
        if not customer:
            create = CustomerCreateForm(request.POST)
            if create.is_valid():
                customer = create.save()
            else:
                # customer creation errors → re-render both forms (showing errors)
                return render(request, self.template_name, {
                    'customer_select_form': sel,
                    'customer_create_form': create,
                    'lead_form': LeadForm(request.POST),
                })

        # 3) Now bind the lead form
        lead = LeadForm(request.POST)
        if lead.is_valid():
            new_lead = lead.save(commit=False)
            new_lead.customer = customer
            new_lead.save()
            # ─── auto‐allocate to a sales rep ──────────────────
            from .utils import allocate_lead_to_user
            allocate_lead_to_user(new_lead)
            return redirect('leads:list')
        else:
            # lead form errors → show them
            return render(request, self.template_name, {
                'customer_select_form': sel,
                'customer_create_form': CustomerCreateForm(),
                'lead_form': lead,
            })

class SalesDepartmentAccessMixin:
    """
    Grabs your Sales-dept membership out of session['memberships'] and
    enforces a 403 if you’re not in Sales.
    """
    def dispatch(self, request, *args, **kwargs):
        mems = request.session.get('memberships', [])
        # pick only the Sales ones
        sales = [m for m in mems if m.get('dept_type') == 'Sales']
        if not sales:
            raise PermissionDenied()
        # if you have multiple Sales depts, you could pick one by name or id;
        # here we just take the first
        sel = sales[0]
        self.department_id = sel['department_id']
        self.user_level    = sel['level']

        # pull your pre‐built map of dept→{ level→[user_ids] }
        self.department_user_map = request.session.get('department_user_map', {})

        return super().dispatch(request, *args, **kwargs)

class LeadListView(LoginRequiredMixin, SalesDepartmentAccessMixin, ListView):
    model               = Lead
    template_name       = "leads/lead_list.html"
    context_object_name = "leads"
    paginate_by         = 200
    ordering            = ["-updated_at"]

    def get_base_qs(self):
        # start with all Leads in your Sales dept:
        qs = (
            Lead.objects
                .select_related(
                    "customer__city",
                    "customer__source",
                    "stage",
                    "lead_manager",
                    "department",
                )
                .filter(department_id=self.department_id)
        )

        lvl_map = self.department_user_map.get(str(self.department_id), {})

        if self.user_level == 1:
            # see _all_ leads in this department
            return qs

        if self.user_level == 2:
            # see only those whose lead_manager is level 2 or 3
            mgr_ids = lvl_map.get("2", []) + lvl_map.get("3", [])
            return qs.filter(lead_manager_id__in=mgr_ids)

        if self.user_level == 3:
            # see only your own
            return qs.filter(lead_manager=self.request.user)

        raise PermissionDenied()

    def get_queryset(self):
        qs = self.get_base_qs().order_by(*self.ordering)

        # quick search:
        q = self.request.GET.get("q", "").strip()
        if q:
            sq = Q(pk=q) if q.isdigit() else Q()
            sq |= Q(customer__primary_phone__icontains=q)
            sq |= Q(customer__first_name__icontains=q)
            sq |= Q(customer__last_name__icontains=q)
            qs = qs.filter(sq)

        # dropdown filters:
        mapping = {
            "city":         "customer__city_id",
            "system_type":  "system_type",
            "grid_type":    "grid_type",
            "lead_quality": "lead_quality",
            "lead_manager": "lead_manager_id",
            "department":   "department_id",
        }
        for param, field in mapping.items():
            val = self.request.GET.get(param)
            if val:
                qs = qs.filter(**{field: val})

        # --- now apply the “last‐stage gets only this month” rule ---
        last_stage = LeadStage.objects.order_by('order').last()
        if last_stage:
            today         = timezone.localdate()
            first_of_month = today.replace(day=1)

            # keep:
            #  • all leads *not* in last_stage, and
            #  • only those in last_stage with created_at ≥ first_of_month
            qs = qs.filter(
                Q(stage=last_stage, created_at__date__gte=first_of_month)
                | ~Q(stage=last_stage)
            )


        return qs.order_by(*self.ordering)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        page_leads = ctx["leads"]

        # — total_amount across ALL filtered leads (one more query) —
        agg = self.get_base_qs().aggregate(sum=Sum("total_amount"))
        ctx["total_amount_sum"] = agg["sum"] or 0

        # — static dropdowns —
        ctx.update({
            "cities":         City.objects.all(),
            "system_types":   SYSTEM_TYPE_CHOICES,
            "grid_types":     GRID_TYPE_CHOICES,
            "lead_qualities": LEAD_QUALITY_CHOICES,            
            "lead_managers":  User.objects.filter(leads_owned__isnull=False).distinct(),
            "departments":    Department.objects.filter(dept_type__name="Sales"),

            "selected_city":       self.request.GET.get("city", ""),
            "selected_system":     self.request.GET.get("system_type", ""),
            "selected_grid":       self.request.GET.get("grid_type", ""),
            "selected_quality":    self.request.GET.get("lead_quality", ""),
            "selected_manager":    self.request.GET.get("lead_manager", ""),
            "selected_department": self.request.GET.get("department", ""),
        })

        # — view mode & stages —
        ctx["view_mode"]       = self.request.GET.get("view", "grid")
        ctx["lead_stage_list"] = list(LeadStage.objects.order_by("order"))

        # — compute created_str & age_display on just the paginated leads —
        now_ist = timezone.now().astimezone(IST)
        for lead in page_leads:
            if lead.created_at:
                ci = lead.created_at.astimezone(IST)
                lead.created_str = ci.strftime("%d-%b-%Y %I:%M %p")
                diff  = now_ist - ci
                hrs   = diff.total_seconds() // 3600
                lead.age_display = (
                    f"{int(hrs)} hr{'s' if hrs != 1 else ''}"
                    if hrs < 24
                    else f"{diff.days} day{'s' if diff.days != 1 else ''}"
                )
            else:
                lead.created_str = ""
                lead.age_display = ""

        # — per-stage summary over just this page —
        summaries = {
            s.id: {"count": 0, "kw_sum": 0, "amt_sum": 0}
            for s in ctx["lead_stage_list"]
        }
        for lead in page_leads:
            summ = summaries[lead.stage_id]
            summ["count"] += 1
            summ["kw_sum"]  += (lead.system_size or 0)
            summ["amt_sum"] += (lead.total_amount or 0)
        ctx["stage_summaries"] = summaries

        return ctx
    
class LeadCreateView(LoginRequiredMixin, CreateView):
    model = Lead
    form_class = LeadForm
    template_name = "leads/lead_form.html"
    success_url = reverse_lazy("leads:list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # pass all LeadStage objects (ordered by `order`) into the template
        ctx["all_stages"] = LeadStage.objects.all()
        return ctx        

def customer_lookup(request, phone):
    """
    GET /api/customer/lookup/<phone>/
    Returns:
      { customer_found: true, customer: { … } }
    or
      { customer_found: false }
    """
    try:
        cust = Customer.objects.get(primary_phone=phone)
        data = {
            "customer_found": True,
            "customer": {
                "designation":    cust.designation_id,
                "first_name":     cust.first_name,
                "last_name":      cust.last_name,
                "primary_phone":  cust.primary_phone,
                "secondary_phone": cust.secondary_phone or "",
                "address":        cust.address,
                "city":           cust.city_id,
                "source":         cust.source_id,
            }
        }
    except Customer.DoesNotExist:
        data = {"customer_found": False}

    return JsonResponse(data)

class LeadUpdateView(LoginRequiredMixin, UpdateView):
    model = Lead
    form_class = LeadForm
    template_name = "leads/lead_form.html"
    success_url = reverse_lazy("leads:list")

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        # 1) Let Django build the basic context (this sets self.object)
        ctx = super().get_context_data(**kwargs)

        # 2) Always pass all LeadStage objects (ordered by `order`) into the template
        ctx["all_stages"] = LeadStage.objects.all()

        lead = self.object
        
        # ─────────────────────────────────────────────────────────────────────────

        # 3) Compute “next_stage” and “prev_stage”
        current_order = lead.stage.order
        ctx["next_stage"] = (
            LeadStage.objects
            .filter(order__gt=current_order)
            .order_by("order")
            .first()
        )
        ctx["prev_stage"] = (
            LeadStage.objects
            .filter(order__lt=current_order)
            .order_by("-order")
            .first()
        )



        # ── THIS IS THE IMPORTANT PART ──
        # Before filtering Reminders, fetch the ContentType for Lead:
        ct = ContentType.objects.get_for_model(Lead)

        # 2) Query all reminders attached to this lead:
        ctx["reminders"] = Reminder.objects.filter(
            content_type=ct,
            object_id=self.object.pk
        ).order_by("-reminder_time")
        # ─────────────────────────────────────────────────────────────────────────

        # fetch only the rules available in this lead’s city
        price_rules = PriceRule.objects.filter(
            available=True,
            price_book__cities=lead.customer.city
        ).select_related('item')

        # <-- here was the typo; change `context` to `ctx`:
        ctx['price_rules'] = price_rules

        # Fetch all site-visits for this lead, newest first
        ctx["site_visits"] = (
            VisitDetail.objects
                       .filter(lead=self.object)
                       .order_by("-visit_date", "-start_time")
       )

        return ctx

class LeadNextStageView(LoginRequiredMixin, View):
    """
    POST /leads/<pk>/next_stage/ → bump this lead to the next‐higher "order" stage.
    """
    def post(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk)
        current_order = lead.stage.order
        # find the very next stage (order > current)
        next_stage = (
            LeadStage.objects
            .filter(order__gt=current_order)
            .order_by('order')
            .first()
        )
        if next_stage:
            lead.stage = next_stage
            lead.updated_by = request.user
            lead.save()
        return redirect('leads:edit', pk=pk)


class LeadPrevStageView(LoginRequiredMixin, View):
    """
    POST /leads/<pk>/prev_stage/ → roll this lead back to the previous "order" stage.
    """
    def post(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk)
        current_order = lead.stage.order
        # find the very previous stage (order < current), pick the highest among them
        prev_stage = (
            LeadStage.objects
            .filter(order__lt=current_order)
            .order_by('-order')
            .first()
        )
        if prev_stage:
            lead.stage = prev_stage
            lead.updated_by = request.user
            lead.save()
        return redirect('leads:edit', pk=pk)


class LeadEditFormView(LoginRequiredMixin, View):
    def get(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk)
        form = LeadForm(instance=lead)
        return render(
            request,
            "leads/_lead_edit_form.html",
            { "lead": lead, "form": form }
        )

    def post(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk)
        form = LeadForm(request.POST, instance=lead)
        if form.is_valid():
            form.save()
            return JsonResponse({"success": True})
        # If invalid, re‐render the same partial with error messages:
        return render(
            request,
            "leads/_lead_edit_form.html",
            { "lead": lead, "form": form }
        )

class LeadKanbanView(SalesDepartmentRequiredMixin, TemplateView):
    template_name = "leads/_lead_kanban.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # prepare IST once
        ist      = IST
        now_ist  = timezone.now().astimezone(ist)

        # 1) build a base Lead queryset that pulls in every FK you'll need
        lead_qs = Lead.objects.select_related(
            "lead_manager",
            "stage",
            "department",
            "customer__city",
            "customer__source",
        )

        # 2) fetch all stages, prefetching their leads in one go
        lead_stage_list = (
            LeadStage.objects
                     .order_by("order")
                     .prefetch_related(
                         Prefetch("lead_set", queryset=lead_qs, to_attr="leads")
                     )
        )

        # 3) annotate each lead with created_str & age_display exactly as before
        for stage in lead_stage_list:
            for lead in stage.leads:
                created = lead.created_at
                if created:
                    created_ist = created.astimezone(ist)
                    lead.created_str = created_ist.strftime("%d-%b-%Y %I:%M %p")

                    diff   = now_ist - created_ist
                    hours  = diff.total_seconds() // 3600
                    if hours < 24:
                        lead.age_display = f"{int(hours)} hr{'s' if hours != 1 else ''}"
                    else:
                        lead.age_display = f"{diff.days} day{'s' if diff.days != 1 else ''}"
                else:
                    lead.created_str  = ""
                    lead.age_display  = ""

        ctx["lead_stage_list"] = lead_stage_list
        # if your template also expects ctx["leads"], you can still do:
        # ctx["leads"] = [lead for stage in lead_stage_list for lead in stage.leads]

        return ctx

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