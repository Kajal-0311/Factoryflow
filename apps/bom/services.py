from decimal import Decimal, ROUND_HALF_UP
from django.core.exceptions import ValidationError
from apps.bom.models import BOM, BOMItem
from apps.inventory.services import InventoryService
from apps.inventory.models import StockItemType

class BOMService:
    """Service to load BOMs and dynamically calculate planned requirements."""

    @classmethod
    def get_active_bom(cls, product_id):
        try:
            return BOM.objects.select_related('product').prefetch_related(
                'items__raw_material__uom',
                'items__packaging_material__uom',
                'items__uom'
            ).get(product_id=product_id, is_active=True)
        except BOM.DoesNotExist:
            raise ValidationError(f"No active Bill of Materials (BOM) found for product ID {product_id}")

    @classmethod
    def calculate_requirements(cls, bom, batch_quantity):
        """
        Calculates planned material and packaging requirements for a given batch quantity.
        """
        batch_qty = Decimal(str(batch_quantity)).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
        if batch_qty <= Decimal('0'):
            raise ValidationError("Batch quantity must be greater than zero.")

        scale_factor = batch_qty / bom.batch_size
        expected_output = (bom.expected_output * scale_factor).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)

        raw_materials = []
        packaging_materials = []

        for item in bom.items.all():
            planned_qty = (item.standard_quantity * scale_factor).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
            
            if item.item_type == BOMItem.ItemType.RAW_MATERIAL:
                mat = item.raw_material
                stock = InventoryService.get_stock(StockItemType.RAW_MATERIAL, mat.id)
                rate = mat.weighted_average_cost
                raw_materials.append({
                    'bom_item_id': item.id,
                    'item_type': item.item_type,
                    'material_id': mat.id,
                    'name': mat.name,
                    'standard_quantity': item.standard_quantity,
                    'planned_quantity': planned_qty,
                    'uom': item.uom.code,
                    'current_stock': stock,
                    'unit_rate': rate,
                    'estimated_cost': (planned_qty * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                })
            else:
                pkg = item.packaging_material
                stock = InventoryService.get_stock(StockItemType.PACKAGING_MATERIAL, pkg.id)
                rate = pkg.purchase_rate
                packaging_materials.append({
                    'bom_item_id': item.id,
                    'item_type': item.item_type,
                    'material_id': pkg.id,
                    'name': pkg.name,
                    'packaging_type': pkg.packaging_type,
                    'standard_quantity': item.standard_quantity,
                    'planned_quantity': planned_qty,
                    'uom': item.uom.code,
                    'current_stock': stock,
                    'unit_rate': rate,
                    'estimated_cost': (planned_qty * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                })

        return {
            'bom_code': bom.bom_code,
            'product_name': bom.product.name,
            'batch_size': bom.batch_size,
            'target_batch_quantity': batch_qty,
            'expected_output': expected_output,
            'raw_materials': raw_materials,
            'packaging_materials': packaging_materials,
        }
