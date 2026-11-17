from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

from apps.accounts.decorators import role_required
from apps.purchases.models import Purchase, PurchaseItem, PurchaseStatus
from apps.purchases.services import PurchaseService
from apps.masters.models import Supplier, RawMaterial, PackagingMaterial, UnitOfMeasurement

@login_required
def purchase_list(request):
    purchases = Purchase.objects.select_related('supplier', 'confirmed_by').prefetch_related('items').order_by('-purchase_date', '-id')
    return render(request, 'purchases/purchase_list.html', {'purchases': purchases})


@login_required
def purchase_detail(request, pk):
    purchase = get_object_or_404(
        Purchase.objects.select_related('supplier', 'confirmed_by', 'created_by').prefetch_related('items__raw_material', 'items__packaging_material', 'items__uom'),
        pk=pk
    )
    return render(request, 'purchases/purchase_detail.html', {'purchase': purchase})


@login_required
@role_required('ADMIN', 'PRODUCTION_SUPERVISOR')
def create_purchase(request):
    suppliers = Supplier.objects.filter(is_active=True).order_by('name')
    raw_materials = RawMaterial.objects.filter(is_active=True).order_by('name')
    packaging_materials = PackagingMaterial.objects.filter(is_active=True).order_by('name')

    if request.method == 'POST':
        try:
            supplier_id = request.POST.get('supplier_id')
            supplier = get_object_or_404(Supplier, pk=supplier_id)
            inv_ref = request.POST.get('supplier_invoice_ref', '')
            p_date_str = request.POST.get('purchase_date')
            p_date = timezone.datetime.strptime(p_date_str, '%Y-%m-%d').date() if p_date_str else timezone.now().date()
            notes = request.POST.get('notes', '')

            item_type = request.POST.get('item_type')
            material_id = request.POST.get('material_id')
            quantity = Decimal(request.POST.get('quantity', '0'))
            rate = Decimal(request.POST.get('purchase_rate', '0'))
            gst_rate = Decimal(request.POST.get('gst_rate', '5.00'))

            if quantity <= Decimal('0') or rate <= Decimal('0'):
                messages.error(request, "Quantity and Rate must both be greater than zero.")
                return redirect('purchases:create_purchase')

            taxable = (quantity * rate).quantize(Decimal('0.01'))
            gst_amt = (taxable * (gst_rate / Decimal('100.0'))).quantize(Decimal('0.01'))
            total = taxable + gst_amt

            p_count = Purchase.objects.count() + 1
            p_num = f"PUR-{p_date.strftime('%Y%m')}-{p_count:04d}"

            purchase = Purchase.objects.create(
                purchase_number=p_num,
                supplier=supplier,
                supplier_invoice_ref=inv_ref,
                purchase_date=p_date,
                status=PurchaseStatus.DRAFT,
                taxable_amount=taxable,
                gst_amount=gst_amt,
                total_amount=total,
                notes=notes,
                created_by=request.user
            )

            if item_type == 'RAW_MATERIAL':
                rm = get_object_or_404(RawMaterial, pk=material_id)
                PurchaseItem.objects.create(
                    purchase=purchase,
                    item_type=PurchaseItem.ItemType.RAW_MATERIAL,
                    raw_material=rm,
                    quantity=quantity,
                    uom=rm.uom,
                    purchase_rate=rate,
                    gst_rate=gst_rate,
                    taxable_amount=taxable,
                    gst_amount=gst_amt,
                    total_amount=total
                )
            else:
                pm = get_object_or_404(PackagingMaterial, pk=material_id)
                PurchaseItem.objects.create(
                    purchase=purchase,
                    item_type=PurchaseItem.ItemType.PACKAGING_MATERIAL,
                    packaging_material=pm,
                    quantity=quantity,
                    uom=pm.uom,
                    purchase_rate=rate,
                    gst_rate=gst_rate,
                    taxable_amount=taxable,
                    gst_amount=gst_amt,
                    total_amount=total
                )

            # Auto-confirm or leave for review? If auto-confirm requested:
            if request.POST.get('confirm_now') == '1':
                PurchaseService.confirm_purchase(purchase.id, user=request.user)
                messages.success(request, f"Purchase {purchase.purchase_number} created and confirmed! Stock updated & WAC recalculated.")
            else:
                messages.success(request, f"Purchase draft {purchase.purchase_number} created.")

            return redirect('purchases:purchase_detail', pk=purchase.id)

        except Exception as e:
            messages.error(request, f"Purchase entry failed: {str(e)}")

    return render(request, 'purchases/create_purchase.html', {
        'suppliers': suppliers,
        'raw_materials': raw_materials,
        'packaging_materials': packaging_materials,
        'today': timezone.now().date(),
    })


@login_required
@role_required('ADMIN', 'PRODUCTION_SUPERVISOR')
def confirm_purchase(request, pk):
    purchase = get_object_or_404(Purchase, pk=pk)
    if request.method == 'POST':
        try:
            PurchaseService.confirm_purchase(purchase.id, user=request.user)
            messages.success(request, f"Purchase {purchase.purchase_number} confirmed! Inventory stock increased and WAC recalculated.")
        except Exception as e:
            messages.error(request, f"Confirmation failed: {str(e)}")
    return redirect('purchases:purchase_detail', pk=purchase.id)
