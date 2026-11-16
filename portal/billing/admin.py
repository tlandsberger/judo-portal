from django.contrib import admin

from .models import Claim, ClaimLine, Rate


@admin.register(Rate)
class RateAdmin(admin.ModelAdmin):
    list_display = ("member", "role", "hourly_rate", "valid_from")
    list_filter = ("role",)


class ClaimLineInline(admin.TabularInline):
    model = ClaimLine
    extra = 0
    readonly_fields = ("participation", "day", "event_title", "role_name", "minutes", "hourly_rate", "amount")


@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = ("member", "month", "status", "is_late", "total_minutes", "total_amount")
    list_filter = ("status", "is_late", "month")
    inlines = (ClaimLineInline,)
