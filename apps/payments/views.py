from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

from apps.accounts.decorators import role_required
from apps.payments.models import Payment, PaymentAllocation, PaymentMethod
from apps.payments.services import PaymentService
from apps.billing.models import Invoice, InvoiceStatus
from apps.masters.models import Customer

@login_required
def payment_list(request):
    payments = Payment.objects.select_related('customer', 'received_by').prefetch_related('allocations__invoice').order_by('-payment_date', '-id')
    return render(request, 'payments/payment_list.html', {'payments': payments})


@login_required
@role_required('ADMIN')
def create_payment(request):
    customers = Customer.objects.filter(is_active=True).order_by('name')
    invoices = Invoice.objects.filter(status=InvoiceStatus.POSTED, outstanding_amount__gt=Decimal('0.00')).select_related('customer')

    selected_invoice_id = request.GET.get('invoice_id')
    preselected_invoice = None
    if selected_invoice_id:
        preselected_invoice = get_object_or_404(Invoice, pk=selected_invoice_id)

    if request.method == 'POST':
        try:
            customer_id = request.POST.get('customer_id')
            invoice_id = request.POST.get('invoice_id') or None
            amount = Decimal(request.POST.get('amount', '0'))
            p_date_str = request.POST.get('payment_date')
            p_date = timezone.datetime.strptime(p_date_str, '%Y-%m-%d').date() if p_date_str else timezone.now().date()
            method = request.POST.get('payment_method', PaymentMethod.BANK_TRANSFER)
            tx_ref = request.POST.get('transaction_reference', '')
            notes = request.POST.get('notes', '')

            payment = PaymentService.record_payment(
                customer_id=customer_id,
                amount=amount,
                payment_date=p_date,
                payment_method=method,
                transaction_reference=tx_ref,
                invoice_id=invoice_id,
                user=request.user,
                notes=notes
            )

            messages.success(request, f"Payment {payment.payment_reference} for ₹{payment.amount} recorded successfully!")
            return redirect('payments:payment_list')

        except Exception as e:
            messages.error(request, f"Payment recording failed: {str(e)}")

    return render(request, 'payments/create_payment.html', {
        'customers': customers,
        'invoices': invoices,
        'preselected_invoice': preselected_invoice,
        'methods': PaymentMethod.choices,
        'today': timezone.now().date(),
    })


@login_required
def ageing_report_view(request):
    data = PaymentService.get_receivables_ageing()
    return render(request, 'payments/ageing_report.html', data)
