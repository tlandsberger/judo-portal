from django.urls import path

from . import views

urlpatterns = [
    path("mitglieder/", views.member_list, name="member_list"),
    path("mitglieder/neu/", views.member_edit, name="member_create"),
    path("mitglieder/<int:pk>/", views.member_detail, name="member_detail"),
    path("mitglieder/<int:pk>/bearbeiten/", views.member_edit, name="member_edit"),
    path("mitglieder/<int:pk>/zugang/", views.member_access, name="member_access"),
    path("mitglieder/<int:pk>/verknuepfung/<int:link_pk>/loesen/", views.member_unlink, name="member_unlink"),
    path("mitglieder/interessen/", views.interest_list, name="interest_list"),
    path("mitglieder/interessen/reihenfolge/", views.interest_reorder, name="interest_reorder"),
    path("mitglieder/interessen/<int:pk>/", views.interest_list, name="interest_edit"),
    path("mitglieder/interessen/<int:pk>/loeschen/", views.interest_delete, name="interest_delete"),
    path("mitglieder/import/", views.member_import, name="member_import"),
    path("mitglieder/import/vorlage.csv", views.import_template, name="member_import_template"),
    path("meine-daten/", views.my_data, name="my_data"),
    path("meine-daten/<int:pk>/", views.my_member, name="my_member"),
    path("meine-daten/<int:pk>/bearbeiten/", views.my_member_edit, name="my_member_edit"),
    path("meine-daten/<int:pk>/eigener-zugang/", views.child_access_view, name="child_access"),
    path("meine-daten/<int:pk>/eigener-zugang/nicht-jetzt/", views.child_access_dismiss, name="child_access_dismiss"),
]
