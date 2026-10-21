from functools import update_wrapper

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import GroupAdmin
from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .forms import TurnstileAdminAuthenticationForm
from .models import (
    AIPromptConfiguration,
    BackupStatus,
    BackupTriggerType,
    DatabaseBackupLog,
    IntakeBatchSession,
    MarketplaceSite,
    Product,
    ProductClarification,
    ProductImage,
    ProductListingLink,
    ProductStatus,
    ProductStatusLog,
    PushSubscription,
)
from .permissions import ROLE_ASSISTANT, ROLE_MANAGER, is_assistant, is_manager
from .services.backup_service import backup_database

User = get_user_model()


class ManagerAdminSite(admin.AdminSite):
    site_header = _("2ndHand Staging - Administration")
    site_title = _("2ndHand Staging Admin")
    index_title = _("Store Administration & User Management")
    login_form = TurnstileAdminAuthenticationForm

    def login(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context.update({
            "TURNSTILE_SITE_KEY": getattr(settings, "TURNSTILE_SITE_KEY", ""),
            "TURNSTILE_ENABLED": getattr(settings, "TURNSTILE_ENABLED", False),
        })
        return super().login(request, extra_context=extra_context)

    def each_context(self, request):
        context = super().each_context(request)
        if request.user and request.user.is_authenticated and is_manager(request.user):
            try:
                latest_backup = DatabaseBackupLog.objects.order_by("-created_at").first()
                if latest_backup and latest_backup.status == BackupStatus.FAILED:
                    context["latest_backup_failed"] = True
                    context["latest_backup_error"] = latest_backup.error_message
                    context["latest_backup_date"] = latest_backup.created_at
            except Exception:
                pass
        return context

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

class CustomGroupAdmin(GroupAdmin):
    list_display = ("name", "user_count")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(num_users=Count("user"))

    @admin.display(description=_("Members Count"), ordering="num_users")
    def user_count(self, obj):
        return obj.num_users

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


admin_site.register(Group, CustomGroupAdmin)


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


def format_status_badge(status_val):
    colors = {
        "draft": ("#f1f5f9", "#475569"),
        "price_pending": ("#fef3c7", "#92400e"),
        "ready": ("#dcfce7", "#166534"),
        "published": ("#dbeafe", "#1e40af"),
        "awaiting_info": ("#fef9c3", "#854d0e"),
        "blocked": ("#ffe4e6", "#9f1239"),
        "sold": ("#f3e8ff", "#6b21a8"),
    }
    bg, fg = colors.get(status_val, ("#f1f5f9", "#334155"))
    label = dict(ProductStatus.choices).get(status_val, status_val)
    return format_html(
        '<span style="background-color: {}; color: {}; padding: 2px 8px; border-radius: 9999px; font-weight: 600; font-size: 11px; text-transform: uppercase;">{}</span>',
        bg,
        fg,
        label,
    )


class ProductClarificationInline(admin.TabularInline):
    model = ProductClarification
    extra = 0
    fields = ("category", "question", "asked_by", "answer", "answered_by", "status", "created_at", "answered_at")
    readonly_fields = ("created_at", "answered_at")


class ProductStatusLogInline(admin.TabularInline):
    model = ProductStatusLog
    extra = 0
    can_delete = False
    fields = ("created_at", "from_status_badge", "to_status_badge", "changed_by", "trigger", "notes")
    readonly_fields = ("created_at", "from_status_badge", "to_status_badge", "changed_by", "trigger", "notes")

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def from_status_badge(self, instance):
        if not instance.from_status:
            return format_html('<span style="color: #64748b; font-style: italic;">{}</span>', _("New"))
        return format_status_badge(instance.from_status)

    from_status_badge.short_description = _("From Status")

    def to_status_badge(self, instance):
        return format_status_badge(instance.to_status)

    to_status_badge.short_description = _("To Status")


@admin.register(Product, site=admin_site)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "display_title",
        "status",
        "sale_price_display",
        "estimated_resale_price_display",
        "estimated_retail_price_display",
        "is_sold",
        "images_count",
        "created_by",
        "created_at",
    )
    list_filter = ("status", "is_sold", "created_at")
    search_fields = ("ai_title", "raw_note", "ai_description")
    inlines = [ProductImageInline, ProductListingLinkInline, ProductClarificationInline, ProductStatusLogInline]
    readonly_fields = ("created_at", "updated_at", "sold_at", "batch_session")
    list_select_related = ("created_by", "batch_session")

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

    def estimated_resale_price_display(self, obj):
        if obj.estimated_resale_price is not None:
            return f"€{obj.estimated_resale_price:.2f}"
        return "-"

    estimated_resale_price_display.short_description = _("Est. Resale (€)")

    def estimated_retail_price_display(self, obj):
        if obj.estimated_retail_price is not None:
            return f"€{obj.estimated_retail_price:.2f}"
        return "-"

    estimated_retail_price_display.short_description = _("Est. Retail (€)")

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


@admin.register(DatabaseBackupLog, site=admin_site)
class DatabaseBackupLogAdmin(admin.ModelAdmin):
    list_display = (
        "filename",
        "status_badge",
        "file_size_display",
        "duration_seconds_display",
        "trigger_type_badge",
        "triggered_by",
        "created_at",
    )
    list_filter = ("status", "trigger_type", "created_at")
    search_fields = ("filename", "remote_path", "error_message", "triggered_by__username")
    readonly_fields = (
        "filename",
        "remote_path",
        "file_size",
        "duration_seconds",
        "status",
        "trigger_type",
        "triggered_by",
        "error_message",
        "created_at",
    )
    change_list_template = "admin/inventory/databasebackuplog/change_list.html"

    def status_badge(self, obj):
        if obj.status == BackupStatus.SUCCESS:
            return format_html(
                '<span style="background-color: #d1fae5; color: #065f46; font-weight: 600; padding: 2px 8px; border-radius: 9999px;">{}</span>',
                obj.get_status_display(),
            )
        return format_html(
            '<span style="background-color: #fee2e2; color: #991b1b; font-weight: 600; padding: 2px 8px; border-radius: 9999px;">{}</span>',
            obj.get_status_display(),
        )

    status_badge.short_description = _("Status")

    def trigger_type_badge(self, obj):
        bg = "#e0e7ff" if obj.trigger_type == BackupTriggerType.MANUAL else "#f3f4f6"
        color = "#3730a3" if obj.trigger_type == BackupTriggerType.MANUAL else "#4b5563"
        return format_html(
            '<span style="background-color: {}; color: {}; padding: 2px 8px; border-radius: 9999px; font-size: 12px;">{}</span>',
            bg,
            color,
            obj.get_trigger_type_display(),
        )

    trigger_type_badge.short_description = _("Trigger")

    def duration_seconds_display(self, obj):
        return f"{obj.duration_seconds:.2f}s"

    duration_seconds_display.short_description = _("Duration")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "trigger-backup/",
                self.admin_site.admin_view(self.trigger_backup_view),
                name="inventory_databasebackuplog_trigger_backup",
            ),
        ]
        return custom_urls + urls

    def trigger_backup_view(self, request):
        if not self.has_module_permission(request):
            raise PermissionDenied(_("Manager privileges required to trigger backups."))

        if request.method == "POST":
            log = backup_database(
                trigger_type=BackupTriggerType.MANUAL,
                triggered_by=request.user,
            )
            if log.status == BackupStatus.SUCCESS:
                self.message_user(
                    request,
                    _("Database backup created successfully: %(filename)s (%(size)s)")
                    % {"filename": log.filename, "size": log.file_size_display},
                    level=messages.SUCCESS,
                )
            else:
                self.message_user(
                    request,
                    _("Database backup failed: %(error)s") % {"error": log.error_message},
                    level=messages.ERROR,
                )
            return redirect("admin:inventory_databasebackuplog_changelist")

        context = {
            **self.admin_site.each_context(request),
            "title": _("Confirm Database Backup"),
            "opts": self.model._meta,
        }
        return render(request, "admin/inventory/databasebackuplog/confirm_backup.html", context)

    def has_module_permission(self, request):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def has_view_permission(self, request, obj=None):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return bool(request.user and request.user.is_active and is_manager(request.user))


@admin.register(PushSubscription, site=admin_site)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "short_endpoint",
        "is_active",
        "user_agent_short",
        "updated_at",
    )
    list_filter = ("is_active", "created_at", "updated_at")
    search_fields = ("user__username", "endpoint", "user_agent")
    readonly_fields = ("created_at", "updated_at")
    actions = ["send_test_push_action"]

    def short_endpoint(self, obj):
        return f"{obj.endpoint[:60]}..." if len(obj.endpoint) > 60 else obj.endpoint

    short_endpoint.short_description = _("Push Endpoint")

    def user_agent_short(self, obj):
        if not obj.user_agent:
            return "-"
        return f"{obj.user_agent[:50]}..." if len(obj.user_agent) > 50 else obj.user_agent

    user_agent_short.short_description = _("User Agent")

    @admin.action(description=_("Send test push notification"))
    def send_test_push_action(self, request, queryset):
        from .services.push_service import is_push_configured, send_push_to_subscription

        if not is_push_configured():
            self.message_user(
                request,
                _("Web Push VAPID keys are not configured in settings/.env."),
                level=messages.WARNING,
            )
            return

        sent_count = 0
        for sub in queryset:
            if send_push_to_subscription(
                subscription=sub,
                title=str(_("🔔 2ndHand Staging Test Alert")),
                body=str(_("Push notifications are working on this device!")),
                url=reverse("inventory:dashboard"),
                tag="2ndhand-test-push",
            ):
                sent_count += 1

        self.message_user(
            request,
            _("Successfully sent %(count)d test push notification(s).") % {"count": sent_count},
            level=messages.SUCCESS if sent_count > 0 else messages.WARNING,
        )

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


@admin.register(ProductStatusLog, site=admin_site)
class ProductStatusLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "product_link",
        "from_status_badge",
        "to_status_badge",
        "changed_by_display",
        "trigger",
        "notes_short",
        "created_at",
    )
    list_filter = ("to_status", "from_status", "trigger", "created_at")
    search_fields = ("product__id", "product__ai_title", "product__raw_note", "changed_by__username", "notes")
    date_hierarchy = "created_at"
    readonly_fields = ("product", "from_status_badge", "to_status_badge", "changed_by", "trigger", "notes", "created_at")
    ordering = ["-created_at"]

    def product_link(self, obj):
        url = reverse("admin:inventory_product_change", args=[obj.product_id])
        return format_html('<a href="{}">#{} - {}</a>', url, obj.product_id, obj.product.display_title)

    product_link.short_description = _("Product")

    def from_status_badge(self, obj):
        if not obj.from_status:
            return format_html('<span style="color: #64748b; font-style: italic;">{}</span>', _("New"))
        return format_status_badge(obj.from_status)

    from_status_badge.short_description = _("From Status")

    def to_status_badge(self, obj):
        return format_status_badge(obj.to_status)

    to_status_badge.short_description = _("To Status")

    def changed_by_display(self, obj):
        if obj.changed_by:
            return obj.changed_by.username
        return format_html('<span style="color: #64748b; font-style: italic;">{}</span>', _("System / Automatic"))

    changed_by_display.short_description = _("Changed By")

    def notes_short(self, obj):
        if not obj.notes:
            return "-"
        return f"{obj.notes[:60]}..." if len(obj.notes) > 60 else obj.notes

    notes_short.short_description = _("Notes")

    def has_module_permission(self, request):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def has_view_permission(self, request, obj=None):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class BatchProductInline(admin.TabularInline):
    model = Product
    fields = ("id", "ai_title", "status", "sale_price", "created_at")
    readonly_fields = ("id", "ai_title", "status", "sale_price", "created_at")
    extra = 0
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(IntakeBatchSession, site=admin_site)
class IntakeBatchSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "assistant_display",
        "product_count",
        "is_notified_badge",
        "started_at",
        "last_activity_at",
        "closed_at",
    )
    list_filter = ("is_notified", "started_at")
    search_fields = ("assistant__username", "assistant__first_name", "assistant__last_name", "assistant__email")
    date_hierarchy = "last_activity_at"
    readonly_fields = (
        "assistant",
        "started_at",
        "last_activity_at",
        "product_count",
        "is_notified",
        "closed_at",
        "created_at",
        "updated_at",
    )
    inlines = [BatchProductInline]
    ordering = ["-last_activity_at"]

    def assistant_display(self, obj):
        name = obj.assistant.get_full_name() or obj.assistant.username
        return f"{name} (@{obj.assistant.username})"

    assistant_display.short_description = _("Assistant")

    def is_notified_badge(self, obj):
        if obj.is_notified:
            return format_html(
                '<span style="background-color: #d1fae5; color: #065f46; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600;">{}</span>',
                _("Notified"),
            )
        return format_html(
            '<span style="background-color: #fef3c7; color: #92400e; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600;">{}</span>',
            _("Pending"),
        )

    is_notified_badge.short_description = _("Push Status")

    def has_module_permission(self, request):
        return bool(request.user and request.user.is_active and is_manager(request.user))

    def has_view_permission(self, request, obj=None):
        return bool(request.user and request.user.is_active and is_manager(request.user))





