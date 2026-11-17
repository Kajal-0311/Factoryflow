import json
from decimal import Decimal
from django.core.serializers.json import DjangoJSONEncoder
from apps.audit.models import AuditLog, AuditAction

class AuditJSONEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)

class AuditService:
    """Service to record immutable audit trail entries across all modules."""

    @classmethod
    def log(cls, user, action, module, record_id, model_name='',
            record_repr='', previous_state=None, new_state=None,
            summary='', ip_address=None):
        """
        Record an audit log entry.
        """
        # Serialize dicts safely
        prev_json = None
        new_json = None
        if previous_state:
            prev_json = json.loads(json.dumps(previous_state, cls=AuditJSONEncoder))
        if new_state:
            new_json = json.loads(json.dumps(new_state, cls=AuditJSONEncoder))

        return AuditLog.objects.create(
            user=user if getattr(user, 'is_authenticated', False) else None,
            action=action,
            module=module,
            model_name=model_name,
            record_id=str(record_id),
            record_representation=str(record_repr)[:255],
            previous_state=prev_json,
            new_state=new_json,
            change_summary=summary,
            ip_address=ip_address
        )
