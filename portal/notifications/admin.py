from django.contrib import admin

from .models import PushNotificationSubscription, SentNotification


@admin.register(PushNotificationSubscription)
class PushNotificationSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "device", "created_at", "last_used_at")


@admin.register(SentNotification)
class SentNotificationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "kind", "user", "channel", "title")
    list_filter = ("kind", "channel")
