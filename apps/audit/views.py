from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from apps.audit.models import AuditLog, AuditAction

@login_required
def audit_log_list(request):
    logs = AuditLog.objects.select_related('user').order_by('-timestamp', '-id')

    module_filter = request.GET.get('module')
    if module_filter:
        logs = logs.filter(module__iexact=module_filter)

    action_filter = request.GET.get('action')
    if action_filter:
        logs = logs.filter(action=action_filter)

    modules = AuditLog.objects.values_list('module', flat=True).distinct()

    return render(request, 'audit/audit_list.html', {
        'logs': logs[:250],
        'modules': sorted(list(set(modules))),
        'actions': AuditAction.choices,
        'selected_module': module_filter,
        'selected_action': action_filter,
    })
