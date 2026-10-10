from django.contrib import admin
from django.utils.html import format_html

from .models import Product, ProductImage


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ("image", "order", "image_preview", "created_at")
    readonly_fields = ("image_preview", "created_at")

    def image_preview(self, instance):
        if instance.image:
            return format_html(
                '<img src="{}" style="max-height: 80px; max-width: 120px; border-radius: 4px; object-fit: cover;" />',
                instance.image.url
            )
        return "-"
    image_preview.short_description = "Preview"


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "display_title",
        "sale_price_display",
        "is_sold",
        "images_count",
        "created_by",
        "created_at"
    )
    list_filter = ("is_sold", "created_at")
    search_fields = ("ai_title", "raw_note", "ai_description")
    inlines = [ProductImageInline]
    readonly_fields = ("created_at", "updated_at", "sold_at")

    def sale_price_display(self, obj):
        if obj.sale_price is not None:
            return f"€{obj.sale_price:.2f}"
        return "-"
    sale_price_display.short_description = "Price (€)"

    def images_count(self, obj):
        return obj.images.count()
    images_count.short_description = "Images"


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "order", "image", "created_at")
    list_filter = ("created_at",)
    search_fields = ("product__ai_title", "product__raw_note")
