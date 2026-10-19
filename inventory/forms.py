from decimal import Decimal

from django import forms
from django.conf import settings
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _

from .models import ClarificationCategory, ClarificationStatus, Product, ProductClarification, ProductStatus
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
            "class": "w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition bg-slate-50 focus:bg-white resize-y"
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
            "class": "w-full pl-8 pr-3.5 py-2.5 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition bg-slate-50 focus:bg-white font-semibold"
        }),
    )
    ai_title = forms.CharField(
        max_length=255,
        required=False,
        label=_("Identified Title"),
        widget=forms.HiddenInput(attrs={"id": "id_ai_title"}),
    )

    class Meta:
        model = Product
        fields = ["raw_note", "sale_price", "ai_title"]


class ProductUpdateForm(forms.ModelForm):
    ai_title = forms.CharField(
        max_length=255,
        required=False,
        label=_("Listing Title"),
        widget=forms.TextInput(attrs={
            "maxlength": "255",
            "class": "w-full px-3.5 py-2.5 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 font-medium"
        }),
    )
    ai_description = forms.CharField(
        max_length=10000,
        required=False,
        label=_("Listing Description / Copy"),
        widget=forms.Textarea(attrs={
            "rows": 6,
            "maxlength": "10000",
            "class": "w-full px-3.5 py-2.5 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 font-mono text-xs leading-relaxed resize-y"
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
            "class": "w-full pl-8 pr-3.5 py-2 rounded-xl border border-slate-300 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-emerald-500",
        }),
    )
    status = forms.ChoiceField(
        choices=ProductStatus.choices,
        required=False,
        label=_("Lifecycle Status"),
        widget=forms.Select(attrs={
            "class": "px-3.5 py-2 rounded-xl border border-slate-300 text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white"
        }),
    )

    class Meta:
        model = Product
        fields = ["ai_title", "ai_description", "sale_price", "status", "is_sold"]
        labels = {
            "is_sold": _("Mark Product as Sold"),
        }
        widgets = {
            "is_sold": forms.CheckboxInput(attrs={
                "class": "w-5 h-5 text-emerald-600 rounded border-slate-300 focus:ring-emerald-500 transition cursor-pointer"
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get("status")
        is_sold = cleaned_data.get("is_sold")
        if self.instance and self.instance.pk and not is_sold and status == ProductStatus.READY:
            if self.instance.clarifications.filter(status=ClarificationStatus.PENDING).exists():
                self.add_error(
                    "status",
                    _("Cannot mark product as Ready to Publish while pending clarifications remain unresolved.")
                )
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
