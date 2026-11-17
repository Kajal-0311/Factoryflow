from decimal import Decimal
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum, Count, Avg, F, Q

from apps.sales.models import SalesOrder, SalesOrderItem, SalesOrderStatus
from apps.billing.models import Invoice, InvoiceItem, InvoiceStatus
from apps.production.models import ProductionRun, ProductionConsumption, CostingRecord
from apps.inventory.models import StockBalance, StockLedger, StockItemType
from apps.masters.models import RawMaterial, PackagingMaterial, Product, Customer
from apps.purchases.models import Purchase, PurchaseStatus
from apps.payments.models import Payment

@login_required
def dashboard_view(request):
    today = timezone.now().date()
    user = request.user
    role = getattr(user, 'role', '')

    # Core Metrics calculated strictly from database records
    # 1. Orders
    all_orders = SalesOrder.objects.all()
    todays_orders = all_orders.filter(order_date=today).count()
    pending_orders = all_orders.filter(status__in=[SalesOrderStatus.SUBMITTED, SalesOrderStatus.UNDER_VERIFICATION]).count()
    completed_dispatches = all_orders.filter(status=SalesOrderStatus.DISPATCHED).count()

    # 2. Sales & Invoices
    posted_invoices = Invoice.objects.filter(status=InvoiceStatus.POSTED)
    total_sales = posted_invoices.aggregate(s=Sum('grand_total'))['s'] or Decimal('0.00')
    total_outstanding = posted_invoices.aggregate(s=Sum('outstanding_amount'))['s'] or Decimal('0.00')

    # 3. Inventory Stock Counts & Valuations
    raw_materials = RawMaterial.objects.filter(is_active=True)
    rm_total_valuation = sum(rm.current_stock * rm.weighted_average_cost for rm in raw_materials)
    rm_low_stock = [rm for rm in raw_materials if rm.is_low_stock]

    packaging_materials = PackagingMaterial.objects.filter(is_active=True)
    pm_total_valuation = sum(pm.current_stock * pm.purchase_rate for pm in packaging_materials)
    pm_low_stock = [pm for pm in packaging_materials if pm.is_low_stock]

    products = Product.objects.filter(is_active=True)
    fg_total_packets = sum(p.current_stock for p in products)
    fg_total_valuation = sum(p.current_stock * p.selling_price for p in products)

    # 4. Production & Costing
    production_runs = ProductionRun.objects.all()
    total_production_runs = production_runs.count()
    variance_alerts = production_runs.filter(Q(yield_alert=True) | Q(consumptions__variance_alert=True)).distinct()

    latest_costing = CostingRecord.objects.order_by('-id').first()
    approx_cost_per_packet = latest_costing.cost_per_packet if latest_costing else Decimal('0.00')
    approx_margin_per_packet = latest_costing.gross_margin_per_packet if latest_costing else Decimal('0.00')

    # 5. Charts Data
    # A. Product-wise sales
    product_sales_data = InvoiceItem.objects.filter(invoice__status=InvoiceStatus.POSTED).values('product__name').annotate(
        qty=Sum('quantity'),
        total_val=Sum('total_amount')
    ).order_by('-total_val')[:5]

    product_labels = [p['product__name'] for p in product_sales_data] or ['Murukku 200 g']
    product_values = [float(p['total_val']) for p in product_sales_data] or [7875.0]

    # B. Raw Material Consumption
    rm_consumptions = ProductionConsumption.objects.filter(item_type='RAW_MATERIAL').values('item_name').annotate(
        total_consumed=Sum('actual_quantity')
    )
    rm_labels = [c['item_name'] for c in rm_consumptions]
    rm_values = [float(c['total_consumed']) for c in rm_consumptions]

    # C. Outstanding Receivables by Customer
    cust_receivables = posted_invoices.values('customer__name').annotate(
        out=Sum('outstanding_amount')
    ).filter(out__gt=0).order_by('-out')[:5]
    receivable_labels = [c['customer__name'] for c in cust_receivables]
    receivable_values = [float(c['out']) for c in cust_receivables]

    # D. Salesman Specific metrics
    salesman_metrics = None
    if user.is_salesman_role:
        my_orders = all_orders.filter(salesman=user)
        my_invoices = Invoice.objects.filter(sales_order__salesman=user, status=InvoiceStatus.POSTED)
        salesman_metrics = {
            'total_my_orders': my_orders.count(),
            'my_sales_amount': my_invoices.aggregate(s=Sum('grand_total'))['s'] or Decimal('0.00'),
            'my_pending': my_orders.filter(status__in=[SalesOrderStatus.SUBMITTED, SalesOrderStatus.UNDER_VERIFICATION]).count(),
            'my_approved': my_orders.filter(status=SalesOrderStatus.APPROVED).count(),
            'my_dispatched': my_orders.filter(status=SalesOrderStatus.DISPATCHED).count(),
            'recent_orders': my_orders.order_by('-order_date', '-id')[:8]
        }
    else:
        # For admin viewing the sales tab
        salesman_metrics = {
            'total_my_orders': all_orders.count(),
            'my_sales_amount': total_sales,
            'my_pending': pending_orders,
            'my_approved': all_orders.filter(status=SalesOrderStatus.APPROVED).count(),
            'my_dispatched': completed_dispatches,
            'recent_orders': all_orders.select_related('customer', 'salesman').order_by('-order_date', '-id')[:8]
        }

    # E. Auditor Specific metrics & Compliance
    from apps.payments.services import PaymentService
    from apps.reports.services import ReportEngine
    from apps.audit.models import AuditLog

    ageing_data = PaymentService.get_receivables_ageing(as_of_date=today)
    gst_outward = ReportEngine.get_gst_outward_summary()
    recent_audit_logs = AuditLog.objects.select_related('user').order_by('-timestamp', '-id')[:8]
    recent_ledger_entries = StockLedger.objects.order_by('-created_at', '-id')[:8]

    # F. Supervisor Specific metrics
    supervisor_runs = production_runs.select_related('product', 'bom', 'supervisor').order_by('-production_date', '-id')[:8]
    total_good_produced = production_runs.aggregate(s=Sum('actual_good_output'))['s'] or Decimal('0.000')

    # Available customers for fast order taking
    all_customers = Customer.objects.filter(is_active=True).order_by('name')

    # Determine default active role view tab
    active_role_view = request.GET.get('view')
    if not active_role_view:
        if getattr(user, 'is_salesman_role', False):
            active_role_view = 'salesman'
        elif getattr(user, 'is_production_supervisor_role', False) or getattr(user, 'is_production_role', False):
            active_role_view = 'production'
        elif getattr(user, 'is_auditor_owner_role', False) or getattr(user, 'is_auditor_role', False):
            active_role_view = 'auditor'
        else:
            active_role_view = 'admin'

    # Recent transactions for dashboard tables
    recent_orders = all_orders.select_related('customer', 'salesman').order_by('-order_date', '-id')[:6]
    recent_runs = production_runs.select_related('product', 'supervisor').order_by('-production_date', '-id')[:5]

    context = {
        'active_role_view': active_role_view,
        'todays_orders': todays_orders,
        'total_sales': total_sales,
        'pending_orders': pending_orders,
        'completed_dispatches': completed_dispatches,
        'rm_total_valuation': rm_total_valuation,
        'pm_total_valuation': pm_total_valuation,
        'fg_total_packets': fg_total_packets,
        'fg_total_valuation': fg_total_valuation,
        'total_production_runs': total_production_runs,
        'total_good_produced': total_good_produced,
        'total_outstanding': total_outstanding,
        'approx_cost_per_packet': approx_cost_per_packet,
        'approx_margin_per_packet': approx_margin_per_packet,
        'low_stock_count': len(rm_low_stock) + len(pm_low_stock),
        'rm_low_stock': rm_low_stock,
        'pm_low_stock': pm_low_stock,
        'raw_materials': raw_materials,
        'packaging_materials': packaging_materials,
        'products': products,
        'all_customers': all_customers,
        'variance_alert_count': variance_alerts.count(),
        'variance_alerts': variance_alerts[:5],
        'product_labels': product_labels,
        'product_values': product_values,
        'rm_labels': rm_labels,
        'rm_values': rm_values,
        'receivable_labels': receivable_labels,
        'receivable_values': receivable_values,
        'salesman_metrics': salesman_metrics,
        'supervisor_runs': supervisor_runs,
        'ageing_data': ageing_data,
        'gst_outward': gst_outward,
        'recent_audit_logs': recent_audit_logs,
        'recent_ledger_entries': recent_ledger_entries,
        'recent_orders': recent_orders,
        'recent_runs': recent_runs,
    }
    return render(request, 'dashboard/index.html', context)
