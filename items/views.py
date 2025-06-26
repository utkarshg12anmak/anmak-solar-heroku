# items/views.py

from django.views.generic import ListView, View
from django.urls import reverse_lazy
from django.db.models import Q  
from .models import Item, Brand, UOM, CategoryLevel1, CategoryLevel2, UPC
from django.shortcuts import get_object_or_404, redirect, render
from django.core.exceptions import ValidationError
from .models import Item, UPC

from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from .models import PriceTier, PriceRule
from .forms import PriceTierForm, PriceRuleForm
from .models import PriceRule


from .forms import PriceRuleForm  # assume you’ll create a ModelForm for PriceRule
from django.http import JsonResponse

import json

from django.views.decorators.http import require_POST   # ← add this
from django.contrib.auth.decorators import login_required  # ← and this

from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from profiles.models import DepartmentMembership


class ItemListView(ListView):
    model = Item
    template_name = "items/items_list.html"
    context_object_name = "items"
    paginate_by = 25

    def dispatch(self, request, *args, **kwargs):
        # lookup ANY level membership in the right DeptType→Category
        membership = (
            DepartmentMembership.objects
            .filter(
                user=request.user,
                department__dept_type__name="Inventory & Pricing",
                department__category__name="Inventory"
            )
            .first()
        )
        if not membership:
            raise PermissionDenied()

        self.membership = membership
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["total_count"] = Item.objects.count()
        ctx["brands"] = Brand.objects.order_by("name")
        ctx["uoms"] = UOM.objects.order_by("unit_name")
        ctx["l1_categories"] = CategoryLevel1.objects.order_by("name")
        ctx["l2_categories"] = CategoryLevel2.objects.select_related("parent").order_by("parent__name", "name")

        ctx["search_query"] = self.request.GET.get("q", "")

        
        # only L1/L2 can edit or create
        ctx["can_edit"] = self.membership.level in (1, 2)

        return ctx


    def get_queryset(self):
        qs = super().get_queryset().select_related("brand", "l1_category", "l2_category", "uom", "created_by")
        q = self.request.GET.get("q", "").strip()
        if q:
            from django.db.models import Q
            qs = qs.filter(
                Q(sku__icontains=q) |
                Q(product_name__icontains=q) |
                Q(brand__name__icontains=q) |
                Q(l1_category__name__icontains=q) |
                Q(l2_category__name__icontains=q)
            )
        return qs

class ManageBrandsView(View):
    """
    Handle the POST from the “Add/Edit Brands” modal:
      - For each existing brand, look for a POST field named 'brand_<id>'.
      - Update its name if changed.
      - If 'new_brand' is nonempty, create a new Brand with that name.
      - Redirect back to the Items list.
    """
    def post(self, request, *args, **kwargs):
        # 1) Update existing brands
        for key, value in request.POST.items():
            if key.startswith("brand_"):
                try:
                    brand_id = int(key.split("_", 1)[1])
                except (IndexError, ValueError):
                    continue
                new_name = value.strip()
                if not new_name:
                    # Skip if user cleared out the field entirely
                    continue
                try:
                    brand = Brand.objects.get(pk=brand_id)
                except Brand.DoesNotExist:
                    continue
                if brand.name != new_name:
                    brand.name = new_name
                    brand.save()

        # 2) Create a new brand if provided
        new_name = request.POST.get("new_brand", "").strip()
        if new_name:
            Brand.objects.get_or_create(name=new_name)

        # 3) Redirect back to the Items page
        return redirect(reverse_lazy("items:list"))

class ManageUOMsView(View):
    """
    Handle POST from the UOMs modal:
      - Update any existing UOM whose 'uom_<id>' field changed.
      - If 'new_uom' is nonempty, create it (if not existing).
      - Redirect back to items:list.
    """
    def post(self, request, *args, **kwargs):
        # 1) Update existing UOMs
        for key, value in request.POST.items():
            if key.startswith("uom_"):
                try:
                    uom_id = int(key.split("_", 1)[1])
                except (IndexError, ValueError):
                    continue
                new_name = value.strip()
                if not new_name:
                    continue
                try:
                    uom = UOM.objects.get(pk=uom_id)
                except UOM.DoesNotExist:
                    continue
                if uom.unit_name != new_name:
                    uom.unit_name = new_name
                    uom.save()

        # 2) Create a new UOM if provided
        new_name = request.POST.get("new_uom", "").strip()
        if new_name:
            UOM.objects.get_or_create(unit_name=new_name)

        return redirect(reverse_lazy("items:list"))


class ManageL1CategoriesView(View):
    """
    Handle POST from the “Add/Edit L1 Categories” modal:
      - Update any existing CategoryLevel1 whose 'category_<id>' field changed.
      - If 'new_category' is nonempty, create a new CategoryLevel1 (if not existing).
      - Redirect back to items:list.
    """
    def post(self, request, *args, **kwargs):
        # 1) Update existing categories
        for key, value in request.POST.items():
            if key.startswith("category_"):
                try:
                    cat_id = int(key.split("_", 1)[1])
                except (IndexError, ValueError):
                    continue
                new_name = value.strip()
                if not new_name:
                    continue
                try:
                    cat = CategoryLevel1.objects.get(pk=cat_id)
                except CategoryLevel1.DoesNotExist:
                    continue
                if cat.name != new_name:
                    cat.name = new_name
                    cat.save()

        # 2) Create a new category if provided
        new_name = request.POST.get("new_category", "").strip()
        if new_name:
            CategoryLevel1.objects.get_or_create(name=new_name)

        return redirect(reverse_lazy("items:list"))

class ManageL2CategoriesView(View):
    """
    Handle POST from the “Add/Edit L2 Categories” modal:
      - For every existing L2, look for fields 'l2_<id>_name' and 'l2_<id>_parent'
        → update name and/or parent if changed.
      - If 'new_l2_name' and 'new_l2_parent' are nonempty, create a new CategoryLevel2.
      - Redirect back to items:list.
    """
    def post(self, request, *args, **kwargs):
        # 1) Update existing L2 categories
        for key, val in request.POST.items():
            if key.startswith("l2_") and key.endswith("_name"):
                # key format: "l2_<id>_name"
                try:
                    cat_id = int(key.split("_", 2)[1])
                except (IndexError, ValueError):
                    continue

                new_name = val.strip()
                # corresponding parent field is "l2_<id>_parent"
                parent_key = f"l2_{cat_id}_parent"
                parent_val = request.POST.get(parent_key, "").strip()
                if not new_name or not parent_val:
                    # either name or parent blank → skip
                    continue

                try:
                    cat = CategoryLevel2.objects.get(pk=cat_id)
                    new_parent = CategoryLevel1.objects.get(pk=int(parent_val))
                except (CategoryLevel2.DoesNotExist, CategoryLevel1.DoesNotExist, ValueError):
                    continue

                # If either the name or the parent changed, update:
                if cat.name != new_name or cat.parent_id != new_parent.id:
                    cat.name = new_name
                    cat.parent = new_parent
                    cat.save()

        # 2) Create a new L2 if provided
        new_name = request.POST.get("new_l2_name", "").strip()
        new_parent_id = request.POST.get("new_l2_parent", "").strip()
        if new_name and new_parent_id:
            try:
                parent = CategoryLevel1.objects.get(pk=int(new_parent_id))
                CategoryLevel2.objects.get_or_create(parent=parent, name=new_name)
            except (CategoryLevel1.DoesNotExist, ValueError):
                pass

        return redirect(reverse_lazy("items:list"))

class UpdateItemView(View):
    template_name = "items/items_list.html"

    def get_context_data(self, request, error_message=None, edit_item=None):
        """
        Returns context needed to render the items_list.html page (including all modals).
        If edit_item is provided, we’ll use its data to pre-populate the Edit modal.
        If error_message is provided, we'll pass it into context so the template shows it.
        """
        ctx = {}
        # --- 1) Main “Items” table ---
        ctx["items"] = Item.objects.all().select_related(
            "l1_category", "l2_category", "brand", "uom"
        )

        # --- 2) Lookup lists for all four modals ---
        ctx["brands"]        = Brand.objects.order_by("name")
        ctx["uoms"]          = UOM.objects.order_by("unit_name")
        ctx["l1_categories"] = CategoryLevel1.objects.order_by("name")
        ctx["l2_categories"] = CategoryLevel2.objects.order_by("name")

        # --- 3) Total count ---
        ctx["total_count"] = ctx["items"].count()

        # --- 4) If we are re-displaying an Edit error, pass the item & error ---
        ctx["edit_item"]    = edit_item
        ctx["upc_error"]    = error_message

        return ctx

    def post(self, request, pk, *args, **kwargs):
        item = get_object_or_404(Item, pk=pk)

        # 1) Update the item’s core fields
        item.product_name   = request.POST.get("edit_name", item.product_name).strip()
        item.brand_id       = int(request.POST.get("edit_brand", item.brand_id))
        item.l1_category_id = int(request.POST.get("edit_l1", item.l1_category_id))
        item.l2_category_id = int(request.POST.get("edit_l2", item.l2_category_id))
        item.uom_id         = int(request.POST.get("edit_uom", item.uom_id))
        item.updated_by     = request.user
        item.save()

        try:
            # 2) Delete any UPCs that were removed from the form
            existing_upc_ids = set(item.upcs.values_list("id", flat=True))
            posted_upc_ids   = {
                int(key.split("_", 1)[1])
                for key in request.POST
                if key.startswith("upc_") and key.split("_", 1)[1].isdigit()
            }
            to_delete_ids = existing_upc_ids - posted_upc_ids
            if to_delete_ids:
                UPC.objects.filter(id__in=to_delete_ids).delete()

            # 3) Update remaining UPCs or delete if blank
            for key, val in request.POST.items():
                if not key.startswith("upc_"):
                    continue
                try:
                    upc_id = int(key.split("_", 1)[1])
                except (IndexError, ValueError):
                    continue

                code = val.strip()
                if code == "":
                    # Field was blanked out; delete this UPC if it still exists
                    UPC.objects.filter(pk=upc_id).delete()
                    continue

                # Check uniqueness (excluding itself)
                if UPC.objects.filter(code=code).exclude(pk=upc_id).exists():
                    raise ValidationError(f"Cannot use '{code}' because that UPC already exists.")

                upc_obj = UPC.objects.get(pk=upc_id)
                if upc_obj.code != code:
                    upc_obj.code = code
                    upc_obj.save()

            # 4) Create any brand-new UPCs from “new_upc_<n>”
            for key, val in request.POST.items():
                if not key.startswith("new_upc_"):
                    continue
                code = val.strip()
                if code == "":
                    continue
                # New code must be globally unique
                if UPC.objects.filter(code=code).exists():
                    raise ValidationError(f"Cannot add '{code}' because that UPC already exists.")
                UPC.objects.create(item=item, code=code)

            # 5) All succeeded; redirect back to the list
            return redirect(reverse_lazy("items:list"))

        except ValidationError as e:
            # If any UPC collision or other validation error happened:
            # Re-render the same items_list.html, passing the error and the item to edit.
            # We also need to tell the template to “open” the Edit modal for this item.

            # 6) Rebuild context with the error message and the item we tried to edit
            ctx = self.get_context_data(
                request,
                error_message=e.messages[0],  # single‐string assumption
                edit_item=item
            )
            return render(request, self.template_name, ctx)

class CreateItemView(View):
    """
    Handles the POST from “Add Item” modal.
    Expects:
      - add_name   (product_name)
      - add_brand  (brand ID)
      - add_l1     (hidden L1 ID)
      - add_l2     (L2 ID)
      - add_uom    (UOM ID)
    Sets created_by = request.user, then save(). Redirect to items:list.
    """
    def post(self, request, *args, **kwargs):
        # 1) Required fields from POST
        name     = request.POST.get("add_name", "").strip()
        brand_id = request.POST.get("add_brand")
        l1_id    = request.POST.get("add_l1")
        l2_id    = request.POST.get("add_l2")
        uom_id   = request.POST.get("add_uom")

        # 2) Basic validation (ensure they exist and are non-empty)
        if not (name and brand_id and l1_id and l2_id and uom_id):
            # If anything missing, you could add an error message or just redirect back.
            return redirect(reverse_lazy("items:list"))

        # 3) Create the new Item
        try:
            brand_obj = Brand.objects.get(pk=int(brand_id))
            l1_obj    = CategoryLevel1.objects.get(pk=int(l1_id))
            l2_obj    = CategoryLevel2.objects.get(pk=int(l2_id))
            uom_obj   = UOM.objects.get(pk=int(uom_id))
        except (Brand.DoesNotExist, CategoryLevel1.DoesNotExist,
                CategoryLevel2.DoesNotExist, UOM.DoesNotExist, ValueError):
            return redirect(reverse_lazy("items:list"))

        new_item = Item(
            product_name = name,
            brand        = brand_obj,
            l1_category  = l1_obj,
            l2_category  = l2_obj,
            uom          = uom_obj,
            created_by   = request.user,   # stamp creator
            updated_by   = request.user,   # also initialize updated_by
        )
        new_item.save()  # SKU is auto-generated in Item.save()

                # -----------------------
        # Now handle new UPCs
        for key, val in request.POST.items():
            if not key.startswith("new_upc_"):
                continue
            code = val.strip()
            if code == "":
                continue
            # Check global uniqueness first:
            if UPC.objects.filter(code=code).exists():
                # Option A: delete the just‐created item and raise
                new_item.delete()
                raise ValidationError(f"Cannot add UPC '{code}' because it already exists.")
            UPC.objects.create(item=new_item, code=code)

        # 4) Redirect back to the items list
        return redirect(reverse_lazy("items:list"))

def price_settings_dashboard(request):
    """
    Renders a page with two sections side-by-side (or stacked on mobile):
      • Left: all PriceTiers
      • Right: all PriceRules
    Each section has an “Add” button that links to the appropriate CreateView.
    """
    tiers = PriceTier.objects.select_related("price_rule").order_by("price_rule__item__product_name", "min_quantity")
    rules = PriceRule.objects.select_related("price_book", "item").order_by("item__product_name")
    return render(request, "items/price_settings.html", {
        "tiers": tiers,
        "rules": rules,
    })


class PriceRuleListView(ListView):
    """
    Displays "All Price Rules" (the table).
    """
    model = PriceRule
    template_name = "items/price_rules.html"
    context_object_name = "rules"
    paginate_by = 25

    def get_queryset(self):
        qs = super().get_queryset().select_related("item", "price_book")
        q = self.request.GET.get("q", "").strip()
        if q:
            from django.db.models import Q
            qs = qs.filter(
                Q(item__sku__icontains=q) |
                Q(item__product_name__icontains=q) |
                Q(price_book__name__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # total_count if you like:
        ctx["total_count"] = self.get_queryset().count()
        # echo back our search string
        ctx["search_query"] = self.request.GET.get("q", "")
        return ctx


class PriceRuleCreateView(CreateView):
    """
    Shows a modal/form to create a new PriceRule.
    """
    model = PriceRule
    form_class = PriceRuleForm
    template_name = "items/price_rule_form.html"  # create this template
    success_url = reverse_lazy("items:price_rules_list")

    def form_valid(self, form):
        # auto‐stamp created_by/updated_by if you want:
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        return super().form_valid(form)


class PriceRuleUpdateView(UpdateView):
    """
    Shows a modal/form to edit an existing PriceRule.
    """
    model = PriceRule
    form_class = PriceRuleForm
    template_name = "items/price_rule_form.html"  # reuse same form template
    success_url = reverse_lazy("items:price_rules_list")

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        return super().form_valid(form)


class PriceRuleDeleteView(DeleteView):
    """
    Simple confirmation at /delete/; after deleting, redirect back to list.
    """
    model = PriceRule
    template_name = "items/price_rule_confirm_delete.html"  # create this
    success_url = reverse_lazy("items:price_rules_list")

def price_rules_list(request):
    """
    Display a list of all PriceRule objects.
    """
    rules = PriceRule.objects.select_related("item", "price_book").all()
    return render(request, "items/price_rules.html", {"rules": rules})

class PriceTierCreateView(View):
    """
    Show a blank form to create a new PriceTier (under a given PriceRule),
    then save it on POST.
    """
    def get(self, request, *args, **kwargs):
        # You probably want to pass a list of PriceRules for the user to choose from,
        # or perhaps the URL includes a price_rule_id. For now, we’ll just render
        # an empty form.
        form = PriceTierForm()
        return render(request, "items/price_tier_form.html", {"form": form})

    def post(self, request, *args, **kwargs):
        form = PriceTierForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect(reverse_lazy("items:price_rules_list"))
        return render(request, "items/price_tier_form.html", {"form": form})

# ---------------------------------------------------
# 1) A ListView that shows ALL PriceRules (and possibly links to their tiers)
# ---------------------------------------------------
class PriceRuleListView(ListView):
    model = PriceRule
    template_name = "items/price_rules.html"
    context_object_name = "rules"
    paginate_by = 25

    def get_queryset(self):
        qs = super().get_queryset().select_related("item", "price_book")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(item__sku__icontains=q) |
                Q(item__product_name__icontains=q) |
                Q(price_book__name__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["search_query"] = self.request.GET.get("q", "")
        ctx["total_count"]  = self.get_queryset().count()
        return ctx

    def dispatch(self, request, *args, **kwargs):
        ok = DepartmentMembership.objects.filter(
            user=request.user,
            department__dept_type__name="Inventory & Pricing",
            department__category__name="Pricing"
        ).exists()
        if not ok:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


# ---------------------------------------------------
# 2) A CreateView for PriceRule
# ---------------------------------------------------
class PriceRuleCreateView(CreateView):
    model = PriceRule
    form_class = PriceRuleForm
    template_name = "items/price_rule_form.html"
    success_url = reverse_lazy("items:price_rules_list")

    def form_valid(self, form):
        # Stamp created_by/updated_by if you have those fields
        obj = form.save(commit=False)
        obj.created_by = self.request.user
        obj.updated_by = self.request.user
        obj.save()
        return super().form_valid(form)


# ---------------------------------------------------
# 3) An UpdateView for PriceRule
# ---------------------------------------------------
class PriceRuleUpdateView(UpdateView):
    model = PriceRule
    form_class = PriceRuleForm
    template_name = "items/price_rule_form.html"
    success_url = reverse_lazy("items:price_rules_list")

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.updated_by = self.request.user
        obj.save()
        return super().form_valid(form)


# ---------------------------------------------------
# 4) A DeleteView for PriceRule (optional)
# ---------------------------------------------------
class PriceRuleDeleteView(DeleteView):
    model = PriceRule
    template_name = "items/price_rule_confirm_delete.html"
    success_url = reverse_lazy("items:price_rules_list")


# ---------------------------------------------------
# 5) A CreateView for PriceTier
# ---------------------------------------------------
class PriceTierCreateView(CreateView):
    model = PriceTier
    form_class = PriceTierForm
    template_name = "items/price_tier_form.html"
    # After creating a tier, we might redirect back to the rule’s detail or the rule list.
    # For simplicity, redirect to the price‐rule list:
    success_url = reverse_lazy("items:price_rules_list")

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.save()
        return super().form_valid(form)


# ---------------------------------------------------
# 6) An UpdateView for PriceTier
# ---------------------------------------------------
class PriceTierUpdateView(UpdateView):
    model = PriceTier
    form_class = PriceTierForm
    template_name = "items/price_tier_form.html"
    success_url = reverse_lazy("items:price_rules_list")

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.save()
        return super().form_valid(form)


# ---------------------------------------------------
# 7) A DeleteView for PriceTier (optional)
# ---------------------------------------------------
class PriceTierDeleteView(DeleteView):
    model = PriceTier
    template_name = "items/price_tier_confirm_delete.html"
    success_url = reverse_lazy("items:price_rules_list")

def price_rule_edit(request, pk=None):
    if pk:
        rule = get_object_or_404(PriceRule, pk=pk)
    else:
        rule = PriceRule()

    if request.method == "POST":
        form = PriceRuleForm(request.POST, instance=rule)
        if form.is_valid():
            pr = form.save(commit=False)
            if not pk:
                pr.created_by = request.user
            pr.updated_by = request.user
            pr.save()
            return redirect(reverse_lazy("items:price_rules_list"))
    else:
        form = PriceRuleForm(instance=rule)

    return render(request, "items/price_rule_form.html", {"form": form})

class PriceTierManageView(View):
    """
    AJAX endpoint to list + add tiers for one PriceRule.
    URL: /items/price-settings/rules/<rule_pk>/tiers/
    """
    def get(self, request, rule_pk, *args, **kwargs):
        price_rule = get_object_or_404(PriceRule, pk=rule_pk)
        tiers      = price_rule.tiers.order_by("min_quantity")
        form       = PriceTierForm(initial={"price_rule": price_rule})
        return render(request, "items/price_tier_manage.html", {
            "price_rule": price_rule,
            "tiers": tiers,
            "form": form,
        })

    def post(self, request, rule_pk, *args, **kwargs):
        price_rule = get_object_or_404(PriceRule, pk=rule_pk)
        form       = PriceTierForm(request.POST)
        if form.is_valid():
            tier = form.save(commit=False)
            tier.price_rule = price_rule
            tier.save()
            return JsonResponse({"success": True})
        # on error re-render the same fragment with form errors
        tiers = price_rule.tiers.order_by("min_quantity")
        return render(request, "items/price_tier_manage.html", {
            "price_rule": price_rule,
            "tiers": tiers,
            "form": form,
        })

class PriceTierDeleteView(DeleteView):
    model = PriceTier
    template_name = "items/price_tier_confirm_delete.html"
    success_url   = reverse_lazy("items:price_rules_list")

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()

        # If this was an AJAX delete, return JSON
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": True})

        return redirect(self.success_url)

@require_POST
@login_required
def toggle_price_rule_availability(request, pk):
    payload = json.loads(request.body.decode('utf-8'))
    rule = get_object_or_404(PriceRule, pk=pk)
    rule.available = bool(payload.get('available'))
    rule.save(update_fields=['available'])
    return JsonResponse({'success': True, 'available': rule.available})