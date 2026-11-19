from django.urls import path

from . import views

urlpatterns = [
    path("abrechnung/", views.billing_index, name="billing_index"),
    path("abrechnung/<int:year>/<int:month>/", views.billing_month, name="billing_month"),
    path("abrechnung/<int:year>/<int:month>/einreichen/", views.billing_submit, name="billing_submit"),
    path("abrechnung/alle/", views.claim_list, name="claim_list"),
    path("abrechnung/alle/pruefen/", views.claim_review, name="claim_review"),
    path("abrechnung/alle/<int:year>-<int:month>.csv", views.claim_csv, name="claim_csv"),
    path("abrechnung/eingereicht/<int:pk>/", views.claim_detail, name="claim_detail"),
    path("abrechnung/eingereicht/<int:pk>/freigeben/", views.claim_approve, name="claim_approve"),
    path("abrechnung/eingereicht/<int:pk>/zurueckgeben/", views.claim_send_back, name="claim_send_back"),
    path("abrechnung/eingereicht/<int:pk>/pdf/", views.claim_pdf, name="claim_pdf"),
    path("abrechnung/saetze/", views.rate_list, name="rate_list"),
    path("abrechnung/saetze/<int:member_pk>/", views.rate_member, name="rate_member"),
    path("abrechnung/saetze/satz/<int:pk>/loeschen/", views.rate_delete, name="rate_delete"),
]
