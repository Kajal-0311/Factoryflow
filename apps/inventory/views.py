from decimal import Decimal
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from apps.inventory.models import StockLedger, StockBalance, StockItemType, StockTransactionType
from apps.inventory.services import InventoryService
from apps.masters.models import RawMaterial, PackagingMaterial, Product

@login_required
def stock_overview(request):
    raw_materials = RawMaterial.objects.select_related('uom').filter(is_active=True).order_by('name')
    packaging_materials = PackagingMaterial.objects.select_related('uom').filter(is_active=True).order_by('name')
    products = Product.objects.select_related('category', 'uom').filter(is_active=True).order_by('name')

    low_stock_filter = request.GET.get('low_stock') == '1'

    rm_data = []
    total_rm_val = Decimal('0.00')
    for rm in raw_materials:
        val = (rm.current_stock * rm.weighted_average_cost).quantize(Decimal('0.01'))
        total_rm_val += val
        if not low_stock_filter or rm.is_low_stock:
            rm_data.append({'item': rm, 'valuation': val})

    pm_data = []
    total_pm_val = Decimal('0.00')
    for pm in packaging_materials:
        val = (pm.current_stock * pm.purchase_rate).quantize(Decimal('0.01'))
        total_pm_val += val
        if not low_stock_filter or pm.is_low_stock:
            pm_data.append({'item': pm, 'valuation': val})

    fg_data = []
    total_fg_val = Decimal('0.00')
    for p in products:
        val = (p.current_stock * p.selling_price).quantize(Decimal('0.01'))
        total_fg_val += val
        fg_data.append({'item': p, 'valuation': val})

    total_holding_val = total_rm_val + total_pm_val + total_fg_val

    return render(request, 'inventory/stock_overview.html', {
        'rm_data': rm_data,
        'pm_data': pm_data,
        'fg_data': fg_data,
        'total_rm_val': total_rm_val,
        'total_pm_val': total_pm_val,
        'total_fg_val': total_fg_val,
        'total_holding_val': total_holding_val,
        'is_low_stock_filtered': low_stock_filter,
    })


@login_required
def stock_ledger(request):
    qs = StockLedger.objects.select_related('user_responsible').order_by('-created_at', '-id')

    item_type = request.GET.get('item_type')
    if item_type:
        qs = qs.filter(item_type=item_type)

    tx_type = request.GET.get('transaction_type')
    if tx_type:
        qs = qs.filter(transaction_type=tx_type)

    search = request.GET.get('search')
    if search:
        qs = qs.filter(item_name__icontains=search)

    return render(request, 'inventory/stock_ledger.html', {
        'ledger_entries': qs[:200], # Paginated/limited view
        'item_types': StockItemType.choices,
        'tx_types': StockTransactionType.choices,
        'selected_item_type': item_type,
        'selected_tx_type': tx_type,
        'search_query': search or '',
    })


@login_required
def stock_reconciliation(request, item_type, item_id):
    result = InventoryService.reconcile_item(item_type, item_id)
    return render(request, 'inventory/stock_reconciliation.html', {
        'result': result,
        'item_type': item_type,
        'item_id': item_id,
    })
