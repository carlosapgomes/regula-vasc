from django.urls import path

from . import views

app_name = "intake"

urlpatterns = [
    path("", views.intake_home, name="home"),
    path("my-cases/", views.my_cases, name="my_cases"),
    path("my-cases/partial/", views.my_cases_partial, name="my_cases_partial"),
    path("<uuid:case_id>/", views.case_detail, name="case_detail"),
    path("<uuid:case_id>/pdf/", views.serve_pdf, name="serve_pdf"),
    path("<uuid:case_id>/attachments/<uuid:attachment_id>/", views.serve_attachment, name="serve_attachment"),
    path(
        "<uuid:case_id>/attachments/<uuid:attachment_id>/suppress/",
        views.suppress_attachment,
        name="suppress_attachment",
    ),
    path(
        "<uuid:case_id>/attachments/supplemental/add/",
        views.add_supplemental_attachment,
        name="supplemental_attachment_add",
    ),
    path("<uuid:case_id>/confirm/", views.confirm_receipt, name="confirm_receipt"),
    path("<uuid:case_id>/lock/renew/", views.lock_renew, name="lock_renew"),
    path("<uuid:case_id>/lock/release/", views.lock_release, name="lock_release"),
    path("<uuid:case_id>/communication/", views.post_case_communication, name="post_case_communication"),
]
