from django.urls import path

from . import views

urlpatterns = [
    path("benachrichtigungen/abo/", views.subscribe, name="push_notification_subscribe"),
    path("benachrichtigungen/abo/beenden/", views.unsubscribe, name="push_notification_unsubscribe"),
    path("benachrichtigungen/geraete/<int:pk>/entfernen/", views.remove_device, name="push_notification_remove_device"),
    path("benachrichtigungen/geraete/<int:pk>/test/", views.test, name="push_notification_test"),
    path("benachrichtigungen/aktion/", views.action, name="push_notification_action"),
]
