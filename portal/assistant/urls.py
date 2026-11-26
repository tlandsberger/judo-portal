from django.urls import path

from . import views

urlpatterns = [
    path("uke/", views.chat, name="assistant"),
    path("uke/frage/", views.send, name="assistant_send"),
    path("uke/neu/", views.new, name="assistant_new"),
]
