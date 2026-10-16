import io
import zipfile

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import URLValidator
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import get_language
from django.utils.translation import gettext as _

from .forms import (
    ProductClarificationAnswerForm,
    ProductClarificationForm,
    ProductIntakeForm,
    ProductUpdateForm,
    TurnstileAuthenticationForm,
)
from .models import (
    ClarificationCategory,
    ClarificationStatus,
    MarketplaceSite,
    Product,
    ProductClarification,
    ProductImage,
    ProductListingLink,
    ProductStatus,
)
from .permissions import is_assistant, is_manager, manager_required
from .services.ai_service import identify_intake_product
from .services.image_service import (
    MAX_IMAGES_PER_PRODUCT,
    process_and_convert_to_webp,
    validate_image_file,
    validate_images_count,
)
from .services.search_service import build_search_query

PAGE_SIZE = 20


class CustomLoginView(LoginView):
    template_name = "registration/login.html"
    authentication_form = TurnstileAuthenticationForm
    redirect_authenticated_user = True

    def get_success_url(self):
        user = self.request.user
        if is_assistant(user) and not is_manager(user):
            return reverse_lazy("inventory:intake")
        return reverse_lazy("inventory:dashboard")



class CustomLogoutView(LogoutView):
    next_page = reverse_lazy("inventory:login")


def root_redirect_view(request):
    """
    Directs visitors based on their login state and role.
    """
    if not request.user.is_authenticated:
        return redirect("inventory:login")
    if is_assistant(request.user) and not is_manager(request.user):
        return redirect("inventory:intake")
    return redirect("inventory:dashboard")


@login_required
def product_intake_view(request):
    """
    Mobile-first rapid product intake for assistants and managers.
    Captures raw notes and up to 10 photos, auto-converting them to WebP.
    """
    if request.method == "POST":
        form = ProductIntakeForm(request.POST)
        files = request.FILES.getlist("images")

        # Validate photos
        has_file_errors = False
        if not files:
            form.add_error(None, _("Please attach at least one photo of the product."))
            has_file_errors = True
        else:
            try:
                validate_images_count(files)
                for f in files:
                    validate_image_file(f)
            except ValidationError as e:
                form.add_error(None, e.message if hasattr(e, "message") else str(e))
                has_file_errors = True

        if form.is_valid() and not has_file_errors:
            try:
                with transaction.atomic():
                    product = form.save(commit=False)
                    product.created_by = request.user
                    product.save()

                    for idx, uploaded_file in enumerate(files):
                        webp_file = process_and_convert_to_webp(uploaded_file)
                        ProductImage.objects.create(
                            product=product,
                            image=webp_file,
                            order=idx,
                        )

                messages.success(
                    request,
                    _("Product #%(id)s cataloged successfully with %(count)d photo%(plural)s!")
                    % {
                        "id": product.id,
                        "count": len(files),
                        "plural": "s" if len(files) > 1 else "",
                    },
                )
                return redirect("inventory:intake")
            except Exception as exc:
                form.add_error(None, _("Error saving product: %(error)s") % {"error": exc})
    else:
        form = ProductIntakeForm()

    recent_products = Product.objects.filter(created_by=request.user).order_by("-created_at")[:5]

    context = {
        "form": form,
        "max_images": MAX_IMAGES_PER_PRODUCT,
        "recent_products": recent_products,
    }
    return render(request, "inventory/intake.html", context)


@login_required
def intake_identify_view(request):
    """
    Asynchronous pre-flight AI identification endpoint for the intake screen.
    Validates uploaded image files, reads image bytes in memory, and passes
    them to Gemini Multimodal Vision API. Returns JSON response.
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "error": _("Method not allowed. Use POST.")}, status=405)

    files = request.FILES.getlist("images")
    if not files:
        return JsonResponse(
            {"success": False, "error": _("Please attach at least one photo to identify the product.")},
            status=400,
        )

    try:
        validate_images_count(files)
        for f in files:
            validate_image_file(f)
    except ValidationError as e:
        return JsonResponse(
            {"success": False, "error": e.message if hasattr(e, "message") else str(e)},
            status=400,
        )

    raw_note = request.POST.get("raw_note", "").strip()
    language = get_language() or "es"

    images_bytes = [f.read() for f in files[:3]]
    result = identify_intake_product(images_bytes=images_bytes, raw_note=raw_note, language=language)

    return JsonResponse(result, status=200)


@login_required
def dashboard_view(request):
    """
    Catalog overview dashboard with status filters, platform filtering,
    multi-field search, and server-side pagination.
    """
    status_filter = request.GET.get("status", "all").strip().lower()
    search_query = request.GET.get("q", "").strip()
    platform_filter = request.GET.get("platform", "").strip().lower()

    # Query only marketplace sites that have at least one active published product
    available_platforms = (
        MarketplaceSite.objects.filter(product_links__is_active=True)
        .annotate(
            published_count=Count(
                "product_links__product",
                filter=Q(product_links__is_active=True),
                distinct=True,
            )
        )
        .filter(published_count__gt=0)
        .order_by("order", "name")
    )

    products = Product.objects.prefetch_related("images", "listing_links__site").all()

    if platform_filter:
        products = products.filter(
            listing_links__site__slug=platform_filter,
            listing_links__is_active=True,
        ).distinct()

    if status_filter == "active":
        products = products.filter(is_sold=False)
    elif status_filter == "sold":
        products = products.filter(is_sold=True)
    elif status_filter == "awaiting_info":
        products = products.filter(
            Q(status=ProductStatus.AWAITING_INFO) | Q(clarifications__status=ClarificationStatus.PENDING, is_sold=False)
        ).distinct()
    elif status_filter == "blocked":
        products = products.filter(status=ProductStatus.BLOCKED)
    elif status_filter == "ready":
        products = products.filter(status=ProductStatus.READY)
    elif status_filter == "draft":
        products = products.filter(status=ProductStatus.DRAFT)

    if search_query:
        products = products.filter(build_search_query(search_query))

    # Calculate status counts (scoped to selected platform if active)
    counts_qs = Product.objects.all()
    if platform_filter:
        counts_qs = counts_qs.filter(
            listing_links__site__slug=platform_filter,
            listing_links__is_active=True,
        ).distinct()

    counts = counts_qs.aggregate(
        total_count=Count("id", distinct=True),
        active_count=Count("id", filter=Q(is_sold=False), distinct=True),
        awaiting_info_count=Count(
            "id",
            filter=Q(status=ProductStatus.AWAITING_INFO) | Q(clarifications__status=ClarificationStatus.PENDING, is_sold=False),
            distinct=True,
        ),
        sold_count=Count("id", filter=Q(status=ProductStatus.SOLD), distinct=True),
        blocked_count=Count("id", filter=Q(status=ProductStatus.BLOCKED), distinct=True),
    )

    paginator = Paginator(products, PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Elided page range for cleaner pagination bar when many pages exist
    elided_page_range = (
        paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1)
        if paginator.num_pages > 1
        else []
    )

    # Clean query string for pagination links preserving status, platform & search filter
    extra_params = request.GET.copy()
    if "page" in extra_params:
        del extra_params["page"]
    query_string = extra_params.urlencode()

    context = {
        "page_obj": page_obj,
        "products": page_obj,
        "paginator": paginator,
        "elided_page_range": elided_page_range,
        "query_string": query_string,
        "status_filter": status_filter,
        "search_query": search_query,
        "platform_filter": platform_filter,
        "available_platforms": available_platforms,
        "total_count": counts["total_count"] or 0,
        "active_count": counts["active_count"] or 0,
        "awaiting_info_count": counts["awaiting_info_count"] or 0,
        "sold_count": counts["sold_count"] or 0,
        "blocked_count": counts["blocked_count"] or 0,
        "can_manage": is_manager(request.user),
    }
    return render(request, "inventory/dashboard.html", context)


@login_required
def product_detail_view(request, pk):
    """
    Product staging detail view: inspect photos, copy listing copy,
    download ZIP, and edit pricing / sold status.
    """
    product = get_object_or_404(
        Product.objects.prefetch_related(
            "images",
            "listing_links__site",
            "clarifications__asked_by",
            "clarifications__answered_by",
        ),
        pk=pk,
    )
    can_manage = is_manager(request.user)

    if request.method == "POST":
        if not can_manage:
            messages.error(request, _("Manager privileges required to edit product details."))
            return redirect("inventory:product_detail", pk=pk)

        form = ProductUpdateForm(request.POST, instance=product)
        if form.is_valid():
            updated_product = form.save(commit=False)
            if updated_product.is_sold:
                if not updated_product.sold_at:
                    updated_product.sold_at = timezone.now()
            else:
                updated_product.sold_at = None
            updated_product.save()
            messages.success(request, _("Product listing updated successfully."))
            return redirect("inventory:product_detail", pk=pk)
    else:
        form = ProductUpdateForm(instance=product)

    active_sites = MarketplaceSite.objects.filter(is_active=True).order_by("order", "name")
    links_by_site = {link.site_id: link for link in product.listing_links.all()}
    site_links_data = [
        {"site": s, "link": links_by_site.get(s.id)}
        for s in active_sites
    ]
    active_site_ids = {s.id for s in active_sites}
    extra_inactive_links = [
        link for link in product.listing_links.all()
        if link.site_id not in active_site_ids
    ]

    pending_clarifications = product.clarifications.filter(status=ClarificationStatus.PENDING)
    resolved_clarifications = product.clarifications.filter(status=ClarificationStatus.RESOLVED)
    has_unapplied_clarifications = resolved_clarifications.exists()

    context = {
        "product": product,
        "form": form,
        "can_manage": can_manage,
        "site_links_data": site_links_data,
        "extra_inactive_links": extra_inactive_links,
        "pending_clarifications": pending_clarifications,
        "resolved_clarifications": resolved_clarifications,
        "has_unapplied_clarifications": has_unapplied_clarifications,
        "clarification_form": ProductClarificationForm(),
        "answer_form": ProductClarificationAnswerForm(),
        "categories": ClarificationCategory.choices,
    }
    return render(request, "inventory/product_detail.html", context)


@login_required
def product_add_clarification_view(request, pk):
    """
    Allows managers to post a structured clarification question attached to a product.
    Immediately updates product status to AWAITING_INFO.
    """
    if not is_manager(request.user):
        messages.error(request, _("Manager privileges required to ask clarifications."))
        return redirect("inventory:product_detail", pk=pk)

    if request.method != "POST":
        return redirect("inventory:product_detail", pk=pk)

    product = get_object_or_404(Product, pk=pk)
    form = ProductClarificationForm(request.POST)
    if form.is_valid():
        clarification = form.save(commit=False)
        clarification.product = product
        clarification.asked_by = request.user
        clarification.status = ClarificationStatus.PENDING
        clarification.save()

        # Transition product status to Awaiting Info
        if product.status != ProductStatus.AWAITING_INFO and product.status != ProductStatus.SOLD:
            product.status = ProductStatus.AWAITING_INFO
            product.save(update_fields=["status"])

        messages.success(request, _("Clarification question sent to assistant."))
    else:
        messages.error(request, _("Please provide a valid question and category."))

    return redirect("inventory:product_detail", pk=pk)


@login_required
def product_answer_clarification_view(request, pk, clarification_pk):
    """
    Allows assistants (or managers) to provide an answer to a pending clarification question.
    When all pending questions on the product are resolved, auto-transitions status to READY.
    """
    if request.method != "POST":
        return redirect("inventory:product_detail", pk=pk)

    product = get_object_or_404(Product, pk=pk)
    clarification = get_object_or_404(ProductClarification, pk=clarification_pk, product=product)

    form = ProductClarificationAnswerForm(request.POST)
    if form.is_valid():
        answer_text = form.cleaned_data["answer"].strip()
        clarification.resolve(answer=answer_text, answered_by=request.user)

        # Check if any pending questions remain
        remaining_pending = product.clarifications.filter(status=ClarificationStatus.PENDING).count()
        if remaining_pending == 0:
            if product.status != ProductStatus.SOLD:
                product.status = ProductStatus.READY
                product.save(update_fields=["status"])
            messages.success(request, _("All doubts resolved! Product marked as ready to publish."))
        else:
            messages.success(request, _("Answer saved. %d doubts still pending.") % remaining_pending)
    else:
        messages.error(request, _("Please provide an answer."))

    return redirect("inventory:product_detail", pk=pk)


@login_required
def product_delete_clarification_view(request, pk, clarification_pk):
    """
    Allows managers to delete/dismiss a clarification question.
    """
    if not is_manager(request.user):
        messages.error(request, _("Manager privileges required to delete clarifications."))
        return redirect("inventory:product_detail", pk=pk)

    if request.method != "POST":
        return redirect("inventory:product_detail", pk=pk)

    product = get_object_or_404(Product, pk=pk)
    clarification = get_object_or_404(ProductClarification, pk=clarification_pk, product=product)
    clarification.delete()

    # If no pending questions left and was awaiting info, revert to ready
    remaining_pending = product.clarifications.filter(status=ClarificationStatus.PENDING).count()
    if remaining_pending == 0 and product.status == ProductStatus.AWAITING_INFO:
        product.status = ProductStatus.READY
        product.save(update_fields=["status"])

    messages.success(request, _("Clarification removed."))
    return redirect("inventory:product_detail", pk=pk)



@login_required
def product_manage_link_view(request, pk):
    """
    Handles adding, updating, and removing marketplace links for a product.
    Restricted to managers.
    """
    if not is_manager(request.user):
        messages.error(request, _("Manager privileges required to manage listing links."))
        return redirect("inventory:product_detail", pk=pk)

    if request.method != "POST":
        return redirect("inventory:product_detail", pk=pk)

    product = get_object_or_404(Product, pk=pk)
    action = request.POST.get("action", "save")
    site_id = request.POST.get("site_id")

    if action == "delete":
        link_id = request.POST.get("link_id")
        if link_id:
            ProductListingLink.objects.filter(pk=link_id, product=product).delete()
            messages.success(request, _("Marketplace link removed successfully."))
        elif site_id:
            ProductListingLink.objects.filter(site_id=site_id, product=product).delete()
            messages.success(request, _("Marketplace link removed successfully."))
        return redirect("inventory:product_detail", pk=pk)

    if not site_id:
        messages.error(request, _("Marketplace site identifier is required."))
        return redirect("inventory:product_detail", pk=pk)

    site = get_object_or_404(MarketplaceSite, pk=site_id)
    raw_url = request.POST.get("url", "").strip()

    if not raw_url:
        ProductListingLink.objects.filter(product=product, site=site).delete()
        messages.success(request, _("Marketplace link cleared."))
        return redirect("inventory:product_detail", pk=pk)

    validator = URLValidator(schemes=["http", "https"])
    try:
        validator(raw_url)
    except ValidationError:
        messages.error(request, _("Please provide a valid URL starting with http:// or https://."))
        return redirect("inventory:product_detail", pk=pk)

    ProductListingLink.objects.update_or_create(
        product=product,
        site=site,
        defaults={"url": raw_url, "is_active": True},
    )
    messages.success(
        request,
        _("Link for %(site)s saved successfully.") % {"site": site.name},
    )
    return redirect("inventory:product_detail", pk=pk)


@login_required
def product_download_zip_view(request, pk):
    """
    Packages all product photos into an in-memory ZIP archive and streams it for download.
    """
    product = get_object_or_404(Product.objects.prefetch_related("images"), pk=pk)
    images = product.images.all()

    if not images.exists():
        messages.warning(request, _("This product has no photos to download."))
        return redirect("inventory:product_detail", pk=pk)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for idx, img_obj in enumerate(images, start=1):
            try:
                with img_obj.image.open("rb") as f:
                    file_content = f.read()
                    archive_filename = f"product_{product.id}_img_{idx}.webp"
                    zip_file.writestr(archive_filename, file_content)
            except Exception:
                # Log or skip missing file
                continue

    zip_buffer.seek(0)
    response = HttpResponse(zip_buffer.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="product_{product.id}_photos.zip"'
    response["X-Content-Type-Options"] = "nosniff"
    return response


@manager_required
def generate_ai_view(request, pk):
    """
    Triggers Gemini AI listing generation for a product, updating ai_title and ai_description
    while strictly preserving the assistant's original raw_note.
    Passes the active session language to ensure localized copy.
    """
    if request.method != "POST":
        return redirect("inventory:product_detail", pk=pk)

    product = get_object_or_404(Product.objects.prefetch_related("images"), pk=pk)

    try:
        from .services.ai_service import AIServiceError, generate_product_listing

        active_language = get_language() or "en"
        listing_data = generate_product_listing(product, language=active_language)

        product.ai_title = (listing_data.get("title") or "").strip()[:255]
        product.ai_description = (listing_data.get("description") or "").strip()
        product.save(update_fields=["ai_title", "ai_description", "updated_at"])

        messages.success(request, _("AI listing successfully generated from photos and notes!"))
    except AIServiceError as e:
        messages.error(request, str(e))
    except Exception as exc:
        messages.error(request, _("Unexpected error during AI generation: %(error)s") % {"error": exc})

    return redirect("inventory:product_detail", pk=pk)
