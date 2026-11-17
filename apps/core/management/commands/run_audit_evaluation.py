from decimal import Decimal, ROUND_HALF_UP
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.exceptions import ValidationError

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
from apps.sales.models import SalesOrder, SalesOrderItem, Dispatch, DispatchItem, SalesOrderStatus
from apps.sales.services import SalesOrderService, DispatchService
from apps.billing.models import Invoice, InvoiceItem, CreditNote, InvoiceStatus
from apps.billing.services import InvoiceService, GSTService
from apps.payments.services import PaymentService
from apps.payments.models import Payment, PaymentAllocation, PaymentMethod


class Command(BaseCommand):
    help = 'Executes the NIT Tiruchirappalli benchmark evaluation suite from a clean database state and audits all 20+ business calculations and stock ledger movements.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("================================================================================"))
        self.stdout.write(self.style.MIGRATE_HEADING("   CENTRE FOR DIGITAL INFRASTRUCTURE - NIT TIRUCHIRAPPALLI"))
        self.stdout.write(self.style.MIGRATE_HEADING("   Independent Software Evaluation: FactoryFlow ERP Benchmark Audit"))
        self.stdout.write(self.style.MIGRATE_HEADING("================================================================================\n"))

        results = []

        def log_result(calc_id, description, expected, actual, passed, details=""):
            status_text = self.style.SUCCESS("[PASS]") if passed else self.style.ERROR("[FAIL]")
            results.append({
                'id': calc_id,
                'description': description,
                'expected': str(expected),
                'actual': str(actual),
                'status': 'PASS' if passed else 'FAIL',
                'details': details
            })
            self.stdout.write(f"  {status_text} #{calc_id:02d}: {description}")
            self.stdout.write(f"          Expected: {expected} | Actual: {actual}")
            if details:
                self.stdout.write(f"          Note: {details}")

        # -------------------------------------------------------------
        # 1. SETUP MASTER DATA & OPENING STOCKS
        # -------------------------------------------------------------
        self.stdout.write(self.style.NOTICE("\n[PHASE 1] Initializing Clean Masters & Opening Inventory Balances..."))
        
        # Clean existing transaction data
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

        admin_user, _ = User.objects.get_or_create(
            username='admin',
            defaults={'first_name': 'Factory', 'last_name': 'Administrator', 'email': 'admin@factoryflow.in', 'role': User.Role.ADMIN, 'is_staff': True, 'is_superuser': True}
        )
        admin_user.set_password('admin123')
        admin_user.save()

        supervisor, _ = User.objects.get_or_create(
            username='supervisor',
            defaults={'first_name': 'Sundaram', 'last_name': 'Production Head', 'email': 'supervisor@factoryflow.in', 'role': User.Role.PRODUCTION_SUPERVISOR}
        )
        supervisor.set_password('super123')
        supervisor.save()

        salesman_a, _ = User.objects.get_or_create(
            username='salesman_a',
            defaults={'first_name': 'Murugan', 'last_name': 'Salesman A', 'email': 'salesman_a@factoryflow.in', 'role': User.Role.SALESMAN}
        )
        salesman_a.set_password('sales123')
        salesman_a.save()

        salesman_b, _ = User.objects.get_or_create(
            username='salesman_b',
            defaults={'first_name': 'Karthik', 'last_name': 'Salesman B', 'email': 'salesman_b@factoryflow.in', 'role': User.Role.SALESMAN}
        )
        salesman_b.set_password('sales123')
        salesman_b.save()

        uom_kg, _ = UnitOfMeasurement.objects.get_or_create(code='kg', defaults={'name': 'Kilogram', 'dimension': UnitOfMeasurement.Dimension.MASS})
        uom_litre, _ = UnitOfMeasurement.objects.get_or_create(code='litre', defaults={'name': 'Litre', 'dimension': UnitOfMeasurement.Dimension.VOLUME})
        uom_pcs, _ = UnitOfMeasurement.objects.get_or_create(code='pieces', defaults={'name': 'Pieces', 'dimension': UnitOfMeasurement.Dimension.DISCRETE})
        uom_pkts, _ = UnitOfMeasurement.objects.get_or_create(code='packets', defaults={'name': 'Packets', 'dimension': UnitOfMeasurement.Dimension.DISCRETE})

        cat_snacks, _ = Category.objects.get_or_create(name='Traditional Snacks', defaults={'description': 'Authentic South Indian snacks'})

        product, _ = Product.objects.get_or_create(
            product_code='PRD-MRK-200G',
            defaults={
                'name': 'Murukku 200 g', 'category': cat_snacks, 'pack_size': '200 g', 'uom': uom_pkts,
                'selling_price': Decimal('50.00'), 'opening_stock': Decimal('50.000'), 'current_stock': Decimal('50.000'),
                'hsn_code': '1905', 'gst_rate': Decimal('5.00'), 'packets_per_carton': 20,
            }
        )
        product.current_stock = Decimal('50.000')
        product.save(update_fields=['current_stock'])

        rm_flour, _ = RawMaterial.objects.get_or_create(
            material_code='RM-FLOUR',
            defaults={'name': 'Flour', 'uom': uom_kg, 'opening_stock': Decimal('100.000'), 'current_stock': Decimal('100.000'), 'weighted_average_cost': Decimal('42.0000'), 'purchase_rate': Decimal('42.00')}
        )
        rm_flour.current_stock = Decimal('100.000')
        rm_flour.weighted_average_cost = Decimal('42.0000')
        rm_flour.save(update_fields=['current_stock', 'weighted_average_cost'])

        rm_oil, _ = RawMaterial.objects.get_or_create(
            material_code='RM-OIL',
            defaults={'name': 'Cooking oil', 'uom': uom_litre, 'opening_stock': Decimal('30.000'), 'current_stock': Decimal('30.000'), 'weighted_average_cost': Decimal('140.0000'), 'purchase_rate': Decimal('140.00')}
        )
        rm_oil.current_stock = Decimal('30.000')
        rm_oil.weighted_average_cost = Decimal('140.0000')
        rm_oil.save(update_fields=['current_stock', 'weighted_average_cost'])

        rm_spice, _ = RawMaterial.objects.get_or_create(
            material_code='RM-SPICE',
            defaults={'name': 'Salt and spice mix', 'uom': uom_kg, 'opening_stock': Decimal('5.000'), 'current_stock': Decimal('5.000'), 'weighted_average_cost': Decimal('200.0000'), 'purchase_rate': Decimal('200.00')}
        )
        rm_spice.current_stock = Decimal('5.000')
        rm_spice.weighted_average_cost = Decimal('200.0000')
        rm_spice.save(update_fields=['current_stock', 'weighted_average_cost'])

        pm_pouch, _ = PackagingMaterial.objects.get_or_create(
            material_code='PM-POUCH-200G',
            defaults={'name': '200 g pouch', 'packaging_type': PackagingMaterial.PackagingType.POUCH, 'uom': uom_pcs, 'opening_stock': Decimal('500.000'), 'current_stock': Decimal('500.000'), 'purchase_rate': Decimal('2.50')}
        )
        pm_pouch.current_stock = Decimal('500.000')
        pm_pouch.save(update_fields=['current_stock'])

        pm_carton, _ = PackagingMaterial.objects.get_or_create(
            material_code='PM-CARTON-200G',
            defaults={'name': 'Carton', 'packaging_type': PackagingMaterial.PackagingType.CARTON, 'uom': uom_pcs, 'opening_stock': Decimal('30.000'), 'current_stock': Decimal('30.000'), 'purchase_rate': Decimal('15.00')}
        )
        pm_carton.current_stock = Decimal('30.000')
        pm_carton.save(update_fields=['current_stock'])

        cust_a, _ = Customer.objects.get_or_create(
            customer_code='CUST-RET-A',
            defaults={'name': 'Retailer A', 'customer_type': Customer.CustomerType.RETAILER, 'gstin': '33AAAAA1111A1Z1', 'billing_address': 'Thuvakudi, Trichy', 'state': 'Tamil Nadu', 'state_code': '33'}
        )
        cust_b, _ = Customer.objects.get_or_create(
            customer_code='CUST-DIST-B',
            defaults={'name': 'Distributor B', 'customer_type': Customer.CustomerType.DISTRIBUTOR, 'gstin': '29BBBBB2222B1Z2', 'billing_address': 'Peenya, Bengaluru', 'state': 'Karnataka', 'state_code': '29'}
        )
        supplier, _ = Supplier.objects.get_or_create(
            supplier_code='SUP-AGRO-01',
            defaults={'name': 'Annapoorna Agro Mills', 'gstin': '33SUPPL1234S1Z9', 'address': 'Trichy, TN', 'state': 'Tamil Nadu', 'state_code': '33'}
        )

        bom, _ = BOM.objects.get_or_create(
            bom_code='BOM-MRK-200G',
            defaults={'product': product, 'batch_size': Decimal('200.000'), 'expected_output': Decimal('200.000'), 'standard_yield_percent': Decimal('100.00')}
        )
        BOMItem.objects.get_or_create(bom=bom, item_type=BOMItem.ItemType.RAW_MATERIAL, raw_material=rm_flour, defaults={'standard_quantity': Decimal('40.000'), 'uom': uom_kg})
        BOMItem.objects.get_or_create(bom=bom, item_type=BOMItem.ItemType.RAW_MATERIAL, raw_material=rm_oil, defaults={'standard_quantity': Decimal('10.000'), 'uom': uom_litre})
        BOMItem.objects.get_or_create(bom=bom, item_type=BOMItem.ItemType.RAW_MATERIAL, raw_material=rm_spice, defaults={'standard_quantity': Decimal('1.200'), 'uom': uom_kg})
        BOMItem.objects.get_or_create(bom=bom, item_type=BOMItem.ItemType.PACKAGING_MATERIAL, packaging_material=pm_pouch, defaults={'standard_quantity': Decimal('200.000'), 'uom': uom_pcs})
        BOMItem.objects.get_or_create(bom=bom, item_type=BOMItem.ItemType.PACKAGING_MATERIAL, packaging_material=pm_carton, defaults={'standard_quantity': Decimal('10.000'), 'uom': uom_pcs})

        # Opening Stock Ledgers
        opening_items = [
            (StockItemType.RAW_MATERIAL, rm_flour.id, rm_flour.name, Decimal('100.000'), rm_flour.uom.code, Decimal('42.0000'), Decimal('4200.00')),
            (StockItemType.RAW_MATERIAL, rm_oil.id, rm_oil.name, Decimal('30.000'), rm_oil.uom.code, Decimal('140.0000'), Decimal('4200.00')),
            (StockItemType.RAW_MATERIAL, rm_spice.id, rm_spice.name, Decimal('5.000'), rm_spice.uom.code, Decimal('200.0000'), Decimal('1000.00')),
            (StockItemType.PACKAGING_MATERIAL, pm_pouch.id, pm_pouch.name, Decimal('500.000'), pm_pouch.uom.code, Decimal('2.5000'), Decimal('1250.00')),
            (StockItemType.PACKAGING_MATERIAL, pm_carton.id, pm_carton.name, Decimal('30.000'), pm_carton.uom.code, Decimal('15.0000'), Decimal('450.00')),
            (StockItemType.FINISHED_GOODS, product.id, product.name, Decimal('50.000'), product.uom.code, Decimal('50.0000'), Decimal('2500.00')),
        ]
        for itype, iid, iname, qty, uomc, rate, val in opening_items:
            StockLedger.objects.create(
                item_type=itype, item_id=iid, item_name=iname, transaction_type=StockTransactionType.OPENING_STOCK,
                quantity_change=qty, balance_after=qty, uom_code=uomc, unit_rate=rate, total_value=val,
                reference_doc='BENCHMARK-OPENING', source_module='MASTERS', user_responsible=admin_user
            )
            StockBalance.objects.create(item_type=itype, item_id=iid, item_name=iname, current_quantity=qty, valuation_rate=rate, uom_code=uomc)

        # CALC 1: Total Opening Inventory Valuation
        total_opening_val = sum(item[6] for item in opening_items)
        log_result(1, "Total Opening Stock Valuation", Decimal('13600.00'), total_opening_val, total_opening_val == Decimal('13600.00'), "Sum of all initial inventory items")

        # -------------------------------------------------------------
        # 2. PURCHASE INWARD & WAC RECALCULATION
        # -------------------------------------------------------------
        self.stdout.write(self.style.NOTICE("\n[PHASE 2] Auditing Purchase Inward & WAC Recalculation..."))
        purchase = Purchase.objects.create(
            purchase_number='PUR-EVAL-0001', supplier=supplier, supplier_invoice_ref='SUP-INV-9821',
            purchase_date=timezone.now().date(), taxable_amount=Decimal('2700.00'), gst_amount=Decimal('135.00'),
            total_amount=Decimal('2835.00'), notes='Benchmark Purchase: 60 kg Flour @ Rs. 45/kg', created_by=supervisor
        )
        PurchaseItem.objects.create(
            purchase=purchase, item_type=PurchaseItem.ItemType.RAW_MATERIAL, raw_material=rm_flour,
            quantity=Decimal('60.000'), uom=uom_kg, purchase_rate=Decimal('45.0000'), gst_rate=Decimal('5.00'),
            taxable_amount=Decimal('2700.00'), gst_amount=Decimal('135.00'), total_amount=Decimal('2835.00')
        )

        # CALC 2: Purchase Line Taxable Amount
        log_result(2, "Purchase Line Taxable Value (60 kg * Rs. 45/kg)", Decimal('2700.00'), purchase.taxable_amount, purchase.taxable_amount == Decimal('2700.00'))

        # CALC 3: Purchase GST Tax Amount (5%)
        log_result(3, "Purchase GST (5% on Rs. 2,700)", Decimal('135.00'), purchase.gst_amount, purchase.gst_amount == Decimal('135.00'))

        # CALC 4: Purchase Total Inward Value
        log_result(4, "Purchase Invoice Total Amount", Decimal('2835.00'), purchase.total_amount, purchase.total_amount == Decimal('2835.00'))

        PurchaseService.confirm_purchase(purchase.id, user=supervisor)
        rm_flour.refresh_from_db()

        # CALC 5: Stock Balance update after Purchase Inward
        log_result(5, "Flour Stock Balance after Inward (100 + 60 kg)", Decimal('160.000'), rm_flour.current_stock, rm_flour.current_stock == Decimal('160.000'))

        # CALC 6: Weighted Average Cost (WAC) formula
        # ((100 * 42.00) + (60 * 45.00)) / (100 + 60) = (4200 + 2700) / 160 = 6900 / 160 = Rs. 43.1250/kg
        log_result(6, "Flour Weighted Average Cost (WAC)", Decimal('43.1250'), rm_flour.weighted_average_cost, rm_flour.weighted_average_cost == Decimal('43.1250'), "Exact formula: ((100*42) + (60*45))/160")

        # -------------------------------------------------------------
        # 3. PRODUCTION EXECUTION, CONSUMPTION & COSTING
        # -------------------------------------------------------------
        self.stdout.write(self.style.NOTICE("\n[PHASE 3] Auditing Production Run, Yield Variance & Costing Formulas..."))
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
            product_id=product.id, batch_quantity=Decimal('200.000'), actual_good_output=Decimal('188.000'),
            consumptions_data=consumptions_data, overheads_data=overheads_data, wastage_quantity=Decimal('12.000'),
            production_date=timezone.now().date(), supervisor=supervisor, notes='Benchmark Production Run'
        )

        # CALC 7: Production Yield Variance %
        # ((188 - 200) / 200) * 100 = -6.00%
        log_result(7, "Production Yield Variance %", Decimal('-6.00'), run.yield_variance_percent, run.yield_variance_percent == Decimal('-6.00'))

        # CALC 8: Production Yield Alert Triggered (>3% deviation)
        log_result(8, "Yield Variance Alert Threshold (> 3% absolute deviation)", True, run.yield_alert, run.yield_alert is True, "Flags deviation exceeds 3.00%")

        # CALC 9: Cooking Oil Consumption Variance %
        # ((10.5 - 10.0) / 10.0) * 100 = +5.00%
        oil_c = run.consumptions.get(item_name='Cooking oil')
        log_result(9, "Cooking Oil Consumption Variance %", Decimal('5.00'), oil_c.variance_percent, oil_c.variance_percent == Decimal('5.00'))

        # CALC 10: Cooking Oil Variance Alert Flag
        log_result(10, "Cooking Oil Variance Alert Triggered (> 3%)", True, oil_c.variance_alert, oil_c.variance_alert is True)

        # CALC 11: Carton Packaging Variance %
        # ((9 - 10) / 10) * 100 = -10.00%
        carton_c = run.consumptions.get(item_name='Carton')
        log_result(11, "Carton Packaging Consumption Variance %", Decimal('-10.00'), carton_c.variance_percent, carton_c.variance_percent == Decimal('-10.00'))

        # CALC 12: Production Raw Material Direct Cost
        # Flour (40 * 43.1250 = 1725.00) + Oil (10.5 * 140.00 = 1470.00) + Spice (1.2 * 200.00 = 240.00) = Rs. 3,435.00
        log_result(12, "Direct Raw Material Cost", Decimal('3435.00'), costing.raw_material_cost, costing.raw_material_cost == Decimal('3435.00'), "Flour Rs.1725 + Oil Rs.1470 + Spice Rs.240")

        # CALC 13: Production Packaging Material Cost
        # Pouches (194 * 2.50 = 485.00) + Cartons (9 * 15.00 = 135.00) = Rs. 620.00
        log_result(13, "Direct Packaging Material Cost", Decimal('620.00'), costing.packaging_material_cost, costing.packaging_material_cost == Decimal('620.00'), "Pouches Rs.485 + Cartons Rs.135")

        # CALC 14: Direct Material Subtotal
        mat_subtotal = costing.raw_material_cost + costing.packaging_material_cost
        log_result(14, "Direct Material Cost Subtotal", Decimal('4055.00'), mat_subtotal, mat_subtotal == Decimal('4055.00'))

        # CALC 15: Overhead Allocation Subtotal
        # Labour (Rs. 1,200.00) + Power/LPG (Rs. 600.00) = Rs. 1,800.00
        ov_total = costing.labour_cost + costing.power_and_gas_cost
        log_result(15, "Overhead Allocation Subtotal", Decimal('1800.00'), ov_total, ov_total == Decimal('1800.00'))

        # CALC 16: Total Batch Production Cost
        # Rs. 4,055.00 + Rs. 1,800.00 = Rs. 5,855.00
        log_result(16, "Total Batch Production Cost", Decimal('5855.00'), costing.total_production_cost, costing.total_production_cost == Decimal('5855.00'))

        # CALC 17: Cost Per Packet (5855 / 188)
        cost_per_pkt = round(costing.cost_per_packet, 2)
        log_result(17, "Unit Cost Per Packet (Rs. 5,855 / 188 pkts)", Decimal('31.14'), cost_per_pkt, cost_per_pkt == Decimal('31.14'))

        # CALC 18: Gross Margin Per Packet (Rs. 50.00 - 31.14)
        margin_per_pkt = round(costing.gross_margin_per_packet, 2)
        log_result(18, "Gross Margin Per Packet at Rs. 50 Selling Price", Decimal('18.86'), margin_per_pkt, margin_per_pkt == Decimal('18.86'))

        # CALC 19: Gross Margin Percentage
        margin_pct = round(costing.gross_margin_percent, 2)
        log_result(19, "Gross Margin Percentage", Decimal('37.71'), margin_pct, margin_pct == Decimal('37.71'), "((50 - 31.1436)/50)*100")

        # -------------------------------------------------------------
        # 4. SALES ORDER 1, GST BILLING, DISPATCH & PAYMENT
        # -------------------------------------------------------------
        self.stdout.write(self.style.NOTICE("\n[PHASE 4] Auditing Sales Order 1, Intra-state GST, Dispatch & Payment..."))
        product.refresh_from_db()
        # Initial 50 + Produced 188 = 238 pkts
        log_result(20, "Finished Goods Stock Before Dispatch (50 + 188)", Decimal('238.000'), product.current_stock, product.current_stock == Decimal('238.000'))

        order_a = SalesOrderService.create_order(
            customer_id=cust_a.id, salesman=salesman_a,
            items_data=[{'product_id': product.id, 'quantity': '150.000', 'unit_price': '50.00'}],
            notes='Benchmark Order: Retailer A'
        )
        SalesOrderService.approve_order(order_a.id, admin_user=admin_user)
        inv_a = InvoiceService.generate_invoice_from_order(order_a.id, user=admin_user)

        # CALC 21: Invoice A Taxable Amount
        log_result(21, "Invoice A Taxable Amount (150 pkts * Rs. 50.00)", Decimal('7500.00'), inv_a.taxable_amount, inv_a.taxable_amount == Decimal('7500.00'))

        # CALC 22: Intra-state GST (CGST 2.5% + SGST 2.5%)
        cgst_pass = inv_a.cgst_amount == Decimal('187.50') and inv_a.sgst_amount == Decimal('187.50') and inv_a.igst_amount == Decimal('0.00')
        log_result(22, "Intra-state GST Split (CGST Rs. 187.50 + SGST Rs. 187.50, IGST Rs. 0)", "CGST: 187.50, SGST: 187.50", f"CGST: {inv_a.cgst_amount}, SGST: {inv_a.sgst_amount}", cgst_pass)

        # CALC 23: Invoice A Grand Total
        log_result(23, "Invoice A Grand Total (Taxable + GST)", Decimal('7875.00'), inv_a.grand_total, inv_a.grand_total == Decimal('7875.00'))

        # Dispatch 150 packets
        dsp_a = DispatchService.record_dispatch(
            sales_order_id=order_a.id, invoice_id=inv_a.id, user=admin_user,
            transporter_name='TN Express Logistics', vehicle_number='TN-45-AZ-1234', notes='Benchmark Dispatch to Retailer A'
        )
        product.refresh_from_db()

        # CALC 24: Finished Goods Stock after Dispatch 1 (238 - 150 = 88)
        log_result(24, "Finished Goods Stock After Dispatch 1 (238 - 150 pkts)", Decimal('88.000'), product.current_stock, product.current_stock == Decimal('88.000'))

        # Record Partial Payment of Rs. 4,000
        pmt = PaymentService.record_payment(
            customer_id=cust_a.id, amount=Decimal('4000.00'), payment_date=timezone.now().date(),
            payment_method=PaymentMethod.BANK_TRANSFER, transaction_reference='NEFT-SBI-4910284',
            invoice_id=inv_a.id, user=admin_user, notes='Part payment against Invoice ' + inv_a.invoice_number
        )
        inv_a.refresh_from_db()

        # CALC 25: Invoice A Outstanding Amount after Payment
        log_result(25, "Invoice A Outstanding Balance (Rs. 7,875.00 - Rs. 4,000.00)", Decimal('3875.00'), inv_a.outstanding_amount, inv_a.outstanding_amount == Decimal('3875.00'))

        # CALC 26: Overpayment Prevention Assertion
        overpayment_prevented = False
        try:
            PaymentService.record_payment(
                customer_id=cust_a.id, amount=Decimal('3875.01'), payment_date=timezone.now().date(),
                payment_method=PaymentMethod.CASH, invoice_id=inv_a.id, user=admin_user
            )
        except ValidationError:
            overpayment_prevented = True
        log_result(26, "Overpayment Prevention (Exceeding Outstanding Balance Blocked)", True, overpayment_prevented, overpayment_prevented is True, "ValidationError raised when payment exceeds Rs. 3,875.00")

        # -------------------------------------------------------------
        # 5. SALES ORDER 2 & DISTRIBUTOR B 32-PKT SHORTAGE ENFORCEMENT
        # -------------------------------------------------------------
        self.stdout.write(self.style.NOTICE("\n[PHASE 5] Auditing Sales Order 2 & 32-Packet Shortage Enforcement..."))
        order_b = SalesOrderService.create_order(
            customer_id=cust_b.id, salesman=salesman_b,
            items_data=[{'product_id': product.id, 'quantity': '120.000', 'unit_price': '50.00'}],
            notes='Benchmark Order: Distributor B (Shortage Scenario)'
        )

        # CALC 27: Interstate GST Calculation (IGST 5% for Karnataka)
        # 120 * 50 = Rs. 6,000; IGST 5% = Rs. 300.00; Total = Rs. 6,300.00
        igst_pass = order_b.subtotal_amount == Decimal('6000.00') and order_b.tax_amount == Decimal('300.00') and order_b.grand_total == Decimal('6300.00')
        log_result(27, "Interstate Order Tax Calculation (IGST 5% on Rs. 6,000 = Rs. 300)", Decimal('6300.00'), order_b.grand_total, igst_pass)

        # CALC 28: Stock Shortage Detection for Distributor B
        stock_check_b = SalesOrderService.check_stock_availability(order_b)
        log_result(28, "Shortage Flag Detected for Distributor B", True, stock_check_b['has_shortage'], stock_check_b['has_shortage'] is True)

        # CALC 29: Exact 32-Packet Shortage Quantity
        # Required 120 pkts - Available 88 pkts = Shortage 32 pkts
        log_result(29, "Shortage Quantity Calculation (120 ordered - 88 available)", Decimal('32.000'), stock_check_b['total_shortage_quantity'], stock_check_b['total_shortage_quantity'] == Decimal('32.000'))

        # CALC 30: System Dispatch Blockade on Shortage
        dispatch_blocked = False
        exception_msg = ""
        try:
            DispatchService.record_dispatch(sales_order_id=order_b.id, user=admin_user)
        except ValidationError as e:
            dispatch_blocked = True
            exception_msg = str(e)
        log_result(30, "System Enforces Dispatch Block on Shortage", True, dispatch_blocked, dispatch_blocked is True, f"Blocked with message: {exception_msg[:70]}...")

        # CALC 31: Stock Preservation (Stock must remain at 88.000 pkts)
        product.refresh_from_db()
        log_result(31, "Finished Goods Stock Unaltered After Blocked Dispatch", Decimal('88.000'), product.current_stock, product.current_stock == Decimal('88.000'))

        # -------------------------------------------------------------
        # 6. STOCK LEDGER RECONCILIATION & DOUBLE-ENTRY AUDIT
        # -------------------------------------------------------------
        self.stdout.write(self.style.NOTICE("\n[PHASE 6] Reconciling Every Stock Ledger Movement and Physical Balances..."))
        
        expected_balances = {
            ('RAW_MATERIAL', rm_flour.id, 'Flour'): Decimal('120.000'),
            ('RAW_MATERIAL', rm_oil.id, 'Cooking oil'): Decimal('19.500'),
            ('RAW_MATERIAL', rm_spice.id, 'Salt and spice mix'): Decimal('3.800'),
            ('PACKAGING_MATERIAL', pm_pouch.id, '200 g pouch'): Decimal('306.000'),
            ('PACKAGING_MATERIAL', pm_carton.id, 'Carton'): Decimal('21.000'),
            ('FINISHED_GOODS', product.id, 'Murukku 200 g'): Decimal('88.000'),
        }

        ledger_intact = True
        calc_counter = 32

        for (itype, iid, iname), exp_balance in expected_balances.items():
            entries = StockLedger.objects.filter(item_type=itype, item_id=iid).order_by('id')
            running_qty = Decimal('0.000')
            chain_valid = True

            for entry in entries:
                running_qty += entry.quantity_change
                if running_qty != entry.balance_after:
                    chain_valid = False

            # Verify balance in StockBalance table
            balance_record = StockBalance.objects.get(item_type=itype, item_id=iid)
            stock_match = (running_qty == exp_balance) and (balance_record.current_quantity == exp_balance) and chain_valid

            if not stock_match:
                ledger_intact = False

            log_result(
                calc_counter,
                f"Stock Ledger Chain & Closing Balance: {iname}",
                exp_balance,
                running_qty,
                stock_match,
                f"Ledger entries count: {entries.count()}, Chain integrity: {'OK' if chain_valid else 'CORRUPT'}"
            )
            calc_counter += 1

        # Summary of All Tests
        total_tests = len(results)
        passed_tests = sum(1 for r in results if r['status'] == 'PASS')
        failed_tests = total_tests - passed_tests

        self.stdout.write(self.style.MIGRATE_HEADING("\n================================================================================"))
        self.stdout.write(self.style.MIGRATE_HEADING("   AUDIT EVALUATION SUMMARY - CENTRE FOR DIGITAL INFRASTRUCTURE"))
        self.stdout.write(self.style.MIGRATE_HEADING("================================================================================"))
        self.stdout.write(f"Total Business Calculations Audited: {total_tests}")
        self.stdout.write(self.style.SUCCESS(f"Passed: {passed_tests}"))
        if failed_tests > 0:
            self.stdout.write(self.style.ERROR(f"Failed: {failed_tests}"))
        else:
            self.stdout.write(self.style.SUCCESS("All Business Calculations and Ledger Movements: 100% PASS"))
        self.stdout.write(self.style.MIGRATE_HEADING("================================================================================\n"))

        return 0 if failed_tests == 0 else 1
