from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.production.models import (
    ProductionRun, ProductionConsumption, Overhead, CostingRecord, ProductionRunStatus
)
from apps.bom.services import BOMService
from apps.inventory.services import InventoryService
from apps.inventory.models import StockItemType, StockTransactionType
from apps.masters.models import RawMaterial, PackagingMaterial, Product

class ProductionService:
    """
    Production Execution & Costing Service.
    Enforces atomic batch processing, variance alerts, and ledger updates.
    """

    VARIANCE_THRESHOLD_PERCENT = Decimal('3.00')

    @classmethod
    def calculate_variance(cls, actual, planned):
        act = Decimal(str(actual))
        plan = Decimal(str(planned))
        if plan == Decimal('0'):
            return Decimal('0.00'), False
        
        diff = act - plan
        variance_pct = ((diff / plan) * Decimal('100.0')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        is_alert = abs(variance_pct) > cls.VARIANCE_THRESHOLD_PERCENT
        return variance_pct, is_alert

    @classmethod
    @transaction.atomic
    def execute_production_run(cls, product_id, batch_quantity, actual_good_output,
                               consumptions_data, overheads_data=None,
                               wastage_quantity=Decimal('0.000'), production_date=None,
                               supervisor=None, notes=''):
        """
        Executes a production run atomically:
        1. Validates BOM and inputs
        2. Deducts raw materials and packaging from stock
        3. Increments finished goods stock
        4. Calculates planned vs actual variances & alerts
        5. Computes production costing (WAC + packaging + overheads)
        """
        product = Product.objects.select_for_update().get(pk=product_id)
        bom = BOMService.get_active_bom(product.id)

        batch_qty = Decimal(str(batch_quantity)).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
        act_output = Decimal(str(actual_good_output)).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
        wastage_qty = Decimal(str(wastage_quantity)).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)

        if batch_qty <= Decimal('0'):
            raise ValidationError("Batch quantity must be greater than zero.")
        if act_output <= Decimal('0'):
            raise ValidationError("Actual good output must be greater than zero.")

        # Scale expected output from BOM
        scale_factor = batch_qty / bom.batch_size
        expected_output = (bom.expected_output * scale_factor).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)

        # Yield variance calculation
        yield_var_pct, yield_alert = cls.calculate_variance(act_output, expected_output)

        # Generate run number
        run_count = ProductionRun.objects.count() + 1
        run_number = f"PRUN-{production_date.strftime('%Y%m') if production_date else '202601'}-{run_count:04d}"

        # Create ProductionRun record
        prod_run = ProductionRun.objects.create(
            run_number=run_number,
            product=product,
            bom=bom,
            batch_quantity=batch_qty,
            expected_output=expected_output,
            actual_good_output=act_output,
            wastage_quantity=wastage_qty,
            yield_variance_percent=yield_var_pct,
            yield_alert=yield_alert,
            status=ProductionRunStatus.COMPLETED,
            production_date=production_date,
            supervisor=supervisor,
            notes=notes
        )

        total_rm_cost = Decimal('0.00')
        total_pkg_cost = Decimal('0.00')

        # Process Consumptions
        for c in consumptions_data:
            item_type = c['item_type']
            planned_qty = Decimal(str(c['planned_quantity'])).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
            actual_qty = Decimal(str(c['actual_quantity'])).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
            damaged_qty = Decimal(str(c.get('damaged_quantity', '0.000'))).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)

            var_pct, var_alert = cls.calculate_variance(actual_qty, planned_qty)

            if item_type == ProductionConsumption.ItemType.RAW_MATERIAL:
                rm = RawMaterial.objects.select_for_update().get(pk=c['raw_material_id'])
                unit_rate = rm.weighted_average_cost
                item_cost = (actual_qty * unit_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                total_rm_cost += item_cost

                # Deduct stock
                InventoryService.record_movement(
                    item_type=StockItemType.RAW_MATERIAL,
                    item_id=rm.id,
                    transaction_type=StockTransactionType.PRODUCTION_ISSUE,
                    quantity=actual_qty,
                    unit_rate=unit_rate,
                    reference_doc=run_number,
                    source_module='PRODUCTION',
                    user=supervisor,
                    notes=f"Consumed in batch {run_number}"
                )

                ProductionConsumption.objects.create(
                    production_run=prod_run,
                    item_type=item_type,
                    raw_material=rm,
                    item_name=rm.name,
                    uom_code=rm.uom.code,
                    planned_quantity=planned_qty,
                    actual_quantity=actual_qty,
                    damaged_quantity=damaged_qty,
                    variance_percent=var_pct,
                    variance_alert=var_alert,
                    unit_rate=unit_rate,
                    total_cost=item_cost
                )

            elif item_type == ProductionConsumption.ItemType.PACKAGING_MATERIAL:
                pm = PackagingMaterial.objects.select_for_update().get(pk=c['packaging_material_id'])
                unit_rate = pm.purchase_rate
                # Note: damaged packaging must be included in consumption and costing
                item_cost = (actual_qty * unit_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                total_pkg_cost += item_cost

                # Deduct stock
                InventoryService.record_movement(
                    item_type=StockItemType.PACKAGING_MATERIAL,
                    item_id=pm.id,
                    transaction_type=StockTransactionType.PRODUCTION_ISSUE,
                    quantity=actual_qty,
                    unit_rate=unit_rate,
                    reference_doc=run_number,
                    source_module='PRODUCTION',
                    user=supervisor,
                    notes=f"Packaging used in batch {run_number} (Damaged: {damaged_qty})"
                )

                ProductionConsumption.objects.create(
                    production_run=prod_run,
                    item_type=item_type,
                    packaging_material=pm,
                    item_name=pm.name,
                    uom_code=pm.uom.code,
                    planned_quantity=planned_qty,
                    actual_quantity=actual_qty,
                    damaged_quantity=damaged_qty,
                    variance_percent=var_pct,
                    variance_alert=var_alert,
                    unit_rate=unit_rate,
                    total_cost=item_cost
                )

        # Process Overheads
        labour_cost = Decimal('0.00')
        power_gas_cost = Decimal('0.00')
        other_overheads_cost = Decimal('0.00')

        if overheads_data:
            for ov in overheads_data:
                ov_type = ov['overhead_type']
                amt = Decimal(str(ov['amount'])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                desc = ov.get('description', '')

                Overhead.objects.create(
                    production_run=prod_run,
                    overhead_type=ov_type,
                    description=desc,
                    amount=amt
                )

                if ov_type == Overhead.OverheadType.LABOUR:
                    labour_cost += amt
                elif ov_type == Overhead.OverheadType.POWER_GAS:
                    power_gas_cost += amt
                else:
                    other_overheads_cost += amt

        # Total Costing Calculation
        total_prod_cost = total_rm_cost + total_pkg_cost + labour_cost + power_gas_cost + other_overheads_cost
        cost_per_packet = (total_prod_cost / act_output).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
        selling_price = product.selling_price
        gross_margin = (selling_price - cost_per_packet).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
        margin_pct = Decimal('0.00')
        if selling_price > Decimal('0'):
            margin_pct = ((gross_margin / selling_price) * Decimal('100.0')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        costing_record = CostingRecord.objects.create(
            production_run=prod_run,
            product=product,
            raw_material_cost=total_rm_cost,
            packaging_material_cost=total_pkg_cost,
            labour_cost=labour_cost,
            power_and_gas_cost=power_gas_cost,
            other_overheads_cost=other_overheads_cost,
            total_production_cost=total_prod_cost,
            cost_per_packet=cost_per_packet,
            selling_price_per_packet=selling_price,
            gross_margin_per_packet=gross_margin,
            gross_margin_percent=margin_pct
        )

        # Increment Finished Goods stock
        InventoryService.record_movement(
            item_type=StockItemType.FINISHED_GOODS,
            item_id=product.id,
            transaction_type=StockTransactionType.PRODUCTION_OUTPUT,
            quantity=act_output,
            unit_rate=cost_per_packet,
            reference_doc=run_number,
            source_module='PRODUCTION',
            user=supervisor,
            notes=f"Produced in batch {run_number} (Wastage: {wastage_qty})"
        )

        return prod_run, costing_record
