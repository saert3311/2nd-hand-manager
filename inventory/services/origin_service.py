from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils.translation import gettext as _

from inventory.models import Pallet, Product, Provider


def build_intake_origin_choices() -> list:
    """
    Builds grouped choices (<optgroup>) for the single sticky Origin selector on /intake/.
    Strictly omits commercial financial figures (purchase_price, estimated_value) so
    Sourcing Assistants never see confidential supplier costs.
    """
    choices: list = [("", _("— No Origin / Unspecified —"))]

    pallets = list(Pallet.objects.select_related("provider").order_by("-number"))
    if pallets:
        pallet_options = []
        for pallet in pallets:
            label = f"Pallet #{pallet.number} ({pallet.received_date.strftime('%Y-%m-%d')})"
            if pallet.provider_id and pallet.provider:
                label = f"{label} · {pallet.provider.name}"
            pallet_options.append((f"pallet:{pallet.pk}", label))
        choices.append((str(_("📦 Active Pallets")), pallet_options))

    providers = list(Provider.objects.filter(is_active=True).order_by("name"))
    if providers:
        provider_options = [
            (f"provider:{provider.pk}", f"{provider.type_icon} {provider.name}")
            for provider in providers
        ]
        choices.append((str(_("🏷️ Direct Origins (No Pallet)")), provider_options))

    return choices


def parse_origin_token(token: str) -> tuple[Pallet | None, Provider | None]:
    """
    Parses a unified origin token ('pallet:<id>', 'provider:<id>', '', or 'none')
    into (pallet, provider). Raises ValidationError on invalid selections.
    """
    cleaned = (token or "").strip()
    if not cleaned or cleaned == "none":
        return None, None

    if cleaned.startswith("pallet:"):
        raw_id = cleaned.split(":", 1)[1]
        if not raw_id.isdigit():
            raise ValidationError(_("Invalid pallet selection."))
        pallet = Pallet.objects.select_related("provider").filter(pk=int(raw_id)).first()
        if not pallet:
            raise ValidationError(_("Selected pallet no longer exists."))
        return pallet, pallet.provider

    if cleaned.startswith("provider:"):
        raw_id = cleaned.split(":", 1)[1]
        if not raw_id.isdigit():
            raise ValidationError(_("Invalid origin provider selection."))
        provider = Provider.objects.filter(pk=int(raw_id), is_active=True).first()
        if not provider:
            raise ValidationError(_("Selected origin provider is unavailable."))
        return None, provider

    raise ValidationError(_("Invalid product origin selection."))


def get_pallets_with_stats():
    """
    Returns Pallet queryset annotated with active item count, sold count,
    and realized sales revenue for the Manager Pallets & Providers Hub.
    """
    return (
        Pallet.objects.select_related("provider")
        .annotate(
            products_count=Count(
                "products",
                filter=Q(products__is_deleted=False),
                distinct=True,
            ),
            sold_products_count=Count(
                "products",
                filter=Q(products__is_deleted=False, products__is_sold=True),
                distinct=True,
            ),
            realized_revenue=Coalesce(
                Sum(
                    "products__sale_price",
                    filter=Q(products__is_deleted=False, products__is_sold=True),
                ),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        )
        .order_by("-number")
    )


def get_providers_with_roi_stats() -> list[dict]:
    """
    Computes Provider ROI & performance summaries in 3 bounded queries (no N+1).
    Prevents double-counting by summing Pallet.purchase_price for palletized stock
    and Product.acquisition_cost ONLY where pallet__isnull=True.
    """
    providers = list(Provider.objects.all().order_by("name"))
    if not providers:
        return []

    zero = Decimal("0.00")
    dec_field = DecimalField(max_digits=12, decimal_places=2)

    pallet_stats_qs = (
        Pallet.objects.filter(provider__isnull=False)
        .values("provider_id")
        .annotate(
            pallets_count=Count("id"),
            pallet_cost_total=Coalesce(Sum("purchase_price"), Value(zero), output_field=dec_field),
            pallet_est_value_total=Coalesce(Sum("estimated_value"), Value(zero), output_field=dec_field),
        )
    )
    pallet_stats_map = {row["provider_id"]: row for row in pallet_stats_qs}

    product_stats_qs = (
        Product.objects.filter(is_deleted=False, provider__isnull=False)
        .values("provider_id")
        .annotate(
            total_products_count=Count("id"),
            active_products_count=Count("id", filter=Q(is_sold=False)),
            sold_products_count=Count("id", filter=Q(is_sold=True)),
            standalone_cost_total=Coalesce(
                Sum("acquisition_cost", filter=Q(pallet__isnull=True)),
                Value(zero),
                output_field=dec_field,
            ),
            realized_revenue=Coalesce(
                Sum("sale_price", filter=Q(is_sold=True)),
                Value(zero),
                output_field=dec_field,
            ),
            active_stock_value=Coalesce(
                Sum(
                    Coalesce("sale_price", "estimated_resale_price", Value(zero), output_field=dec_field),
                    filter=Q(is_sold=False),
                ),
                Value(zero),
                output_field=dec_field,
            ),
        )
    )
    product_stats_map = {row["provider_id"]: row for row in product_stats_qs}

    results = []
    for provider in providers:
        pal = pallet_stats_map.get(provider.pk, {})
        prod = product_stats_map.get(provider.pk, {})

        pallet_cost = pal.get("pallet_cost_total") or zero
        standalone_cost = prod.get("standalone_cost_total") or zero
        total_cost = pallet_cost + standalone_cost
        realized_revenue = prod.get("realized_revenue") or zero
        active_stock_value = prod.get("active_stock_value") or zero
        net_margin = realized_revenue - total_cost
        roi_pct = (
            ((net_margin / total_cost) * Decimal("100")).quantize(Decimal("0.1"))
            if total_cost > zero
            else None
        )

        results.append({
            "provider": provider,
            "pallets_count": pal.get("pallets_count", 0),
            "pallet_cost_total": pallet_cost,
            "pallet_est_value_total": pal.get("pallet_est_value_total") or zero,
            "standalone_cost_total": standalone_cost,
            "total_cost": total_cost,
            "total_products_count": prod.get("total_products_count", 0),
            "active_products_count": prod.get("active_products_count", 0),
            "sold_products_count": prod.get("sold_products_count", 0),
            "realized_revenue": realized_revenue,
            "active_stock_value": active_stock_value,
            "net_margin": net_margin,
            "roi_pct": roi_pct,
        })

    return results
