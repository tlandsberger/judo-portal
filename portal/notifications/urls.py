from django.urls import path

from . import views

urlpatterns = [
    path("benachrichtigungen/abo/", views.subscribe, name="push_subscribe"),
    path("benachrichtigungen/abo/beenden/", views.unsubscribe, name="push_unsubscribe"),
    path("benachrichtigungen/geraete/<int:pk>/entfernen/", views.remove_device, name="push_remove_device"),
    path("benachrichtigungen/geraete/<int:pk>/test/", views.test, name="push_test"),
    path("benachrichtigungen/aktion/", views.action, name="push_action"),
]
