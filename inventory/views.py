import io
import json
import zipfile

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import URLValidator
from django.db import transaction
from django.db.models import Count, Max, Prefetch, Q
from django.http import HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .forms import (
    ProductClarificationAnswerForm,
    ProductClarificationForm,
    ProductDirectClarificationForm,
    ProductIntakeForm,
    ProductUpdateForm,
    TurnstileAuthenticationForm,
)
from .models import (
    Category,
    ClarificationCategory,
    ClarificationStatus,
    MarketplaceSite,
    Product,
    ProductClarification,
    ProductCondition,
    ProductImage,
    ProductListingLink,
    ProductStatus,
    ProductStatusLog,
    PushSubscription,
    SaleChannelType,
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
    channel_filter = request.GET.get("channel", "").strip().lower()
    sync_filter = request.GET.get("sync", "").strip().lower()

    # Query only marketplace sites that have at least one active published product
    available_platforms = (
        MarketplaceSite.objects.filter(product_links__is_active=True, product_links__product__is_deleted=False)
        .annotate(
            published_count=Count(
                "product_links__product",
                filter=Q(product_links__is_active=True, product_links__product__is_deleted=False),
                distinct=True,
            )
        )
        .filter(published_count__gt=0)
        .order_by("order", "name")
    )

    products = Product.objects.select_related("category", "sold_marketplace").prefetch_related("images", "listing_links__site").all()

    if platform_filter:
        products = products.filter(
            listing_links__site__slug=platform_filter,
            listing_links__is_active=True,
        ).distinct()

    if status_filter == "erased":
        products = products.filter(is_deleted=True)
    else:
        products = products.filter(is_deleted=False)
        if status_filter == "active":
            products = products.filter(is_sold=False)
        elif status_filter == "sold":
            products = products.filter(is_sold=True)
            if channel_filter == "in_store":
                products = products.filter(sold_channel_type=SaleChannelType.IN_STORE)
            elif channel_filter == "marketplace":
                products = products.filter(sold_channel_type=SaleChannelType.MARKETPLACE)
                if platform_filter:
                    products = products.filter(sold_marketplace__slug=platform_filter)
            elif channel_filter == "other":
                products = products.filter(sold_channel_type=SaleChannelType.OTHER)
        elif status_filter == "awaiting_info":
            products = products.filter(
                Q(status=ProductStatus.AWAITING_INFO) | Q(clarifications__status=ClarificationStatus.PENDING, is_sold=False)
            ).distinct()
        elif status_filter == "price_pending":
            products = products.filter(status=ProductStatus.PRICE_PENDING)
        elif status_filter == "published":
            products = products.filter(status=ProductStatus.PUBLISHED)
            if sync_filter == "out_of_sync":
                products = products.filter(needs_platform_sync=True)
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
        total_count=Count("id", filter=Q(is_deleted=False), distinct=True),
        active_count=Count("id", filter=Q(is_sold=False, is_deleted=False), distinct=True),
        price_pending_count=Count("id", filter=Q(status=ProductStatus.PRICE_PENDING, is_deleted=False), distinct=True),
        awaiting_info_count=Count(
            "id",
            filter=(Q(status=ProductStatus.AWAITING_INFO) | Q(clarifications__status=ClarificationStatus.PENDING, is_sold=False)) & Q(is_deleted=False),
            distinct=True,
        ),
        sold_count=Count("id", filter=Q(status=ProductStatus.SOLD, is_deleted=False), distinct=True),
        sold_in_store_count=Count(
            "id",
            filter=Q(status=ProductStatus.SOLD, sold_channel_type=SaleChannelType.IN_STORE, is_deleted=False),
            distinct=True,
        ),
        sold_marketplace_count=Count(
            "id",
            filter=Q(status=ProductStatus.SOLD, sold_channel_type=SaleChannelType.MARKETPLACE, is_deleted=False),
            distinct=True,
        ),
        sold_other_count=Count(
            "id",
            filter=Q(status=ProductStatus.SOLD, sold_channel_type=SaleChannelType.OTHER, is_deleted=False),
            distinct=True,
        ),
        published_count=Count("id", filter=Q(status=ProductStatus.PUBLISHED, is_deleted=False), distinct=True),
        out_of_sync_count=Count(
            "id",
            filter=Q(status=ProductStatus.PUBLISHED, needs_platform_sync=True, is_deleted=False),
            distinct=True,
        ),
        blocked_count=Count("id", filter=Q(status=ProductStatus.BLOCKED, is_deleted=False), distinct=True),
        erased_count=Count("id", filter=Q(is_deleted=True), distinct=True),
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
        "price_pending_count": counts["price_pending_count"] or 0,
        "awaiting_info_count": counts["awaiting_info_count"] or 0,
        "sold_count": counts["sold_count"] or 0,
        "sold_in_store_count": counts["sold_in_store_count"] or 0,
        "sold_marketplace_count": counts["sold_marketplace_count"] or 0,
        "sold_other_count": counts["sold_other_count"] or 0,
        "channel_filter": channel_filter,
        "sync_filter": sync_filter,
        "published_count": counts["published_count"] or 0,
        "out_of_sync_count": counts["out_of_sync_count"] or 0,
        "blocked_count": counts["blocked_count"] or 0,
        "erased_count": counts["erased_count"] or 0,
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
        Product.objects.select_related("category").prefetch_related(
            "images",
            "listing_links__site",
            "clarifications__asked_by",
            "clarifications__answered_by",
            Prefetch(
                "status_logs",
                queryset=ProductStatusLog.objects.select_related("changed_by").order_by("-created_at"),
            ),
        ),
        pk=pk,
    )
    can_manage = is_manager(request.user)

    if product.is_deleted and not can_manage:
        messages.warning(request, _("This product has been moved to trash and is not accessible."))
        return redirect("inventory:dashboard")

    if request.method == "POST":
        if not can_manage:
            messages.error(request, _("Manager privileges required to edit product details."))
            return redirect("inventory:product_detail", pk=pk)

        form = ProductUpdateForm(request.POST, instance=product)
        if form.is_valid():
            from datetime import timedelta

            updated_product = form.save(commit=False)
            if updated_product.is_sold:
                if not updated_product.sold_at:
                    updated_product.sold_at = timezone.now()
                updated_product.is_reserved = False
                updated_product.reserved_until = None
            else:
                updated_product.sold_at = None
                if updated_product.is_reserved and not updated_product.reserved_until:
                    updated_product.reserved_until = timezone.now() + timedelta(hours=24)
                elif not updated_product.is_reserved:
                    updated_product.reserved_until = None
            updated_product.save(changed_by=request.user)

            files = request.FILES.getlist("images")
            if files:
                current_count = product.images.count()
                if current_count + len(files) <= 10:
                    with transaction.atomic():
                        max_order = product.images.aggregate(m=Max("order"))["m"]
                        start_order = 0 if max_order is None else max_order + 1
                        for idx, uploaded_file in enumerate(files):
                            webp_file = process_and_convert_to_webp(uploaded_file)
                            ProductImage.objects.create(
                                product=product,
                                image=webp_file,
                                order=start_order + idx,
                            )
                        is_published = (
                            product.status == ProductStatus.PUBLISHED
                            or product.listing_links.filter(is_active=True).exists()
                        )
                        if is_published and not product.needs_platform_sync:
                            product.needs_platform_sync = True
                            product.save(update_fields=["needs_platform_sync"])

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

    available_slots = max(0, 10 - product.images.count())

    context = {
        "product": product,
        "form": form,
        "can_manage": can_manage,
        "available_slots": available_slots,
        "site_links_data": site_links_data,
        "extra_inactive_links": extra_inactive_links,
        "pending_clarifications": pending_clarifications,
        "resolved_clarifications": resolved_clarifications,
        "has_unapplied_clarifications": has_unapplied_clarifications,
        "status_logs": product.status_logs.all(),
        "clarification_form": ProductClarificationForm(),
        "direct_clarification_form": ProductDirectClarificationForm(),
        "answer_form": ProductClarificationAnswerForm(),
        "categories": ClarificationCategory.choices,
    }
    return render(request, "inventory/product_detail.html", context)


@login_required
def product_add_direct_clarification_view(request, pk):
    """
    Allows assistants or managers to add a direct post-intake clarification note attached to a product.
    Immediately saves as RESOLVED with is_direct_note=True without altering product lifecycle status.
    """
    if request.method != "POST":
        return redirect("inventory:product_detail", pk=pk)

    product = get_object_or_404(Product, pk=pk)
    if product.is_deleted and not is_manager(request.user):
        messages.warning(request, _("This product has been moved to trash and is not accessible."))
        return redirect("inventory:dashboard")

    form = ProductDirectClarificationForm(request.POST)
    if form.is_valid():
        category = form.cleaned_data["category"]
        note_text = form.cleaned_data["note"]

        ProductClarification.objects.create(
            product=product,
            category=category,
            is_direct_note=True,
            question=str(_("Direct Note")),
            answer=note_text,
            asked_by=request.user,
            answered_by=request.user,
            status=ClarificationStatus.RESOLVED,
            answered_at=timezone.now(),
        )
        messages.success(request, _("Clarification note added successfully."))
    else:
        messages.error(request, _("Please provide a valid category and note text."))

    return redirect(f"{reverse('inventory:product_detail', kwargs={'pk': pk})}#clarifications-section")


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
def product_soft_delete_view(request, pk):
    """
    Moves a product to the trash (soft-delete), hiding it from default catalog views.
    Restricted to managers; requires POST.
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    product = get_object_or_404(Product, pk=pk)
    product.soft_delete(user=request.user)
    messages.success(request, _("Product successfully moved to trash."))
    return redirect(f"{reverse('inventory:dashboard')}?status=erased")


@manager_required
def product_restore_view(request, pk):
    """
    Restores a soft-deleted product from trash back to the active catalog in its previous status.
    Restricted to managers; requires POST.
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    product = get_object_or_404(Product, pk=pk)
    product.restore(user=request.user)
    messages.success(request, _("Product successfully restored to catalog."))
    return redirect("inventory:product_detail", pk=pk)


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
        from .services.ai_service import (
            AIServiceError,
            generate_product_listing,
            infer_taxonomy_heuristically,
        )

        active_language = get_language() or "en"
        listing_data = generate_product_listing(product, language=active_language)

        product.ai_title = (listing_data.get("title") or "").strip()[:255]
        product.ai_description = (listing_data.get("description") or "").strip()

        cat_slug = (listing_data.get("category_slug") or "").strip()
        cond_code = (listing_data.get("condition") or "").strip()
        if not cat_slug or not cond_code:
            fallback_cat, fallback_cond = infer_taxonomy_heuristically(
                f"{product.ai_title} {product.ai_description} {product.raw_note}"
            )
            cat_slug = cat_slug or fallback_cat
            cond_code = cond_code or fallback_cond

        update_fields = ["ai_title", "ai_description", "updated_at"]
        if cat_slug:
            matched_cat = Category.objects.filter(slug=cat_slug).first()
            if matched_cat:
                product.category = matched_cat
                update_fields.append("category")
        if cond_code and cond_code in dict(ProductCondition.choices):
            product.condition = cond_code
            update_fields.append("condition")

        product.save(update_fields=update_fields)

        messages.success(request, _("AI listing successfully generated from photos and notes!"))
    except AIServiceError as e:
        messages.error(request, str(e))
    except Exception as exc:
        messages.error(request, _("Unexpected error during AI generation: %(error)s") % {"error": exc})

    return redirect("inventory:product_detail", pk=pk)


def manifest_view(request):
    """
    Serves the W3C Web App Manifest (/manifest.json) for PWA installation.
    """
    manifest_data = {
        "name": "2ndHand Product Intake & Staging Hub",
        "short_name": "2ndHand",
        "description": str(_("Mobile intake & AI staging workspace for second-hand inventory.")),
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "orientation": "portrait-primary",
        "background_color": "#f8fafc",
        "theme_color": "#059669",
        "icons": [
            {
                "src": "/static/inventory/icons/icon-192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": "/static/inventory/icons/icon-192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "maskable",
            },
            {
                "src": "/static/inventory/icons/icon-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": "/static/inventory/icons/icon-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable",
            },
        ],
        "shortcuts": [
            {
                "name": str(_("New Intake")),
                "short_name": str(_("Intake")),
                "url": "/intake/",
                "icons": [{"src": "/static/inventory/icons/icon-192.png", "sizes": "192x192"}],
            },
            {
                "name": str(_("Catalog Dashboard")),
                "short_name": str(_("Dashboard")),
                "url": "/dashboard/",
                "icons": [{"src": "/static/inventory/icons/icon-192.png", "sizes": "192x192"}],
            },
            {
                "name": str(_("Pending Doubts")),
                "short_name": str(_("Doubts")),
                "url": "/dashboard/?status=awaiting_info",
                "icons": [{"src": "/static/inventory/icons/icon-192.png", "sizes": "192x192"}],
            },
        ],
    }
    return JsonResponse(manifest_data, content_type="application/manifest+json")


def service_worker_view(request):
    """
    Serves the root Service Worker (/sw.js) with root scope permission and zero caching.
    """
    response = render(request, "inventory/sw.js", content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


@login_required
def push_subscribe_view(request):
    """
    Registers or updates an authenticated user's browser PushSubscription.
    """
    if request.method != "POST":
        return JsonResponse({"error": _("Method not allowed.")}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": _("Invalid JSON payload.")}, status=400)

    endpoint = (data.get("endpoint") or "").strip()
    keys = data.get("keys") if isinstance(data.get("keys"), dict) else {}
    p256dh = (keys.get("p256dh") or data.get("p256dh") or "").strip()
    auth = (keys.get("auth") or data.get("auth") or "").strip()

    if not endpoint or not p256dh or not auth:
        return JsonResponse(
            {"error": _("Missing required push subscription fields (endpoint, p256dh, auth).")},
            status=400,
        )

    validator = URLValidator(schemes=["http", "https"])
    try:
        validator(endpoint)
    except ValidationError:
        return JsonResponse({"error": _("Invalid push endpoint URL.")}, status=400)

    user_agent = (request.META.get("HTTP_USER_AGENT") or "")[:500]
    subscription, _created = PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            "user": request.user,
            "p256dh": p256dh,
            "auth": auth,
            "user_agent": user_agent,
            "is_active": True,
        },
    )
    return JsonResponse({"status": "subscribed", "id": subscription.pk})


@login_required
def push_unsubscribe_view(request):
    """
    Removes an authenticated user's browser PushSubscription by endpoint (or all for user if omitted).
    """
    if request.method != "POST":
        return JsonResponse({"error": _("Method not allowed.")}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        data = {}

    endpoint = (data.get("endpoint") or "").strip()
    qs = PushSubscription.objects.filter(user=request.user)
    if endpoint:
        qs = qs.filter(endpoint=endpoint)
    deleted_count, _details = qs.delete()
    return JsonResponse({"status": "unsubscribed", "deleted": deleted_count})


@login_required
def push_test_view(request):
    """
    Sends a self-test Web Push notification to all active subscriptions of the authenticated user.
    """
    if request.method != "POST":
        return JsonResponse({"error": _("Method not allowed.")}, status=405)

    from .services.push_service import is_push_configured, send_push_to_user

    if not is_push_configured():
        return JsonResponse(
            {"error": _("Web Push VAPID keys are not configured.")},
            status=503,
        )

    sent_count = send_push_to_user(
        user=request.user,
        title=str(_("🔔 2ndHand Staging Test Alert")),
        body=str(_("Push notifications are working on this device!")),
        url=str(reverse_lazy("inventory:dashboard")),
        tag="2ndhand-test-push",
    )
    return JsonResponse({"status": "ok", "sent": sent_count})

@login_required
@manager_required
@require_POST
def product_reorder_images_view(request, pk):
    """
    Allows managers to reorder existing product images.
    Payload: JSON { "image_ids": [id1, id2, ...] } or form-data image_ids.
    Validates that all image IDs belong to the product and updates their order in a single atomic transaction.
    """
    product = get_object_or_404(Product, pk=pk)

    try:
        if request.content_type == "application/json" or (request.body and request.body.startswith(b"{")):
            data = json.loads(request.body.decode("utf-8"))
            image_ids = data.get("image_ids", [])
        else:
            image_ids = request.POST.getlist("image_ids")
            if not image_ids and "image_ids[]" in request.POST:
                image_ids = request.POST.getlist("image_ids[]")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"success": False, "error": _("Invalid JSON payload.")}, status=400)

    if not isinstance(image_ids, list) or not image_ids:
        return JsonResponse({"success": False, "error": _("No image IDs provided.")}, status=400)

    try:
        image_ids = [int(i) for i in image_ids]
    except (ValueError, TypeError):
        return JsonResponse({"success": False, "error": _("Image IDs must be integers.")}, status=400)

    # Verify that all image_ids belong to this product and length matches
    existing_images = list(product.images.all())
    existing_ids = {img.id for img in existing_images}

    if set(image_ids) != existing_ids or len(image_ids) != len(existing_images):
        return JsonResponse(
            {"success": False, "error": _("Provided image IDs do not match the product's images.")},
            status=400,
        )

    initial_primary = product.images.order_by("order", "id").first()
    initial_primary_id = initial_primary.id if initial_primary else None

    # Update order atomically
    with transaction.atomic():
        for order_idx, img_id in enumerate(image_ids):
            ProductImage.objects.filter(id=img_id, product=product).update(order=order_idx)

        is_published = (
            product.status == ProductStatus.PUBLISHED
            or product.listing_links.filter(is_active=True).exists()
        )
        if is_published and image_ids and image_ids[0] != initial_primary_id:
            if not product.needs_platform_sync:
                product.needs_platform_sync = True
                product.save(update_fields=["needs_platform_sync"])

    # Return updated list and new primary image url
    primary_image = product.images.order_by("order", "id").first()
    primary_image_url = primary_image.image.url if primary_image else None

    return JsonResponse({
        "success": True,
        "reordered_ids": image_ids,
        "primary_image_url": primary_image_url,
    })

@login_required
@manager_required
@require_POST
def product_upload_images_view(request, pk):
    """
    Allows managers to upload additional photos for an existing product.
    Enforces maximum of 10 photos total, processes images into WebP,
    and flags needs_platform_sync = True if product is published.
    """
    product = get_object_or_404(Product, pk=pk)
    files = request.FILES.getlist("images")
    if not files:
        messages.error(request, _("Please select at least one photo to upload."))
        return redirect("inventory:product_detail", pk=pk)

    current_count = product.images.count()
    if current_count + len(files) > 10:
        messages.error(
            request,
            _("Cannot upload %(new)d photo(s). Product already has %(current)d photo(s) (maximum is 10).")
            % {"new": len(files), "current": current_count},
        )
        return redirect("inventory:product_detail", pk=pk)

    try:
        with transaction.atomic():
            max_order = product.images.aggregate(m=Max("order"))["m"]
            start_order = 0 if max_order is None else max_order + 1
            for idx, uploaded_file in enumerate(files):
                webp_file = process_and_convert_to_webp(uploaded_file)
                ProductImage.objects.create(
                    product=product,
                    image=webp_file,
                    order=start_order + idx,
                )

            is_published = (
                product.status == ProductStatus.PUBLISHED
                or product.listing_links.filter(is_active=True).exists()
            )
            if is_published and not product.needs_platform_sync:
                product.needs_platform_sync = True
                product.save(update_fields=["needs_platform_sync"])

        messages.success(
            request,
            _("Successfully added %(count)d photo(s).") % {"count": len(files)},
        )
    except ValidationError as ve:
        messages.error(request, str(ve.message if hasattr(ve, "message") else ve))
    except Exception as exc:
        messages.error(request, _("Error processing uploaded photos: %(error)s") % {"error": str(exc)})

    return redirect("inventory:product_detail", pk=pk)


@login_required
@manager_required
@require_POST
def product_delete_image_view(request, pk, image_id):
    """
    Allows managers to delete a specific photo from a product.
    Requires at least 1 photo to remain.
    Reindexes remaining photos to maintain clean order indexing (0, 1, 2...).
    If the product is published, flags needs_platform_sync = True.
    """
    product = get_object_or_404(Product, pk=pk)
    image = get_object_or_404(ProductImage, id=image_id, product=product)

    if product.images.count() <= 1:
        messages.error(
            request,
            _("Cannot delete the only photo. Each product must have at least one photo."),
        )
        return redirect("inventory:product_detail", pk=pk)

    with transaction.atomic():
        image.delete()

        # Re-index remaining images
        remaining_images = product.images.order_by("order", "id")
        for idx, img in enumerate(remaining_images):
            if img.order != idx:
                ProductImage.objects.filter(id=img.id).update(order=idx)

        is_published = (
            product.status == ProductStatus.PUBLISHED
            or product.listing_links.filter(is_active=True).exists()
        )
        if is_published and not product.needs_platform_sync:
            product.needs_platform_sync = True
            product.save(update_fields=["needs_platform_sync"])

    messages.success(request, _("Photo deleted successfully."))
    return redirect("inventory:product_detail", pk=pk)


@login_required
@manager_required
@require_POST
def product_mark_platform_synced_view(request, pk):
    """
    Allows managers to mark a published product's external listings as synchronized.
    Clears needs_platform_sync and records an audit log entry.
    """
    product = get_object_or_404(Product, pk=pk)
    product.mark_platform_synced(user=request.user)
    messages.success(request, _("Platforms marked as updated successfully."))
    return redirect("inventory:product_detail", pk=pk)

