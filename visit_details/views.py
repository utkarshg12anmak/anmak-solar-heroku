# visit_details/views.py

from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from .models import VisitDetail

from django.http import HttpResponseRedirect


from .forms import VisitDetailForm, VisitImageForm
from .models import VisitDetail, VisitImage     # ← you only had VisitDetail

import logging

from django.shortcuts import get_object_or_404
from django.http import FileResponse
from django.views.decorators.clickjacking import xframe_options_sameorigin

from .models import VisitDetail


class VisitListView(ListView):
    model = VisitDetail
    template_name = "visit_details/visit_list.html"
    context_object_name = "visits"
    paginate_by = 20

    def get_queryset(self):
        return VisitDetail.objects.filter(lead_id=self.kwargs["lead_pk"]).order_by("-visit_date")

    def get_context_data(self, **ctx):
        ctx = super().get_context_data(**ctx)
        ctx["lead_pk"] = self.kwargs["lead_pk"]
        return ctx


class VisitCreateView(CreateView):
    model         = VisitDetail
    form_class    = VisitDetailForm
    template_name = "visit_details/visit_form.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["lead_pk"]    = self.kwargs["lead_pk"]
        ctx["image_form"] = VisitImageForm()
        return ctx

    def form_valid(self, form):
        files = self.request.FILES.getlist("images")

        # 1) Too many files?
        if len(files) > 10:
            form.add_error("images", "You can upload at most 10 images.")
            return self.form_invalid(form)

        # 2) Validate extensions as before
        ALLOWED = {"jpg", "jpeg", "png"}
        for f in files:
            ext = f.name.rsplit(".", 1)[-1].lower()
            if ext not in ALLOWED:
                form.add_error("images", f"“{f.name}” isn’t a supported image.")
                return self.form_invalid(form)

        # 3) **New**: total size ≤ 100 MB
        total_bytes = sum(f.size for f in files)
        max_total = 100 * 1024 * 1024
        if total_bytes > max_total:
            form.add_error(
                "images",
                "Total size of all images must not exceed 100 MB."
            )
            return self.form_invalid(form)

        # — if we get here, everything’s good —
        visit = form.save(commit=False)
        visit.lead_id    = self.kwargs["lead_pk"]
        visit.created_by = self.request.user
        visit.updated_by = self.request.user
        visit.save()

        for f in files:
            img = VisitImage.objects.create(image=f)
            visit.images.add(img)

        return HttpResponseRedirect(
            reverse_lazy("leads:edit", args=[self.kwargs["lead_pk"]])
        )


class VisitUpdateView(UpdateView):
    model = VisitDetail
    form_class = VisitDetailForm
    template_name = "visit_details/visit_form.html"

    def get_context_data(self, **ctx):
        ctx = super().get_context_data(**ctx)
        # you still need lead_pk so your {% url %} tag works
        ctx["lead_pk"] = self.object.lead_id
        return ctx

    def form_valid(self, form):
        form.instance.updated_by = self.request.user

        # super().form_valid will save the VisitDetail
        response = super().form_valid(form)

        # if user attached new files, add them
        for f in self.request.FILES.getlist("images"):
            img = VisitImage.objects.create(image=f)
            self.object.images.add(img)

        return response

    def get_success_url(self):
    	
        # back to the lead-edit
        return reverse_lazy("leads:edit", args=[self.object.lead_id])


class VisitDeleteView(DeleteView):
    model = VisitDetail

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()

        # AJAX?
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": True})

        # fallback for normal browsers
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        # you probably want to go back to your lead page:
        return reverse_lazy("leads:edit", args=[ self.object.lead_id ])


@xframe_options_sameorigin
def inspection_report_preview(request, pk):
    """
    Stream the PDF with SAMEORIGIN so it can be embedded in an <iframe>.
    """
    visit = get_object_or_404(VisitDetail, pk=pk)
    # FileResponse will set Content-Type to application/pdf
    return FileResponse(
        visit.inspection_report.open("rb"),
        content_type="application/pdf"
    )