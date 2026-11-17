from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.accounts.models import User
from apps.masters.models import (
    UnitOfMeasurement, Category, Product, Customer, Supplier,
    RawMaterial, PackagingMaterial
)
from apps.bom.models import BOM, BOMItem
from apps.inventory.services import InventoryService
from apps.inventory.models import StockItemType, StockTransactionType, StockLedger, StockBalance
from apps.purchases.models import Purchase, PurchaseItem
from apps.purchases.services import PurchaseService
from apps.production.models import ProductionRun, ProductionConsumption, Overhead, CostingRecord
from apps.production.services import ProductionService
from apps.sales.models import SalesOrder, SalesOrderItem, Dispatch, DispatchItem
from apps.sales.services import SalesOrderService, DispatchService
from apps.billing.models import Invoice, InvoiceItem, CreditNote
from apps.billing.services import InvoiceService
from apps.payments.services import PaymentService
from apps.payments.models import Payment, PaymentAllocation, PaymentMethod

class Command(BaseCommand):
    help = 'Seeds all master data, opening stocks, and executes the mandatory benchmark scenario.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-transactions',
            action='store_true',
            help='Only seed master data and opening stock without executing benchmark transactions',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting FactoryFlow Benchmark Seeding..."))

        # Clean existing transaction data for idempotent execution
        from apps.billing.models import CreditNote
        from apps.sales.models import Dispatch, DispatchItem
        PaymentAllocation.objects.all().delete()
        Payment.objects.all().delete()
        DispatchItem.objects.all().delete()
        Dispatch.objects.all().delete()
        CreditNote.objects.all().delete()
        Invoice.objects.all().delete()
        SalesOrder.objects.all().delete()
        ProductionConsumption.objects.all().delete()
        Overhead.objects.all().delete()
        CostingRecord.objects.all().delete()
        ProductionRun.objects.all().delete()
        Purchase.objects.all().delete()
        StockLedger.objects.all().delete()
        StockBalance.objects.all().delete()

        # 1. Create Users
        admin_user, _ = User.objects.get_or_create(
            username='admin',
            defaults={
                'first_name': 'Factory',
                'last_name': 'Administrator',
                'email': 'admin@factoryflow.in',
                'role': User.Role.ADMIN,
                'is_staff': True,
                'is_superuser': True,
            }
        )
        admin_user.set_password('admin123')
        admin_user.save()

        salesman_a, _ = User.objects.get_or_create(
            username='salesman_a',
            defaults={
                'first_name': 'Murugan',
                'last_name': 'Salesman A',
                'email': 'salesman_a@factoryflow.in',
                'role': User.Role.SALESMAN,
            }
        )
        salesman_a.set_password('sales123')
        salesman_a.save()

        salesman_b, _ = User.objects.get_or_create(
            username='salesman_b',
            defaults={
                'first_name': 'Karthik',
                'last_name': 'Salesman B',
                'email': 'salesman_b@factoryflow.in',
                'role': User.Role.SALESMAN,
            }
        )
        salesman_b.set_password('sales123')
        salesman_b.save()

        supervisor, _ = User.objects.get_or_create(
            username='supervisor',
            defaults={
                'first_name': 'Sundaram',
                'last_name': 'Production Head',
                'email': 'supervisor@factoryflow.in',
                'role': User.Role.PRODUCTION_SUPERVISOR,
            }
        )
        supervisor.set_password('super123')
        supervisor.save()

        auditor, _ = User.objects.get_or_create(
            username='auditor',
            defaults={
                'first_name': 'Narayanan',
                'last_name': 'Financial Auditor',
                'email': 'auditor@factoryflow.in',
                'role': User.Role.OWNER_AUDITOR,
            }
        )
        auditor.set_password('audit123')
        auditor.save()

        self.stdout.write(self.style.SUCCESS("[OK] Demo users created (admin, salesman_a, salesman_b, supervisor, auditor)"))

        # 2. Units of Measurement
        uom_kg, _ = UnitOfMeasurement.objects.get_or_create(code='kg', defaults={'name': 'Kilogram', 'dimension': UnitOfMeasurement.Dimension.MASS})
        uom_litre, _ = UnitOfMeasurement.objects.get_or_create(code='litre', defaults={'name': 'Litre', 'dimension': UnitOfMeasurement.Dimension.VOLUME})
        uom_g, _ = UnitOfMeasurement.objects.get_or_create(code='g', defaults={'name': 'Gram', 'dimension': UnitOfMeasurement.Dimension.MASS})
        uom_ml, _ = UnitOfMeasurement.objects.get_or_create(code='ml', defaults={'name': 'Millilitre', 'dimension': UnitOfMeasurement.Dimension.VOLUME})
        uom_pcs, _ = UnitOfMeasurement.objects.get_or_create(code='pieces', defaults={'name': 'Pieces', 'dimension': UnitOfMeasurement.Dimension.DISCRETE})
        uom_pkts, _ = UnitOfMeasurement.objects.get_or_create(code='packets', defaults={'name': 'Packets', 'dimension': UnitOfMeasurement.Dimension.DISCRETE})
        uom_box, _ = UnitOfMeasurement.objects.get_or_create(code='cartons', defaults={'name': 'Cartons', 'dimension': UnitOfMeasurement.Dimension.DISCRETE})

        # 3. Product Category & Product
        cat_snacks, _ = Category.objects.get_or_create(name='Traditional Snacks', defaults={'description': 'Authentic South Indian packaged snacks'})

        product, _ = Product.objects.get_or_create(
            product_code='PRD-MRK-200G',
            defaults={
                'name': 'Murukku 200 g',
                'category': cat_snacks,
                'pack_size': '200 g',
                'uom': uom_pkts,
                'selling_price': Decimal('50.00'),
                'opening_stock': Decimal('50.000'),
                'current_stock': Decimal('50.000'),
                'hsn_code': '1905',
                'gst_rate': Decimal('5.00'),
                'packets_per_carton': 20,
            }
        )

        # 4. Raw Materials
        rm_flour, _ = RawMaterial.objects.get_or_create(
            material_code='RM-FLOUR',
            defaults={
                'name': 'Flour',
                'uom': uom_kg,
                'opening_stock': Decimal('100.000'),
                'current_stock': Decimal('100.000'),
                'weighted_average_cost': Decimal('42.0000'),
                'purchase_rate': Decimal('42.00'),
                'reorder_level': Decimal('20.000'),
            }
        )

        rm_oil, _ = RawMaterial.objects.get_or_create(
            material_code='RM-OIL',
            defaults={
                'name': 'Cooking oil',
                'uom': uom_litre,
                'opening_stock': Decimal('30.000'),
                'current_stock': Decimal('30.000'),
                'weighted_average_cost': Decimal('140.0000'),
                'purchase_rate': Decimal('140.00'),
                'reorder_level': Decimal('10.000'),
            }
        )

        rm_spice, _ = RawMaterial.objects.get_or_create(
            material_code='RM-SPICE',
            defaults={
                'name': 'Salt and spice mix',
                'uom': uom_kg,
                'opening_stock': Decimal('5.000'),
                'current_stock': Decimal('5.000'),
                'weighted_average_cost': Decimal('200.0000'),
                'purchase_rate': Decimal('200.00'),
                'reorder_level': Decimal('2.000'),
            }
        )

        # 5. Packaging Materials
        pm_pouch, _ = PackagingMaterial.objects.get_or_create(
            material_code='PM-POUCH-200G',
            defaults={
                'name': '200 g pouch',
                'packaging_type': PackagingMaterial.PackagingType.POUCH,
                'uom': uom_pcs,
                'opening_stock': Decimal('500.000'),
                'current_stock': Decimal('500.000'),
                'purchase_rate': Decimal('2.50'),
                'reorder_level': Decimal('100.000'),
            }
        )

        pm_carton, _ = PackagingMaterial.objects.get_or_create(
            material_code='PM-CARTON-200G',
            defaults={
                'name': 'Carton',
                'packaging_type': PackagingMaterial.PackagingType.CARTON,
                'uom': uom_pcs,
                'opening_stock': Decimal('30.000'),
                'current_stock': Decimal('30.000'),
                'purchase_rate': Decimal('15.00'),
                'reorder_level': Decimal('10.000'),
            }
        )

        # Reset item stock states to exact benchmark opening values
        product.current_stock = Decimal('50.000')
        product.save(update_fields=['current_stock'])

        rm_flour.current_stock = Decimal('100.000')
        rm_flour.weighted_average_cost = Decimal('42.0000')
        rm_flour.save(update_fields=['current_stock', 'weighted_average_cost'])

        rm_oil.current_stock = Decimal('30.000')
        rm_oil.weighted_average_cost = Decimal('140.0000')
        rm_oil.save(update_fields=['current_stock', 'weighted_average_cost'])

        rm_spice.current_stock = Decimal('5.000')
        rm_spice.weighted_average_cost = Decimal('200.0000')
        rm_spice.save(update_fields=['current_stock', 'weighted_average_cost'])

        pm_pouch.current_stock = Decimal('500.000')
        pm_pouch.purchase_rate = Decimal('2.50')
        pm_pouch.save(update_fields=['current_stock', 'purchase_rate'])

        pm_carton.current_stock = Decimal('30.000')
        pm_carton.purchase_rate = Decimal('15.00')
        pm_carton.save(update_fields=['current_stock', 'purchase_rate'])

        # 6. Customers & Suppliers
        cust_a, _ = Customer.objects.get_or_create(
            customer_code='CUST-RET-A',
            defaults={
                'name': 'Retailer A',
                'customer_type': Customer.CustomerType.RETAILER,
                'gstin': '33AAAAA1111A1Z1',
                'billing_address': 'Shop 14, Main Bazaar, Thuvakudi, Tiruchirappalli',
                'state': 'Tamil Nadu',
                'state_code': '33',
                'phone': '+91 94431 11111',
                'email': 'retailer_a@example.com',
            }
        )

        cust_b, _ = Customer.objects.get_or_create(
            customer_code='CUST-DIST-B',
            defaults={
                'name': 'Distributor B',
                'customer_type': Customer.CustomerType.DISTRIBUTOR,
                'gstin': '29BBBBB2222B1Z2',
                'billing_address': 'Godown 8, Peenya Industrial Area, Bengaluru',
                'state': 'Karnataka',
                'state_code': '29',
                'phone': '+91 98450 22222',
                'email': 'distributor_b@example.com',
            }
        )

        supplier, _ = Supplier.objects.get_or_create(
            supplier_code='SUP-AGRO-01',
            defaults={
                'name': 'Annapoorna Agro Mills',
                'gstin': '33SUPPL1234S1Z9',
                'address': 'Dindigul Highway, Trichy, Tamil Nadu',
                'state': 'Tamil Nadu',
                'state_code': '33',
                'phone': '+91 431 2400000',
                'email': 'sales@annapoornaagro.com',
            }
        )

        # 7. Bill of Materials (BOM)
        bom, _ = BOM.objects.get_or_create(
            bom_code='BOM-MRK-200G',
            defaults={
                'product': product,
                'batch_size': Decimal('200.000'),
                'expected_output': Decimal('200.000'),
                'standard_yield_percent': Decimal('100.00'),
                'notes': 'Standard Murukku 200g production recipe batch'
            }
        )

        BOMItem.objects.get_or_create(
            bom=bom, item_type=BOMItem.ItemType.RAW_MATERIAL, raw_material=rm_flour,
            defaults={'standard_quantity': Decimal('40.000'), 'uom': uom_kg}
        )
        BOMItem.objects.get_or_create(
            bom=bom, item_type=BOMItem.ItemType.RAW_MATERIAL, raw_material=rm_oil,
            defaults={'standard_quantity': Decimal('10.000'), 'uom': uom_litre}
        )
        BOMItem.objects.get_or_create(
            bom=bom, item_type=BOMItem.ItemType.RAW_MATERIAL, raw_material=rm_spice,
            defaults={'standard_quantity': Decimal('1.200'), 'uom': uom_kg}
        )
        BOMItem.objects.get_or_create(
            bom=bom, item_type=BOMItem.ItemType.PACKAGING_MATERIAL, packaging_material=pm_pouch,
            defaults={'standard_quantity': Decimal('200.000'), 'uom': uom_pcs}
        )
        BOMItem.objects.get_or_create(
            bom=bom, item_type=BOMItem.ItemType.PACKAGING_MATERIAL, packaging_material=pm_carton,
            defaults={'standard_quantity': Decimal('10.000'), 'uom': uom_pcs}
        )

        self.stdout.write(self.style.SUCCESS("[OK] Master data, Customers, Suppliers, and BOM configured"))

        # 8. Record Opening Stock Ledgers (if not already logged)
        if not StockLedger.objects.filter(transaction_type=StockTransactionType.OPENING_STOCK).exists():
            today = timezone.now().date()
            # RM Flour
            StockLedger.objects.create(
                item_type=StockItemType.RAW_MATERIAL, item_id=rm_flour.id, item_name=rm_flour.name,
                transaction_type=StockTransactionType.OPENING_STOCK, quantity_change=Decimal('100.000'),
                balance_after=Decimal('100.000'), uom_code=rm_flour.uom.code, unit_rate=Decimal('42.0000'),
                total_value=Decimal('4200.00'), reference_doc='BENCHMARK-OPENING', source_module='MASTERS', user_responsible=admin_user
            )
            StockBalance.objects.update_or_create(
                item_type=StockItemType.RAW_MATERIAL, item_id=rm_flour.id,
                defaults={'item_name': rm_flour.name, 'current_quantity': Decimal('100.000'), 'valuation_rate': Decimal('42.0000'), 'uom_code': rm_flour.uom.code}
            )

            # RM Oil
            StockLedger.objects.create(
                item_type=StockItemType.RAW_MATERIAL, item_id=rm_oil.id, item_name=rm_oil.name,
                transaction_type=StockTransactionType.OPENING_STOCK, quantity_change=Decimal('30.000'),
                balance_after=Decimal('30.000'), uom_code=rm_oil.uom.code, unit_rate=Decimal('140.0000'),
                total_value=Decimal('4200.00'), reference_doc='BENCHMARK-OPENING', source_module='MASTERS', user_responsible=admin_user
            )
            StockBalance.objects.update_or_create(
                item_type=StockItemType.RAW_MATERIAL, item_id=rm_oil.id,
                defaults={'item_name': rm_oil.name, 'current_quantity': Decimal('30.000'), 'valuation_rate': Decimal('140.0000'), 'uom_code': rm_oil.uom.code}
            )

            # RM Spice
            StockLedger.objects.create(
                item_type=StockItemType.RAW_MATERIAL, item_id=rm_spice.id, item_name=rm_spice.name,
                transaction_type=StockTransactionType.OPENING_STOCK, quantity_change=Decimal('5.000'),
                balance_after=Decimal('5.000'), uom_code=rm_spice.uom.code, unit_rate=Decimal('200.0000'),
                total_value=Decimal('1000.00'), reference_doc='BENCHMARK-OPENING', source_module='MASTERS', user_responsible=admin_user
            )
            StockBalance.objects.update_or_create(
                item_type=StockItemType.RAW_MATERIAL, item_id=rm_spice.id,
                defaults={'item_name': rm_spice.name, 'current_quantity': Decimal('5.000'), 'valuation_rate': Decimal('200.0000'), 'uom_code': rm_spice.uom.code}
            )

            # PM Pouch
            StockLedger.objects.create(
                item_type=StockItemType.PACKAGING_MATERIAL, item_id=pm_pouch.id, item_name=pm_pouch.name,
                transaction_type=StockTransactionType.OPENING_STOCK, quantity_change=Decimal('500.000'),
                balance_after=Decimal('500.000'), uom_code=pm_pouch.uom.code, unit_rate=Decimal('2.5000'),
                total_value=Decimal('1250.00'), reference_doc='BENCHMARK-OPENING', source_module='MASTERS', user_responsible=admin_user
            )
            StockBalance.objects.update_or_create(
                item_type=StockItemType.PACKAGING_MATERIAL, item_id=pm_pouch.id,
                defaults={'item_name': pm_pouch.name, 'current_quantity': Decimal('500.000'), 'valuation_rate': Decimal('2.5000'), 'uom_code': pm_pouch.uom.code}
            )

            # PM Carton
            StockLedger.objects.create(
                item_type=StockItemType.PACKAGING_MATERIAL, item_id=pm_carton.id, item_name=pm_carton.name,
                transaction_type=StockTransactionType.OPENING_STOCK, quantity_change=Decimal('30.000'),
                balance_after=Decimal('30.000'), uom_code=pm_carton.uom.code, unit_rate=Decimal('15.0000'),
                total_value=Decimal('450.00'), reference_doc='BENCHMARK-OPENING', source_module='MASTERS', user_responsible=admin_user
            )
            StockBalance.objects.update_or_create(
                item_type=StockItemType.PACKAGING_MATERIAL, item_id=pm_carton.id,
                defaults={'item_name': pm_carton.name, 'current_quantity': Decimal('30.000'), 'valuation_rate': Decimal('15.0000'), 'uom_code': pm_carton.uom.code}
            )

            # FG Product
            StockLedger.objects.create(
                item_type=StockItemType.FINISHED_GOODS, item_id=product.id, item_name=product.name,
                transaction_type=StockTransactionType.OPENING_STOCK, quantity_change=Decimal('50.000'),
                balance_after=Decimal('50.000'), uom_code=product.uom.code, unit_rate=Decimal('50.0000'),
                total_value=Decimal('2500.00'), reference_doc='BENCHMARK-OPENING', source_module='MASTERS', user_responsible=admin_user
            )
            StockBalance.objects.update_or_create(
                item_type=StockItemType.FINISHED_GOODS, item_id=product.id,
                defaults={'item_name': product.name, 'current_quantity': Decimal('50.000'), 'valuation_rate': Decimal('50.0000'), 'uom_code': product.uom.code}
            )
            self.stdout.write(self.style.SUCCESS("[OK] Opening stock ledgers initialized"))

        if options['no_transactions']:
            self.stdout.write(self.style.SUCCESS("Skipping transactions as requested."))
            return

        # 9. BENCHMARK TRANSACTION SEQUENCE
        self.stdout.write(self.style.NOTICE("\nExecuting Benchmark Transactions..."))

        # B. Purchase Transaction: 60 kg Flour @ Rs. 45/kg
        if not Purchase.objects.filter(purchase_number='PUR-BM-0001').exists():
            purchase = Purchase.objects.create(
                purchase_number='PUR-BM-0001',
                supplier=supplier,
                supplier_invoice_ref='SUP-INV-9821',
                purchase_date=timezone.now().date(),
                taxable_amount=Decimal('2700.00'),
                gst_amount=Decimal('135.00'),
                total_amount=Decimal('2835.00'),
                notes='Benchmark Purchase: 60 kg Flour @ Rs. 45/kg',
                created_by=supervisor
            )
            PurchaseItem.objects.create(
                purchase=purchase,
                item_type=PurchaseItem.ItemType.RAW_MATERIAL,
                raw_material=rm_flour,
                quantity=Decimal('60.000'),
                uom=uom_kg,
                purchase_rate=Decimal('45.0000'),
                gst_rate=Decimal('5.00'),
                taxable_amount=Decimal('2700.00'),
                gst_amount=Decimal('135.00'),
                total_amount=Decimal('2835.00')
            )
            PurchaseService.confirm_purchase(purchase.id, user=supervisor)
            rm_flour.refresh_from_db()
            self.stdout.write(f"  -> Flour Purchase Confirmed: Stock = {rm_flour.current_stock} kg (Expected: 160 kg)")
            self.stdout.write(f"  -> Flour Weighted Average Cost = Rs. {rm_flour.weighted_average_cost}/kg (Expected: Rs. 43.125/kg)")

        # C. Production Run: Murukku 200 g
        consumptions_data = [
            {'item_type': 'RAW_MATERIAL', 'raw_material_id': rm_flour.id, 'planned_quantity': '40.000', 'actual_quantity': '40.000'},
            {'item_type': 'RAW_MATERIAL', 'raw_material_id': rm_oil.id, 'planned_quantity': '10.000', 'actual_quantity': '10.500'},
            {'item_type': 'RAW_MATERIAL', 'raw_material_id': rm_spice.id, 'planned_quantity': '1.200', 'actual_quantity': '1.200'},
            {'item_type': 'PACKAGING_MATERIAL', 'packaging_material_id': pm_pouch.id, 'planned_quantity': '200.000', 'actual_quantity': '194.000', 'damaged_quantity': '6.000'},
            {'item_type': 'PACKAGING_MATERIAL', 'packaging_material_id': pm_carton.id, 'planned_quantity': '10.000', 'actual_quantity': '9.000'},
        ]
        overheads_data = [
            {'overhead_type': Overhead.OverheadType.LABOUR, 'description': 'Batch Direct Labour', 'amount': '1200.00'},
            {'overhead_type': Overhead.OverheadType.POWER_GAS, 'description': 'LPG and Electricity Power', 'amount': '600.00'},
        ]

        run, costing = ProductionService.execute_production_run(
            product_id=product.id,
            batch_quantity=Decimal('200.000'),
            actual_good_output=Decimal('188.000'),
            consumptions_data=consumptions_data,
            overheads_data=overheads_data,
            wastage_quantity=Decimal('12.000'),
            production_date=timezone.now().date(),
            supervisor=supervisor,
            notes='Benchmark Production Run'
        )
        self.stdout.write(f"  -> Production Run Executed: {run.run_number}")
        self.stdout.write(f"  -> Yield Variance: {run.yield_variance_percent}% (Alert: {run.yield_alert})")
        self.stdout.write(f"  -> Total Production Cost: Rs. {costing.total_production_cost} (Expected: Rs. 5,855.00)")
        self.stdout.write(f"  -> Cost Per Packet: Rs. {costing.cost_per_packet:.2f} (Expected: ~Rs. 31.14)")
        self.stdout.write(f"  -> Gross Margin Per Packet: Rs. {costing.gross_margin_per_packet:.2f} (Expected: ~Rs. 18.86)")

        # D. Sales Order 1: Retailer A (150 packets)
        order_a = SalesOrderService.create_order(
            customer_id=cust_a.id,
            salesman=salesman_a,
            items_data=[{'product_id': product.id, 'quantity': '150.000', 'unit_price': '50.00'}],
            notes='Benchmark Order: Retailer A'
        )
        SalesOrderService.approve_order(order_a.id, admin_user=admin_user)
        inv_a = InvoiceService.generate_invoice_from_order(order_a.id, user=admin_user)
        self.stdout.write(f"  -> Invoice A Generated: {inv_a.invoice_number}")
        self.stdout.write(f"  -> Taxable: Rs. {inv_a.taxable_amount}, CGST: Rs. {inv_a.cgst_amount}, SGST: Rs. {inv_a.sgst_amount}, Total: Rs. {inv_a.grand_total}")

        # Dispatch 150 packets
        dsp_a = DispatchService.record_dispatch(
            sales_order_id=order_a.id,
            invoice_id=inv_a.id,
            user=admin_user,
            transporter_name='TN Express Logistics',
            vehicle_number='TN-45-AZ-1234',
            notes='Benchmark Dispatch to Retailer A'
        )
        product.refresh_from_db()
        self.stdout.write(f"  -> Dispatch A Completed: {dsp_a.dispatch_number}, FG Stock = {product.current_stock} pkts (Expected: 88 pkts)")

        # E. Sales Order 2: Distributor B (120 packets) -> Shortage Check
        order_b = SalesOrderService.create_order(
            customer_id=cust_b.id,
            salesman=salesman_b,
            items_data=[{'product_id': product.id, 'quantity': '120.000', 'unit_price': '50.00'}],
            notes='Benchmark Order: Distributor B (Shortage Scenario)'
        )
        stock_check = SalesOrderService.check_stock_availability(order_b)
        self.stdout.write(f"  -> Order B Created: {order_b.order_number}")
        self.stdout.write(f"  -> Shortage Detected: {stock_check['has_shortage']}, Shortage Qty = {stock_check['total_shortage_quantity']} pkts (Expected: 32 pkts)")

        # F. Payment: Rs. 4,000 against Retailer A Invoice
        pmt = PaymentService.record_payment(
            customer_id=cust_a.id,
            amount=Decimal('4000.00'),
            payment_date=timezone.now().date(),
            payment_method=PaymentMethod.BANK_TRANSFER,
            transaction_reference='NEFT-SBI-4910284',
            invoice_id=inv_a.id,
            user=admin_user,
            notes='Part payment against Invoice ' + inv_a.invoice_number
        )
        inv_a.refresh_from_db()
        self.stdout.write(f"  -> Payment Recorded: {pmt.payment_reference} (Rs. {pmt.amount})")
        self.stdout.write(f"  -> Invoice A Outstanding Balance = Rs. {inv_a.outstanding_amount} (Expected: Rs. 3,875.00)")

        # 10. Summary Verification
        rm_flour.refresh_from_db()
        rm_oil.refresh_from_db()
        rm_spice.refresh_from_db()
        pm_pouch.refresh_from_db()
        pm_carton.refresh_from_db()
        product.refresh_from_db()

        self.stdout.write(self.style.SUCCESS("\n========================================================"))
        self.stdout.write(self.style.SUCCESS("    FACTORYFLOW BENCHMARK VERIFICATION SUMMARY"))
        self.stdout.write(self.style.SUCCESS("========================================================"))
        self.stdout.write(f"Flour Closing Stock:       {rm_flour.current_stock} kg (Expected: 120.000 kg)")
        self.stdout.write(f"Cooking Oil Closing Stock: {rm_oil.current_stock} L (Expected: 19.500 L)")
        self.stdout.write(f"Spice Mix Closing Stock:   {rm_spice.current_stock} kg (Expected: 3.800 kg)")
        self.stdout.write(f"Pouches Closing Stock:     {pm_pouch.current_stock} pcs (Expected: 306.000 pcs)")
        self.stdout.write(f"Cartons Closing Stock:     {pm_carton.current_stock} pcs (Expected: 21.000 pcs)")
        self.stdout.write(f"Finished Goods Closing:    {product.current_stock} pkts (Expected: 88.000 pkts)")
        self.stdout.write(f"Yield Variance:            {run.yield_variance_percent}% (Expected: -6.00%)")
        self.stdout.write(f"Production Cost:           Rs. {costing.total_production_cost} (Expected: Rs. 5,855.00)")
        self.stdout.write(f"Cost Per Packet:           Rs. {costing.cost_per_packet:.2f} (Expected: ~Rs. 31.14)")
        self.stdout.write(f"Invoice Grand Total:       Rs. {inv_a.grand_total} (Expected: Rs. 7,875.00)")
        self.stdout.write(f"Invoice Outstanding:       Rs. {inv_a.outstanding_amount} (Expected: Rs. 3,875.00)")
        self.stdout.write(self.style.SUCCESS("========================================================\n"))
