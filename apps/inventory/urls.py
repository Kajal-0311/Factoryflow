from django.urls import path
from apps.inventory import views

app_name = 'inventory'

urlpatterns = [
    path('', views.stock_overview, name='stock_overview'),
    path('ledger/', views.stock_ledger, name='stock_ledger'),
    path('reconcile/<str:item_type>/<int:item_id>/', views.stock_reconciliation, name='stock_reconciliation'),
]
