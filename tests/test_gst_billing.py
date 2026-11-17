from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from apps.accounts.models import User
from apps.masters.models import UnitOfMeasurement, Category, Product, Customer
from apps.sales.models import SalesOrder, SalesOrderItem, SalesOrderStatus
from apps.sales.services import SalesOrderService
from apps.billing.models import Invoice, InvoiceItem, CreditNote
from apps.billing.services import GSTService, InvoiceService
from apps.billing.pdf import generate_invoice_pdf


class GSTBillingTestCase(TestCase):
    """
    Tests GST calculation engine:
    1. Intra-state: Tamil Nadu to Tamil Nadu (CGST 2.5% + SGST 2.5%, IGST 0.00%)
    2. Interstate: Tamil Nadu to Karnataka (IGST 5.0%, CGST 0.00%, SGST 0.00%)
    3. FY invoice numbering (e.g. INV/2026-27/0001)
    4. ReportLab PDF generation
    5. Credit note issuance and balance reduction
    """

    def setUp(self):
        self.admin = User.objects.create_superuser('admin_gst', 'gst@admin.com', 'pass123')
        self.salesman = User.objects.create_user('sales_gst', 'sgst@admin.com', 'pass123', role=User.Role.SALESMAN)
        self.uom_pkts = UnitOfMeasurement.objects.create(code='packets', name='Packets', dimension=UnitOfMeasurement.Dimension.DISCRETE)
        self.cat = Category.objects.create(name='Snacks')
        self.product = Product.objects.create(
            name='Murukku 200 g', product_code='PRD-MRK-200G', category=self.cat,
            pack_size='200 g', uom=self.uom_pkts, selling_price=Decimal('50.00'),
            opening_stock=Decimal('500.000'), current_stock=Decimal('500.000'),
            gst_rate=Decimal('5.00')
        )
        self.cust_tn = Customer.objects.create(
            name='Retailer TN', customer_code='CUST-TN-01', customer_type=Customer.CustomerType.RETAILER,
            gstin='33AAAAA1111A1Z1', billing_address='Trichy', phone='+91 94431 11111',
            state='Tamil Nadu', state_code='33'
        )
        self.cust_ka = Customer.objects.create(
            name='Distributor KA', customer_code='CUST-KA-01', customer_type=Customer.CustomerType.DISTRIBUTOR,
            gstin='29BBBBB2222B1Z2', billing_address='Bengaluru', phone='+91 98450 22222',
            state='Karnataka', state_code='29'
        )

    def test_intrastate_gst_calculation(self):
        """Intra-state sales split GST 50/50 into CGST and SGST with no IGST."""
        taxes = GSTService.calculate_taxes(Decimal('7500.00'), Decimal('5.00'), is_interstate=False)
        self.assertEqual(taxes['cgst_rate'], Decimal('2.50'))
        self.assertEqual(taxes['cgst_amount'], Decimal('187.50'))
        self.assertEqual(taxes['sgst_rate'], Decimal('2.50'))
        self.assertEqual(taxes['sgst_amount'], Decimal('187.50'))
        self.assertEqual(taxes['igst_amount'], Decimal('0.00'))
        self.assertEqual(taxes['total_tax'], Decimal('375.00'))
        self.assertEqual(taxes['total_amount'], Decimal('7875.00'))

    def test_interstate_gst_calculation(self):
        """Interstate sales apply full GST rate to IGST with zero CGST/SGST."""
        taxes = GSTService.calculate_taxes(Decimal('10000.00'), Decimal('5.00'), is_interstate=True)
        self.assertEqual(taxes['cgst_rate'], Decimal('0.00'))
        self.assertEqual(taxes['cgst_amount'], Decimal('0.00'))
        self.assertEqual(taxes['sgst_rate'], Decimal('0.00'))
        self.assertEqual(taxes['sgst_amount'], Decimal('0.00'))
        self.assertEqual(taxes['igst_rate'], Decimal('5.00'))
        self.assertEqual(taxes['igst_amount'], Decimal('500.00'))
        self.assertEqual(taxes['total_tax'], Decimal('500.00'))
        self.assertEqual(taxes['total_amount'], Decimal('10500.00'))

    def test_invoice_generation_and_pdf_download(self):
        """Test invoice creation from sales order and ensure ReportLab produces a valid PDF."""
        order = SalesOrderService.create_order(
            customer_id=self.cust_tn.id,
            salesman=self.salesman,
            items_data=[{'product_id': self.product.id, 'quantity': '100.000', 'unit_price': '50.00'}],
            notes='Test order for PDF'
        )
        SalesOrderService.approve_order(order.id, admin_user=self.admin)
        invoice = InvoiceService.generate_invoice_from_order(order.id, user=self.admin)

        self.assertIsNotNone(invoice)
        self.assertTrue(invoice.invoice_number.startswith('INV/'))
        self.assertEqual(invoice.taxable_amount, Decimal('5000.00'))
        self.assertEqual(invoice.cgst_amount, Decimal('125.00'))
        self.assertEqual(invoice.sgst_amount, Decimal('125.00'))
        self.assertEqual(invoice.grand_total, Decimal('5250.00'))

        # Generate PDF and check header
        pdf_bytes = generate_invoice_pdf(invoice)
        self.assertTrue(len(pdf_bytes) > 1000)
        self.assertTrue(pdf_bytes.startswith(b'%PDF-'))

    def test_credit_note_issuance(self):
        """Credit note reduces outstanding amount on the invoice."""
        order = SalesOrderService.create_order(
            customer_id=self.cust_tn.id,
            salesman=self.salesman,
            items_data=[{'product_id': self.product.id, 'quantity': '20.000', 'unit_price': '50.00'}],
        )
        SalesOrderService.approve_order(order.id, admin_user=self.admin)
        invoice = InvoiceService.generate_invoice_from_order(order.id, user=self.admin)

        # Total = 1000 + 50 = 1050. Issue credit note for Rs. 250
        cn = InvoiceService.issue_credit_note(
            invoice_id=invoice.id,
            amount=Decimal('250.00'),
            reason='Return of 5 damaged packets during transit',
            user=self.admin
        )
        self.assertIsNotNone(cn)
        self.assertTrue(cn.credit_note_number.startswith('CN/'))

        invoice.refresh_from_db()
        self.assertEqual(invoice.credit_note_amount, Decimal('250.00'))
        self.assertEqual(invoice.outstanding_amount, Decimal('800.00')) # 1050 - 250
