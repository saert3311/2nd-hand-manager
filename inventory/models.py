from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


class ProductStatus(models.TextChoices):
    DRAFT = "draft", _("Draft")
    AWAITING_INFO = "awaiting_info", _("Awaiting Info")
    READY = "ready", _("Ready to Publish")
    SOLD = "sold", _("Sold")
    BLOCKED = "blocked", _("Blocked")


class ClarificationCategory(models.TextChoices):
    MEASUREMENTS = "measurements", _("Measurements / Sizing")
    TAG_COMPOSITION = "tag_composition", _("Tag / Brand / Composition")
    FLAWS_CONDITION = "flaws_condition", _("Flaws / Condition / Stains")
    MATERIAL_AUTHENTICITY = "material_authenticity", _("Material / Authenticity")
    GENERAL = "general", _("General Question")


class ClarificationStatus(models.TextChoices):
    PENDING = "pending", _("Pending")
    RESOLVED = "resolved", _("Resolved")


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
    status = models.CharField(
        max_length=20,
        choices=ProductStatus.choices,
        default=ProductStatus.DRAFT,
        db_index=True,
        verbose_name=_("Status"),
        help_text=_("Current lifecycle status of the product"),
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._initial_status = self.status
        self._initial_is_sold = self.is_sold

    def save(self, *args, **kwargs):
        initial_status = getattr(self, "_initial_status", None)
        initial_is_sold = getattr(self, "_initial_is_sold", None)

        if self._state.adding:
            if self.is_sold and self.status == ProductStatus.DRAFT:
                self.status = ProductStatus.SOLD
            else:
                self.is_sold = (self.status == ProductStatus.SOLD)
        else:
            status_changed = self.status != initial_status
            is_sold_changed = self.is_sold != initial_is_sold

            if status_changed:
                self.is_sold = (self.status == ProductStatus.SOLD)
            elif is_sold_changed:
                if self.is_sold:
                    self.status = ProductStatus.SOLD
                else:
                    self.status = ProductStatus.READY
            else:
                self.is_sold = (self.status == ProductStatus.SOLD)

        if "update_fields" in kwargs and kwargs["update_fields"] is not None:
            fields = set(kwargs["update_fields"])
            fields.add("is_sold")
            fields.add("status")
            kwargs["update_fields"] = list(fields)

        super().save(*args, **kwargs)
        self._initial_status = self.status
        self._initial_is_sold = self.is_sold

    def mark_as_sold(self, price=None, commit=True):
        self.is_sold = True
        self.status = ProductStatus.SOLD
        self.sold_at = timezone.now()
        if price is not None:
            self.sale_price = price
        if commit:
            self.save(update_fields=["is_sold", "status", "sold_at", "sale_price", "updated_at"])

    def mark_as_unsold(self, commit=True):
        self.is_sold = False
        self.status = ProductStatus.READY
        self.sold_at = None
        if commit:
            self.save(update_fields=["is_sold", "status", "sold_at", "updated_at"])



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


class ProductClarification(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="clarifications",
        verbose_name=_("Product"),
    )
    category = models.CharField(
        max_length=30,
        choices=ClarificationCategory.choices,
        default=ClarificationCategory.GENERAL,
        verbose_name=_("Category"),
        help_text=_("Area of clarification"),
    )
    question = models.TextField(
        verbose_name=_("Question"),
        help_text=_("Question from manager regarding missing product details"),
    )
    asked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="asked_clarifications",
        verbose_name=_("Asked By"),
    )
    answer = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Answer"),
        help_text=_("Response from assistant"),
    )
    answered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="answered_clarifications",
        verbose_name=_("Answered By"),
    )
    status = models.CharField(
        max_length=20,
        choices=ClarificationStatus.choices,
        default=ClarificationStatus.PENDING,
        db_index=True,
        verbose_name=_("Status"),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    answered_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Answered At"))

    class Meta:
        ordering = ["status", "-created_at"]
        verbose_name = _("Product Clarification")
        verbose_name_plural = _("Product Clarifications")

    def __str__(self):
        return f"{self.get_category_display()} - {self.product.display_title}"

    def resolve(self, answer: str, answered_by=None, commit=True):
        self.answer = answer
        self.answered_by = answered_by
        self.status = ClarificationStatus.RESOLVED
        self.answered_at = timezone.now()
        if commit:
            self.save(update_fields=["answer", "answered_by", "status", "answered_at"])

