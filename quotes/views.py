# quotes/views.py
import json
import logging
import os
import subprocess
import tempfile  
from decimal import Decimal, InvalidOperation

from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

from leads.models import Lead
from items.models import PriceRule
from .models import Quote, QuoteItem

logger = logging.getLogger(__name__)

from django.views.decorators.http import require_POST

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts        import get_object_or_404, redirect
from django.urls            import reverse_lazy
from django.views.generic   import ListView
from django.contrib import messages

from .models import Quote

from django.core.exceptions import PermissionDenied
from profiles.models import DepartmentMembership

from django.utils import timezone
from django.db.models import Q, Prefetch

from .mixins import LeadAccessMixin

from profiles.models import DepartmentMembership, ApprovalLimit
from decimal import Decimal

from docx2pdf import convert

from docx import Document   # python-docx

from django.http import FileResponse, Http404
from django.contrib.auth.decorators import login_required, permission_required

from docx.oxml.ns import qn
from docx.shared import RGBColor, Pt
from docx.oxml.ns import qn

from .models import Quote, QuoteItem
from .mixins import LeadAccessMixin
from profiles.models import DepartmentMembership

from django.db.models import Prefetch
from django.shortcuts import render

import io
from django.template.loader import render_to_string
from django.http          import FileResponse, Http404

from django.shortcuts     import get_object_or_404
from django.contrib.auth.decorators import login_required

from .models import Quote

import io
from django.template.loader import render_to_string
from django.http          import FileResponse, Http404
from django.shortcuts     import get_object_or_404

from PyPDF2               import PdfMerger

from .models import Quote

from io import BytesIO
from xhtml2pdf import pisa
from django.http import HttpResponse

import os
from io import BytesIO
from django.shortcuts       import get_object_or_404
from django.http            import FileResponse, Http404
from django.contrib.auth.decorators import login_required
from PyPDF2               import PdfReader, PdfWriter

from .models import Quote

from django.template.loader import render_to_string
from django.http import FileResponse
from .utils import html_to_png, png_to_pdf


@login_required
@require_POST
def create_quote_json(request, lead_id):
    """
    AJAX endpoint to create a Quote for a Lead.
    Expects either:
      - JSON body:   {"items":[{"price_rule":1,"quantity":2},…],
                     "selling_price":12345,
                     "discount":500}
      - OR form data: items_json='…', selling_price=…, discount=…
    Returns JSON {success:True, quote_id:…} or HTTP 400 on client errors.
    """
    lead = get_object_or_404(Lead, pk=lead_id)
    logger.debug("Raw body for lead %s: %r", lead_id, request.body)

    # 1) Try parsing a JSON body
    items = None
    selling_price = None
    discount = 0
    try:
        payload = json.loads(request.body)
        items         = payload.get("items")
        selling_price = payload.get("selling_price")
        discount      = payload.get("discount", 0)
    except json.JSONDecodeError:
        pass

    # 2) Fallback to form-encoded
    if items is None or selling_price is None:
        items_json     = request.POST.get("items_json", "[]")
        selling_price  = request.POST.get("selling_price", "")
        discount       = request.POST.get("discount", "0")
        try:
            items = json.loads(items_json)
        except json.JSONDecodeError:
            return HttpResponseBadRequest("Invalid items_json")

    # 3) Validate presence
    if not isinstance(items, list) or selling_price in (None, ""):
        return HttpResponseBadRequest("Missing items or selling_price")

    # 4) Parse decimals
    try:
        selling_dec = Decimal(str(selling_price))
    except InvalidOperation:
        return HttpResponseBadRequest("Invalid selling_price")
    try:
        discount_dec = Decimal(str(discount))
    except InvalidOperation:
        discount_dec = Decimal("0")

    # 5) Create the Quote header (now with discount)
    quote = Quote.objects.create(
        lead           = lead,
        created_by     = request.user,
        updated_by     = request.user,
        selling_price  = selling_dec,
        discount       = discount_dec,
        minimum_price  = Decimal("0"),  # will recalc below
        status         = Quote.STATUS_PENDING,
    )

    # 6) Build line items & accumulate minimum_price
    total_min = Decimal("0")
    for entry in items:
        pr_id = entry.get("price_rule")
        qty   = entry.get("quantity")
        if not pr_id or qty in (None, ""):
            continue

        pr = get_object_or_404(
            PriceRule.objects.filter(
                pk=pr_id,
                available=True,
                price_book__cities=lead.customer.city
            )
        )

        try:
            qty_dec = Decimal(str(qty))
        except InvalidOperation:
            continue

        tiers     = pr.tiers.filter(min_quantity__lte=qty_dec).order_by("-min_quantity")
        unit_price = tiers[0].price if tiers else pr.base_price
        line_min   = unit_price * qty_dec
        total_min += line_min

        QuoteItem.objects.create(
            quote       = quote,
            price_rule  = pr,
            quantity    = qty_dec,
        )

    # 7) Persist computed minimum_price
    quote.minimum_price = total_min
    quote.save(update_fields=["minimum_price"])

    logger.info(
        "Created Quote #%s (lead=%s) with min=%s, sell=%s, discount=%s",
        quote.pk, lead_id, total_min, selling_dec, discount_dec
    )

    return JsonResponse({"success": True, "quote_id": quote.pk})


@login_required
@require_POST
def soft_delete_quote(request, lead_id, quote_id):
    """
    Soft-delete a Quote by setting its status to 'deleted'
    only if it's still pending.
    """
    quote = get_object_or_404(Quote, pk=quote_id, lead_id=lead_id)
    if quote.status != Quote.STATUS_PENDING:
        return JsonResponse({"success": False, "error": "Only pending quotes may be deleted."}, status=400)

    quote.status = Quote.STATUS_DELETED
    quote.save(update_fields=["status"])
    return JsonResponse({"success": True})

class QuoteApprovalListView(LeadAccessMixin, ListView):
    template_name        = "quotes/approval_list.html"
    context_object_name  = "quotes"
    paginate_by          = 10

    def dispatch(self, request, *args, **kwargs):
        user = request.user

        # 1) only Sales/Finance may even GET this page:
        if not DepartmentMembership.objects.filter(
            user=user,
            department__dept_type__name__in=["Sales", "Finance"]
        ).exists():
            raise PermissionDenied

        # 2) stash your active_membership (dept_id, level) in session
        if "active_membership" not in request.session:
            mem = DepartmentMembership.objects.filter(
                user=user,
                department__dept_type__name__in=["Sales", "Finance"]
            ).first()
            request.session["active_membership"] = {
                "department_id":  mem.department_id,
                "level":          mem.level,
            }

        # 3) stash all approval limits (per dept, per level) in session
        if "approval_limit_map" not in request.session:
            raw = ApprovalLimit.objects.values(
                "department_id", "level", "max_amount"
            )
            limit_map = {}
            for row in raw:
                dept = str(row["department_id"])
                lvl  = str(row["level"])
                amt  = str(row["max_amount"])   # store as string
                limit_map.setdefault(dept, {})[lvl] = amt
            request.session["approval_limit_map"] = limit_map

        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        # 1) Which tab?
        tab = self.request.GET.get("tab", "pending")

        # 2) Build base queryset with all related objects needed for the template
        base_qs = (
            Quote.objects
                .select_related(
                    "lead__lead_manager",
                    "lead__customer__city",
                    "created_by",
                    "approved_by",
                    "updated_by",
                    
                )
                .prefetch_related(
                    Prefetch(
                        "items",
                        queryset=QuoteItem.objects.select_related("price_rule__item")
                    )
                )
                .order_by("-updated_at")
        )

        # 3) Filter to only leads this user may access
        allowed_lead_ids = list(self.get_allowed_leads().values_list("pk", flat=True))
        qs = base_qs.filter(lead_id__in=allowed_lead_ids)

        # 4) Status filtering by tab
        if tab == "completed":
            qs = qs.filter(status__in=[
                Quote.STATUS_APPROVED,
                Quote.STATUS_DECLINED,
                Quote.STATUS_DELETED,
            ])
        else:
            qs = qs.filter(status=Quote.STATUS_PENDING)

        # 5) Prepare memberships and approval limits from session
        memberships = [
            m for m in self.request.session.get("memberships", [])
            if m["dept_type"] in ["Sales", "Finance"]
        ]
        approval_limit_map = self.request.session.get("approval_limit_map", {})

        # 6) Attach can_approve per quote (this is what your template will check)
        quotes = list(qs)  # Evaluate queryset so we can loop over it

        for q in quotes:
            q.can_approve = False
            quote_dept_id = str(q.lead.department_id)
            print(f"Quote {q.pk} department: {quote_dept_id}, amount: {q.selling_price}")
            for mem in memberships:
                dept_id = str(mem["department_id"])
                level = str(mem["level"])
                print(f"Checking membership: {dept_id=} {level=}")
                if dept_id == quote_dept_id:
                    print("  Dept matches")
                    if dept_id in approval_limit_map and level in approval_limit_map[dept_id]:
                        max_amt = int(approval_limit_map[dept_id][level])
                        print(f"  Found limit: {max_amt}")
                        if q.selling_price <= max_amt:
                            print("  APPROVE!")
                            q.can_approve = True
                            break  # No need to check more memberships
        return quotes

    def get_context_data(self, **kwargs):
        ctx  = super().get_context_data(**kwargs)
        user = self.request.user
        tab  = self.request.GET.get("tab", "pending")

        ctx["tab"] = tab

        # grab them out of the session
        mem     = self.request.session["active_membership"]
        dept_id = str(mem["department_id"])
        lvl     = str(mem["level"])
        limits  = self.request.session["approval_limit_map"]

        for quote in ctx["quotes"]:
            # recompute per-item on the fly
            for item in quote.items.all():
                cp  = item.calculated_price or Decimal("0")
                qty = item.quantity         or Decimal("0")
                item.price_per_item = (cp / qty) if qty else Decimal("0")

            # decide if this user may approve/decline
        allowed = False
        memberships = [
            m for m in self.request.session.get("memberships", [])
            if m["dept_type"] in ["Sales", "Finance"]
        ]
        approval_limit_map = self.request.session.get("approval_limit_map", {})

        for mem in memberships:
            dept_id = str(mem["department_id"])
            level = str(mem["level"])
            quote_dept_id = str(quote.lead.department_id)
            # Only L1 can approve below minimum
            if quote.selling_price < quote.minimum_price:
                if dept_id == quote_dept_id and level == "1":
                    allowed = True
                    break
            else:
                if dept_id == quote_dept_id and dept_id in approval_limit_map and level in approval_limit_map[dept_id]:
                    max_amt = int(approval_limit_map[dept_id][level])
                    if quote.selling_price <= max_amt:
                        allowed = True
                        break

        quote.can_approve = allowed
        quote.can_decline = allowed


        return ctx 


@login_required
@require_POST
def approve_quote(request, pk):
    q = get_object_or_404(Quote, pk=pk, status=Quote.STATUS_PENDING)
    q.status      = Quote.STATUS_APPROVED
    q.approved_by = request.user
    q.approved_at = timezone.now()
    q.updated_by  = request.user
    q.save(update_fields=["status", "approved_by", "approved_at", "updated_by", "updated_at"])
    messages.success(request, f"Quote #{q.pk} approved.")
    return redirect(request.META.get("HTTP_REFERER", reverse_lazy("quotes:approval_list")))


@login_required
@require_POST
def decline_quote(request, pk):
    q = get_object_or_404(Quote, pk=pk, status=Quote.STATUS_PENDING)
    q.status     = Quote.STATUS_DECLINED
    q.updated_by = request.user
    q.save(update_fields=["status", "updated_by", "updated_at"])
    messages.success(request, f"Quote #{q.pk} declined.")
    return redirect(request.META.get("HTTP_REFERER", reverse_lazy("quotes:approval_list")))

    
@login_required
def quotation_view(request, quote_pk):
    # 1) Fetch the quote (only approved ones? add filter if you like)
    quote = get_object_or_404(Quote, pk=quote_pk)

    # 2) Grab its items and any related data
    items = (
        QuoteItem.objects
                 .filter(quote=quote)
                 .select_related("price_rule__item")
    )

    # 3) Build whatever extra context you need
    context = {
        "quote": quote,
        "items": items,
        # add customer, totals, etc. if your template expects them
    }
    return render(request, "quotes/quotation_pdf_base.html", context)

def quotation_preview(request):
    # you can pass whatever dummy context you like here
    context = {
      "some_value": "foo",
      "another": 123,
      # …
    }
    return render(request, "quotes/quotation_pdf_base.html", context)

@login_required
def preview_quote_pdf(request, quote_pk):
    # 1) Load & validate
    quote = get_object_or_404(Quote, pk=quote_pk)
    # (you can enforce only-approved if you like)

    # 2) Render HTML template to a string
    html_string = render_to_string(
        "quotes/quotation_pdf_base.html",
        {"quote": quote},
        request=request  # so static() tags resolve correctly
    )

    # 3) Use WeasyPrint to write a PDF into a BytesIO buffer
    pdf_io = io.BytesIO()
    HTML(string=html_string, base_url=request.build_absolute_uri("/")) \
        .write_pdf(target=pdf_io)
    pdf_io.seek(0)

    # 4) Stream it back
    filename = f"AMKSLR-{quote.pk:03d}.pdf"
    return FileResponse(
        pdf_io,
        as_attachment=True,
        filename=filename,
        content_type="application/pdf"
    )

def html_to_pdf(html: str) -> bytes:
    buff = BytesIO()
    pisa_status = pisa.CreatePDF(src=html, dest=buff)
    if pisa_status.err:
        raise ValueError("PDF generation failed")
    return buff.getvalue()



# quotes/views.py (snippet)
from django.template.loader import render_to_string
from django.http import FileResponse
from .utils import html_to_pdf_with_chrome

from django.templatetags.static import static


@login_required
def download_full_quote(request, quote_pk):
    quote = get_object_or_404(Quote, pk=quote_pk, status=Quote.STATUS_APPROVED)

    logo_url = request.build_absolute_uri(static('logo_dark.svg'))

    html = render_to_string(
        "quotes/quotation_pdf_base.html",
        {"quote": quote, "logo_url": logo_url},
        request=request
    )    

    # 1) Pre + body + post merging
    from PyPDF2 import PdfReader, PdfWriter
    writer = PdfWriter()

    # -- Pre PDF --
    pre = quote.lead.department.quote_template.pre_pdf
    if not pre: raise Http404("No pre-PDF")
    writer.append(PdfReader(pre))

    # -- Body PDF via headless Chrome --
    body_pdf = html_to_pdf_with_chrome(html)
    writer.append(PdfReader(BytesIO(body_pdf)))

    # -- Post PDF --
    post = quote.lead.department.quote_template.post_pdf
    if not post: raise Http404("No post-PDF")
    writer.append(PdfReader(post))

    # 2) Emit
    out = BytesIO()
    writer.write(out)
    out.seek(0)
    filename = f"AMKSLR-{quote.pk:03d}.pdf"
    return FileResponse(out, as_attachment=True, filename=filename,
                        content_type="application/pdf")
