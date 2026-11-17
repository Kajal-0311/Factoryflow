from decimal import Decimal
import datetime
from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.accounts.models import User
from apps.masters.models import UnitOfMeasurement, Category, Product, Customer
from apps.billing.models import Invoice, InvoiceItem, InvoiceStatus
from apps.payments.models import Payment, PaymentMethod, PaymentAllocation
from apps.payments.services import PaymentService


class PaymentsAgeingTestCase(TestCase):
    """
    Tests payment recording, FIFO invoice allocation, overpayment prevention,
    and receivables ageing buckets (0-30, 31-60, 61-90, 90+ days).
    """

    def setUp(self):
        self.user = User.objects.create_superuser('pay_admin', 'pay@admin.com', 'pass123')
        self.uom_pkts = UnitOfMeasurement.objects.create(code='packets', name='Packets', dimension=UnitOfMeasurement.Dimension.DISCRETE)
        self.cat = Category.objects.create(name='Snacks')
        self.product = Product.objects.create(
            name='Banana Chips 200 g', product_code='PRD-BAN-200G', category=self.cat,
            pack_size='200 g', uom=self.uom_pkts, selling_price=Decimal('70.00'),
            opening_stock=Decimal('100.000'), current_stock=Decimal('100.000'),
        )
        self.customer = Customer.objects.create(
            name='Coimbatore Sweets', customer_code='CUST-CBE-01',
            billing_address='Cross Cut Road, Coimbatore', phone='+91 94422 33333',
            state='Tamil Nadu', state_code='33'
        )

    def test_payment_allocation_and_outstanding(self):
        """Record payment against a specific invoice and verify outstanding balance reduction."""
        inv = Invoice.objects.create(
            invoice_number='INV/2026-27/0010',
            customer=self.customer,
            invoice_date=timezone.now().date(),
            financial_year='2026-27',
            state='Tamil Nadu', state_code='33',
            taxable_amount=Decimal('7000.00'),
            cgst_amount=Decimal('175.00'),
            sgst_amount=Decimal('175.00'),
            total_tax=Decimal('350.00'),
            grand_total=Decimal('7350.00'),
            outstanding_amount=Decimal('7350.00'),
            status=InvoiceStatus.POSTED
        )

        # Partial payment of Rs. 3,350
        pmt = PaymentService.record_payment(
            customer_id=self.customer.id,
            amount=Decimal('3350.00'),
            payment_method=PaymentMethod.UPI,
            transaction_reference='UPI-GPay-98127391',
            invoice_id=inv.id,
            user=self.user
        )
        self.assertIsNotNone(pmt)
        inv.refresh_from_db()
        self.assertEqual(inv.paid_amount, Decimal('3350.00'))
        self.assertEqual(inv.outstanding_amount, Decimal('4000.00'))

        # Full payment of remainder Rs. 4,000
        pmt2 = PaymentService.record_payment(
            customer_id=self.customer.id,
            amount=Decimal('4000.00'),
            payment_method=PaymentMethod.BANK_TRANSFER,
            transaction_reference='NEFT-HDFC-10928301',
            invoice_id=inv.id,
            user=self.user
        )
        inv.refresh_from_db()
        self.assertEqual(inv.paid_amount, Decimal('7350.00'))
        self.assertEqual(inv.outstanding_amount, Decimal('0.00'))

    def test_overpayment_prevention(self):
        """Attempting to pay more than the outstanding invoice amount MUST raise ValidationError."""
        inv = Invoice.objects.create(
            invoice_number='INV/2026-27/0011',
            customer=self.customer,
            invoice_date=timezone.now().date(),
            financial_year='2026-27',
            state='Tamil Nadu', state_code='33',
            grand_total=Decimal('1000.00'),
            outstanding_amount=Decimal('1000.00'),
            status=InvoiceStatus.POSTED
        )
        # Attempt to pay Rs. 1,500
        with self.assertRaises(ValidationError) as ctx:
            PaymentService.record_payment(
                customer_id=self.customer.id,
                amount=Decimal('1500.00'),
                invoice_id=inv.id,
                user=self.user
            )
        self.assertIn("exceeds invoice outstanding balance", str(ctx.exception))

    def test_receivables_ageing_buckets(self):
        """Test calculation of ageing buckets across 0-30, 31-60, 61-90, and 90+ days."""
        today = timezone.now().date()

        # Bucket 0-30 days: 10 days old invoice
        Invoice.objects.create(
            invoice_number='INV/2026-27/0020', customer=self.customer,
            invoice_date=today - datetime.timedelta(days=10),
            financial_year='2026-27', state='Tamil Nadu', state_code='33',
            grand_total=Decimal('1000.00'), outstanding_amount=Decimal('1000.00'),
            status=InvoiceStatus.POSTED
        )
        # Bucket 31-60 days: 45 days old invoice
        Invoice.objects.create(
            invoice_number='INV/2026-27/0021', customer=self.customer,
            invoice_date=today - datetime.timedelta(days=45),
            financial_year='2026-27', state='Tamil Nadu', state_code='33',
            grand_total=Decimal('2000.00'), outstanding_amount=Decimal('2000.00'),
            status=InvoiceStatus.POSTED
        )
        # Bucket 61-90 days: 75 days old invoice
        Invoice.objects.create(
            invoice_number='INV/2026-27/0022', customer=self.customer,
            invoice_date=today - datetime.timedelta(days=75),
            financial_year='2026-27', state='Tamil Nadu', state_code='33',
            grand_total=Decimal('3000.00'), outstanding_amount=Decimal('3000.00'),
            status=InvoiceStatus.POSTED
        )
        # Bucket 90+ days: 120 days old invoice
        Invoice.objects.create(
            invoice_number='INV/2026-27/0023', customer=self.customer,
            invoice_date=today - datetime.timedelta(days=120),
            financial_year='2026-27', state='Tamil Nadu', state_code='33',
            grand_total=Decimal('4000.00'), outstanding_amount=Decimal('4000.00'),
            status=InvoiceStatus.POSTED
        )

        ageing = PaymentService.get_receivables_ageing(as_of_date=today)
        gt = ageing['grand_total']

        self.assertEqual(gt['b_0_30'], Decimal('1000.00'))
        self.assertEqual(gt['b_31_60'], Decimal('2000.00'))
        self.assertEqual(gt['b_61_90'], Decimal('3000.00'))
        self.assertEqual(gt['b_90_plus'], Decimal('4000.00'))
        self.assertEqual(gt['total'], Decimal('10000.00'))
