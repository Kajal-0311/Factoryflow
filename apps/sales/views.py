from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone

from apps.accounts.decorators import role_required
from apps.sales.models import SalesOrder, SalesOrderItem, SalesOrderStatus, Dispatch
from apps.sales.services import SalesOrderService, DispatchService
from apps.masters.models import Customer, Product, ProductPrice
from apps.billing.models import Invoice
from apps.billing.services import InvoiceService
from apps.inventory.services import InventoryService
from apps.inventory.models import StockItemType

@login_required
def order_list(request):
    user = request.user
    qs = SalesOrder.objects.select_related('customer', 'salesman').prefetch_related('items__product').order_by('-order_date', '-id')

    # If salesman, default to own orders unless filtered
    if user.is_salesman_role:
        qs = qs.filter(salesman=user)

    status_filter = request.GET.get('status')
    if status_filter:
        qs = qs.filter(status=status_filter)

    customer_id = request.GET.get('customer')
    if customer_id:
        qs = qs.filter(customer_id=customer_id)

    customers = Customer.objects.filter(is_active=True).order_by('name')

    return render(request, 'sales/order_list.html', {
        'orders': qs,
        'customers': customers,
        'selected_status': status_filter,
        'selected_customer': int(customer_id) if customer_id else None,
        'statuses': SalesOrderStatus.choices,
    })


@login_required
def order_detail(request, pk):
    order = get_object_or_404(
        SalesOrder.objects.select_related('customer', 'salesman', 'verified_by').prefetch_related('items__product', 'invoices', 'dispatches'),
        pk=pk
    )
    stock_analysis = SalesOrderService.check_stock_availability(order)
    invoice = order.invoices.first() if order.invoices.exists() else None
    dispatch = order.dispatches.first() if order.dispatches.exists() else None

    return render(request, 'sales/order_detail.html', {
        'order': order,
        'stock_analysis': stock_analysis,
        'invoice': invoice,
        'dispatch': dispatch,
    })


@login_required
def create_order(request):
    """Mobile-friendly order taking interface for salesmen."""
    customers = Customer.objects.filter(is_active=True).order_by('name')
    products = Product.objects.filter(is_active=True).order_by('name')

    if request.method == 'POST':
        try:
            customer_id = request.POST.get('customer_id')
            notes = request.POST.get('notes', '')
            product_ids = request.POST.getlist('product_id[]')
            quantities = request.POST.getlist('quantity[]')
            prices = request.POST.getlist('price[]')

            items_data = []
            for pid, qty, prc in zip(product_ids, quantities, prices):
                if pid and qty and Decimal(qty) > 0:
                    items_data.append({
                        'product_id': int(pid),
                        'quantity': qty,
                        'unit_price': prc if prc else None,
                    })

            if not items_data:
                messages.error(request, "Please add at least one product with valid quantity.")
                return redirect('sales:create_order')

            sales_order = SalesOrderService.create_order(
                customer_id=customer_id,
                salesman=request.user,
                items_data=items_data,
                notes=notes
            )

            messages.success(request, f"Sales Order {sales_order.order_number} submitted successfully!")
            return redirect('sales:order_detail', pk=sales_order.id)

        except Exception as e:
            messages.error(request, f"Failed to submit sales order: {str(e)}")

    return render(request, 'sales/create_order.html', {
        'customers': customers,
        'products': products,
        'today': timezone.now().date(),
    })


@login_required
def api_get_product_price(request):
    """API for dynamic price fetching on customer selection."""
    product_id = request.GET.get('product_id')
    customer_id = request.GET.get('customer_id')

    if not product_id:
        return JsonResponse({'error': 'product_id required'}, status=400)

    product = get_object_or_404(Product, pk=product_id)
    price = product.selling_price

    if customer_id:
        customer = get_object_or_404(Customer, pk=customer_id)
        price = SalesOrderService.get_applicable_price(product, customer)

    available_stock = InventoryService.get_stock(StockItemType.FINISHED_GOODS, product.id)

    return JsonResponse({
        'product_id': product.id,
        'name': product.name,
        'price': float(price),
        'gst_rate': float(product.gst_rate),
        'available_stock': float(available_stock),
        'hsn_code': product.hsn_code,
    })


@login_required
@role_required('ADMIN')
def approve_order(request, pk):
    order = get_object_or_404(SalesOrder, pk=pk)
    if request.method == 'POST':
        try:
            notes = request.POST.get('verification_notes', 'Order verified and approved.')
            SalesOrderService.approve_order(order.id, admin_user=request.user, verification_notes=notes)
            messages.success(request, f"Order {order.order_number} has been approved.")
        except Exception as e:
            messages.error(request, f"Approval failed: {str(e)}")
    return redirect('sales:order_detail', pk=order.id)


@login_required
@role_required('ADMIN')
def reject_order(request, pk):
    order = get_object_or_404(SalesOrder, pk=pk)
    if request.method == 'POST':
        reason = request.POST.get('rejection_reason', 'Order rejected due to stock shortage or credit limits.')
        SalesOrderService.reject_order(order.id, admin_user=request.user, reason=reason)
        messages.warning(request, f"Order {order.order_number} has been rejected.")
    return redirect('sales:order_detail', pk=order.id)


@login_required
@role_required('ADMIN')
def create_invoice_from_order(request, pk):
    order = get_object_or_404(SalesOrder, pk=pk)
    if request.method == 'POST':
        try:
            invoice = InvoiceService.generate_invoice_from_order(order.id, user=request.user)
            messages.success(request, f"Tax Invoice {invoice.invoice_number} created successfully!")
            return redirect('billing:invoice_detail', pk=invoice.id)
        except Exception as e:
            messages.error(request, f"Invoice generation failed: {str(e)}")
    return redirect('sales:order_detail', pk=order.id)


@login_required
@role_required('ADMIN')
def record_dispatch(request, pk):
    order = get_object_or_404(SalesOrder, pk=pk)
    invoice = order.invoices.first() if order.invoices.exists() else None

    if request.method == 'POST':
        try:
            transporter = request.POST.get('transporter_name', '')
            vehicle = request.POST.get('vehicle_number', '')
            lr = request.POST.get('lr_number', '')
            notes = request.POST.get('notes', '')

            dispatch = DispatchService.record_dispatch(
                sales_order_id=order.id,
                invoice_id=invoice.id if invoice else None,
                user=request.user,
                transporter_name=transporter,
                vehicle_number=vehicle,
                lr_number=lr,
                notes=notes
            )
            messages.success(request, f"Dispatch {dispatch.dispatch_number} recorded! Finished goods inventory reduced.")
            return redirect('sales:order_detail', pk=order.id)
        except Exception as e:
            messages.error(request, f"Dispatch failed: {str(e)}")

    stock_analysis = SalesOrderService.check_stock_availability(order)
    return render(request, 'sales/record_dispatch.html', {
        'order': order,
        'invoice': invoice,
        'stock_analysis': stock_analysis,
        'today': timezone.now().date(),
    })
