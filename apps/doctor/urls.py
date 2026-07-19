"""URL patterns for doctor app."""

from django.urls import path

from . import views

app_name = "doctor"

urlpatterns = [
    path("", views.doctor_queue, name="queue"),
    path("partial/", views.doctor_queue_partial, name="queue_partial"),
    path("cases/<uuid:case_id>/", views.doctor_decision, name="decision"),
    path("cases/<uuid:case_id>/submit/", views.doctor_submit, name="submit"),
    path("cases/<uuid:case_id>/decided/", views.doctor_decided_detail, name="decided_detail"),
    path("cases/<uuid:case_id>/pdf/", views.serve_pdf, name="serve_pdf"),
    path(
        "cases/<uuid:case_id>/attachments/<uuid:attachment_id>/",
        views.serve_attachment,
        name="serve_attachment",
    ),
    path("cases/<uuid:case_id>/lock/renew/", views.lock_renew, name="lock_renew"),
    path("cases/<uuid:case_id>/lock/release/", views.lock_release, name="lock_release"),
    path(
        "cases/<uuid:case_id>/communication/",
        views.post_case_communication,
        name="post_case_communication",
    ),
]
