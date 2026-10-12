from functools import update_wrapper

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import GroupAdmin
from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import (
    AIPromptConfiguration,
    MarketplaceSite,
    Product,
    ProductClarification,
    ProductImage,
    ProductListingLink,
)
from .permissions import ROLE_ASSISTANT, ROLE_MANAGER, is_assistant, is_manager

User = get_user_model()


class ManagerAdminSite(admin.AdminSite):
    site_header = _("2ndHand Staging - Administration")
    site_title = _("2ndHand Staging Admin")
    index_title = _("Store Administration & User Management")

    def has_permission(self, request):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def admin_view(self, view, cacheable=False):
        parent_func = super().admin_view(view, cacheable=cacheable)

        def inner(request, *args, **kwargs):
            if not self.has_permission(request):
                if request.user.is_authenticated:
                    raise PermissionDenied(_("Manager privileges required to access administration."))
            return parent_func(request, *args, **kwargs)

        return update_wrapper(inner, view)


# Global admin_site instance
admin_site = ManagerAdminSite(name="admin")
admin.site = admin_site
manager_admin_site = admin_site


class RoleListFilter(admin.SimpleListFilter):
    title = _("Role")
    parameter_name = "role"

    def lookups(self, request, model_admin):
        return [
            ("superuser", _("Superuser")),
            ("manager", _("Manager")),
            ("assistant", _("Assistant")),
        ]

    def queryset(self, request, queryset):
        if self.value() == "superuser":
            return queryset.filter(is_superuser=True)
        if self.value() == "manager":
            return queryset.filter(
                Q(is_superuser=True) | Q(is_staff=True) | Q(groups__name=ROLE_MANAGER)
            ).distinct()
        if self.value() == "assistant":
            return (
                queryset.filter(groups__name=ROLE_ASSISTANT, is_superuser=False, is_staff=False)
                .exclude(groups__name=ROLE_MANAGER)
                .distinct()
            )
        return queryset


@admin.register(User, site=admin_site)
class CustomUserAdmin(DefaultUserAdmin):
    list_display = (
        "username",
        "email",
        "role_badge",
        "cataloged_items_count",
        "is_active",
        "date_joined",
    )
    list_filter = (RoleListFilter, "is_active", "date_joined")
    actions = ["make_assistant", "make_manager", "deactivate_users", "activate_users"]

    def has_module_permission(self, request):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def has_view_permission(self, request, obj=None):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def has_change_permission(self, request, obj=None):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def has_add_permission(self, request):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def has_delete_permission(self, request, obj=None):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(cataloged_count=Count("created_products"))

    def role_badge(self, obj):
        if obj.is_superuser:
            return format_html(
                '<span style="background-color: #f3e8ff; color: #6b21a8; font-weight: 700; '
                'padding: 2px 8px; border-radius: 9999px; font-size: 11px;">{}</span>',
                _("Superuser"),
            )
        if is_manager(obj):
            return format_html(
                '<span style="background-color: #dcfce7; color: #15803d; font-weight: 700; '
                'padding: 2px 8px; border-radius: 9999px; font-size: 11px;">{}</span>',
                _("Manager"),
            )
        if is_assistant(obj):
            return format_html(
                '<span style="background-color: #dbeafe; color: #1d4ed8; font-weight: 700; '
                'padding: 2px 8px; border-radius: 9999px; font-size: 11px;">{}</span>',
                _("Assistant"),
            )
        return format_html(
            '<span style="background-color: #f1f5f9; color: #64748b; font-weight: 600; '
            'padding: 2px 8px; border-radius: 9999px; font-size: 11px;">{}</span>',
            _("None"),
        )

    role_badge.short_description = _("Role")

    def cataloged_items_count(self, obj):
        count = getattr(obj, "cataloged_count", 0)
        if count > 0:
            url = reverse("admin:inventory_product_changelist") + f"?created_by__id__exact={obj.id}"
            return format_html('<a href="{}" style="font-weight: 600;">{}</a>', url, count)
        return "0"

    cataloged_items_count.short_description = _("Cataloged Items")
    cataloged_items_count.admin_order_field = "cataloged_count"

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        user = form.instance
        if user.groups.filter(name=ROLE_MANAGER).exists() or user.is_superuser:
            if not user.is_staff:
                user.is_staff = True
                user.save(update_fields=["is_staff"])
        elif user.groups.filter(name=ROLE_ASSISTANT).exists():
            if user.is_staff and not user.is_superuser:
                user.is_staff = False
                user.save(update_fields=["is_staff"])

    @admin.action(description=_("Assign Assistant role to selected users"))
    def make_assistant(self, request, queryset):
        asst_group, _created = Group.objects.get_or_create(name=ROLE_ASSISTANT)
        mgr_group, _created2 = Group.objects.get_or_create(name=ROLE_MANAGER)
        count = 0
        for user in queryset:
            user.groups.remove(mgr_group)
            user.groups.add(asst_group)
            if not user.is_superuser:
                user.is_staff = False
            user.save()
            count += 1
        self.message_user(
            request,
            _("Successfully assigned Assistant role to %(count)d user(s).") % {"count": count},
        )

    @admin.action(description=_("Assign Manager role to selected users"))
    def make_manager(self, request, queryset):
        mgr_group, _created = Group.objects.get_or_create(name=ROLE_MANAGER)
        count = 0
        for user in queryset:
            user.groups.add(mgr_group)
            user.is_staff = True
            user.save()
            count += 1
        self.message_user(
            request,
            _("Successfully assigned Manager role to %(count)d user(s).") % {"count": count},
        )

    @admin.action(description=_("Deactivate selected users (Revoke access, preserve items)"))
    def deactivate_users(self, request, queryset):
        updated = queryset.exclude(id=request.user.id).update(is_active=False)
        self.message_user(
            request,
            _("Successfully deactivated %(count)d user(s). Access revoked while preserving product attributions.")
            % {"count": updated},
        )

    @admin.action(description=_("Activate selected users"))
    def activate_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            _("Successfully activated %(count)d user(s).") % {"count": updated},
        )


admin_site.register(Group, GroupAdmin)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ("image", "order", "image_preview", "created_at")
    readonly_fields = ("image_preview", "created_at")

    def image_preview(self, instance):
        if instance.image:
            return format_html(
                '<img src="{}" style="max-height: 80px; max-width: 120px; border-radius: 4px; object-fit: cover;" />',
                instance.image.url,
            )
        return "-"

    image_preview.short_description = _("Preview")


class ProductListingLinkInline(admin.TabularInline):
    model = ProductListingLink
    extra = 1
    fields = ("site", "url", "is_active", "created_at", "updated_at")
    readonly_fields = ("created_at", "updated_at")


class ProductClarificationInline(admin.TabularInline):
    model = ProductClarification
    extra = 0
    fields = ("category", "question", "asked_by", "answer", "answered_by", "status", "created_at", "answered_at")
    readonly_fields = ("created_at", "answered_at")


@admin.register(Product, site=admin_site)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "display_title",
        "status",
        "sale_price_display",
        "is_sold",
        "images_count",
        "created_by",
        "created_at",
    )
    list_filter = ("status", "is_sold", "created_at")
    search_fields = ("ai_title", "raw_note", "ai_description")
    inlines = [ProductImageInline, ProductListingLinkInline, ProductClarificationInline]
    readonly_fields = ("created_at", "updated_at", "sold_at")

    def has_module_permission(self, request):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def has_view_permission(self, request, obj=None):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def has_change_permission(self, request, obj=None):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def has_add_permission(self, request):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def has_delete_permission(self, request, obj=None):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def sale_price_display(self, obj):
        if obj.sale_price is not None:
            return f"€{obj.sale_price:.2f}"
        return "-"

    sale_price_display.short_description = _("Price (€)")

    def images_count(self, obj):
        return obj.images.count()

    images_count.short_description = _("Images")


@admin.register(ProductImage, site=admin_site)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "order", "image", "created_at")
    list_filter = ("created_at",)
    search_fields = ("product__ai_title", "product__raw_note")

    def has_module_permission(self, request):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def has_view_permission(self, request, obj=None):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def has_change_permission(self, request, obj=None):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def has_add_permission(self, request):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def has_delete_permission(self, request, obj=None):
        return bool(request.user and request.user.is_active and is_manager(request.user))


@admin.register(AIPromptConfiguration, site=admin_site)
class AIPromptConfigurationAdmin(admin.ModelAdmin):
    list_display = (
        "language",
        "model_name",
        "temperature",
        "is_active_badge",
        "updated_at",
    )
    list_filter = ("is_active", "language")
    search_fields = ("model_name", "system_instruction")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (
            _("Model Parameters"),
            {
                "fields": ("language", "model_name", "temperature"),
                "description": _(
                    "Specify the Gemini model identifier (e.g. gemini-2.5-flash, gemini-2.5-pro) "
                    "and sampling temperature (0.0 = deterministic, 1.0 = creative)."
                ),
            },
        ),
        (
            _("Copywriting & Prompt Instructions"),
            {
                "fields": ("system_instruction",),
                "description": _(
                    "Define marketplace instructions, selling tone, and format guidelines. "
                    "Note: The system automatically appends assistant field notes and enforces "
                    "the structured title/description output schema."
                ),
            },
        ),
        (
            _("Status & Timestamps"),
            {
                "fields": ("is_active", "created_at", "updated_at"),
            },
        ),
    )

    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="background-color: #d1fae5; color: #065f46; font-weight: 600; padding: 2px 8px; border-radius: 9999px;">{}</span>',
                _("Active"),
            )
        return format_html(
            '<span style="background-color: #f3f4f6; color: #4b5563; padding: 2px 8px; border-radius: 9999px;">{}</span>',
            _("Inactive"),
        )

    is_active_badge.short_description = _("Status")

    def has_module_permission(self, request):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def has_view_permission(self, request, obj=None):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def has_change_permission(self, request, obj=None):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def has_add_permission(self, request):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def has_delete_permission(self, request, obj=None):
        return bool(request.user and request.user.is_active and is_manager(request.user))


@admin.register(MarketplaceSite, site=admin_site)
class MarketplaceSiteAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "base_url",
        "is_active",
        "order",
        "links_count",
        "updated_at",
    )
    list_editable = ("is_active", "order")
    list_filter = ("is_active",)
    search_fields = ("name", "slug", "base_url")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")

    def links_count(self, obj):
        return obj.product_links.count()

    links_count.short_description = _("Linked Products")

    def has_module_permission(self, request):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def has_view_permission(self, request, obj=None):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def has_change_permission(self, request, obj=None):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def has_add_permission(self, request):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def has_delete_permission(self, request, obj=None):
        return bool(request.user and request.user.is_active and is_manager(request.user))


@admin.register(ProductListingLink, site=admin_site)
class ProductListingLinkAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "site", "url", "is_active", "created_at")
    list_filter = ("site", "is_active", "created_at")
    search_fields = ("product__ai_title", "product__raw_note", "url")
    readonly_fields = ("created_at", "updated_at")

    def has_module_permission(self, request):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def has_view_permission(self, request, obj=None):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def has_change_permission(self, request, obj=None):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def has_add_permission(self, request):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def has_delete_permission(self, request, obj=None):
        return bool(request.user and request.user.is_active and is_manager(request.user))


@admin.register(ProductClarification, site=admin_site)
class ProductClarificationAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "category", "status", "asked_by", "answered_by", "created_at")
    list_filter = ("category", "status", "created_at")
    search_fields = ("product__ai_title", "product__raw_note", "question", "answer")
    readonly_fields = ("created_at", "answered_at")

    def has_module_permission(self, request):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def has_view_permission(self, request, obj=None):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def has_change_permission(self, request, obj=None):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def has_add_permission(self, request):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def has_delete_permission(self, request, obj=None):
        return bool(request.user and request.user.is_active and is_manager(request.user))


