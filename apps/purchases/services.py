from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.purchases.models import Purchase, PurchaseItem, PurchaseStatus
from apps.inventory.services import InventoryService
from apps.inventory.models import StockItemType, StockTransactionType
from apps.masters.models import RawMaterial, PackagingMaterial

class PurchaseService:
    """Service handling purchase order processing and weighted average cost valuation."""

    @classmethod
    def calculate_new_wac(cls, current_qty, current_wac, inward_qty, purchase_rate):
        """
        Calculate new weighted average cost:
        New WAC = ((current_qty * current_wac) + (inward_qty * purchase_rate)) / (current_qty + inward_qty)
        """
        c_qty = Decimal(str(current_qty))
        c_wac = Decimal(str(current_wac))
        i_qty = Decimal(str(inward_qty))
        p_rate = Decimal(str(purchase_rate))

        total_qty = c_qty + i_qty
        if total_qty <= Decimal('0'):
            return p_rate

        total_valuation = (c_qty * c_wac) + (i_qty * p_rate)
        new_wac = total_valuation / total_qty
        # Precision: 4 decimal places for unit cost
        return new_wac.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)

    @classmethod
    @transaction.atomic
    def confirm_purchase(cls, purchase_id, user=None):
        """
        Confirms a purchase order, updates inventory, recalculates WAC, and logs ledger entries.
        """
        purchase = Purchase.objects.select_for_update().get(pk=purchase_id)
        if purchase.status == PurchaseStatus.CONFIRMED:
            raise ValidationError(f"Purchase {purchase.purchase_number} is already confirmed.")

        for item in purchase.items.all():
            qty = Decimal(str(item.quantity))
            rate = Decimal(str(item.purchase_rate))

            if item.item_type == PurchaseItem.ItemType.RAW_MATERIAL:
                rm = RawMaterial.objects.select_for_update().get(pk=item.raw_material.id)
                current_qty = InventoryService.get_stock(StockItemType.RAW_MATERIAL, rm.id)
                current_wac = rm.weighted_average_cost

                # Calculate new WAC
                new_wac = cls.calculate_new_wac(current_qty, current_wac, qty, rate)
                rm.weighted_average_cost = new_wac
                rm.purchase_rate = rate
                rm.save(update_fields=['weighted_average_cost', 'purchase_rate', 'updated_at'])

                # Record stock movement
                InventoryService.record_movement(
                    item_type=StockItemType.RAW_MATERIAL,
                    item_id=rm.id,
                    transaction_type=StockTransactionType.PURCHASE_RECEIPT,
                    quantity=qty,
                    unit_rate=rate,
                    reference_doc=purchase.purchase_number,
                    source_module='PURCHASES',
                    user=user,
                    notes=f"Inward from {purchase.supplier.name} (Supplier Inv: {purchase.supplier_invoice_ref})"
                )

            elif item.item_type == PurchaseItem.ItemType.PACKAGING_MATERIAL:
                pm = PackagingMaterial.objects.select_for_update().get(pk=item.packaging_material.id)
                pm.purchase_rate = rate
                pm.save(update_fields=['purchase_rate', 'updated_at'])

                # Record stock movement
                InventoryService.record_movement(
                    item_type=StockItemType.PACKAGING_MATERIAL,
                    item_id=pm.id,
                    transaction_type=StockTransactionType.PURCHASE_RECEIPT,
                    quantity=qty,
                    unit_rate=rate,
                    reference_doc=purchase.purchase_number,
                    source_module='PURCHASES',
                    user=user,
                    notes=f"Inward from {purchase.supplier.name} (Supplier Inv: {purchase.supplier_invoice_ref})"
                )

        purchase.status = PurchaseStatus.CONFIRMED
        purchase.confirmed_by = user
        purchase.confirmed_at = timezone.now()
        purchase.save(update_fields=['status', 'confirmed_by', 'confirmed_at', 'updated_at'])

        return purchase
