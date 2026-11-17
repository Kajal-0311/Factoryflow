from django.db import models
from django.conf import settings

class AuditAction(models.TextChoices):
    CREATE = 'CREATE', 'Create'
    UPDATE = 'UPDATE', 'Update'
    DELETE = 'DELETE', 'Delete'
    APPROVE = 'APPROVE', 'Approve'
    REJECT = 'REJECT', 'Reject'
    POST = 'POST', 'Post'
    CANCEL = 'CANCEL', 'Cancel'
    DISPATCH = 'DISPATCH', 'Dispatch'
    PAYMENT = 'PAYMENT', 'Payment'


class AuditLog(models.Model):
    """Immutable audit trail for tracking critical transactions and configuration modifications."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_entries'
    )
    action = models.CharField(max_length=30, choices=AuditAction.choices, db_index=True)
    module = models.CharField(max_length=50, db_index=True, help_text="e.g. Sales, Production, Purchases, Billing, Inventory")
    model_name = models.CharField(max_length=50, blank=True)
    record_id = models.CharField(max_length=100, db_index=True)
    record_representation = models.CharField(max_length=255, blank=True)
    
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    previous_state = models.JSONField(null=True, blank=True)
    new_state = models.JSONField(null=True, blank=True)
    change_summary = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        ordering = ['-timestamp', '-id']
        indexes = [
            models.Index(fields=['module', 'timestamp']),
            models.Index(fields=['record_id', 'timestamp']),
        ]

    def __str__(self):
        user_str = self.user.username if self.user else 'System'
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M')}] {user_str} - {self.action} on {self.module}:{self.record_id}"
