from decimal import Decimal

from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Product


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

    class Meta:
        model = Product
        fields = ["raw_note"]


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
            "class": "w-36 px-3.5 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 font-semibold"
        }),
    )

    class Meta:
        model = Product
        fields = ["ai_title", "ai_description", "sale_price", "is_sold"]
        labels = {
            "is_sold": _("Mark Product as Sold"),
        }
        widgets = {
            "is_sold": forms.CheckboxInput(attrs={
                "class": "w-5 h-5 text-emerald-600 rounded border-slate-300 focus:ring-emerald-500 transition cursor-pointer"
            }),
        }
