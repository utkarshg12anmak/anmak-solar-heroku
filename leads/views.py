# leads/views.py

from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView
from .models import Lead, LeadStage
from django.http import JsonResponse
from customers.models import Customer

from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, View
from .forms import CustomerSelectionForm, CustomerCreateForm, LeadForm
from customers.models import Customer
from django.db.models import Sum
from django.views import View

from django.db.models import Q

from django.views.generic import TemplateView
from django.utils import timezone
from datetime import timedelta

from reminders.models import Reminder   # ← Make sure this is present
from django.contrib.contenttypes.models import ContentType

# leads/views.py (in your LeadUpdateView.get_context_data or similar)
from items.models import PriceRule

from django.db.models import Q
from profiles.models import DepartmentMembership

from profiles.mixins import SalesDepartmentRequiredMixin

from zoneinfo import ZoneInfo
from django.utils import timezone

IST = ZoneInfo("Asia/Kolkata")

import logging
logger = logging.getLogger(__name__)

from django.contrib.auth import get_user_model
from profiles.models import Department     # used in context_data
from customers.models import City          # you already have this

from .models import (
    Lead,
    LeadStage,
    SYSTEM_TYPE_CHOICES,
    LEAD_QUALITY_CHOICES,
    GRID_TYPE_CHOICES,
)
from django.contrib.auth import get_user_model
User = get_user_model()

from visit_details.models import VisitDetail

from items.models import PriceRule



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

class LeadListView(LoginRequiredMixin,
                   SalesDepartmentRequiredMixin,
                   ListView):
    model = Lead
    template_name = "leads/lead_list.html"
    context_object_name = "leads"
    paginate_by = 15
    ordering = ["-updated_at"]

    def get_queryset(self):
        me = self.request.user

        # 1) Base queryset + search
        qs = super().get_queryset().select_related(
            "customer__city", "stage", "lead_manager", "department"
        )
        search = self.request.GET.get("q", "").strip()
        if search:
            q_obj = Q(pk=search) if search.isdigit() else Q()
            q_obj |= Q(customer__primary_phone__icontains=search)
            q_obj |= Q(customer__first_name__icontains=search)
            q_obj |= Q(customer__last_name__icontains=search)
            qs = qs.filter(q_obj)

        # ––– 2) dropdown filters –––
        city     = self.request.GET.get("city")
        sys_type = self.request.GET.get("system_type")
        grid     = self.request.GET.get("grid_type")
        quality  = self.request.GET.get("lead_quality")
        mgr      = self.request.GET.get("lead_manager")
        dept     = self.request.GET.get("department")


        if city:      qs = qs.filter(customer__city_id=city)
        if sys_type:  qs = qs.filter(system_type=sys_type)
        if grid:      qs = qs.filter(grid_type=grid)
        if quality:   qs = qs.filter(lead_quality=quality)
        if mgr:       qs = qs.filter(lead_manager_id=mgr)
        if dept:      qs = qs.filter(department_id=dept)   

        # 2) Grab only your Sales‐dept memberships
        my_mems = DepartmentMembership.objects.filter(
            user=me,
            department__dept_type__name="Sales"
        )

        # 3) Build a Q for “dept‐level” access
        allowed_q = Q(lead_manager=me)  # always see your own leads

        for mem in my_mems:
            dept = mem.department
            if mem.level == 1:
                # Level 1 in dept: include managers at level 2 & level 3 of *this* dept
                mgr_ids = DepartmentMembership.objects.filter(
                    department=dept,
                    level__in=[2,3]
                ).values_list("user_id", flat=True)
                allowed_q |= Q(department=dept, lead_manager_id__in=mgr_ids)

            elif mem.level == 2:
                # Level 2 in dept: include managers at level 3 of *this* dept
                mgr_ids = DepartmentMembership.objects.filter(
                    department=dept,
                    level=3
                ).values_list("user_id", flat=True)
                allowed_q |= Q(department=dept, lead_manager_id__in=mgr_ids)

            # Level 3: no extra dept‐wide access beyond your own leads

        # 4) Apply the combined filter
        return qs.filter(allowed_q)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # 2) Compute the total sum of `total_amount`
        total_sum = self.get_queryset().aggregate(sum=Sum("total_amount"))["sum"] or 0
        ctx["total_amount_sum"] = total_sum

        # pass your dropdown options & current selections
        ctx.update({
            "cities": City.objects.all(),
            "system_types":   SYSTEM_TYPE_CHOICES,
            "grid_types":     GRID_TYPE_CHOICES,
            "lead_qualities": LEAD_QUALITY_CHOICES,    
            "lead_managers": User.objects.filter(leads_owned__isnull=False).distinct(),
            "departments": Department.objects.filter(dept_type__name="Sales"),

            "selected_city":     self.request.GET.get("city", ""),
            "selected_system":   self.request.GET.get("system_type", ""),
            "selected_grid":     self.request.GET.get("grid_type", ""),
            "selected_quality":  self.request.GET.get("lead_quality", ""),
            "selected_manager":  self.request.GET.get("lead_manager", ""),
            "selected_department": self.request.GET.get("department", ""),
        })

        # 3) Decide view_mode
        ctx["view_mode"] = self.request.GET.get("view", "grid")

        # 4) All LeadStage objects
        lead_stage_list = LeadStage.objects.all().order_by("order")
        ctx["lead_stage_list"] = lead_stage_list

        # ─────────────────────────────────────────────────────
        # 5) Attach created_str & age_display to each lead in IST
        now_ist = timezone.now().astimezone(IST)

        for lead in ctx["leads"]:
            if lead.created_at:
                # convert stored UTC → IST
                created_ist = lead.created_at.astimezone(IST)

                # format
                lead.created_str = created_ist.strftime("%d-%b-%Y %I:%M %p")

                # compute age in hours/days
                diff = now_ist - created_ist
                hours = diff.total_seconds() // 3600

                if hours < 24:
                    lead.age_display = f"{int(hours)} hr{'s' if hours != 1 else ''}"
                else:
                    days = diff.days
                    lead.age_display = f"{days} day{'s' if days != 1 else ''}"
            else:
                lead.created_str = ""
                lead.age_display = ""
        # ─────────────────────────────────────────────────────

        # 6) Build per-stage summaries
        stage_summaries = {}
        for stage in lead_stage_list:
            leads_in_stage = [l for l in ctx["leads"] if l.stage_id == stage.id]
            stage_summaries[stage.id] = {
                "count": len(leads_in_stage),
                "kw_sum": sum((l.system_size or 0) for l in leads_in_stage),
                "amt_sum": sum((l.total_amount or 0) for l in leads_in_stage),
            }
        ctx["stage_summaries"] = stage_summaries

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

        # 1) Fetch your stages and leads
        lead_stage_list = LeadStage.objects.all().order_by("order")
        leads = Lead.objects.select_related("customer", "lead_manager").all()

        # 2) Prepare IST tzinfo
        ist = ZoneInfo("Asia/Kolkata")
        now_ist = timezone.now().astimezone(ist)

        # 3) Convert and log
        for lead in leads:
            raw = lead.created_at
            logger.debug(f"Lead #{lead.pk} raw created_at: {raw!r} (tzinfo={raw.tzinfo!r})")

            # If raw is naive (tzinfo=None), this will silently treat it as local,
            # so let’s make sure it’s UTC before converting:
            if raw.tzinfo is None:
                raw = raw.replace(tzinfo=timezone.utc)
                logger.debug(f"  → assigned UTC tzinfo: {raw!r} (tzinfo={raw.tzinfo!r})")

            created_ist = raw.astimezone(ist)
            logger.debug(f"  → converted to IST: {created_ist!r} (tzinfo={created_ist.tzinfo!r})")

            # Now use that for display
            lead.created_str = created_ist.strftime("%d-%b-%Y %I:%M %p")

            diff = now_ist - created_ist
            hours = diff.total_seconds() // 3600
            if hours < 24:
                lead.age_display = f"{int(hours)} hr{'s' if hours != 1 else ''}"
            else:
                lead.age_display = f"{diff.days} day{'s' if diff.days != 1 else ''}"

        # 4) Pass into template
        ctx["lead_stage_list"] = lead_stage_list
        ctx["leads"] = leads
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