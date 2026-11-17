from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.billing.models import Invoice, InvoiceItem, CreditNote, InvoiceStatus
from apps.sales.models import SalesOrder, SalesOrderStatus
from apps.masters.models import Customer, Product

class GSTService:
    """GST calculation logic for intra-state (TN) and interstate transactions."""

    @classmethod
    def get_financial_year(cls, d):
        if not d:
            d = timezone.now().date()
        year = d.year
        if d.month >= 4:
            fy_start = year
            fy_end = (year + 1) % 100
        else:
            fy_start = year - 1
            fy_end = year % 100
        return f"{fy_start}-{fy_end:02d}"

    @classmethod
    def calculate_taxes(cls, taxable_amount, gst_rate, is_interstate):
        taxable = Decimal(str(taxable_amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        rate = Decimal(str(gst_rate)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        if is_interstate:
            # Interstate: IGST applies at full rate
            cgst_rate = Decimal('0.00')
            cgst_amt = Decimal('0.00')
            sgst_rate = Decimal('0.00')
            sgst_amt = Decimal('0.00')
            igst_rate = rate
            igst_amt = (taxable * (igst_rate / Decimal('100.0'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            total_tax = igst_amt
        else:
            # Intra-state (Tamil Nadu to Tamil Nadu): CGST + SGST split 50/50
            cgst_rate = (rate / Decimal('2.0')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            sgst_rate = (rate / Decimal('2.0')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            cgst_amt = (taxable * (cgst_rate / Decimal('100.0'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            sgst_amt = (taxable * (sgst_rate / Decimal('100.0'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            igst_rate = Decimal('0.00')
            igst_amt = Decimal('0.00')
            total_tax = cgst_amt + sgst_amt

        return {
            'cgst_rate': cgst_rate,
            'cgst_amount': cgst_amt,
            'sgst_rate': sgst_rate,
            'sgst_amount': sgst_amt,
            'igst_rate': igst_rate,
            'igst_amount': igst_amt,
            'total_tax': total_tax,
            'total_amount': taxable + total_tax,
        }


class InvoiceService:
    """Service for managing GST invoices and Credit Notes."""

    @classmethod
    def generate_invoice_number(cls, financial_year):
        count = Invoice.objects.filter(financial_year=financial_year).count() + 1
        return f"INV/{financial_year}/{count:04d}"

    @classmethod
    @transaction.atomic
    def generate_invoice_from_order(cls, sales_order_id, user=None, invoice_date=None):
        """Generate a GST-compliant tax invoice from an approved sales order."""
        order = SalesOrder.objects.select_for_update().get(pk=sales_order_id)
        if order.status not in (SalesOrderStatus.APPROVED, SalesOrderStatus.SUBMITTED):
            raise ValidationError(f"Cannot generate invoice for order {order.order_number} in status {order.status}")

        if not invoice_date:
            invoice_date = timezone.now().date()

        fy = GSTService.get_financial_year(invoice_date)
        inv_number = cls.generate_invoice_number(fy)

        customer = order.customer
        is_interstate = customer.is_interstate

        invoice = Invoice.objects.create(
            invoice_number=inv_number,
            sales_order=order,
            customer=customer,
            invoice_date=invoice_date,
            financial_year=fy,
            is_interstate=is_interstate,
            customer_gstin=customer.gstin,
            billing_address=customer.billing_address,
            state=customer.state,
            state_code=customer.state_code,
            status=InvoiceStatus.POSTED,
            created_by=user,
            posted_at=timezone.now(),
            notes=f"Generated from Sales Order {order.order_number}"
        )

        total_taxable = Decimal('0.00')
        total_cgst = Decimal('0.00')
        total_sgst = Decimal('0.00')
        total_igst = Decimal('0.00')
        total_tax = Decimal('0.00')
        grand_total = Decimal('0.00')

        for item in order.items.all():
            taxable = (item.quantity * item.unit_price).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            tax_calc = GSTService.calculate_taxes(taxable, item.gst_rate, is_interstate)

            InvoiceItem.objects.create(
                invoice=invoice,
                product=item.product,
                hsn_code=item.product.hsn_code,
                description=f"{item.product.name} ({item.product.pack_size})",
                quantity=item.quantity,
                unit_price=item.unit_price,
                taxable_amount=taxable,
                gst_rate=item.gst_rate,
                cgst_rate=tax_calc['cgst_rate'],
                cgst_amount=tax_calc['cgst_amount'],
                sgst_rate=tax_calc['sgst_rate'],
                sgst_amount=tax_calc['sgst_amount'],
                igst_rate=tax_calc['igst_rate'],
                igst_amount=tax_calc['igst_amount'],
                total_amount=tax_calc['total_amount']
            )

            total_taxable += taxable
            total_cgst += tax_calc['cgst_amount']
            total_sgst += tax_calc['sgst_amount']
            total_igst += tax_calc['igst_amount']
            total_tax += tax_calc['total_tax']
            grand_total += tax_calc['total_amount']

        invoice.taxable_amount = total_taxable
        invoice.cgst_amount = total_cgst
        invoice.sgst_amount = total_sgst
        invoice.igst_amount = total_igst
        invoice.total_tax = total_tax
        invoice.grand_total = grand_total
        invoice.outstanding_amount = grand_total
        invoice.save()

        # Update order status to INVOICED
        order.status = SalesOrderStatus.INVOICED
        order.save(update_fields=['status', 'updated_at'])

        return invoice

    @classmethod
    @transaction.atomic
    def issue_credit_note(cls, invoice_id, amount, reason, user=None):
        """Issue credit note against posted invoice."""
        invoice = Invoice.objects.select_for_update().get(pk=invoice_id)
        cn_amount = Decimal(str(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        if cn_amount <= Decimal('0.00'):
            raise ValidationError("Credit note amount must be strictly positive.")
        if cn_amount > invoice.outstanding_amount:
            raise ValidationError(f"Credit note amount (₹{cn_amount}) exceeds invoice outstanding (₹{invoice.outstanding_amount})")

        fy = GSTService.get_financial_year(timezone.now().date())
        cn_count = CreditNote.objects.count() + 1
        cn_number = f"CN/{fy}/{cn_count:04d}"

        cn = CreditNote.objects.create(
            credit_note_number=cn_number,
            invoice=invoice,
            date=timezone.now().date(),
            reason=reason,
            amount=cn_amount,
            created_by=user
        )

        invoice.credit_note_amount += cn_amount
        invoice.recalculate_outstanding()

        return cn
