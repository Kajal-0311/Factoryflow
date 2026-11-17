from django.conf import settings

def company_context(request):
    """Provides company branding and current user role helpers across templates."""
    context = {
        'company': getattr(settings, 'COMPANY_INFO', {}),
        'app_name': 'FactoryFlow',
        'app_subtitle': 'Integrated Food Manufacturing ERP',
    }
    if request.user.is_authenticated:
        role = getattr(request.user, 'role', '')
        context['user_role'] = role
        context['is_admin'] = request.user.is_superuser or role == 'ADMIN'
        context['is_salesman'] = role == 'SALESMAN'
        context['is_production_supervisor'] = role == 'PRODUCTION_SUPERVISOR'
        context['is_auditor_owner'] = role in ('OWNER', 'ACCOUNTANT', 'AUDITOR', 'OWNER_AUDITOR')
    return context
