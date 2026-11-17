from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.accounts.models import User
from apps.masters.models import (
    UnitOfMeasurement, Category, Product, RawMaterial, PackagingMaterial, Customer, Supplier
)
from apps.inventory.models import StockLedger, StockBalance, StockTransactionType, StockItemType
from apps.inventory.services import InventoryService
from apps.bom.models import BOM, BOMItem
from apps.bom.services import BOMService
from apps.purchases.models import Purchase, PurchaseItem, PurchaseStatus
from apps.purchases.services import PurchaseService
from apps.production.models import ProductionRun, ProductionRunStatus, CostingRecord, Overhead
from apps.production.services import ProductionService
from apps.sales.models import SalesOrder, SalesOrderItem, SalesOrderStatus, Dispatch
from apps.sales.services import SalesOrderService, DispatchService
from apps.billing.models import Invoice, InvoiceStatus
from apps.billing.services import InvoiceService, GSTService
from apps.payments.models import Payment, PaymentMethod
from apps.payments.services import PaymentService


class BenchmarkScenarioTestCase(TestCase):
    """
    Exact Reproduction of NIT Trichy Mandatory Benchmark Scenario:
    1. Opening Raw Materials, Packaging, and Finished Goods
    2. Purchase Inward: 60 kg Flour @ Rs. 45/kg -> WAC = Rs. 43.1250/kg
    3. Production of Murukku (200 g): 188 pkts good output (-6% yield variance)
       - Cooking oil: 10.5 L (+5% variance)
       - Pouches: 194 consumed (including 6 damaged)
       - Cartons: 9 consumed
       - Direct Cost: RM & Pkg Rs. 4,055 + Labour Rs. 1,200 + Power Rs. 600 = Rs. 5,855
       - Cost per packet: Rs. 31.14, Gross margin: Rs. 18.86 (at Rs. 50 selling price)
    4. Sales Order 1 (Retailer A, TN): 150 pkts -> Taxable Rs. 7,500, CGST Rs. 187.50, SGST Rs. 187.50, Total Rs. 7,875
       - Payment: Rs. 4,000 -> Outstanding Rs. 3,875
    5. Sales Order 2 (Distributor B, Karnataka): 120 pkts -> 32 pkts shortage detected, dispatch prevented.
    """

    def setUp(self):
        # 1. Users
        self.admin = User.objects.create_superuser('admin_user', 'admin@example.com', 'pass123')
        self.supervisor = User.objects.create_user(
            'super_user', 'super@example.com', 'pass123', role=User.Role.PRODUCTION_SUPERVISOR
        )
        self.salesman_tn = User.objects.create_user(
            'sales_tn', 'sales_tn@example.com', 'pass123', role=User.Role.SALESMAN
        )
        self.salesman_ka = User.objects.create_user(
            'sales_ka', 'sales_ka@example.com', 'pass123', role=User.Role.SALESMAN
        )
        self.auditor = User.objects.create_user(
            'auditor_user', 'audit@example.com', 'pass123', role=User.Role.OWNER_AUDITOR
        )

        # 2. Units of Measurement
        self.uom_kg = UnitOfMeasurement.objects.create(code='kg', name='Kilogram', dimension=UnitOfMeasurement.Dimension.MASS)
        self.uom_litre = UnitOfMeasurement.objects.create(code='litre', name='Litre', dimension=UnitOfMeasurement.Dimension.VOLUME)
        self.uom_pcs = UnitOfMeasurement.objects.create(code='pieces', name='Pieces', dimension=UnitOfMeasurement.Dimension.DISCRETE)
        self.uom_pkts = UnitOfMeasurement.objects.create(code='packets', name='Packets', dimension=UnitOfMeasurement.Dimension.DISCRETE)
        self.uom_box = UnitOfMeasurement.objects.create(code='cartons', name='Cartons', dimension=UnitOfMeasurement.Dimension.DISCRETE)

        # 3. Categories
        self.cat_snacks = Category.objects.create(name='Snacks', description='Snacks category')

        # 4. Product
        self.product = Product.objects.create(
            name='Murukku 200 g',
            product_code='PRD-MRK-200G',
            category=self.cat_snacks,
            pack_size='200 g',
            uom=self.uom_pkts,
            selling_price=Decimal('50.00'),
            opening_stock=Decimal('50.000'),
            current_stock=Decimal('50.000'),
            hsn_code='1905',
            gst_rate=Decimal('5.00'),
            packets_per_carton=20,
        )

        # 5. Raw Materials
        self.rm_flour = RawMaterial.objects.create(
            name='Flour',
            material_code='RM-FLOUR',
            uom=self.uom_kg,
            opening_stock=Decimal('100.000'),
            current_stock=Decimal('100.000'),
            weighted_average_cost=Decimal('42.0000'),
            purchase_rate=Decimal('42.00'),
            reorder_level=Decimal('20.000'),
        )
        self.rm_oil = RawMaterial.objects.create(
            name='Cooking oil',
            material_code='RM-OIL',
            uom=self.uom_litre,
            opening_stock=Decimal('30.000'),
            current_stock=Decimal('30.000'),
            weighted_average_cost=Decimal('140.0000'),
            purchase_rate=Decimal('140.00'),
            reorder_level=Decimal('10.000'),
        )
        self.rm_spice = RawMaterial.objects.create(
            name='Salt and spice mix',
            material_code='RM-SPICE',
            uom=self.uom_kg,
            opening_stock=Decimal('5.000'),
            current_stock=Decimal('5.000'),
            weighted_average_cost=Decimal('200.0000'),
            purchase_rate=Decimal('200.00'),
            reorder_level=Decimal('2.000'),
        )

        # 6. Packaging Materials
        self.pm_pouch = PackagingMaterial.objects.create(
            name='200 g pouch',
            material_code='PM-POUCH-200G',
            packaging_type=PackagingMaterial.PackagingType.POUCH,
            uom=self.uom_pcs,
            opening_stock=Decimal('500.000'),
            current_stock=Decimal('500.000'),
            purchase_rate=Decimal('2.50'),
            reorder_level=Decimal('100.000'),
        )
        self.pm_carton = PackagingMaterial.objects.create(
            name='Carton',
            material_code='PM-CARTON-200G',
            packaging_type=PackagingMaterial.PackagingType.CARTON,
            uom=self.uom_pcs,
            opening_stock=Decimal('30.000'),
            current_stock=Decimal('30.000'),
            purchase_rate=Decimal('15.00'),
            reorder_level=Decimal('10.000'),
        )

        # 7. Customers & Suppliers
        self.customer_a = Customer.objects.create(
            name='Retailer A',
            customer_code='CUST-RET-A',
            customer_type=Customer.CustomerType.RETAILER,
            gstin='33AAAAA1111A1Z1',
            billing_address='12 Main Bazaar, Tiruchirappalli',
            phone='+91 94431 11111',
            state='Tamil Nadu',
            state_code='33',
            credit_limit=Decimal('50000.00'),
        )
        self.customer_b = Customer.objects.create(
            name='Distributor B',
            customer_code='CUST-DST-B',
            customer_type=Customer.CustomerType.DISTRIBUTOR,
            gstin='29BBBBB2222B1Z2',
            billing_address='45 Industrial Area, Bengaluru',
            phone='+91 98450 22222',
            state='Karnataka',
            state_code='29',
            credit_limit=Decimal('100000.00'),
        )
        self.supplier = Supplier.objects.create(
            name='Southern Agri Traders',
            supplier_code='SUP-SAT-01',
            gstin='33CCCC9999C1Z9',
            address='Dindigul Road, Trichy',
            phone='+91 431 2400000',
            state='Tamil Nadu',
            state_code='33',
        )

        # 8. BOM Definition: Murukku 200 g, Batch = 200 pkts
        self.bom = BOM.objects.create(
            product=self.product,
            bom_code='BOM-MRK-200-V1',
            batch_size=Decimal('200.000'),
            expected_output=Decimal('200.000'),
            standard_yield_percent=Decimal('100.00'),
            is_active=True,
            notes='Standard 200 packet batch recipe',
        )
        BOMItem.objects.create(
            bom=self.bom,
            item_type=BOMItem.ItemType.RAW_MATERIAL,
            raw_material=self.rm_flour,
            standard_quantity=Decimal('40.000'),
            uom=self.uom_kg,
        )
        BOMItem.objects.create(
            bom=self.bom,
            item_type=BOMItem.ItemType.RAW_MATERIAL,
            raw_material=self.rm_oil,
            standard_quantity=Decimal('10.000'),
            uom=self.uom_litre,
        )
        BOMItem.objects.create(
            bom=self.bom,
            item_type=BOMItem.ItemType.RAW_MATERIAL,
            raw_material=self.rm_spice,
            standard_quantity=Decimal('1.200'),
            uom=self.uom_kg,
        )
        BOMItem.objects.create(
            bom=self.bom,
            item_type=BOMItem.ItemType.PACKAGING_MATERIAL,
            packaging_material=self.pm_pouch,
            standard_quantity=Decimal('200.000'),
            uom=self.uom_pcs,
        )
        BOMItem.objects.create(
            bom=self.bom,
            item_type=BOMItem.ItemType.PACKAGING_MATERIAL,
            packaging_material=self.pm_carton,
            standard_quantity=Decimal('10.000'),
            uom=self.uom_pcs,
        )

    def test_complete_benchmark_flow(self):
        """Execute and assert the complete NIT Trichy benchmark workflow."""
        # -------------------------------------------------------------
        # STEP 1: Purchase Receipt & WAC Recalculation
        # -------------------------------------------------------------
        purchase = Purchase.objects.create(
            purchase_number='PUR-TEST-0001',
            supplier=self.supplier,
            supplier_invoice_ref='SUP-INV-9821',
            purchase_date=timezone.now().date(),
            taxable_amount=Decimal('2700.00'),
            gst_amount=Decimal('135.00'),
            total_amount=Decimal('2835.00'),
            notes='Benchmark Purchase: 60 kg Flour @ Rs. 45/kg',
            created_by=self.supervisor,
        )
        PurchaseItem.objects.create(
            purchase=purchase,
            item_type=PurchaseItem.ItemType.RAW_MATERIAL,
            raw_material=self.rm_flour,
            quantity=Decimal('60.000'),
            uom=self.uom_kg,
            purchase_rate=Decimal('45.0000'),
            gst_rate=Decimal('5.00'),
            taxable_amount=Decimal('2700.00'),
            gst_amount=Decimal('135.00'),
            total_amount=Decimal('2835.00'),
        )
        # Confirm Purchase
        PurchaseService.confirm_purchase(purchase.id, user=self.supervisor)
        
        self.rm_flour.refresh_from_db()
        # Initial: 100 kg @ Rs. 42 = Rs. 4,200
        # Inward:   60 kg @ Rs. 45 = Rs. 2,700
        # Total:   160 kg, Value = Rs. 6,900
        # WAC = 6900 / 160 = Rs. 43.1250 / kg
        self.assertEqual(self.rm_flour.current_stock, Decimal('160.000'))
        self.assertEqual(self.rm_flour.weighted_average_cost, Decimal('43.1250'))

        # -------------------------------------------------------------
        # STEP 2: Production Execution & 3% Variance Alert
        # -------------------------------------------------------------
        consumptions_data = [
            {'item_type': 'RAW_MATERIAL', 'raw_material_id': self.rm_flour.id, 'planned_quantity': '40.000', 'actual_quantity': '40.000'},
            {'item_type': 'RAW_MATERIAL', 'raw_material_id': self.rm_oil.id, 'planned_quantity': '10.000', 'actual_quantity': '10.500'},
            {'item_type': 'RAW_MATERIAL', 'raw_material_id': self.rm_spice.id, 'planned_quantity': '1.200', 'actual_quantity': '1.200'},
            {'item_type': 'PACKAGING_MATERIAL', 'packaging_material_id': self.pm_pouch.id, 'planned_quantity': '200.000', 'actual_quantity': '194.000', 'damaged_quantity': '6.000'},
            {'item_type': 'PACKAGING_MATERIAL', 'packaging_material_id': self.pm_carton.id, 'planned_quantity': '10.000', 'actual_quantity': '9.000'},
        ]
        overheads_data = [
            {'overhead_type': Overhead.OverheadType.LABOUR, 'description': 'Batch Direct Labour', 'amount': '1200.00'},
            {'overhead_type': Overhead.OverheadType.POWER_GAS, 'description': 'LPG and Electricity Power', 'amount': '600.00'},
        ]

        run, costing = ProductionService.execute_production_run(
            product_id=self.product.id,
            batch_quantity=Decimal('200.000'),
            actual_good_output=Decimal('188.000'),
            consumptions_data=consumptions_data,
            overheads_data=overheads_data,
            wastage_quantity=Decimal('12.000'),
            production_date=timezone.now().date(),
            supervisor=self.supervisor,
            notes='Benchmark Production Run'
        )

        run.refresh_from_db()
        self.assertEqual(run.status, ProductionRunStatus.COMPLETED)
        self.assertEqual(run.actual_good_output, Decimal('188.000'))

        # Yield variance = (188 - 200) / 200 = -6.00%
        self.assertEqual(run.yield_variance_percent, Decimal('-6.00'))
        self.assertTrue(run.yield_alert)

        # Check Oil Consumption Variance: Plan 10.0, Actual 10.5 -> +5.00% -> Alert True
        oil_c = run.consumptions.get(item_name='Cooking oil')
        self.assertEqual(oil_c.variance_percent, Decimal('5.00'))
        self.assertTrue(oil_c.variance_alert)

        # Check Pouches: Plan 200, Actual 194 (damaged 6) -> Var -3.00%
        pouch_c = run.consumptions.get(item_name='200 g pouch')
        self.assertEqual(pouch_c.actual_quantity, Decimal('194.000'))
        self.assertEqual(pouch_c.damaged_quantity, Decimal('6.000'))

        # Check Cartons: Plan 10, Actual 9 -> Var -10.00% -> Alert True
        carton_c = run.consumptions.get(item_name='Carton')
        self.assertEqual(carton_c.actual_quantity, Decimal('9.000'))
        self.assertEqual(carton_c.variance_percent, Decimal('-10.00'))
        self.assertTrue(carton_c.variance_alert)

        # Costing Verification:
        # RM Flour: 40 * 43.1250 = 1725.00
        # RM Oil: 10.5 * 140.00 = 1470.00
        # RM Spice: 1.2 * 200.00 = 240.00
        # PM Pouch: 194 * 2.50 = 485.00
        # PM Carton: 9 * 15.00 = 135.00
        # Total Direct Material = 1725 + 1470 + 240 + 485 + 135 = 4055.00
        # Overheads: 1200 + 600 = 1800.00
        # Total Cost = 4055 + 1800 = 5855.00
        # Cost per packet = 5855 / 188 = 31.1436 -> 31.14
        self.assertEqual(costing.raw_material_cost, Decimal('3435.00'))
        self.assertEqual(costing.packaging_material_cost, Decimal('620.00'))
        self.assertEqual(costing.raw_material_cost + costing.packaging_material_cost, Decimal('4055.00'))
        self.assertEqual(costing.labour_cost, Decimal('1200.00'))
        self.assertEqual(costing.power_and_gas_cost, Decimal('600.00'))
        self.assertEqual(costing.total_production_cost, Decimal('5855.00'))
        self.assertEqual(round(costing.cost_per_packet, 2), Decimal('31.14'))
        self.assertEqual(round(costing.gross_margin_per_packet, 2), Decimal('18.86'))
        self.assertEqual(round(costing.gross_margin_percent, 2), Decimal('37.71'))

        # Inventory Balances after Production:
        self.rm_flour.refresh_from_db()
        self.rm_oil.refresh_from_db()
        self.rm_spice.refresh_from_db()
        self.pm_pouch.refresh_from_db()
        self.pm_carton.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(self.rm_flour.current_stock, Decimal('120.000')) # 160 - 40
        self.assertEqual(self.rm_oil.current_stock, Decimal('19.500'))    # 30 - 10.5
        self.assertEqual(self.rm_spice.current_stock, Decimal('3.800'))   # 5 - 1.2
        self.assertEqual(self.pm_pouch.current_stock, Decimal('306.000')) # 500 - 194
        self.assertEqual(self.pm_carton.current_stock, Decimal('21.000')) # 30 - 9
        self.assertEqual(self.product.current_stock, Decimal('238.000'))   # 50 + 188

        # -------------------------------------------------------------
        # STEP 3: Sales Order 1 (Retailer A, Tamil Nadu) - 150 pkts
        # -------------------------------------------------------------
        order_1 = SalesOrderService.create_order(
            customer_id=self.customer_a.id,
            salesman=self.salesman_tn,
            items_data=[{'product_id': self.product.id, 'quantity': '150.000', 'unit_price': '50.00'}],
            notes='Benchmark Order: Retailer A'
        )
        # Verify stock sufficiency
        stock_check_1 = SalesOrderService.check_stock_availability(order_1)
        self.assertFalse(stock_check_1['has_shortage'])

        # Approve Order
        SalesOrderService.approve_order(order_1.id, admin_user=self.admin)
        order_1.refresh_from_db()
        self.assertEqual(order_1.status, SalesOrderStatus.APPROVED)

        # Generate Invoice
        invoice_1 = InvoiceService.generate_invoice_from_order(order_1.id, user=self.admin)
        self.assertIsNotNone(invoice_1)

        # Dispatch Order
        dispatch_1 = DispatchService.record_dispatch(
            sales_order_id=order_1.id,
            invoice_id=invoice_1.id,
            user=self.admin,
            transporter_name='TN Express Logistics',
            vehicle_number='TN-45-AZ-1234',
            notes='Benchmark Dispatch to Retailer A'
        )
        self.assertIsNotNone(dispatch_1)

        # Check Inventory of Finished Goods after dispatch: 238 - 150 = 88 pkts
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, Decimal('88.000'))

        # Check Tax Invoice 1:
        # Intra-state Tamil Nadu -> CGST 2.5% (187.50) + SGST 2.5% (187.50)
        self.assertEqual(invoice_1.taxable_amount, Decimal('7500.00'))
        self.assertEqual(invoice_1.cgst_amount, Decimal('187.50'))
        self.assertEqual(invoice_1.sgst_amount, Decimal('187.50'))
        self.assertEqual(invoice_1.igst_amount, Decimal('0.00'))
        self.assertEqual(invoice_1.grand_total, Decimal('7875.00'))
        self.assertEqual(invoice_1.outstanding_amount, Decimal('7875.00'))

        # Record Partial Payment of Rs. 4,000 against Invoice 1
        payment = PaymentService.record_payment(
            customer_id=self.customer_a.id,
            amount=Decimal('4000.00'),
            payment_date=timezone.now().date(),
            payment_method=PaymentMethod.BANK_TRANSFER,
            transaction_reference='NEFT-SBI-4910284',
            invoice_id=invoice_1.id,
            user=self.admin,
            notes='Part payment against Invoice ' + invoice_1.invoice_number
        )
        self.assertIsNotNone(payment)
        invoice_1.refresh_from_db()
        self.assertEqual(invoice_1.status, InvoiceStatus.POSTED)
        self.assertEqual(invoice_1.paid_amount, Decimal('4000.00'))
        self.assertEqual(invoice_1.outstanding_amount, Decimal('3875.00'))

        # -------------------------------------------------------------
        # STEP 4: Sales Order 2 (Distributor B, Karnataka) - 120 pkts
        # -------------------------------------------------------------
        order_2 = SalesOrderService.create_order(
            customer_id=self.customer_b.id,
            salesman=self.salesman_ka,
            items_data=[{'product_id': self.product.id, 'quantity': '120.000', 'unit_price': '50.00'}],
            notes='Benchmark Order: Distributor B (Shortage Scenario)'
        )
        self.assertEqual(order_2.subtotal_amount, Decimal('6000.00'))
        self.assertEqual(order_2.tax_amount, Decimal('300.00'))
        self.assertEqual(order_2.grand_total, Decimal('6300.00'))

        # Verify stock for Order 2: Available = 88 pkts, Ordered = 120 pkts -> Shortage of 32 pkts
        stock_check_2 = SalesOrderService.check_stock_availability(order_2)
        self.assertTrue(stock_check_2['has_shortage'])
        self.assertEqual(stock_check_2['total_shortage_quantity'], Decimal('32.000'))

        # Attempting dispatch MUST fail with ValidationError
        with self.assertRaises(ValidationError) as ctx:
            DispatchService.record_dispatch(
                sales_order_id=order_2.id,
                user=self.admin,
            )
        self.assertIn('shortage', str(ctx.exception).lower())

        # Stock must remain unchanged at 88 pkts
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, Decimal('88.000'))
