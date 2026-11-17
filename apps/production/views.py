from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from apps.accounts.decorators import role_required
from apps.production.models import ProductionRun, ProductionConsumption, Overhead, CostingRecord
from apps.production.services import ProductionService
from apps.masters.models import Product, RawMaterial, PackagingMaterial
from apps.bom.models import BOM, BOMItem
from apps.bom.services import BOMService

@login_required
def run_list(request):
    runs = ProductionRun.objects.select_related('product', 'bom', 'supervisor', 'costing').order_by('-production_date', '-id')
    if request.GET.get('has_alert') == '1':
        runs = runs.filter(yield_alert=True)

    return render(request, 'production/run_list.html', {'runs': runs})


@login_required
def run_detail(request, pk):
    run = get_object_or_404(
        ProductionRun.objects.select_related('product', 'bom', 'supervisor', 'costing').prefetch_related(
            'consumptions__raw_material',
            'consumptions__packaging_material',
            'overheads'
        ),
        pk=pk
    )
    consumptions = run.consumptions.all()
    overheads = run.overheads.all()
    costing = getattr(run, 'costing', None)

    return render(request, 'production/run_detail.html', {
        'run': run,
        'consumptions': consumptions,
        'overheads': overheads,
        'costing': costing,
    })


@login_required
@role_required('ADMIN', 'PRODUCTION_SUPERVISOR')
def create_run(request):
    products = Product.objects.filter(is_active=True).order_by('name')
    selected_product_id = request.GET.get('product_id') or (products.first().id if products.exists() else None)
    
    bom = None
    requirements = None
    if selected_product_id:
        try:
            bom = BOMService.get_active_bom(selected_product_id)
            requirements = BOMService.calculate_requirements(bom, bom.batch_size)
        except Exception:
            bom = None

    if request.method == 'POST':
        try:
            product_id = request.POST.get('product_id')
            batch_qty = Decimal(request.POST.get('batch_quantity', '200'))
            actual_good_output = Decimal(request.POST.get('actual_good_output', '188'))
            wastage_qty = Decimal(request.POST.get('wastage_quantity', '0'))
            prod_date_str = request.POST.get('production_date')
            prod_date = timezone.datetime.strptime(prod_date_str, '%Y-%m-%d').date() if prod_date_str else timezone.now().date()
            notes = request.POST.get('notes', '')

            # Collect raw materials and packaging from POST
            consumptions_data = []
            active_bom = BOMService.get_active_bom(product_id)

            for item in active_bom.items.all():
                if item.item_type == BOMItem.ItemType.RAW_MATERIAL:
                    act_key = f"actual_rm_{item.raw_material.id}"
                    plan_key = f"planned_rm_{item.raw_material.id}"
                    act_val = request.POST.get(act_key, str(item.standard_quantity))
                    plan_val = request.POST.get(plan_key, str(item.standard_quantity))
                    consumptions_data.append({
                        'item_type': 'RAW_MATERIAL',
                        'raw_material_id': item.raw_material.id,
                        'planned_quantity': plan_val,
                        'actual_quantity': act_val,
                        'damaged_quantity': '0.000',
                    })
                elif item.item_type == BOMItem.ItemType.PACKAGING_MATERIAL:
                    act_key = f"actual_pm_{item.packaging_material.id}"
                    plan_key = f"planned_pm_{item.packaging_material.id}"
                    dmg_key = f"damaged_pm_{item.packaging_material.id}"
                    act_val = request.POST.get(act_key, str(item.standard_quantity))
                    plan_val = request.POST.get(plan_key, str(item.standard_quantity))
                    dmg_val = request.POST.get(dmg_key, '0.000')
                    consumptions_data.append({
                        'item_type': 'PACKAGING_MATERIAL',
                        'packaging_material_id': item.packaging_material.id,
                        'planned_quantity': plan_val,
                        'actual_quantity': act_val,
                        'damaged_quantity': dmg_val,
                    })

            # Overheads
            labour_amt = request.POST.get('overhead_labour', '1200.00')
            power_amt = request.POST.get('overhead_power_gas', '600.00')
            overheads_data = [
                {'overhead_type': Overhead.OverheadType.LABOUR, 'description': 'Batch Direct Labour', 'amount': labour_amt},
                {'overhead_type': Overhead.OverheadType.POWER_GAS, 'description': 'Gas & Electricity Power', 'amount': power_amt},
            ]

            run, costing = ProductionService.execute_production_run(
                product_id=product_id,
                batch_quantity=batch_qty,
                actual_good_output=actual_good_output,
                consumptions_data=consumptions_data,
                overheads_data=overheads_data,
                wastage_quantity=wastage_qty,
                production_date=prod_date,
                supervisor=request.user,
                notes=notes
            )

            messages.success(request, f"Production Run {run.run_number} posted successfully! Cost per packet: ₹{costing.cost_per_packet:.2f}")
            return redirect('production:run_detail', pk=run.id)

        except Exception as e:
            messages.error(request, f"Error saving production run: {str(e)}")

    return render(request, 'production/create_run.html', {
        'products': products,
        'selected_product_id': int(selected_product_id) if selected_product_id else None,
        'bom': bom,
        'requirements': requirements,
        'today': timezone.now().date(),
    })
