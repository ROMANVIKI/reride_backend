from django.contrib import admin
from django.utils import timezone

from .models import ContactMessage, Reservation, SellLead, ServiceBooking, TestRideBooking


@admin.register(SellLead)
class SellLeadAdmin(admin.ModelAdmin):
    list_display = ("brand", "model_name", "year", "km", "phone", "estimated_price", "status", "created_at")
    list_filter = ("status", "brand", "type", "city")
    search_fields = ("phone", "email", "name", "brand", "model_name", "registration_number")
    list_editable = ("status",)
    readonly_fields = ("estimated_low", "estimated_price", "estimated_high", "created_at", "updated_at")
    date_hierarchy = "created_at"


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "subject", "email", "phone", "vehicle", "is_read", "created_at")
    list_filter = ("subject", "is_read")
    search_fields = ("name", "email", "phone", "message")
    list_editable = ("is_read",)
    readonly_fields = ("created_at", "updated_at")
    actions = ["mark_read", "mark_replied"]

    @admin.action(description="Mark as read")
    def mark_read(self, request, queryset):
        queryset.update(is_read=True)

    @admin.action(description="Mark as replied")
    def mark_replied(self, request, queryset):
        queryset.update(is_read=True, replied_at=timezone.now())


@admin.register(ServiceBooking)
class ServiceBookingAdmin(admin.ModelAdmin):
    list_display = ("name", "package", "preferred_date", "is_doorstep", "status", "created_at")
    list_filter = ("status", "package", "is_doorstep")
    search_fields = ("name", "phone", "email", "registration_number")
    list_editable = ("status",)
    date_hierarchy = "created_at"


@admin.register(TestRideBooking)
class TestRideBookingAdmin(admin.ModelAdmin):
    list_display = ("name", "vehicle", "preferred_date", "preferred_slot", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("name", "phone", "vehicle__brand", "vehicle__model_name")
    list_editable = ("status",)
    autocomplete_fields = ("vehicle",)


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("name", "vehicle", "amount", "status", "reference", "created_at")
    list_filter = ("status",)
    search_fields = ("name", "phone", "reference", "vehicle__brand")
    list_editable = ("status", "reference")
    autocomplete_fields = ("vehicle",)
