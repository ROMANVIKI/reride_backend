from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import EmailOTP, User


class UserCreateForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("email", "full_name")


class UserEditForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    add_form = UserCreateForm
    form = UserEditForm
    model = User

    list_display = ("email", "full_name", "phone", "city", "is_email_verified", "is_staff", "date_joined")
    list_filter = ("is_email_verified", "is_staff", "is_active", "city")
    search_fields = ("email", "full_name", "phone")
    ordering = ("-date_joined",)
    readonly_fields = ("date_joined", "last_login", "updated_at")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("full_name", "phone", "city", "avatar")}),
        ("Status", {"fields": ("is_email_verified", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Timestamps", {"fields": ("date_joined", "last_login", "updated_at")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "full_name", "phone", "password1", "password2", "is_email_verified", "is_staff"),
        }),
    )

    actions = ["mark_verified"]

    @admin.action(description="Mark selected users as e-mail verified")
    def mark_verified(self, request, queryset):
        updated = queryset.update(is_email_verified=True, is_active=True)
        self.message_user(request, f"{updated} user(s) marked verified.")


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = ("email", "purpose", "code", "is_used", "attempts", "expires_at", "created_at")
    list_filter = ("purpose", "is_used")
    search_fields = ("email", "code")
    readonly_fields = ("created_at",)
