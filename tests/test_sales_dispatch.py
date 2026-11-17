from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.accounts.models import User
from apps.masters.models import UnitOfMeasurement, Category, Product, Customer
from apps.sales.models import SalesOrder, SalesOrderItem, SalesOrderStatus, Dispatch
from apps.sales.services import SalesOrderService, DispatchService
from apps.billing.services import InvoiceService


class SalesDispatchTestCase(TestCase):
    """
    Tests sales workflow:
    1. Order stock verification and shortage detection
    2. Prevention of dispatch when shortage exists
    3. Prevention of duplicate dispatch
    4. Proper stock deduction on successful dispatch
    """

    def setUp(self):
        self.admin = User.objects.create_superuser('admin_sd', 'sd@admin.com', 'pass123')
        self.salesman = User.objects.create_user('sales_sd', 'sales@sd.com', 'pass123', role=User.Role.SALESMAN)
        self.uom_pkts = UnitOfMeasurement.objects.create(code='packets', name='Packets', dimension=UnitOfMeasurement.Dimension.DISCRETE)
        self.cat = Category.objects.create(name='Snacks')
        self.product = Product.objects.create(
            name='Ribbon Pakoda 200 g', product_code='PRD-RIB-200G', category=self.cat,
            pack_size='200 g', uom=self.uom_pkts, selling_price=Decimal('55.00'),
            opening_stock=Decimal('80.000'), current_stock=Decimal('80.000'),
            gst_rate=Decimal('5.00')
        )
        self.customer = Customer.objects.create(
            name='Chennai Wholesale Traders', customer_code='CUST-CHE-01',
            billing_address='Koyambedu Market, Chennai', phone='+91 94440 12345',
            state='Tamil Nadu', state_code='33'
        )

    def test_shortage_detection_and_dispatch_block(self):
        """Order quantity exceeding available inventory triggers shortage and blocks dispatch."""
        # Available stock: 80 packets. Order: 100 packets.
        order = SalesOrderService.create_order(
            customer_id=self.customer.id,
            salesman=self.salesman,
            items_data=[{'product_id': self.product.id, 'quantity': '100.000', 'unit_price': '55.00'}],
        )

        stock_check = SalesOrderService.check_stock_availability(order)
        self.assertTrue(stock_check['has_shortage'])
        self.assertEqual(stock_check['total_shortage_quantity'], Decimal('20.000'))

        # Attempting dispatch MUST fail with ValidationError
        with self.assertRaises(ValidationError) as ctx:
            DispatchService.record_dispatch(
                sales_order_id=order.id,
                user=self.admin
            )
        self.assertIn("shortage", str(ctx.exception).lower())

        # Stock must remain unaffected at 80 packets
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, Decimal('80.000'))

    def test_successful_dispatch_and_stock_deduction(self):
        """Dispatch within available inventory succeeds and deducts stock."""
        # Order: 50 packets (available: 80)
        order = SalesOrderService.create_order(
            customer_id=self.customer.id,
            salesman=self.salesman,
            items_data=[{'product_id': self.product.id, 'quantity': '50.000', 'unit_price': '55.00'}],
        )
        SalesOrderService.approve_order(order.id, admin_user=self.admin)
        inv = InvoiceService.generate_invoice_from_order(order.id, user=self.admin)

        dsp = DispatchService.record_dispatch(
            sales_order_id=order.id,
            invoice_id=inv.id,
            user=self.admin,
            transporter_name='TN Parcel Service',
            vehicle_number='TN-45-C-9999'
        )
        self.assertIsNotNone(dsp)

        # Finished goods stock reduced from 80 to 30 pkts
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, Decimal('30.000'))

        order.refresh_from_db()
        self.assertEqual(order.status, SalesOrderStatus.DISPATCHED)

    def test_duplicate_dispatch_prevention(self):
        """Attempting to dispatch an already-dispatched order MUST raise ValidationError."""
        order = SalesOrderService.create_order(
            customer_id=self.customer.id,
            salesman=self.salesman,
            items_data=[{'product_id': self.product.id, 'quantity': '30.000', 'unit_price': '55.00'}],
        )
        SalesOrderService.approve_order(order.id, admin_user=self.admin)
        inv = InvoiceService.generate_invoice_from_order(order.id, user=self.admin)

        # Dispatch 1: Succeeds
        DispatchService.record_dispatch(sales_order_id=order.id, invoice_id=inv.id, user=self.admin)

        # Dispatch 2: Must fail
        with self.assertRaises(ValidationError) as ctx:
            DispatchService.record_dispatch(sales_order_id=order.id, invoice_id=inv.id, user=self.admin)
        self.assertIn("already been dispatched", str(ctx.exception))
