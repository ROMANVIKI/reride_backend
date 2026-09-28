from django.contrib import admin
from django.utils.html import format_html

from .models import (
    FAQ,
    Favorite,
    ServicePackage,
    ServicePackageItem,
    SiteStat,
    Store,
    Testimonial,
    Vehicle,
    VehicleHighlight,
    VehicleImage,
)


class VehicleHighlightInline(admin.TabularInline):
    model = VehicleHighlight
    extra = 1


class VehicleImageInline(admin.TabularInline):
    model = VehicleImage
    extra = 1
    readonly_fields = ("preview",)

    def preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="height:70px;" />', obj.image.url)
        return "—"


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = (
        "__str__", "tier", "price", "km", "city", "area",
        "status", "is_approved", "seller", "created_at",
    )
    list_filter = ("tier", "type", "status", "is_approved", "brand", "city", "warranty", "free_service")
    search_fields = ("brand", "model_name", "variant", "registration", "slug", "seller__email")
    list_editable = ("tier", "status", "is_approved")
    prepopulated_fields = {"slug": ("brand", "model_name", "variant")}
    readonly_fields = ("views_count", "created_at", "updated_at", "discount_display")
    inlines = [VehicleHighlightInline, VehicleImageInline]
    autocomplete_fields = ("store",)
    date_hierarchy = "created_at"
    list_per_page = 30

    fieldsets = (
        ("Listing", {"fields": ("slug", "seller", "store", "tier", "status", "is_approved")}),
        ("Vehicle", {"fields": ("brand", "model_name", "variant", "type", "year", "km", "owners", "fuel", "color", "registration")}),
        ("Pricing", {"fields": ("price", "original_price", "discount_display", "emi")}),
        ("Location", {"fields": ("city", "area")}),
        ("Trust signals", {"fields": ("warranty", "free_service", "demand", "sold_last_month")}),
        ("Content", {"fields": ("description",)}),
        ("Meta", {"fields": ("views_count", "created_at", "updated_at")}),
    )

    actions = ["approve_listings", "mark_sold", "mark_available"]

    @admin.display(description="Discount")
    def discount_display(self, obj):
        pct = obj.discount_percent
        return f"{pct}% off" if pct else "No discount"

    @admin.action(description="Approve selected listings")
    def approve_listings(self, request, queryset):
        count = queryset.update(is_approved=True)
        self.message_user(request, f"{count} listing(s) approved.")

    @admin.action(description="Mark selected as sold")
    def mark_sold(self, request, queryset):
        count = queryset.update(status=Vehicle.Status.SOLD)
        self.message_user(request, f"{count} listing(s) marked sold.")

    @admin.action(description="Mark selected as available")
    def mark_available(self, request, queryset):
        count = queryset.update(status=Vehicle.Status.AVAILABLE)
        self.message_user(request, f"{count} listing(s) marked available.")


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("name", "area", "city", "phone", "is_active")
    list_filter = ("city", "is_active")
    search_fields = ("name", "area", "city")


class ServicePackageItemInline(admin.TabularInline):
    model = ServicePackageItem
    extra = 2


@admin.register(ServicePackage)
class ServicePackageAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "price", "is_highlighted", "is_active", "order")
    list_editable = ("price", "is_highlighted", "is_active", "order")
    inlines = [ServicePackageItemInline]


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ("question", "order", "is_active")
    list_editable = ("order", "is_active")
    search_fields = ("question", "answer")


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ("name", "location", "order", "is_active")
    list_editable = ("order", "is_active")


@admin.register(SiteStat)
class SiteStatAdmin(admin.ModelAdmin):
    list_display = ("value", "label", "order", "is_active")
    list_editable = ("label", "order", "is_active")


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("user", "vehicle", "created_at")
    search_fields = ("user__email",)
