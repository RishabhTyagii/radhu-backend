from django.contrib import admin
from .models import AiAuditLog


@admin.register(AiAuditLog)
class AiAuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at", "user", "approved_by", "action_type", "module",
        "status", "risk_level", "summary",
    )
    list_filter = ("status", "action_type", "module", "risk_level")
    search_fields = ("summary", "confirm_token", "batch_id", "error_message", "user__username")
    readonly_fields = (
        "user", "approved_by", "batch_id", "confirm_token", "action_type", "module",
        "status", "risk_level", "summary", "payload", "result", "error_message",
        "created_at", "executed_at", "expires_at",
    )
