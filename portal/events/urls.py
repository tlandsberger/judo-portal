from django.urls import path

from . import views

urlpatterns = [
    path("termine/", views.agenda, name="agenda"),
    path("termine/<int:pk>/", views.occurrence_detail, name="occurrence_detail"),
    path("termine/<int:pk>/anmelden/<int:member_pk>/", views.register, name="register"),
    path("termine/<int:pk>/abmelden/<int:member_pk>/", views.unregister, name="unregister"),
    path("termine/<int:pk>/bearbeiten/", views.occurrence_edit, name="occurrence_edit"),
    path("termine/<int:pk>/hinweis/", views.occurrence_note, name="occurrence_note"),
    path("termine/<int:pk>/absagen/", views.occurrence_cancel, name="occurrence_cancel"),
    path("termine/<int:pk>/team/", views.occurrence_staff, name="occurrence_staff"),
    path(
        "termine/<int:pk>/team/<int:staffing_pk>/entfernen/",
        views.occurrence_staff_remove,
        name="occurrence_staff_remove",
    ),
    path("termine/<int:pk>/bestaetigen/", views.staffing_confirm, name="staffing_confirm"),
    path("termine/<int:pk>/teilnehmer/", views.participant_add, name="participant_add"),
    path(
        "termine/<int:pk>/teilnehmer/<int:registration_pk>/entfernen/",
        views.participant_remove,
        name="participant_remove",
    ),
    path("einsaetze/", views.my_staffings, name="my_staffings"),
    path("veranstaltungen/", views.event_list, name="event_list"),
    path("veranstaltungen/neu/", views.event_edit, name="event_create"),
    path("veranstaltungen/<int:pk>/", views.event_detail, name="event_detail"),
    path("veranstaltungen/<int:pk>/bearbeiten/", views.event_edit, name="event_edit"),
    path("veranstaltungen/<int:pk>/loeschen/", views.event_delete, name="event_delete"),
    path("veranstaltungen/<int:pk>/zeitplaene/neu/", views.schedule_edit, name="schedule_create"),
    path("veranstaltungen/<int:pk>/zeitplaene/<int:schedule_pk>/", views.schedule_edit, name="schedule_edit"),
    path(
        "veranstaltungen/<int:pk>/zeitplaene/<int:schedule_pk>/loeschen/", views.schedule_delete, name="schedule_delete"
    ),
    path("veranstaltungen/<int:pk>/termine/neu/", views.occurrence_create, name="occurrence_create"),
    path("veranstaltungen/<int:pk>/absagen/", views.event_cancel_range, name="event_cancel_range"),
    path("veranstaltungen/<int:pk>/team/", views.event_staff, name="event_staff"),
    path(
        "veranstaltungen/<int:pk>/team/<int:staff_pk>/entfernen/", views.event_staff_remove, name="event_staff_remove"
    ),
    path("zielgruppen/", views.target_group_list, name="target_group_list"),
    path("zielgruppen/neu/", views.target_group_edit, name="target_group_create"),
    path("zielgruppen/<int:pk>/", views.target_group_members, name="target_group_members"),
    path("zielgruppen/<int:pk>/bearbeiten/", views.target_group_edit, name="target_group_edit"),
    path("zielgruppen/<int:pk>/loeschen/", views.target_group_delete, name="target_group_delete"),
]
