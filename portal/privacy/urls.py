from django.urls import path

from . import views

urlpatterns = [
    path("meine-daten/auskunft/", views.my_privacy, name="my_privacy"),
    path("mitglieder/<int:pk>/auskunft/", views.member_export, name="member_export"),
    path("mitglieder/<int:pk>/loeschen/", views.member_delete, name="member_delete"),
    path("protokoll/", views.audit_list, name="audit_list"),
    path("zugang/loeschen/", views.own_access_delete, name="own_access_delete"),
]
