from django.contrib import admin
from .models import AiAuditLog, AiConfig


@admin.register(AiConfig)
class AiConfigAdmin(admin.ModelAdmin):
    list_display = ("__str__", "model_name", "fallback_model", "is_enabled", "updated_at")
    fieldsets = (
        ("API Credentials", {
            "fields": ("api_key", "is_enabled"),
            "description": "Enter your Google AI Studio API key here. You can rotate/change it anytime without restarting the server.",
        }),
        ("Model Selection & Behavior", {
            "fields": ("model_name", "fallback_model", "temperature"),
            "description": "Choose which Gemini model handles your ERP requests. Gemini 2.5 Flash is recommended.",
        }),
        ("Custom Instructions (Optional)", {
            "fields": ("system_instructions_extra",),
            "classes": ("collapse",),
            "description": "Optional business rules to append to the AI prompt.",
        }),
        ("Metadata", {
            "fields": ("updated_at",),
            "classes": ("collapse",),
        }),
    )
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        # Allow only 1 configuration record
        return not AiConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


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
