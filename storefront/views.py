import json
from decimal import Decimal, InvalidOperation
from urllib.parse import quote
from xml.sax.saxutils import escape as xml_escape

from django.core.paginator import Paginator
from django.db.models import Count, F, Prefetch, Q
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _

from inventory.models import (
    Category,
    Product,
    ProductCondition,
    ProductImage,
    ProductListingLink,
    StorefrontConfiguration,
)

PUBLIC_PAGE_SIZE = 20

SAFE_PUBLIC_PRODUCT_FIELDS = (
    "id",
    "ai_title",
    "ai_description",
    "sale_price",
    "estimated_retail_price",
    "estimated_resale_price",
    "status",
    "is_sold",
    "sold_at",
    "is_public",
    "is_featured",
    "is_reserved",
    "reserved_until",
    "category_id",
    "condition",
    "views_count",
    "whatsapp_clicks",
    "created_at",
    "updated_at",
)

CONDITION_PARAM_ALIASES = {
    "nuevo-con-etiquetas": ProductCondition.NEW_WITH_TAGS,
    "new_with_tags": ProductCondition.NEW_WITH_TAGS,
    "muy-bueno": ProductCondition.VERY_GOOD,
    "very_good": ProductCondition.VERY_GOOD,
    "buen-estado": ProductCondition.GOOD,
    "good": ProductCondition.GOOD,
    "vintage": ProductCondition.VINTAGE,
}

CONDITION_TO_SPANISH_SLUG = {
    ProductCondition.NEW_WITH_TAGS: "nuevo-con-etiquetas",
    ProductCondition.VERY_GOOD: "muy-bueno",
    ProductCondition.GOOD: "buen-estado",
    ProductCondition.VINTAGE: "vintage",
}

PRICE_PARAM_ALIASES = {
    "0-20": "under_20",
    "lt_20": "under_20",
    "under_20": "under_20",
    "20-50": "20_50",
    "20_50": "20_50",
    "50-": "over_50",
    "50+": "over_50",
    "gt_50": "over_50",
    "over_50": "over_50",
}

SORT_PARAM_ALIASES = {
    "recientes": "newest",
    "newest": "newest",
    "destacados": "featured",
    "featured": "featured",
    "precio-asc": "price_asc",
    "price_asc": "price_asc",
    "precio-desc": "price_desc",
    "price_desc": "price_desc",
}


def _sanitize_public_product(product: Product) -> Product:
    """
    Defense-in-depth firewall: ensures internal-only fields (raw_note, created_by_id)
    are blanked in memory so no template or serializer can ever leak them.
    """
    product.__dict__["raw_note"] = ""
    product.__dict__["created_by_id"] = None
    return product


def _get_public_queryset():
    return (
        Product.objects.public_visible()
        .select_related("category")
        .only(
            *SAFE_PUBLIC_PRODUCT_FIELDS,
            "category__id",
            "category__name",
            "category__name_en",
            "category__slug",
            "category__icon",
            "category__order",
        )
        .prefetch_related(
            Prefetch("images", queryset=ProductImage.objects.order_by("order", "id")),
            Prefetch(
                "listing_links",
                queryset=ProductListingLink.objects.filter(is_active=True)
                .select_related("site")
                .order_by("site__order", "site__name"),
            ),
        )
    )


def _parse_decimal(val: str):
    if not val:
        return None
    try:
        d = Decimal(val.strip().replace(",", "."))
        return d if d >= Decimal("0.00") else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def home_view(request):
    """
    Corporate Business Landing Page (/) for Rápido Pack (rapidopack.es).
    Showcases parcel point services (SEUR, GLS, InPost, Amazon Hub, Kanguro, DHL),
    Punto Pack, brand identity ("Quiénes somos"), the 4 newest available products
    ("Recién llegados"), trust stats, Alfafar location & contact, and LocalBusiness JSON-LD.
    """
    latest_products = list(
        _get_public_queryset()
        .filter(is_sold=False, is_reserved=False)
        .order_by("-created_at")[:4]
    )
    for prod in latest_products:
        _sanitize_public_product(prod)

    store_config = StorefrontConfiguration.get_solo()
    home_url = request.build_absolute_uri(reverse("storefront:home"))

    local_business_schema = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": store_config.store_name,
        "description": _(
            "Punto de paquetería multimarca (SEUR, GLS, InPost, Amazon, Kanguro, DHL), "
            "Punto Pack oficial y tienda de segunda mano y oportunidad con artículos revisados en Alfafar, Valencia."
        ),
        "url": home_url,
        "telephone": f"+{store_config.clean_whatsapp_number}",
        "email": store_config.contact_email,
        "priceRange": "€",
        "address": {
            "@type": "PostalAddress",
            "streetAddress": "Carrer del Comte Ronrée, 8",
            "addressLocality": "Alfafar",
            "addressRegion": "Valencia",
            "postalCode": "46910",
            "addressCountry": "ES",
        },
        "openingHoursSpecification": [
            {
                "@type": "OpeningHoursSpecification",
                "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                "opens": "09:30",
                "closes": "20:00",
            },
            {
                "@type": "OpeningHoursSpecification",
                "dayOfWeek": ["Saturday"],
                "opens": "10:00",
                "closes": "15:00",
            },
        ],
        "hasOfferCatalog": {
            "@type": "OfferCatalog",
            "name": _("Servicios de Paquetería, Punto Pack y Tienda de Segunda Mano"),
            "itemListElement": [
                {"@type": "Offer", "itemOffered": {"@type": "Service", "name": "Punto Pack Oficial y Paquetería Multimarca (SEUR, GLS, InPost, Amazon, Kanguro, DHL)"}},
                {"@type": "Offer", "itemOffered": {"@type": "Service", "name": "Envíos, recepción y devoluciones de paquetes en Alfafar"}},
                {"@type": "Offer", "itemOffered": {"@type": "Service", "name": "Tienda de segunda mano y oportunidad con artículos revisados"}},
            ],
        },
    }

    context = {
        "latest_products": latest_products,
        "featured_products": latest_products,
        "canonical_url": home_url,
        "local_business_json_ld": json.dumps(local_business_schema, ensure_ascii=False),
        "is_landing_page": True,
    }
    return render(request, "storefront/home.html", context)


def category_catalog_view(request, category_slug: str):
    """
    Category-filtered Marketplace Catalog (/tienda/categoria/<slug:category_slug>/).
    Returns 404 if the category slug is not one of the active official categories.
    """
    active_category = get_object_or_404(Category, slug=category_slug, is_active=True)
    return catalog_view(request, category_slug=active_category.slug, resolved_category=active_category)


def catalog_view(request, category_slug: str | None = None, resolved_category: Category | None = None):
    """
    Public Marketplace Filterable Catalog (/tienda/ and /tienda/categoria/<slug>/).
    Enforces strict public visibility rules and 7-day SOLD social proof ordering.
    Supports both Spanish query parameters (?estado=, ?precio=, ?orden=, ?categoria=)
    and English aliases (?condition=, ?price=, ?sort=, ?category=).
    """
    qs = _get_public_queryset()

    raw_cat = category_slug or request.GET.get("categoria") or request.GET.get("category", "")
    category_slug_clean = raw_cat.strip().lower()

    raw_cond = (request.GET.get("estado") or request.GET.get("condition", "")).strip().lower()
    condition_filter = CONDITION_PARAM_ALIASES.get(raw_cond, "")

    raw_price = (request.GET.get("precio") or request.GET.get("price", "")).strip().lower()
    price_range = PRICE_PARAM_ALIASES.get(raw_price, "")

    min_price_raw = request.GET.get("min_price", "").strip()
    max_price_raw = request.GET.get("max_price", "").strip()
    search_query = request.GET.get("q", "").strip()

    raw_sort = (request.GET.get("orden") or request.GET.get("sort", "newest")).strip().lower()
    sort_by = SORT_PARAM_ALIASES.get(raw_sort, "newest")

    active_category = resolved_category
    if category_slug_clean:
        if not active_category:
            active_category = Category.objects.filter(slug=category_slug_clean, is_active=True).first()
        if active_category:
            qs = qs.filter(category=active_category)
        else:
            qs = qs.filter(category__slug=category_slug_clean)

    if condition_filter:
        qs = qs.filter(condition=condition_filter)

    if price_range == "under_20":
        qs = qs.filter(sale_price__lt=Decimal("20.00"))
    elif price_range == "20_50":
        qs = qs.filter(sale_price__gte=Decimal("20.00"), sale_price__lte=Decimal("50.00"))
    elif price_range == "over_50":
        qs = qs.filter(sale_price__gt=Decimal("50.00"))

    min_price = _parse_decimal(min_price_raw)
    max_price = _parse_decimal(max_price_raw)
    if min_price is not None:
        qs = qs.filter(sale_price__gte=min_price)
    if max_price is not None:
        qs = qs.filter(sale_price__lte=max_price)

    if search_query:
        # Strict firewall: search ONLY public fields (ai_title, ai_description, category, reference id)
        q_filter = (
            Q(ai_title__icontains=search_query)
            | Q(ai_description__icontains=search_query)
            | Q(category__name__icontains=search_query)
            | Q(category__name_en__icontains=search_query)
        )
        cleaned_ref = search_query.lower().replace("ref.", "").replace("ref", "").replace("#", "").strip()
        if cleaned_ref.isdigit():
            q_filter |= Q(pk=int(cleaned_ref))
        qs = qs.filter(q_filter)

    if sort_by == "price_asc":
        qs = qs.order_by("is_sold", "sale_price", "-created_at")
    elif sort_by == "price_desc":
        qs = qs.order_by("is_sold", "-sale_price", "-created_at")
    elif sort_by == "featured":
        qs = qs.order_by("is_sold", "-is_featured", "-created_at")
    else:
        sort_by = "newest"
        qs = qs.order_by("is_sold", "-is_featured", "-created_at")

    paginator = Paginator(qs, PUBLIC_PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    for prod in page_obj.object_list:
        _sanitize_public_product(prod)

    elided_page_range = (
        paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1)
        if paginator.num_pages > 1
        else []
    )

    extra_params = request.GET.copy()
    if "page" in extra_params:
        del extra_params["page"]
    query_string = extra_params.urlencode()

    # Category counts for active visible inventory
    visible_base_ids = Product.objects.public_visible().values_list("id", flat=True)
    categories_with_counts = (
        Category.objects.filter(is_active=True)
        .annotate(
            visible_count=Count(
                "products",
                filter=Q(products__id__in=visible_base_ids),
                distinct=True,
            )
        )
        .order_by("order", "name")
    )

    base_filter_url = (
        reverse("storefront:category", kwargs={"category_slug": active_category.slug})
        if active_category and category_slug
        else reverse("storefront:catalog")
    )

    context = {
        "page_obj": page_obj,
        "products": page_obj.object_list,
        "paginator": paginator,
        "total_results": paginator.count,
        "total_count": paginator.count,
        "elided_page_range": elided_page_range,
        "query_string": query_string,
        "categories": categories_with_counts,
        "active_category": category_slug_clean,
        "active_category_obj": active_category,
        "category_filter": category_slug_clean,
        "base_filter_url": base_filter_url,
        "active_condition": condition_filter,
        "active_estado": CONDITION_TO_SPANISH_SLUG.get(condition_filter, ""),
        "condition_filter": condition_filter,
        "condition_choices": ProductCondition.choices,
        "active_price": price_range,
        "price_filter": price_range,
        "min_price": min_price_raw,
        "max_price": max_price_raw,
        "search_query": search_query,
        "active_sort": sort_by,
        "sort_by": sort_by,
        "has_active_filters": bool(
            category_slug_clean or condition_filter or price_range or min_price_raw or max_price_raw or search_query
        ),
    }
    return render(request, "storefront/catalog.html", context)


def _build_whatsapp_inquiry_url(request, product: Product, store_config: StorefrontConfiguration) -> str:
    product_url = request.build_absolute_uri(product.get_public_url())
    price_str = f"{product.sale_price:.2f} €" if product.sale_price is not None else ""
    if product.is_reserved:
        text = _(
            "Hola %(store)s, me interesa saber si sigue disponible o entrar en lista de espera para: "
            "%(title)s (%(ref)s - %(price)s) %(url)s"
        ) % {
            "store": store_config.store_name,
            "title": product.ai_title,
            "ref": product.public_reference,
            "price": price_str,
            "url": product_url,
        }
    else:
        text = _(
            "Hola %(store)s, me interesa el artículo %(title)s (%(ref)s - %(price)s). "
            "¿Sigue disponible en la tienda de Alfafar? %(url)s"
        ) % {
            "store": store_config.store_name,
            "title": product.ai_title,
            "ref": product.public_reference,
            "price": price_str,
            "url": product_url,
        }
    return f"https://wa.me/{store_config.clean_whatsapp_number}?text={quote(text)}"


def legacy_product_detail_redirect_view(request, slug: str, pk: int):
    """
    Redirects legacy /p/<slug>-<pk>/ URLs permanently (301) to /tienda/producto/<slug>-<pk>/.
    """
    product = get_object_or_404(_get_public_queryset(), pk=pk)
    _sanitize_public_product(product)
    return redirect(product.get_public_url(), permanent=True)


def public_product_detail_view(request, slug: str, pk: int):
    """
    Public 60/40 Product Detail page (/tienda/producto/<slug>-<pk>/).
    Enforces 301 canonical slug redirect, strict non-leak firewall, view counter increment,
    OpenGraph metadata, and Schema.org Product JSON-LD.
    """
    product = get_object_or_404(_get_public_queryset(), pk=pk)
    _sanitize_public_product(product)

    if slug != product.slug:
        return redirect(product.get_public_url(), permanent=True)

    # Atomically increment public views counter
    Product.objects.filter(pk=product.pk).update(views_count=F("views_count") + 1)
    product.views_count = (product.views_count or 0) + 1

    store_config = StorefrontConfiguration.get_solo()
    canonical_url = request.build_absolute_uri(product.get_public_url())

    images = list(product.images.all())
    primary_image = images[0] if images else None
    primary_image_abs_url = request.build_absolute_uri(primary_image.image.url) if primary_image else ""

    active_links = list(product.listing_links.all())

    # Related products (same category preferred, excluding current item)
    related_qs = _get_public_queryset().exclude(pk=product.pk)
    if product.category_id:
        same_cat = list(
            related_qs.filter(category_id=product.category_id).order_by(
                "is_sold", "-is_featured", "-created_at"
            )[:4]
        )
        if len(same_cat) < 4:
            needed = 4 - len(same_cat)
            existing_ids = [p.pk for p in same_cat]
            others = list(
                related_qs.exclude(pk__in=existing_ids).order_by(
                    "is_sold", "-is_featured", "-created_at"
                )[:needed]
            )
            related_products = same_cat + others
        else:
            related_products = same_cat
    else:
        related_products = list(related_qs.order_by("is_sold", "-is_featured", "-created_at")[:4])

    for rel in related_products:
        _sanitize_public_product(rel)

    # Build Schema.org Product JSON-LD
    if product.is_sold:
        availability_url = "https://schema.org/SoldOut"
    elif product.is_reserved:
        availability_url = "https://schema.org/LimitedAvailability"
    else:
        availability_url = "https://schema.org/InStock"

    if product.condition == ProductCondition.NEW_WITH_TAGS:
        condition_schema = "https://schema.org/NewCondition"
    else:
        condition_schema = "https://schema.org/UsedCondition"

    schema_data = {
        "@context": "https://schema.org/",
        "@type": "Product",
        "name": product.ai_title,
        "description": product.ai_description,
        "sku": product.public_reference,
        "mpn": str(product.pk),
        "brand": {
            "@type": "Brand",
            "name": store_config.store_name,
        },
        "offers": {
            "@type": "Offer",
            "url": canonical_url,
            "priceCurrency": "EUR",
            "price": f"{product.sale_price:.2f}" if product.sale_price is not None else "0.00",
            "itemCondition": condition_schema,
            "availability": availability_url,
            "seller": {
                "@type": "Organization",
                "name": store_config.store_name,
            },
        },
    }
    if images:
        schema_data["image"] = [request.build_absolute_uri(img.image.url) for img in images]
    if product.category:
        schema_data["category"] = product.category.localized_name

    # Split description bullet lines cleanly for template rendering
    description_lines = [
        line.strip().lstrip("•*-").strip()
        for line in (product.ai_description or "").splitlines()
        for _ in [0]
        if line.strip()
    ]

    # Discount percentage if estimated_retail_price > sale_price
    savings_pct = None
    if (
        product.estimated_retail_price
        and product.sale_price
        and product.estimated_retail_price > product.sale_price
    ):
        try:
            diff = product.estimated_retail_price - product.sale_price
            pct = int(round((diff / product.estimated_retail_price) * 100))
            if 5 <= pct <= 95:
                savings_pct = pct
        except (ArithmeticError, ValueError, TypeError):
            savings_pct = None

    context = {
        "product": product,
        "images": images,
        "primary_image": primary_image,
        "primary_image_url": primary_image_abs_url,
        "primary_image_abs_url": primary_image_abs_url,
        "active_links": active_links,
        "related_products": related_products,
        "canonical_url": canonical_url,
        "whatsapp_direct_url": _build_whatsapp_inquiry_url(request, product, store_config),
        "schema_json_ld": json.dumps(schema_data, ensure_ascii=False),
        "description_lines": description_lines,
        "savings_pct": savings_pct,
    }
    return render(request, "storefront/product_detail.html", context)


def how_to_buy_view(request):
    """
    Standalone shareable "¿Cómo comprar en Rápido Pack Alfafar?" page (/como-comprar/).
    Provides the full guide for non-JS visitors and direct link sharing.
    """
    return render(
        request,
        "storefront/how_to_buy.html",
        {
            "page_title": _("¿Cómo comprar en Rápido Pack Alfafar?"),
        },
    )


def go_store_whatsapp_view(request):
    """
    General store WhatsApp redirector (/go/whatsapp/) used by landing page and header CTAs.
    """
    store_config = StorefrontConfiguration.get_solo()
    text = _(
        "Hola %(store)s, os escribo desde la web para hacer una consulta sobre paquetería o artículos de la tienda de Alfafar."
    ) % {"store": store_config.store_name}
    target_url = f"https://wa.me/{store_config.clean_whatsapp_number}?text={quote(text)}"
    return HttpResponseRedirect(target_url)


def go_whatsapp_view(request, pk: int):
    """
    First-party outbound click tracker for product WhatsApp inquiries (/go/whatsapp/<pk>/).
    Atomically increments product.whatsapp_clicks and redirects to wa.me.
    """
    product = get_object_or_404(_get_public_queryset(), pk=pk)
    _sanitize_public_product(product)

    Product.objects.filter(pk=product.pk).update(whatsapp_clicks=F("whatsapp_clicks") + 1)
    store_config = StorefrontConfiguration.get_solo()
    target_url = _build_whatsapp_inquiry_url(request, product, store_config)
    return HttpResponseRedirect(target_url)


def go_marketplace_link_view(request, link_pk: int):
    """
    First-party outbound click tracker for external marketplace links (/go/link/<link_pk>/).
    Atomically increments link.clicks_count and redirects to the external platform URL.
    """
    link = get_object_or_404(
        ProductListingLink.objects.select_related("product", "site"),
        pk=link_pk,
        is_active=True,
    )
    if not Product.objects.public_visible().filter(pk=link.product_id).exists():
        raise Http404("Product is not publicly visible.")

    ProductListingLink.objects.filter(pk=link.pk).update(clicks_count=F("clicks_count") + 1)
    return HttpResponseRedirect(link.url)


def sitemap_view(request):
    """
    Dynamic XML sitemap (/sitemap.xml) listing only public URLs:
    /, /tienda/, /tienda/categoria/<slug>/ (12), /tienda/producto/<slug>-<pk>/ (public_visible()),
    /como-comprar/, and legal pages (/aviso-legal/, /privacidad/, /cookies/).
    Never exposes internal routes or notes.
    """
    products = (
        Product.objects.public_visible()
        .only("id", "ai_title", "updated_at", "status", "is_sold")
        .order_by("-updated_at")
    )
    categories = Category.objects.filter(is_active=True).order_by("order", "name")

    urls = [
        {
            "loc": request.build_absolute_uri(reverse("storefront:home")),
            "changefreq": "daily",
            "priority": "1.0",
        },
        {
            "loc": request.build_absolute_uri(reverse("storefront:catalog")),
            "changefreq": "daily",
            "priority": "0.9",
        },
        {
            "loc": request.build_absolute_uri(reverse("storefront:how_to_buy")),
            "changefreq": "monthly",
            "priority": "0.5",
        },
        {
            "loc": request.build_absolute_uri(reverse("storefront:legal_notice")),
            "changefreq": "monthly",
            "priority": "0.3",
        },
        {
            "loc": request.build_absolute_uri(reverse("storefront:privacy")),
            "changefreq": "monthly",
            "priority": "0.3",
        },
        {
            "loc": request.build_absolute_uri(reverse("storefront:cookies")),
            "changefreq": "monthly",
            "priority": "0.3",
        },
    ]

    for category in categories:
        urls.append(
            {
                "loc": request.build_absolute_uri(
                    reverse("storefront:category", kwargs={"category_slug": category.slug})
                ),
                "changefreq": "daily",
                "priority": "0.8",
            }
        )

    for product in products:
        _sanitize_public_product(product)
        urls.append(
            {
                "loc": request.build_absolute_uri(product.get_public_url()),
                "lastmod": product.updated_at.strftime("%Y-%m-%d"),
                "changefreq": "daily",
                "priority": "0.8",
            }
        )

    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for entry in urls:
        xml_lines.append("  <url>")
        xml_lines.append(f"    <loc>{xml_escape(entry['loc'])}</loc>")
        if "lastmod" in entry:
            xml_lines.append(f"    <lastmod>{entry['lastmod']}</lastmod>")
        xml_lines.append(f"    <changefreq>{entry['changefreq']}</changefreq>")
        xml_lines.append(f"    <priority>{entry['priority']}</priority>")
        xml_lines.append("  </url>")
    xml_lines.append("</urlset>")

    return HttpResponse("\n".join(xml_lines), content_type="application/xml; charset=utf-8")


def robots_view(request):
    """
    Serves /robots.txt allowing public storefront indexing while disallowing
    internal staging (/panel/, /dashboard/, /intake/, /products/), admin, API, and redirect routes.
    """
    sitemap_url = request.build_absolute_uri(reverse("storefront:sitemap"))
    lines = [
        "User-agent: *",
        "Allow: /",
        "Allow: /tienda/",
        "Disallow: /admin/",
        "Disallow: /panel/",
        "Disallow: /staff/",
        "Disallow: /dashboard/",
        "Disallow: /intake/",
        "Disallow: /products/",
        "Disallow: /login/",
        "Disallow: /logout/",
        "Disallow: /api/",
        "Disallow: /go/",
        f"Sitemap: {sitemap_url}",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")


def legal_notice_view(request):
    return render(
        request,
        "storefront/legal_page.html",
        {
            "page_type": "legal_notice",
            "page_title": _("Aviso Legal y Condiciones de Uso"),
        },
    )


def privacy_policy_view(request):
    return render(
        request,
        "storefront/legal_page.html",
        {
            "page_type": "privacy_policy",
            "page_title": _("Política de Privacidad (RGPD)"),
        },
    )


def cookies_policy_view(request):
    return render(
        request,
        "storefront/legal_page.html",
        {
            "page_type": "cookies_policy",
            "page_title": _("Política de Cookies"),
        },
    )
