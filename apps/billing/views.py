from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.utils import timezone

from apps.accounts.decorators import role_required
from apps.billing.models import Invoice, InvoiceItem, CreditNote, InvoiceStatus
from apps.billing.services import InvoiceService, GSTService
from apps.billing.pdf import generate_invoice_pdf
from apps.masters.models import Customer

@login_required
def invoice_list(request):
    invoices = Invoice.objects.select_related('customer', 'sales_order').order_by('-invoice_date', '-id')
    
    customer_id = request.GET.get('customer')
    if customer_id:
        invoices = invoices.filter(customer_id=customer_id)

    status_filter = request.GET.get('status')
    if status_filter:
        invoices = invoices.filter(status=status_filter)

    customers = Customer.objects.filter(is_active=True).order_by('name')

    return render(request, 'billing/invoice_list.html', {
        'invoices': invoices,
        'customers': customers,
        'selected_customer': int(customer_id) if customer_id else None,
        'selected_status': status_filter,
    })


@login_required
def invoice_detail(request, pk):
    invoice = get_object_or_404(
        Invoice.objects.select_related('customer', 'sales_order', 'created_by').prefetch_related(
            'items__product',
            'payment_allocations__payment',
            'credit_notes'
        ),
        pk=pk
    )

    return render(request, 'billing/invoice_detail.html', {
        'invoice': invoice,
        'items': invoice.items.all(),
        'allocations': invoice.payment_allocations.all(),
        'credit_notes': invoice.credit_notes.all(),
    })


@login_required
def download_pdf_invoice(request, pk):
    invoice = get_object_or_404(
        Invoice.objects.select_related('customer', 'sales_order').prefetch_related('items__product'),
        pk=pk
    )
    pdf_bytes = generate_invoice_pdf(invoice)

    clean_num = invoice.invoice_number.replace('/', '_')
    filename = f"Invoice_{clean_num}.pdf"

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@role_required('ADMIN')
def issue_credit_note(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if request.method == 'POST':
        try:
            amount = request.POST.get('amount')
            reason = request.POST.get('reason', 'Goods return / pricing adjustment')
            cn = InvoiceService.issue_credit_note(invoice.id, amount, reason, user=request.user)
            messages.success(request, f"Credit Note {cn.credit_note_number} issued for ₹{cn.amount}. Outstanding updated.")
        except Exception as e:
            messages.error(request, f"Credit Note failed: {str(e)}")
    return redirect('billing:invoice_detail', pk=invoice.id)


@login_required
def credit_note_list(request):
    credit_notes = CreditNote.objects.select_related('invoice__customer', 'created_by').order_by('-date', '-id')
    return render(request, 'billing/credit_note_list.html', {'credit_notes': credit_notes})
