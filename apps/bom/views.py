from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from decimal import Decimal
from apps.bom.models import BOM, BOMItem
from apps.bom.services import BOMService

@login_required
def bom_list(request):
    boms = BOM.objects.select_related('product', 'product__uom').prefetch_related('items').filter(is_active=True)
    return render(request, 'bom/bom_list.html', {'boms': boms})

@login_required
def bom_detail(request, pk):
    bom = get_object_or_404(
        BOM.objects.select_related('product', 'product__uom').prefetch_related(
            'items__raw_material__uom',
            'items__packaging_material__uom',
            'items__uom'
        ),
        pk=pk
    )
    raw_items = bom.items.filter(item_type=BOMItem.ItemType.RAW_MATERIAL)
    pkg_items = bom.items.filter(item_type=BOMItem.ItemType.PACKAGING_MATERIAL)

    return render(request, 'bom/bom_detail.html', {
        'bom': bom,
        'raw_items': raw_items,
        'pkg_items': pkg_items,
    })

@login_required
def api_calculate_requirements(request, product_id):
    """API endpoint to dynamically compute planned requirements based on input batch quantity."""
    batch_qty = request.GET.get('batch_quantity', '200')
    try:
        bom = BOMService.get_active_bom(product_id)
        calc = BOMService.calculate_requirements(bom, batch_qty)
        # Convert Decimal values to float/str for JSON response
        for item in calc['raw_materials']:
            item['standard_quantity'] = float(item['standard_quantity'])
            item['planned_quantity'] = float(item['planned_quantity'])
            item['current_stock'] = float(item['current_stock'])
            item['unit_rate'] = float(item['unit_rate'])
            item['estimated_cost'] = float(item['estimated_cost'])
        for item in calc['packaging_materials']:
            item['standard_quantity'] = float(item['standard_quantity'])
            item['planned_quantity'] = float(item['planned_quantity'])
            item['current_stock'] = float(item['current_stock'])
            item['unit_rate'] = float(item['unit_rate'])
            item['estimated_cost'] = float(item['estimated_cost'])
        calc['batch_size'] = float(calc['batch_size'])
        calc['target_batch_quantity'] = float(calc['target_batch_quantity'])
        calc['expected_output'] = float(calc['expected_output'])
        return JsonResponse({'success': True, 'data': calc})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
