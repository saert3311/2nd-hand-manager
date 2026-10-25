from decimal import Decimal

from django import forms
from django.conf import settings
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _

from .models import (
    ClarificationCategory,
    ClarificationStatus,
    MarketplaceSite,
    Product,
    ProductClarification,
    ProductStatus,
    SaleChannelType,
)
from .services.turnstile_service import verify_turnstile_token


class TurnstileValidationMixin:
    """
    Mixin for Django authentication forms that validates Cloudflare Turnstile tokens
    prior to evaluating password credentials.
    """

    def clean(self):
        if getattr(settings, "TURNSTILE_ENABLED", False):
            turnstile_token = self.data.get("cf-turnstile-response")
            remote_ip = None
            request = getattr(self, "request", None)
            if request:
                x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
                if x_forwarded:
                    remote_ip = x_forwarded.split(",")[0].strip()
                else:
                    remote_ip = request.META.get("REMOTE_ADDR")

            if not turnstile_token:
                raise forms.ValidationError(
                    _("Please complete the security challenge."),
                    code="turnstile_missing",
                )
            if not verify_turnstile_token(turnstile_token, remote_ip=remote_ip):
                raise forms.ValidationError(
                    _("Security verification failed. Please try again."),
                    code="turnstile_failed",
                )
        return super().clean()


class TurnstileAuthenticationForm(TurnstileValidationMixin, AuthenticationForm):
    """
    Public login authentication form requiring Cloudflare Turnstile verification.
    """
    pass


class TurnstileAdminAuthenticationForm(TurnstileValidationMixin, AdminAuthenticationForm):
    """
    Django Admin authentication form requiring Cloudflare Turnstile verification.
    """
    pass




class ProductIntakeForm(forms.ModelForm):
    raw_note = forms.CharField(
        max_length=5000,
        widget=forms.Textarea(attrs={
            "rows": 3,
            "maxlength": "5000",
            "placeholder": _("Brief description / field notes (e.g., 'Vintage 90s Nike windbreaker, blue/white, small tear on left sleeve')"),
            "class": "w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-base sm:text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition bg-slate-50 focus:bg-white resize-y"
        }),
        required=False,
        label=_("Raw Field Notes")
    )
    sale_price = forms.DecimalField(
        min_value=Decimal("0.00"),
        max_value=Decimal("9999999.99"),
        decimal_places=2,
        required=False,
        label=_("Sale Price (€)"),
        widget=forms.NumberInput(attrs={
            "step": "0.01",
            "min": "0",
            "max": "9999999.99",
            "placeholder": "0.00",
            "inputmode": "decimal",
            "class": "w-full pl-8 pr-3.5 py-2.5 rounded-xl border border-slate-300 text-base sm:text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition bg-slate-50 focus:bg-white font-semibold"
        }),
    )
    ai_title = forms.CharField(
        max_length=255,
        required=False,
        label=_("Identified Title"),
        widget=forms.HiddenInput(attrs={"id": "id_ai_title"}),
    )
    estimated_retail_price = forms.DecimalField(
        min_value=Decimal("0.00"),
        max_value=Decimal("9999999.99"),
        decimal_places=2,
        required=False,
        label=_("Estimated Retail Price (€)"),
        widget=forms.HiddenInput(attrs={"id": "id_estimated_retail_price"}),
    )
    estimated_resale_price = forms.DecimalField(
        min_value=Decimal("0.00"),
        max_value=Decimal("9999999.99"),
        decimal_places=2,
        required=False,
        label=_("Estimated Resale Price (€)"),
        widget=forms.HiddenInput(attrs={"id": "id_estimated_resale_price"}),
    )

    class Meta:
        model = Product
        fields = [
            "raw_note",
            "sale_price",
            "ai_title",
            "estimated_retail_price",
            "estimated_resale_price",
        ]


class ProductUpdateForm(forms.ModelForm):
    ai_title = forms.CharField(
        max_length=255,
        required=False,
        label=_("Listing Title"),
        widget=forms.TextInput(attrs={
            "maxlength": "255",
            "class": "w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-base sm:text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 font-medium"
        }),
    )
    ai_description = forms.CharField(
        max_length=10000,
        required=False,
        label=_("Listing Description / Copy"),
        widget=forms.Textarea(attrs={
            "rows": 6,
            "maxlength": "10000",
            "class": "w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-base sm:text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 font-mono leading-relaxed resize-y"
        }),
    )
    sale_price = forms.DecimalField(
        min_value=Decimal("0.00"),
        max_value=Decimal("9999999.99"),
        decimal_places=2,
        required=False,
        label=_("Sale Price (€)"),
        widget=forms.NumberInput(attrs={
            "step": "0.01",
            "min": "0",
            "max": "9999999.99",
            "placeholder": "0.00",
            "inputmode": "decimal",
            "class": "w-full pl-8 pr-3.5 py-2.5 rounded-xl border border-slate-300 text-base sm:text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-emerald-500",
        }),
    )
    status = forms.ChoiceField(
        choices=ProductStatus.choices,
        required=False,
        label=_("Lifecycle Status"),
        widget=forms.Select(attrs={
            "class": "w-full sm:w-auto px-3.5 py-2.5 rounded-xl border border-slate-300 text-base sm:text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white"
        }),
    )
    sold_channel_type = forms.ChoiceField(
        choices=[("", "---------")] + list(SaleChannelType.choices),
        required=False,
        label=_("Sale Channel"),
        widget=forms.Select(attrs={
            "class": "w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-base sm:text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white"
        }),
    )
    sold_marketplace = forms.ModelChoiceField(
        queryset=MarketplaceSite.objects.filter(is_active=True).order_by("order", "name"),
        required=False,
        label=_("Marketplace Platform"),
        empty_label=_("---------"),
        widget=forms.Select(attrs={
            "class": "w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-base sm:text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white"
        }),
    )
    sold_channel_notes = forms.CharField(
        max_length=255,
        required=False,
        label=_("Sale Reference / Notes"),
        widget=forms.TextInput(attrs={
            "maxlength": "255",
            "placeholder": _("Ticket #, order ID, buyer username (optional)"),
            "class": "w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-base sm:text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 font-medium"
        }),
    )

    class Meta:
        model = Product
        fields = [
            "ai_title",
            "ai_description",
            "sale_price",
            "status",
            "is_sold",
            "sold_channel_type",
            "sold_marketplace",
            "sold_channel_notes",
        ]
        labels = {
            "is_sold": _("Mark Product as Sold"),
        }
        widgets = {
            "is_sold": forms.CheckboxInput(attrs={
                "class": "w-5 h-5 text-emerald-600 rounded border-slate-300 focus:ring-emerald-500 transition cursor-pointer"
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.db.models import Q
        if self.instance and self.instance.sold_marketplace_id:
            self.fields["sold_marketplace"].queryset = MarketplaceSite.objects.filter(
                Q(is_active=True) | Q(id=self.instance.sold_marketplace_id)
            ).order_by("order", "name")

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get("status")
        is_sold = cleaned_data.get("is_sold")
        sold_channel_type = cleaned_data.get("sold_channel_type")
        sold_marketplace = cleaned_data.get("sold_marketplace")

        if self.instance and self.instance.pk and not is_sold and status == ProductStatus.READY:
            if self.instance.clarifications.filter(status=ClarificationStatus.PENDING).exists():
                self.add_error(
                    "status",
                    _("Cannot mark product as Ready to Publish while pending clarifications remain unresolved.")
                )

        is_marking_sold = bool(is_sold or status == ProductStatus.SOLD)
        if is_marking_sold:
            if not sold_channel_type:
                self.add_error(
                    "sold_channel_type",
                    _("Please select where this product was sold (In-Store, Marketplace, or Other).")
                )
            elif sold_channel_type == SaleChannelType.MARKETPLACE and not sold_marketplace:
                self.add_error(
                    "sold_marketplace",
                    _("Please select the marketplace platform where the product was sold.")
                )
        else:
            cleaned_data["sold_channel_type"] = ""
            cleaned_data["sold_marketplace"] = None
            cleaned_data["sold_channel_notes"] = ""

        return cleaned_data



class ProductClarificationForm(forms.ModelForm):
    category = forms.ChoiceField(
        choices=ClarificationCategory.choices,
        label=_("Category"),
        widget=forms.Select(attrs={
            "class": "w-full px-3.5 py-2 rounded-xl border border-slate-300 text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-amber-500 bg-white"
        }),
    )
    question = forms.CharField(
        max_length=2000,
        label=_("Question for Assistant"),
        widget=forms.Textarea(attrs={
            "rows": 2,
            "maxlength": "2000",
            "placeholder": _("Ask the assistant for missing info (e.g., 'Confirm pit-to-pit measurement or verify fabric composition tag')"),
            "class": "w-full px-3.5 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-amber-500 resize-y"
        }),
    )

    class Meta:
        model = ProductClarification
        fields = ["category", "question"]


class ProductClarificationAnswerForm(forms.Form):
    answer = forms.CharField(
        max_length=3000,
        label=_("Answer"),
        widget=forms.Textarea(attrs={
            "rows": 2,
            "maxlength": "3000",
            "placeholder": _("Provide measurements, material details, or condition observations..."),
            "class": "w-full px-3.5 py-2 rounded-xl border border-amber-300 text-xs focus:outline-none focus:ring-2 focus:ring-emerald-500 resize-y"
        }),
    )
