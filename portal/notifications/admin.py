from django.contrib import admin

from .models import PushSubscription, SentNotification


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "device", "created_at", "last_used_at")


@admin.register(SentNotification)
class SentNotificationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "kind", "user", "channel", "title")
    list_filter = ("kind", "channel")
