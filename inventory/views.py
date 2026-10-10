import io
import zipfile

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import get_language
from django.utils.translation import gettext as _

from .forms import ProductIntakeForm, ProductUpdateForm
from .models import Product, ProductImage
from .permissions import is_assistant, is_manager, manager_required
from .services.image_service import (
    MAX_IMAGES_PER_PRODUCT,
    process_and_convert_to_webp,
    validate_image_file,
    validate_images_count,
)


class CustomLoginView(LoginView):
    template_name = "registration/login.html"
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
def dashboard_view(request):
    """
    Catalog overview dashboard with filters and search.
    """
    status_filter = request.GET.get("status", "all").strip().lower()
    search_query = request.GET.get("q", "").strip()

    products = Product.objects.prefetch_related("images").all()

    if status_filter == "active":
        products = products.filter(is_sold=False)
    elif status_filter == "sold":
        products = products.filter(is_sold=True)

    if search_query:
        products = products.filter(
            Q(ai_title__icontains=search_query)
            | Q(raw_note__icontains=search_query)
            | Q(ai_description__icontains=search_query)
        )

    counts = Product.objects.aggregate(
        total_count=Count("id"),
        active_count=Count("id", filter=Q(is_sold=False)),
        sold_count=Count("id", filter=Q(is_sold=True)),
    )

    context = {
        "products": products,
        "status_filter": status_filter,
        "search_query": search_query,
        "total_count": counts["total_count"] or 0,
        "active_count": counts["active_count"] or 0,
        "sold_count": counts["sold_count"] or 0,
        "can_manage": is_manager(request.user),
    }
    return render(request, "inventory/dashboard.html", context)


@login_required
def product_detail_view(request, pk):
    """
    Product staging detail view: inspect photos, copy listing copy,
    download ZIP, and edit pricing / sold status.
    """
    product = get_object_or_404(Product.objects.prefetch_related("images"), pk=pk)
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

    context = {
        "product": product,
        "form": form,
        "can_manage": can_manage,
    }
    return render(request, "inventory/product_detail.html", context)


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

        product.ai_title = listing_data["title"]
        product.ai_description = listing_data["description"]
        product.save(update_fields=["ai_title", "ai_description", "updated_at"])

        messages.success(request, _("AI listing successfully generated from photos and notes!"))
    except AIServiceError as e:
        messages.error(request, str(e))
    except Exception as exc:
        messages.error(request, _("Unexpected error during AI generation: %(error)s") % {"error": exc})

    return redirect("inventory:product_detail", pk=pk)
