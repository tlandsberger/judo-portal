from django.contrib import admin

from .models import Invitation, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "first_name", "last_name", "roles", "is_active", "date_joined")
    search_fields = ("email", "first_name", "last_name")
    list_filter = ("is_active",)
    exclude = ("password", "groups", "user_permissions")
    readonly_fields = ("last_login", "date_joined")


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ("email", "roles", "created_at", "expires_at", "accepted_at")
    search_fields = ("email",)
    readonly_fields = ("token",)
