from contextvars import ContextVar
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, URLValidator
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from .middleware import get_current_user

HTTP_URL_VALIDATOR = URLValidator(
    schemes=["http", "https"],
    message=_("Enter a valid URL starting with http:// or https://."),
)


class ProductStatus(models.TextChoices):
    DRAFT = "draft", _("Draft")
    PRICE_PENDING = "price_pending", _("Price Pending")
    READY = "ready", _("Ready to Publish")
    PUBLISHED = "published", _("Published")
    AWAITING_INFO = "awaiting_info", _("Awaiting Info")
    SOLD = "sold", _("Sold")
    BLOCKED = "blocked", _("Blocked")


class SaleChannelType(models.TextChoices):
    IN_STORE = "in_store", _("In-Store / Physical Store")
    MARKETPLACE = "marketplace", _("Online Marketplace")
    OTHER = "other", _("Other / Direct Sale")


class ClarificationCategory(models.TextChoices):
    MEASUREMENTS = "measurements", _("Measurements / Sizing")
    TAG_COMPOSITION = "tag_composition", _("Tag / Brand / Composition")
    FLAWS_CONDITION = "flaws_condition", _("Flaws / Condition / Stains")
    MATERIAL_AUTHENTICITY = "material_authenticity", _("Material / Authenticity")
    GENERAL = "general", _("General Question")


class ClarificationStatus(models.TextChoices):
    PENDING = "pending", _("Pending")
    RESOLVED = "resolved", _("Resolved")


class BackupStatus(models.TextChoices):
    SUCCESS = "success", _("Success")
    FAILED = "failed", _("Failed")


class BackupTriggerType(models.TextChoices):
    SCHEDULED = "scheduled", _("Scheduled / CLI")
    MANUAL = "manual", _("Manual / Admin")


_deleting_product_pks = ContextVar("deleting_product_pks", default=frozenset())


def is_product_deleting(pk) -> bool:
    if not pk:
        return False
    return pk in _deleting_product_pks.get()


def mark_product_deleting(pk):
    current = _deleting_product_pks.get()
    return _deleting_product_pks.set(current | {pk})


def unmark_product_deleting(token):
    _deleting_product_pks.reset(token)


class ProductQuerySet(models.QuerySet):
    def delete(self):
        pks = set(self.values_list("pk", flat=True))
        current = _deleting_product_pks.get()
        token = _deleting_product_pks.set(current | pks)
        try:
            return super().delete()
        finally:
            _deleting_product_pks.reset(token)


class Product(models.Model):
    objects = ProductQuerySet.as_manager()

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
    estimated_retail_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal("0.00")),
            MaxValueValidator(Decimal("9999999.99")),
        ],
        verbose_name=_("Estimated Retail Price (€)"),
        help_text=_("Estimated original retail price when new (MSRP)"),
    )
    estimated_resale_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal("0.00")),
            MaxValueValidator(Decimal("9999999.99")),
        ],
        verbose_name=_("Estimated Resale Price (€)"),
        help_text=_("Estimated secondhand market resale value"),
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
    sold_channel_type = models.CharField(
        max_length=20,
        choices=SaleChannelType.choices,
        blank=True,
        default="",
        db_index=True,
        verbose_name=_("Sale Channel Type"),
        help_text=_("Commercial channel through which the product was sold"),
    )
    sold_marketplace = models.ForeignKey(
        "MarketplaceSite",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sold_products",
        verbose_name=_("Sold Marketplace"),
        help_text=_("Marketplace platform where the sale occurred"),
    )
    sold_channel_notes = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name=_("Sale Reference / Notes"),
        help_text=_("Optional ticket number, order ID, or buyer reference"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_products"
    )
    batch_session = models.ForeignKey(
        "IntakeBatchSession",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="products",
        verbose_name=_("Intake Batch Session"),
        help_text=_("The intake uploading session in which this product was cataloged"),
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
    def sale_channel_display(self) -> str:
        """Return human-readable, localized representation of where the item was sold."""
        if not self.is_sold and self.status != ProductStatus.SOLD:
            return ""
        if self.sold_channel_type == SaleChannelType.IN_STORE:
            return str(_("In-Store"))
        if self.sold_channel_type == SaleChannelType.MARKETPLACE:
            if self.sold_marketplace:
                return self.sold_marketplace.name
            return str(_("Marketplace"))
        if self.sold_channel_type == SaleChannelType.OTHER:
            return str(_("Other"))
        return "-"

    @property
    def primary_image(self):
        return self.images.order_by("order", "id").first()

    def compute_lifecycle_status(self) -> str:
        """
        Calculates the lifecycle status according to business precedence:
        1. SOLD if marked sold
        2. BLOCKED if administratively blocked
        3. AWAITING_INFO if pending clarifications exist
        4. PUBLISHED if any active marketplace link is attached
        5. DRAFT if no description exists
        6. PRICE_PENDING if title and description exist but price is None or <= 0
        7. READY if title, description, and price > 0 exist
        """
        if self.is_sold:
            return ProductStatus.SOLD
        if self.status == ProductStatus.BLOCKED:
            return ProductStatus.BLOCKED
        if self.pk and self.clarifications.filter(status=ClarificationStatus.PENDING).exists():
            return ProductStatus.AWAITING_INFO
        if self.pk and self.listing_links.filter(is_active=True).exists():
            return ProductStatus.PUBLISHED

        has_title = bool((self.ai_title or "").strip())
        has_description = bool((self.ai_description or "").strip())
        has_price = False
        if self.sale_price is not None:
            try:
                has_price = Decimal(str(self.sale_price)) > Decimal("0.00")
            except (ValueError, TypeError, ArithmeticError):
                has_price = False

        if not has_description:
            return ProductStatus.DRAFT
        if has_title and has_description and not has_price:
            return ProductStatus.PRICE_PENDING
        if has_title and has_description and has_price:
            return ProductStatus.READY

        return ProductStatus.DRAFT

    def sync_lifecycle_status(self, user=None, trigger=None, notes=None, commit=True):
        computed = self.compute_lifecycle_status()
        if self.status != computed:
            self.status = computed
            self.is_sold = (computed == ProductStatus.SOLD)
            if user is not None:
                self._changed_by = user
            if trigger is not None:
                self._status_trigger = trigger
            if notes is not None:
                self._status_notes = notes
            if commit:
                self.save(update_fields=["status", "is_sold"])
        return self.status

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._initial_status = self.status
        self._initial_is_sold = self.is_sold
        self._changed_by = None
        self._status_trigger = None
        self._status_notes = None

    def _infer_status_trigger(self, from_status: str, to_status: str) -> str:
        if to_status == ProductStatus.SOLD:
            return "marked_sold"
        if from_status == ProductStatus.SOLD:
            return "reverted_unsold"
        if to_status == ProductStatus.BLOCKED:
            return "blocked"
        if from_status == ProductStatus.BLOCKED:
            return "unblocked"
        if to_status == ProductStatus.AWAITING_INFO:
            return "clarification_opened"
        if from_status == ProductStatus.AWAITING_INFO:
            return "clarification_resolved"
        if to_status == ProductStatus.PUBLISHED:
            return "marketplace_link_added"
        if from_status == ProductStatus.PUBLISHED and to_status != ProductStatus.SOLD:
            return "marketplace_link_removed"
        if to_status == ProductStatus.PRICE_PENDING:
            return "description_added"
        if to_status == ProductStatus.READY:
            return "price_assigned" if from_status == ProductStatus.PRICE_PENDING else "ready"
        if to_status == ProductStatus.DRAFT:
            return "draft"
        return "status_updated"

    def save(self, *args, changed_by=None, trigger=None, notes=None, **kwargs):
        initial_status = getattr(self, "_initial_status", None)
        initial_is_sold = getattr(self, "_initial_is_sold", None)
        is_adding = self._state.adding

        if is_adding:
            if self.is_sold or self.status == ProductStatus.SOLD:
                self.status = ProductStatus.SOLD
                self.is_sold = True
            elif self.status == ProductStatus.BLOCKED:
                self.is_sold = False
            elif self.status == ProductStatus.AWAITING_INFO:
                self.is_sold = False
            else:
                self.status = self.compute_lifecycle_status()
                self.is_sold = (self.status == ProductStatus.SOLD)
        else:
            status_changed = self.status != initial_status
            is_sold_changed = self.is_sold != initial_is_sold

            if status_changed:
                if self.status == ProductStatus.SOLD:
                    self.is_sold = True
                elif self.status in (ProductStatus.BLOCKED, ProductStatus.AWAITING_INFO):
                    self.is_sold = False
                else:
                    self.is_sold = False
                    self.status = self.compute_lifecycle_status()
            elif is_sold_changed:
                if self.is_sold:
                    self.status = ProductStatus.SOLD
                else:
                    self.status = self.compute_lifecycle_status()
            else:
                if self.status not in (ProductStatus.SOLD, ProductStatus.BLOCKED, ProductStatus.AWAITING_INFO):
                    self.status = self.compute_lifecycle_status()
                self.is_sold = (self.status == ProductStatus.SOLD)

        if "update_fields" in kwargs and kwargs["update_fields"] is not None:
            fields = set(kwargs["update_fields"])
            fields.add("is_sold")
            fields.add("status")
            kwargs["update_fields"] = list(fields)

        self._previous_status = initial_status
        super().save(*args, **kwargs)

        from_status = None if is_adding else initial_status
        to_status = self.status

        if is_adding or from_status != to_status:
            effective_user = (
                changed_by
                or getattr(self, "_changed_by", None)
                or (self.created_by if is_adding else None)
                or get_current_user()
            )
            effective_trigger = (
                trigger
                or getattr(self, "_status_trigger", None)
                or ("intake" if is_adding else self._infer_status_trigger(from_status, to_status))
            )
            effective_notes = (
                notes
                or getattr(self, "_status_notes", None)
                or ""
            )
            if not effective_notes and to_status == ProductStatus.SOLD:
                note_parts = []
                if self.sold_channel_type:
                    note_parts.append(f"Sold via {self.sale_channel_display}")
                else:
                    note_parts.append("Marked sold")
                if self.sale_price is not None:
                    try:
                        note_parts.append(f"for €{Decimal(str(self.sale_price)):.2f}")
                    except Exception:
                        note_parts.append(f"for €{self.sale_price}")
                if self.sold_channel_notes:
                    note_parts.append(f"({self.sold_channel_notes})")
                effective_notes = " ".join(note_parts)
            try:
                log_status_change(
                    product=self,
                    from_status=from_status,
                    to_status=to_status,
                    user=effective_user,
                    trigger=effective_trigger,
                    notes=effective_notes,
                )
            except Exception:
                pass

        self._initial_status = self.status
        self._initial_is_sold = self.is_sold
        self._changed_by = None
        self._status_trigger = None
        self._status_notes = None

    def mark_as_sold(
        self,
        price=None,
        user=None,
        channel_type=None,
        marketplace=None,
        notes=None,
        commit=True,
    ):
        self.is_sold = True
        self.status = ProductStatus.SOLD
        self.sold_at = timezone.now()
        if price is not None:
            self.sale_price = price
        if channel_type is not None:
            self.sold_channel_type = channel_type
        if marketplace is not None:
            self.sold_marketplace = marketplace
        if notes is not None:
            self.sold_channel_notes = notes
        if user is not None:
            self._changed_by = user
        self._status_trigger = "marked_sold"

        status_note_parts = []
        if self.sold_channel_type:
            status_note_parts.append(f"Sold via {self.sale_channel_display}")
        else:
            status_note_parts.append("Marked sold")
        if self.sale_price is not None:
            try:
                status_note_parts.append(f"for €{Decimal(str(self.sale_price)):.2f}")
            except Exception:
                status_note_parts.append(f"for €{self.sale_price}")
        if self.sold_channel_notes:
            status_note_parts.append(f"({self.sold_channel_notes})")
        self._status_notes = " ".join(status_note_parts)

        if commit:
            self.save(
                update_fields=[
                    "is_sold",
                    "status",
                    "sold_at",
                    "sale_price",
                    "sold_channel_type",
                    "sold_marketplace",
                    "sold_channel_notes",
                    "updated_at",
                ]
            )
    def mark_as_unsold(self, user=None, commit=True):
        self.is_sold = False
        self.status = self.compute_lifecycle_status()
        self.sold_at = None
        self.sold_channel_type = ""
        self.sold_marketplace = None
        self.sold_channel_notes = ""
        if user is not None:
            self._changed_by = user
        self._status_trigger = "reverted_unsold"
        if commit:
            self.save(
                update_fields=[
                    "is_sold",
                    "status",
                    "sold_at",
                    "sold_channel_type",
                    "sold_marketplace",
                    "sold_channel_notes",
                    "updated_at",
                ]
            )

    def delete(self, *args, **kwargs):
        token = None
        if self.pk:
            token = mark_product_deleting(self.pk)
        try:
            return super().delete(*args, **kwargs)
        finally:
            if token is not None:
                unmark_product_deleting(token)




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
        validators=[HTTP_URL_VALIDATOR],
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
        validators=[HTTP_URL_VALIDATOR],
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
        max_length=2000,
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
        max_length=3000,
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._initial_status = self.status

    def __str__(self):
        return f"{self.get_category_display()} - {self.product.display_title}"

    def save(self, *args, **kwargs):
        self._previous_status = getattr(self, "_initial_status", None)
        super().save(*args, **kwargs)
        self._initial_status = self.status

    def resolve(self, answer: str, answered_by=None, commit=True):
        self.answer = answer
        self.answered_by = answered_by
        self.status = ClarificationStatus.RESOLVED
        self.answered_at = timezone.now()
        if commit:
            self.save(update_fields=["answer", "answered_by", "status", "answered_at"])


@receiver(post_save, sender=ProductClarification)
def sync_product_on_clarification_save(sender, instance, created=False, **kwargs):
    if kwargs.get("raw", False):
        return
    product = instance.product
    if product.is_sold or product.status == ProductStatus.SOLD:
        return
    if instance.status == ClarificationStatus.PENDING:
        if product.status != ProductStatus.AWAITING_INFO:
            product.status = ProductStatus.AWAITING_INFO
            notes = f"Clarification opened: {instance.question[:60]}" if instance.question else ""
            product.save(
                update_fields=["status"],
                changed_by=instance.asked_by,
                trigger="clarification_opened",
                notes=notes,
            )
        if created and getattr(settings, "PUSH_NOTIFICATIONS_LIVE_SIGNALS", False):
            try:
                from .permissions import ROLE_ASSISTANT
                from .services.push_service import send_push_to_group

                send_push_to_group(
                    group_name=ROLE_ASSISTANT,
                    title=str(_("❓ New Doubt on %(title)s") % {"title": product.display_title}),
                    body=(instance.question or "")[:140],
                    url=f"/products/{product.pk}/",
                    tag=f"clarification-product-{product.pk}",
                )
            except Exception:
                pass
    elif instance.status == ClarificationStatus.RESOLVED:
        has_pending = product.clarifications.filter(status=ClarificationStatus.PENDING).exists()
        if not has_pending and product.status == ProductStatus.AWAITING_INFO:
            product.status = product.compute_lifecycle_status()
            notes = f"Clarification resolved: {instance.question[:60]}" if instance.question else ""
            product.save(
                update_fields=["status", "is_sold"],
                changed_by=instance.answered_by,
                trigger="clarification_resolved",
                notes=notes,
            )
        was_pending = getattr(instance, "_previous_status", None) == ClarificationStatus.PENDING
        if (created or was_pending) and getattr(settings, "PUSH_NOTIFICATIONS_LIVE_SIGNALS", False):
            try:
                from .permissions import ROLE_MANAGER
                from .services.push_service import send_push_to_group

                send_push_to_group(
                    group_name=ROLE_MANAGER,
                    title=str(_("✅ Doubt Answered: %(title)s") % {"title": product.display_title}),
                    body=(instance.answer or str(_("Assistant provided clarification details.")))[:140],
                    url=f"/products/{product.pk}/",
                    tag=f"clarification-resolved-{product.pk}",
                )
            except Exception:
                pass


@receiver(post_save, sender=Product)
def notify_managers_on_product_lifecycle_save(sender, instance, created=False, **kwargs):
    if kwargs.get("raw", False):
        return

    # Sourcing session batch grouping for newly created draft uploads
    if created and instance.status == ProductStatus.DRAFT:
        try:
            from .services.intake_batch_service import (
                process_pending_intake_batches,
                record_product_intake,
            )

            record_product_intake(product=instance, assistant=instance.created_by)
            if getattr(settings, "PUSH_NOTIFICATIONS_LIVE_SIGNALS", False):
                process_pending_intake_batches()
        except Exception:
            pass
        return

    if not getattr(settings, "PUSH_NOTIFICATIONS_LIVE_SIGNALS", False):
        return

    previous_status = getattr(instance, "_previous_status", None)
    try:
        from .permissions import ROLE_MANAGER
        from .services.push_service import send_push_to_group

        if instance.status == ProductStatus.PRICE_PENDING and (
            created or previous_status != ProductStatus.PRICE_PENDING
        ):
            send_push_to_group(
                group_name=ROLE_MANAGER,
                title=str(_("🏷️ Price Needed: %(title)s") % {"title": instance.display_title}),
                body=str(_("Title and description are ready — waiting for sale price (€).")),
                url=f"/products/{instance.pk}/",
                tag=f"product-price-pending-{instance.pk}",
            )
    except Exception:
        pass


@receiver(post_delete, sender=ProductClarification)
def sync_product_on_clarification_delete(sender, instance, **kwargs):
    if kwargs.get("raw", False):
        return
    if is_product_deleting(instance.product_id):
        return
    try:
        product = instance.product
    except Product.DoesNotExist:
        return
    if product.is_sold or product.status == ProductStatus.SOLD:
        return
    has_pending = product.clarifications.filter(status=ClarificationStatus.PENDING).exists()
    if not has_pending and product.status == ProductStatus.AWAITING_INFO:
        product.status = product.compute_lifecycle_status()
        notes = f"Clarification deleted: {instance.question[:60]}" if instance.question else ""
        product.save(
            update_fields=["status", "is_sold"],
            trigger="clarification_resolved",
            notes=notes,
        )


@receiver(post_save, sender=ProductListingLink)
def sync_product_on_listing_link_save(sender, instance, created=False, **kwargs):
    if kwargs.get("raw", False):
        return
    product = instance.product
    if product.is_sold or product.status in (ProductStatus.SOLD, ProductStatus.BLOCKED, ProductStatus.AWAITING_INFO):
        return
    site_name = instance.site.name if instance.site else "Marketplace"
    action = "added" if created else "updated"
    trigger = "marketplace_link_added" if instance.is_active else "marketplace_link_removed"
    notes = f"Marketplace link {action} ({site_name})"
    product.sync_lifecycle_status(trigger=trigger, notes=notes)


@receiver(post_delete, sender=ProductListingLink)
def sync_product_on_listing_link_delete(sender, instance, **kwargs):
    if kwargs.get("raw", False):
        return
    if is_product_deleting(instance.product_id):
        return
    try:
        product = instance.product
    except Product.DoesNotExist:
        return
    if product.is_sold or product.status in (ProductStatus.SOLD, ProductStatus.BLOCKED, ProductStatus.AWAITING_INFO):
        return
    site_name = instance.site.name if instance.site else "Marketplace"
    notes = f"Marketplace link deleted ({site_name})"
    product.sync_lifecycle_status(trigger="marketplace_link_removed", notes=notes)


class DatabaseBackupLog(models.Model):
    filename = models.CharField(
        max_length=255,
        verbose_name=_("Filename"),
        help_text=_("Name of generated backup archive (e.g. db_20261014_030000.sqlite3.gz)"),
    )
    remote_path = models.CharField(
        max_length=500,
        verbose_name=_("Remote Path"),
        help_text=_("Storage object path in OCI Object Storage bucket or local path"),
    )
    file_size = models.BigIntegerField(
        default=0,
        verbose_name=_("File Size (Bytes)"),
        help_text=_("Size of backup archive in bytes"),
    )
    duration_seconds = models.FloatField(
        default=0.0,
        verbose_name=_("Duration (Seconds)"),
        help_text=_("Total backup execution time in seconds"),
    )
    status = models.CharField(
        max_length=20,
        choices=BackupStatus.choices,
        default=BackupStatus.SUCCESS,
        db_index=True,
        verbose_name=_("Status"),
    )
    trigger_type = models.CharField(
        max_length=20,
        choices=BackupTriggerType.choices,
        default=BackupTriggerType.SCHEDULED,
        verbose_name=_("Trigger Type"),
    )
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="database_backups",
        verbose_name=_("Triggered By"),
        help_text=_("User who initiated manual backup (null for scheduled/CLI runs)"),
    )
    error_message = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Error Message"),
        help_text=_("Detailed exception trace or error description if backup failed"),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name=_("Created At"),
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Database Backup Log")
        verbose_name_plural = _("Database Backup Logs")

    def __str__(self):
        created_str = self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else ""
        return f"{self.filename or _('Backup')} - {self.get_status_display()} ({created_str})"

    @property
    def file_size_display(self) -> str:
        """Return human-readable formatted file size."""
        size = self.file_size
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.2f} GB"


class PushSubscription(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
        verbose_name=_("User"),
    )
    endpoint = models.URLField(
        max_length=1000,
        unique=True,
        validators=[HTTP_URL_VALIDATOR],
        verbose_name=_("Push Endpoint"),
        help_text=_("Unique browser push service endpoint URL"),
    )
    p256dh = models.CharField(
        max_length=255,
        verbose_name=_("P-256DH Key"),
        help_text=_("Client public encryption key (Base64URL)"),
    )
    auth = models.CharField(
        max_length=255,
        verbose_name=_("Auth Secret"),
        help_text=_("Client authentication secret (Base64URL)"),
    )
    user_agent = models.CharField(
        max_length=500,
        blank=True,
        default="",
        verbose_name=_("User Agent"),
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name=_("Is Active"),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = _("Push Subscription")
        verbose_name_plural = _("Push Subscriptions")

    def __str__(self):
        return f"{self.user.username} ({self.endpoint[:40]}...)"


class ProductStatusLog(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="status_logs",
        verbose_name=_("Product"),
        help_text=_("The product whose state changed"),
    )
    from_status = models.CharField(
        max_length=20,
        choices=ProductStatus.choices,
        null=True,
        blank=True,
        verbose_name=_("From Status"),
        help_text=_("Previous lifecycle status (null for initial creation)"),
    )
    to_status = models.CharField(
        max_length=20,
        choices=ProductStatus.choices,
        verbose_name=_("To Status"),
        help_text=_("New lifecycle status"),
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="status_changes",
        verbose_name=_("Changed By"),
        help_text=_("User who initiated the change (null if automated system event)"),
    )
    trigger = models.CharField(
        max_length=50,
        blank=True,
        default="",
        verbose_name=_("Trigger / Reason"),
        help_text=_("Machine code for event trigger (e.g. intake, staging_update, clarification_opened, etc.)"),
    )
    notes = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Notes / Description"),
        help_text=_("Human-readable explanation or contextual details"),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name=_("Timestamp"),
        help_text=_("Exact time the state change was recorded"),
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Product Status Log")
        verbose_name_plural = _("Product Status Logs")

    def __str__(self):
        from_s = self.from_status or _("New")
        return f"{self.product_id}: {from_s} -> {self.to_status} ({self.created_at:%Y-%m-%d %H:%M})"


def log_status_change(product, from_status, to_status, user=None, trigger="", notes=""):
    """
    Creates an immutable audit log entry for a product lifecycle status change.
    Ignores no-op transitions where from_status == to_status on existing products.
    """
    if product.pk and from_status == to_status:
        return None
    acting_user = user if (user and getattr(user, "is_authenticated", False)) else None
    return ProductStatusLog.objects.create(
        product=product,
        from_status=from_status,
        to_status=to_status,
        changed_by=acting_user,
        trigger=trigger or "",
        notes=notes or "",
    )


class IntakeBatchSession(models.Model):
    assistant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="intake_batches",
        verbose_name=_("Assistant"),
        help_text=_("The assistant who uploaded products during this session"),
    )
    started_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("Started At"),
        help_text=_("Timestamp when the first product of the batch was uploaded"),
    )
    last_activity_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name=_("Last Activity At"),
        help_text=_("Timestamp of the most recent product upload in this session"),
    )
    product_count = models.PositiveIntegerField(
        default=1,
        verbose_name=_("Product Count"),
        help_text=_("Total number of products cataloged during this batch session"),
    )
    is_notified = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_("Is Notified"),
        help_text=_("Whether the consolidated manager push notification has been sent"),
    )
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Closed At"),
        help_text=_("Timestamp when the session was finalized and marked closed"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_activity_at"]
        verbose_name = _("Intake Batch Session")
        verbose_name_plural = _("Intake Batch Sessions")
        indexes = [
            models.Index(fields=["is_notified", "last_activity_at"]),
            models.Index(fields=["assistant", "is_notified"]),
        ]

    def __str__(self):
        assistant_name = self.assistant.get_full_name() or self.assistant.username
        status_label = _("Notified") if self.is_notified else _("Pending")
        return f"Batch #{self.pk} by {assistant_name} ({self.product_count} items) - {status_label}"


