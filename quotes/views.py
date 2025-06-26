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



@login_required
@require_POST
def create_quote_json(request, lead_id):
    """
    AJAX endpoint to create a Quote for a Lead.
    Expects either:
      - JSON body:   {"items":[{"price_rule":1,"quantity":2},…], "selling_price":12345}
      - OR form data: items_json='[{"price_rule":…}]', selling_price=…
    Returns JSON {success:True, quote_id:…} or HTTP 400 on client errors.
    """
    lead = get_object_or_404(Lead, pk=lead_id)
    logger.debug("Raw body for lead %s: %r", lead_id, request.body)

    # 1) Try parsing a JSON body
    items = None
    selling_price = None
    try:
        payload = json.loads(request.body)
        items        = payload.get("items")
        selling_price = payload.get("selling_price")
    except json.JSONDecodeError:
        # not JSON, we'll fall back
        pass

    # 2) Fallback to form-encoded
    if items is None or selling_price is None:
        items_json = request.POST.get("items_json", "[]")
        selling_price = request.POST.get("selling_price", "")
        try:
            items = json.loads(items_json)
        except json.JSONDecodeError:
            return HttpResponseBadRequest("Invalid items_json")

    # 3) Validate
    if not isinstance(items, list) or selling_price in (None, ""):
        return HttpResponseBadRequest("Missing items or selling_price")

    try:
        selling_dec = Decimal(str(selling_price))
    except InvalidOperation:
        return HttpResponseBadRequest("Invalid selling_price")

    # 4) Create the Quote header
    quote = Quote.objects.create(
        lead=lead,
        created_by=request.user,
        updated_by=request.user,
        selling_price=selling_dec,
        minimum_price=Decimal("0"),              # will recalc below
        status=Quote.STATUS_PENDING,
    )

    # 5) Build line items & accumulate minimum_price
    total_min = Decimal("0")
    for entry in items:
        pr_id = entry.get("price_rule")
        qty   = entry.get("quantity")
        if not pr_id or qty in (None, ""):
            continue

        # only allow PriceRules available in this lead’s city
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

        # compute tiered unit price
        tiers = pr.tiers.filter(min_quantity__lte=qty_dec).order_by("-min_quantity")
        unit_price = tiers[0].price if tiers else pr.base_price
        line_min = unit_price * qty_dec
        total_min += line_min        

        QuoteItem.objects.create(
            quote=quote,
            price_rule=pr,
            quantity=qty_dec,
        )

    # 6) Persist computed minimum_price
    quote.minimum_price = total_min
    quote.save(update_fields=["minimum_price"])

    logger.info("Created Quote #%s (lead=%s) with min=%s sell=%s",
                quote.pk, lead_id, total_min, selling_dec)

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
    template_name = "quotes/approval_list.html"
    context_object_name = "quotes"
    paginate_by = 10

    def dispatch(self, request, *args, **kwargs):
        # only allow if user is in a Sales or Finance department
        if not DepartmentMembership.objects.filter(
            user=request.user,
            department__dept_type__name__in=["Sales", "Finance"]
        ).exists():
            raise PermissionDenied("You do not have permission to view quote approvals.")
        return super().dispatch(request, *args, **kwargs)


    def get_queryset(self):
        tab = self.request.GET.get("tab", "pending")

        # start from all Quotes on leads this user may access:
        allowed_leads = self.get_allowed_leads().values_list("pk", flat=True)

        base = (
            Quote.objects
                 .select_related("lead", "created_by", "approved_by", "updated_by")
                 .filter(lead_id__in=allowed_leads)
                 .order_by("-updated_at")
        )

        if tab == "completed":
            return base.filter(status__in=[
                Quote.STATUS_APPROVED,
                Quote.STATUS_DECLINED,
                Quote.STATUS_DELETED,
            ])
        return base.filter(status=Quote.STATUS_PENDING)

    def get_context_data(self, **kwargs):
        ctx  = super().get_context_data(**kwargs)
        user = self.request.user
        tab  = self.request.GET.get("tab", "pending")
        ctx["tab"] = tab

        for quote in ctx["quotes"]:
            # Re‐compute price_per_item
            for item in quote.items.all():
                cp = item.calculated_price or Decimal("0.00")
                qty = item.quantity or Decimal("0.00")
                item.price_per_item = (cp / qty) if qty != 0 else Decimal("0.00")

            # Pull membership & init limit
            membership = DepartmentMembership.objects.filter(
                user=user,
                department=quote.lead.department
            ).first()
            limit = None

            # 1) Under-minimum rule: ONLY L1 may approve if selling < minimum
            if quote.selling_price < quote.minimum_price:
                allowed = bool(membership and membership.level == 1)

            # 2) Otherwise, normal ApprovalLimit logic
            elif membership:
                try:
                    limit = ApprovalLimit.objects.get(
                        department=quote.lead.department,
                        level=membership.level
                    )
                except ApprovalLimit.DoesNotExist:
                    limit = None

                allowed = bool(
                    limit and
                    quote.selling_price <= Decimal(limit.max_amount)
                )

            # 3) Everyone else cannot approve
            else:
                allowed = False

            # Attach flags for template
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
def download_department_draft_pdf(request, quote_pk):
    # 1) Load & validate
    quote    = get_object_or_404(Quote, pk=quote_pk, status=Quote.STATUS_APPROVED)
    lead     = quote.lead
    customer = lead.customer
    draft    = lead.department.draft_quotation
    if not draft:
        raise Http404("No draft uploaded.")

    # 2) Prepare all of your simple replacements
    raw = {
        "Quote_Number": f"AMKSLR-{quote.pk:03d}",
        "Quote_Date":   quote.approved_at.strftime("%d-%B-%Y") if quote.approved_at else "Null",
        "Customer_Name": " ".join(filter(None, [
            getattr(customer.designation, "title", None),
            customer.first_name,
            customer.last_name
        ])) or "Null",
        "Cust_Address": " ".join(filter(None, [
            customer.address,
            getattr(customer.city, "name", None)
        ])) or "Null",
        "Product_Name": f"{lead.system_size} kW • {lead.get_grid_type_display()} • "
                        f"{lead.get_system_type_display()} • {customer.city.name}",
        "Cust_Price":   f"₹{quote.selling_price:,}",
    }
    replacements = { f"{{{{{k}}}}}": v for k, v in raw.items() }

    # 3) Work in a tempdir
    with tempfile.TemporaryDirectory() as td:
        base, _ = os.path.splitext(os.path.basename(draft.path))
        doc = Document(draft.path)

        # helper to sweep any run text
        def replace_in_runs(runs):
            for run in runs:
                t = run.text
                for ph, val in replacements.items():
                    if ph in t:
                        run.text = t.replace(ph, val)

        # 4) global walk for your normal placeholders
        for p in doc.paragraphs:
            replace_in_runs(p.runs)
        for tbl in doc.tables:
            for row in tbl.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        replace_in_runs(p.runs)

        # 5) insert horizontal line after Product_Name match
        for p in doc.paragraphs:
            if raw["Product_Name"] in p.text:
                br = doc.add_paragraph()
                ppr = br._p.get_or_add_pPr()
                pbdr = ppr.get_or_add_pbdr()

                # make it a single line
                pbdr.set(qn('w:val'), 'single')
                # thickness: '4' = 4 eighths of a point = 0.5pt (you can bump this up)
                pbdr.set(qn('w:sz'), '4')
                # color black
                pbdr.set(qn('w:color'), '000000')

                # insert it *before* the last paragraph we just created,
                # so that it appears immediately after the Product_Name one
                doc.paragraphs[-1]._p.addprevious(br._p)
                break

        # 6) expand your {{items}} token, forcing 8 pt for each item line
        token = "{{items}}"
        items = list(quote.items.select_related("price_rule__item"))
        for container in (
            list(doc.paragraphs),
            *(cell.paragraphs for tbl in doc.tables for row in tbl.rows for cell in row.cells)
        ):
            for p in container:
                # find any run containing our lower-cased token
                for run in list(p.runs):
                    if token in run.text.lower():
                        # remove the token
                        run.text = run.text.lower().replace(token, "")
                        # now append one line per item
                        for qi in items:
                            name = qi.price_rule.item.product_name
                            qty  = int(qi.quantity)
                            unit = qi.price_rule.get_unit_type_display().lower()

                            # product name at 8pt
                            r1 = p.add_run(name)
                            r1.font.size = Pt(8)

                            # “× N” in blue also at 8pt
                            if unit != "per kw":
                                r2 = p.add_run(f" × {qty}")
                                r2.font.color.rgb = RGBColor(0x25, 0x63, 0xEB)
                                r2.font.size = Pt(8)

                            # break line
                            p.add_run().add_break()
                        # done with this paragraph
                        break

        # 7) save & convert
        filled_docx = os.path.join(td, f"{base}_filled.docx")
        doc.save(filled_docx)

        filled_pdf = os.path.join(td, f"{base}_filled.pdf")
        subprocess.run([
            "soffice", "--headless",
            "--convert-to",
            "pdf:writer_pdf_Export:SelectPdfVersion=1;Quality=100",
            filled_docx, "--outdir", td
        ], check=True)

        if not os.path.exists(filled_pdf):
            logger.error("Temp dir contents: %r", os.listdir(td))
            raise Http404("PDF conversion failed.")

        # 8) stream it back
        return FileResponse(
            open(filled_pdf, "rb"),
            content_type="application/pdf",
            as_attachment=True,
            filename=f"{raw['Quote_Number']}.pdf"
        )