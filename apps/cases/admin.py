"""Admin registration for cases models."""

from django.contrib import admin

from .models import Case, CaseAttachment, CaseCommunicationMessage, CaseEvent


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ("case_id", "status", "created_by", "created_at")
    list_filter = ("status",)
    search_fields = ("case_id",)
    readonly_fields = ("case_id", "created_at", "updated_at")


@admin.register(CaseEvent)
class CaseEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "case", "timestamp", "actor")
    list_filter = ("event_type", "timestamp")
    readonly_fields = ("case", "timestamp", "actor", "event_type", "payload")


@admin.register(CaseAttachment)
class CaseAttachmentAdmin(admin.ModelAdmin):
    list_display = ("attachment_id", "case", "original_filename", "content_type", "is_suppressed")
    list_filter = ("is_suppressed", "content_type")


@admin.register(CaseCommunicationMessage)
class CaseCommunicationMessageAdmin(admin.ModelAdmin):
    list_display = ("message_id", "case", "author_role", "created_at")
    list_filter = ("message_type",)
