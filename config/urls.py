"""
URL configuration for FactoryFlow ERP.
Root routing table linking all modular apps.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.core.views import dashboard_view

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Dashboard (Home)
    path('', dashboard_view, name='dashboard'),
    
    # Core Modular Apps
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('masters/', include('apps.masters.urls', namespace='masters')),
    path('inventory/', include('apps.inventory.urls', namespace='inventory')),
    path('bom/', include('apps.bom.urls', namespace='bom')),
    path('purchases/', include('apps.purchases.urls', namespace='purchases')),
    path('production/', include('apps.production.urls', namespace='production')),
    path('sales/', include('apps.sales.urls', namespace='sales')),
    path('billing/', include('apps.billing.urls', namespace='billing')),
    path('payments/', include('apps.payments.urls', namespace='payments')),
    path('reports/', include('apps.reports.urls', namespace='reports')),
    path('audit/', include('apps.audit.urls', namespace='audit')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
