# customers/views.py
import logging
import traceback

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.decorators.http import require_GET
from django.views.generic import ListView, CreateView, UpdateView, TemplateView

from .models import Customer
from .forms import CustomerForm
from leads.models import Lead
from leads.forms import LeadForm
from interests.models import Interest
from django.shortcuts import render, redirect, get_object_or_404
from leads.utils import allocate_lead_to_user

logger = logging.getLogger(__name__)

from django.contrib.auth import get_user_model
from django.db.models import Q, Sum, Prefetch
from .models import Customer, City

from django.core.exceptions import PermissionDenied

User = get_user_model()

class CustomerListView(LoginRequiredMixin, ListView):
    model = Customer
    paginate_by = 10
    ordering = ['-updated_at']

    def dispatch(self, request, *args, **kwargs):
        allowed = request.session.get('viewable_city_ids')
        if not allowed:
            # one-time check
            if not City.objects.filter(
                Q(view_only_users=request.user) |
                Q(view_edit_users=request.user)
            ).exists():
                raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        allowed = self.request.session.get('viewable_city_ids')
        if not allowed:
            allowed = list(
                City.objects
                    .filter(Q(view_only_users=user) | Q(view_edit_users=user))
                    .values_list('pk', flat=True)
            )
            self.request.session['viewable_city_ids'] = allowed

        return (
            Customer.objects
            .filter(city_id__in=allowed)
            .select_related('city', 'source', 'created_by', 'updated_by')
            .prefetch_related(
                'city__view_edit_users',
                'city__view_only_users',
            )
        )

class CustomerCreateView(LoginRequiredMixin, CreateView):
    model = Customer
    form_class = CustomerForm
    success_url = reverse_lazy('interests:list')  # redirect after save

    def get_initial(self):
        initial = super().get_initial()
        # grab the phone & source if passed in the URL
        phone  = self.request.GET.get('phone')
        source = self.request.GET.get('source')
        if phone:
            initial['primary_phone'] = phone
        if source:
            initial['source'] = source
        return initial

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # if we're coming from an Interest, lock the phone field
        if self.request.GET.get('from_interest'):
            form.fields['primary_phone'].widget.attrs['readonly'] = True
        return form

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        return super().form_valid(form)


class CustomerUpdateView(LoginRequiredMixin, UpdateView):
    model = Customer
    form_class = CustomerForm
    template_name = "customers/customer_form.html"
    success_url = reverse_lazy("customers:list")

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        user = request.user
        # must be in the city’s “view_edit_users”
        if not obj.city.view_edit_users.filter(pk=user.pk).exists():
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # disable the primary_phone field
        form.fields['primary_phone'].disabled = True
        form.fields['primary_phone'].widget.attrs['readonly'] = True
        return form

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        return super().form_valid(form)


class CustomerLeadCreateView(LoginRequiredMixin, TemplateView):
    template_name = "customers/customer_leads_form.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['interest_id']   = self.request.GET.get('from_interest')
        ctx['customer_form'] = CustomerForm(initial={
            'primary_phone': self.request.GET.get('phone'),
            'source':        self.request.GET.get('source'),
        })
        ctx['lead_form']     = LeadForm()
        return ctx

    def post(self, request, *args, **kwargs):
        data         = request.POST
        phone        = data.get('primary_phone', '').strip()
        interest_pk  = data.get('from_interest')

        # 1) Existing customer lookup
        try:
            existing_customer = Customer.objects.get(primary_phone=phone)
        except Customer.DoesNotExist:
            existing_customer = None

        # 2) Bind forms
        customer_form = CustomerForm(data)
        lead_form     = LeadForm(data)

        if not data.get('system_type'):
            lead_form.add_error('system_type', 'Please select a system type.')
            return self.render_to_response({
                'customer_form': customer_form,
                'lead_form':     lead_form,
                'interest_id':   interest_pk,
            })

        # 3) If existing customer, only validate lead
        if existing_customer:
            if not lead_form.is_valid():
                return self.render_to_response({
                    'customer_form': customer_form,
                    'lead_form':     lead_form,
                })

            lead = lead_form.save(commit=False)
            lead.customer   = existing_customer
            lead.created_by = request.user
            lead.updated_by = request.user

            # link the interest if passed
            if interest_pk:
                lead.interest = get_object_or_404(Interest, pk=interest_pk)

            lead.save()

            # ←←← CALL YOUR ALLOCATOR & LOGGING HERE
            assigned_id = allocate_lead_to_user(lead)
            logger.info("Auto‐allocated Lead %s to user %s", lead.pk, assigned_id)


            if interest_pk:
                return render(request, "customers/close_window.html")

            return redirect('leads:list')

        # 4) Otherwise, new-customer + lead
        if not (customer_form.is_valid() and lead_form.is_valid()):
            return self.render_to_response({
                'customer_form': customer_form,
                'lead_form':     lead_form,
            })

        customer = customer_form.save(commit=False)
        customer.created_by = request.user
        customer.updated_by = request.user
        customer.save()    

        
        lead     = lead_form.save(commit=False)
        lead.customer   = customer
        lead.created_by = request.user
        lead.updated_by = request.user

        if interest_pk:
            lead.interest = get_object_or_404(Interest, pk=interest_pk)

        lead.save()

         # ←←← AND HERE TOO
        assigned_id = allocate_lead_to_user(lead)
        logger.info("Auto‐allocated Lead %s to user %s", lead.pk, assigned_id)


        if interest_pk:
                return render(request, "customers/close_window.html")
                
        return redirect(reverse_lazy('customers:list'))

        
@require_GET
def api_customer_exists(request):
    phone = request.GET.get('phone', '').strip()
    if not phone:
        return JsonResponse({'error': 'Missing phone parameter'}, status=400)

    try:
        cust = Customer.objects.get(primary_phone=phone)

        # Build our payload
        return JsonResponse({
            'exists': True,
            'customer': {
                'designation':     cust.designation_id or '',
                'first_name':      cust.first_name or '',
                'last_name':       cust.last_name or '',
                'secondary_phone': cust.secondary_phone or '',
                'address':         cust.address or '',
                'city':            cust.city_id or '',
                'source':          cust.source_id or '',
            }
        })
    except Customer.DoesNotExist:
        return JsonResponse({'exists': False})
    except Exception as e:
        # Log the full traceback
        logger.exception("api_customer_exists failed for phone=%s", phone)
        # Return a JSON‐friendly error
        return JsonResponse({'error': 'Server side error'}, status=500)