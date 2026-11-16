from django.contrib import admin

from .models import AuditEntry


@admin.register(AuditEntry)
class AuditEntryAdmin(admin.ModelAdmin):
    list_display = ("at", "actor_name", "area", "action", "summary")
    list_filter = ("area",)
    search_fields = ("summary", "actor_name")
    readonly_fields = [field.name for field in AuditEntry._meta.fields]

    def has_add_permission(self, request: object) -> bool:
        return False

    def has_change_permission(self, request: object, obj: object = None) -> bool:
        return False
