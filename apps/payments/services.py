from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.payments.models import Payment, PaymentAllocation, PaymentMethod
from apps.billing.models import Invoice, InvoiceStatus
from apps.masters.models import Customer

class PaymentService:
    """Service handling payment receipts, invoice allocation, and receivables ageing."""

    @classmethod
    @transaction.atomic
    def record_payment(cls, customer_id, amount, payment_date=None,
                       payment_method=PaymentMethod.BANK_TRANSFER,
                       transaction_reference='', invoice_id=None,
                       user=None, notes=''):
        """
        Record a customer payment and allocate it against outstanding invoices.
        Strictly prevents over-allocation beyond outstanding invoice amounts.
        """
        customer = Customer.objects.get(pk=customer_id)
        pmt_amount = Decimal(str(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if pmt_amount <= Decimal('0.00'):
            raise ValidationError("Payment amount must be greater than zero.")

        if not payment_date:
            payment_date = timezone.now().date()

        pmt_count = Payment.objects.count() + 1
        pmt_ref = f"PAY-{payment_date.strftime('%Y%m')}-{pmt_count:04d}"

        # If specific invoice targeted
        if invoice_id:
            invoice = Invoice.objects.select_for_update().get(pk=invoice_id)
            if invoice.customer_id != customer.id:
                raise ValidationError("Specified invoice does not belong to this customer.")
            if pmt_amount > invoice.outstanding_amount:
                raise ValidationError(
                    f"Payment amount (₹{pmt_amount}) exceeds invoice outstanding balance (₹{invoice.outstanding_amount})"
                )

            payment = Payment.objects.create(
                payment_reference=pmt_ref,
                customer=customer,
                payment_date=payment_date,
                payment_method=payment_method,
                amount=pmt_amount,
                transaction_reference=transaction_reference,
                notes=notes,
                received_by=user
            )

            PaymentAllocation.objects.create(
                payment=payment,
                invoice=invoice,
                allocated_amount=pmt_amount,
                allocation_date=payment_date
            )

            invoice.paid_amount += pmt_amount
            invoice.recalculate_outstanding()
            return payment

        # If no specific invoice, allocate across outstanding invoices (FIFO)
        unpaid_invoices = Invoice.objects.select_for_update().filter(
            customer=customer,
            status=InvoiceStatus.POSTED,
            outstanding_amount__gt=Decimal('0.00')
        ).order_by('invoice_date', 'id')

        total_outstanding = sum(inv.outstanding_amount for inv in unpaid_invoices)
        if pmt_amount > total_outstanding:
            raise ValidationError(
                f"Payment amount (₹{pmt_amount}) exceeds total customer outstanding balance (₹{total_outstanding})"
            )

        payment = Payment.objects.create(
            payment_reference=pmt_ref,
            customer=customer,
            payment_date=payment_date,
            payment_method=payment_method,
            amount=pmt_amount,
            transaction_reference=transaction_reference,
            notes=notes,
            received_by=user
        )

        remaining_to_allocate = pmt_amount
        for inv in unpaid_invoices:
            if remaining_to_allocate <= Decimal('0.00'):
                break
            alloc = min(remaining_to_allocate, inv.outstanding_amount)
            PaymentAllocation.objects.create(
                payment=payment,
                invoice=inv,
                allocated_amount=alloc,
                allocation_date=payment_date
            )
            inv.paid_amount += alloc
            inv.recalculate_outstanding()
            remaining_to_allocate -= alloc

        return payment

    @classmethod
    def get_receivables_ageing(cls, as_of_date=None):
        """
        Calculate customer-wise receivables ageing buckets:
        0-30 days, 31-60 days, 61-90 days, > 90 days
        """
        if not as_of_date:
            as_of_date = timezone.now().date()

        invoices = Invoice.objects.filter(
            status=InvoiceStatus.POSTED,
            outstanding_amount__gt=Decimal('0.00')
        ).select_related('customer')

        customer_ageing = {}
        grand_total = {
            'b_0_30': Decimal('0.00'),
            'b_31_60': Decimal('0.00'),
            'b_61_90': Decimal('0.00'),
            'b_90_plus': Decimal('0.00'),
            'total': Decimal('0.00'),
        }

        for inv in invoices:
            cid = inv.customer.id
            if cid not in customer_ageing:
                customer_ageing[cid] = {
                    'customer_id': cid,
                    'customer_name': inv.customer.name,
                    'customer_type': inv.customer.get_customer_type_display(),
                    'state': inv.customer.state,
                    'b_0_30': Decimal('0.00'),
                    'b_31_60': Decimal('0.00'),
                    'b_61_90': Decimal('0.00'),
                    'b_90_plus': Decimal('0.00'),
                    'total': Decimal('0.00'),
                }

            days = (as_of_date - inv.invoice_date).days
            amt = inv.outstanding_amount

            if days <= 30:
                customer_ageing[cid]['b_0_30'] += amt
                grand_total['b_0_30'] += amt
            elif 31 <= days <= 60:
                customer_ageing[cid]['b_31_60'] += amt
                grand_total['b_31_60'] += amt
            elif 61 <= days <= 90:
                customer_ageing[cid]['b_61_90'] += amt
                grand_total['b_61_90'] += amt
            else:
                customer_ageing[cid]['b_90_plus'] += amt
                grand_total['b_90_plus'] += amt

            customer_ageing[cid]['total'] += amt
            grand_total['total'] += amt

        return {
            'as_of_date': as_of_date,
            'customers': list(customer_ageing.values()),
            'grand_total': grand_total,
        }
