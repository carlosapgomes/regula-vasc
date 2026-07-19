"""URL patterns for dashboard app."""

from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    # Index
    path("", views.dashboard_index, name="index"),
    # Case detail & administrative close
    path("cases/<uuid:case_id>/", views.dashboard_case_detail, name="case_detail"),
    path(
        "cases/<uuid:case_id>/administrative-close/",
        views.dashboard_administrative_close,
        name="administrative_close",
    ),
    # User CRUD
    path("users/", views.dashboard_user_list, name="user_list"),
    path("users/create/", views.dashboard_user_create, name="user_create"),
    path("users/<int:user_id>/edit/", views.dashboard_user_edit, name="user_edit"),
    # Prompt management
    path("prompts/", views.dashboard_prompt_list, name="prompt_list"),
    path("prompts/create/", views.dashboard_prompt_create, name="prompt_create"),
    # LLM Config
    path("llm-config/", views.dashboard_llm_config, name="llm_config"),
    # Communication
    path(
        "cases/<uuid:case_id>/communication/",
        views.post_case_communication,
        name="post_case_communication",
    ),
]
