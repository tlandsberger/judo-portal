from django.urls import path

from . import views

urlpatterns = [
    path("hilfe/", views.index, name="help_index"),
    path("hilfe/<slug:slug>/", views.chapter, name="help_chapter"),
]
