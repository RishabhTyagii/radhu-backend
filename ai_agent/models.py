from django.conf import settings
from django.db import models


class AiAuditLog(models.Model):
    STATUS_PROPOSED = "proposed"
    STATUS_CONFIRMED = "confirmed"
    STATUS_REJECTED = "rejected"
    STATUS_EXECUTED = "executed"
    STATUS_FAILED = "failed"
    STATUS_EXPIRED = "expired"

    STATUS_CHOICES = [
        (STATUS_PROPOSED, "Proposed"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_EXECUTED, "Executed"),
        (STATUS_FAILED, "Failed"),
        (STATUS_EXPIRED, "Expired"),
    ]

    RISK_NORMAL = "normal"
    RISK_HIGH = "high"
    RISK_CHOICES = [
        (RISK_NORMAL, "Normal"),
        (RISK_HIGH, "High"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="ai_proposals",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_approvals",
    )
    batch_id = models.CharField(max_length=64, db_index=True, blank=True)
    confirm_token = models.CharField(max_length=64, unique=True)
    action_type = models.CharField(max_length=40, db_index=True)
    module = models.CharField(max_length=20, db_index=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PROPOSED, db_index=True
    )
    risk_level = models.CharField(max_length=10, choices=RISK_CHOICES, default=RISK_NORMAL)
    summary = models.CharField(max_length=500)
    payload = models.JSONField(default=dict)
    result = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "AI Audit Log"
        verbose_name_plural = "AI Audit Logs"

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} | {self.user} | {self.action_type} | {self.status}"


class AiConfig(models.Model):
    MODEL_CHOICES = [
        ("gemini-2.5-flash", "Gemini 2.5 Flash (Recommended — Fastest & Smartest)"),
        ("gemini-2.0-flash", "Gemini 2.0 Flash (Fast & High Volume)"),
        ("gemini-1.5-flash", "Gemini 1.5 Flash (Stable & Highly Compatible)"),
        ("gemini-1.5-pro", "Gemini 1.5 Pro (Deep Reasoning & Large Analysis)"),
    ]

    api_key = models.CharField(
        max_length=255,
        blank=True,
        help_text="Google AI Studio Gemini API Key (e.g. AIzaSy...). Rotate/update anytime here.",
        verbose_name="Gemini API Key",
    )
    model_name = models.CharField(
        max_length=50,
        choices=MODEL_CHOICES,
        default="gemini-2.5-flash",
        help_text="Primary model used by the AI Agent.",
        verbose_name="Active AI Model",
    )
    fallback_model = models.CharField(
        max_length=50,
        choices=MODEL_CHOICES,
        default="gemini-1.5-flash",
        help_text="Secondary model used automatically if the primary model hits quota/rate limits.",
        verbose_name="Fallback Model",
    )
    is_enabled = models.BooleanField(
        default=True,
        help_text="Enable or disable the AI Agent assistant across the ERP.",
        verbose_name="Enable AI Assistant",
    )
    temperature = models.FloatField(
        default=0.4,
        help_text="0.0 to 1.0. Lower values (0.2-0.4) are more precise for ERP data; higher is more conversational.",
        verbose_name="Temperature (Creativity)",
    )
    system_instructions_extra = models.TextField(
        blank=True,
        help_text="Optional custom instructions to add to the ERP system prompt (e.g. custom pricing policies, holiday notices).",
        verbose_name="Extra Prompt Instructions",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "AI Configuration & API Keys"
        verbose_name_plural = "AI Configuration & API Keys"

    def __str__(self):
        status = "Active" if self.is_enabled else "Disabled"
        key_status = "Key Set" if self.api_key else "No Key"
        return f"AI Config ({self.model_name}) — [{status} | {key_status}]"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj
