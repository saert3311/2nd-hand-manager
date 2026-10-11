from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


class Product(models.Model):
    raw_note = models.TextField(
        blank=True,
        default="",
        help_text=_("Original raw field note taken during intake")
    )
    ai_title = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text=_("AI-generated marketplace title")
    )
    ai_description = models.TextField(
        blank=True,
        default="",
        help_text=_("AI-generated marketplace listing description")
    )
    sale_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal("0.00")),
            MaxValueValidator(Decimal("9999999.99")),
        ],
        help_text=_("Sale price in Euros (€)")
    )
    is_sold = models.BooleanField(
        default=False,
        db_index=True,
        help_text=_("Whether the product has been sold")
    )
    sold_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Timestamp when marked as sold")
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_products"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Product")
        verbose_name_plural = _("Products")

    def __str__(self):
        return self.display_title

    @property
    def display_title(self) -> str:
        ai_t = (self.ai_title or "").strip()
        if ai_t:
            return ai_t
        raw_n = (self.raw_note or "").strip()
        if raw_n:
            return raw_n[:40] + ("..." if len(raw_n) > 40 else "")
        return f"{_('Product')} #{self.pk or _('New')}"

    @property
    def primary_image(self):
        return self.images.order_by("order", "id").first()

    def mark_as_sold(self, price=None, commit=True):
        self.is_sold = True
        self.sold_at = timezone.now()
        if price is not None:
            self.sale_price = price
        if commit:
            self.save(update_fields=["is_sold", "sold_at", "sale_price", "updated_at"])

    def mark_as_unsold(self, commit=True):
        self.is_sold = False
        self.sold_at = None
        if commit:
            self.save(update_fields=["is_sold", "sold_at", "updated_at"])


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images"
    )
    image = models.ImageField(upload_to="products/%Y/%m/")
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "created_at", "id"]
        verbose_name = _("Product Image")
        verbose_name_plural = _("Product Images")

    def __str__(self):
        return f"{_('Image')} #{self.pk or _('New')} - {_('Product')} #{self.product_id}"


class AIPromptConfiguration(models.Model):
    LANGUAGE_CHOICES = [
        ("es", _("Spanish")),
        ("en", _("English")),
    ]

    language = models.CharField(
        max_length=10,
        choices=LANGUAGE_CHOICES,
        default="es",
        db_index=True,
        verbose_name=_("Language"),
        help_text=_("Target listing language")
    )
    model_name = models.CharField(
        max_length=64,
        default="gemini-2.5-flash",
        verbose_name=_("Model Name"),
        help_text=_("Gemini model identifier (e.g. gemini-2.5-flash, gemini-2.5-pro)")
    )
    temperature = models.FloatField(
        default=0.3,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        verbose_name=_("Temperature"),
        help_text=_("Sampling temperature between 0.0 and 1.0")
    )
    system_instruction = models.TextField(
        verbose_name=_("System Instruction"),
        help_text=_("Custom listing instructions, marketplace guidelines (Wallapop, Vinted, eBay), and tone of voice.")
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name=_("Is Active"),
        help_text=_("Whether this configuration is actively used for listing generation.")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))

    class Meta:
        ordering = ["language", "-is_active", "-updated_at"]
        verbose_name = _("AI Prompt Configuration")
        verbose_name_plural = _("AI Prompt Configurations")

    def __str__(self):
        status = _("Active") if self.is_active else _("Inactive")
        return f"{self.get_language_display()} - {self.model_name} ({status})"

    def clean(self):
        super().clean()
        if self.temperature is not None and not (0.0 <= self.temperature <= 1.0):
            from django.core.exceptions import ValidationError
            raise ValidationError({"temperature": _("Temperature must be between 0.0 and 1.0.")})

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.is_active:
            # Option A: Automatic demotion of previous active configurations for the same language
            AIPromptConfiguration.objects.filter(
                language=self.language,
                is_active=True
            ).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)


class MarketplaceSite(models.Model):
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("Site Name"),
        help_text=_("Marketplace platform name (e.g. Wallapop, Vinted, eBay, Milanuncios)"),
    )
    slug = models.SlugField(
        max_length=100,
        unique=True,
        blank=True,
        verbose_name=_("Slug"),
        help_text=_("Unique identifier slug for styling and programmatic reference"),
    )
    base_url = models.URLField(
        max_length=255,
        blank=True,
        default="",
        verbose_name=_("Base URL"),
        help_text=_("Base homepage URL of the marketplace (e.g. https://es.wallapop.com)"),
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name=_("Is Active"),
        help_text=_("Whether this platform is actively offered when adding listing links"),
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Display Order"),
        help_text=_("Sorting order for displaying platforms in dropdowns and lists"),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))

    class Meta:
        ordering = ["order", "name"]
        verbose_name = _("Marketplace Site")
        verbose_name_plural = _("Marketplace Sites")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug and self.name:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class ProductListingLink(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="listing_links",
        verbose_name=_("Product"),
    )
    site = models.ForeignKey(
        MarketplaceSite,
        on_delete=models.CASCADE,
        related_name="product_links",
        verbose_name=_("Marketplace Site"),
    )
    url = models.URLField(
        max_length=1000,
        verbose_name=_("Listing URL"),
        help_text=_("Direct link to the active ad on the marketplace platform"),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active Listing"),
        help_text=_("Whether this listing is currently live"),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))

    class Meta:
        ordering = ["site__order", "site__name"]
        verbose_name = _("Product Listing Link")
        verbose_name_plural = _("Product Listing Links")
        constraints = [
            models.UniqueConstraint(
                fields=["product", "site"],
                name="unique_product_site_link",
            )
        ]

    def __str__(self):
        return f"{self.site.name} - {self.product.display_title}"
