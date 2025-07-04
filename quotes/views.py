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
from .utils  import html_to_pdf


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
        # 1) which tab?
        tab = self.request.GET.get("tab", "pending")

        # 2) build your “base” Quote qs with all the joins
        #    – select_related for every FK you touch in template
        #    – prefetch_related for the items → price_rule → item chain
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
                         "items",  # `related_name` on QuoteItem
                         queryset=(
                             QuoteItem.objects
                                      .select_related("price_rule__item")
                         )
                     )
                 )
                 .order_by("-updated_at")
        )

        # 3) filter to only the leads this user may access
        allowed_lead_ids = list(self.get_allowed_leads().values_list("pk", flat=True))
        qs = base_qs.filter(lead_id__in=allowed_lead_ids)

        # 4) finally, status‐branch by “pending” vs “completed”
        if tab == "completed":
            return qs.filter(status__in=[
                Quote.STATUS_APPROVED,
                Quote.STATUS_DECLINED,
                Quote.STATUS_DELETED,
            ])
        return qs.filter(status=Quote.STATUS_PENDING)


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

            # 1) under-minimum → only L1 may
            if quote.selling_price < quote.minimum_price:
                allowed = (lvl == "1")
            else:
                # 2) otherwise check your session-cached limit
                max_amt = limits.get(dept_id, {}).get(lvl)
                if max_amt is not None:
                    allowed = (quote.selling_price <= Decimal(max_amt))

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

@login_required
def download_full_quote(request, quote_pk):
    # 1) Load & validate
    quote = get_object_or_404(Quote, pk=quote_pk, status=Quote.STATUS_APPROVED)

    # 2) Render your HTML template to a string
    html = render_to_string(
        "quotes/quotation_pdf_base.html",
        {"quote": quote},
        request=request
    )
    # 3) Turn that HTML into PDF bytes
    body_pdf = html_to_pdf(html)

    # 4) Grab the pre/post PDFs from the template config
    qt = quote.lead.department.quote_template
    if not qt or not qt.pre_pdf or not qt.post_pdf:
        raise Http404("Pre/Post PDFs not set up for this department.")
    pre_bytes  = qt.pre_pdf.read()
    post_bytes = qt.post_pdf.read()

    # 5) Merge them all
    writer = PdfWriter()
    for blob in (pre_bytes, body_pdf, post_bytes):
        reader = PdfReader(BytesIO(blob))
        for page in reader.pages:
            writer.add_page(page)

    # 6) Stream it back
    output = BytesIO()
    writer.write(output)
    output.seek(0)
    filename = f"AMKSLR-{quote.pk:03d}.pdf"
    return FileResponse(output, as_attachment=True, filename=filename)