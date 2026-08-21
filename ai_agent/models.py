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
