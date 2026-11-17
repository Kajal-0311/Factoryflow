from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.inventory.models import StockLedger, StockBalance, StockItemType, StockTransactionType
from apps.masters.models import RawMaterial, PackagingMaterial, Product

class InventoryService:
    """
    Central Ledger-based Inventory Service.
    Enforces atomic transactions and prevents negative stock balances.
    """

    @classmethod
    def get_item(cls, item_type, item_id, lock=False):
        """Fetch item instance with optional database-level row lock."""
        queryset = None
        if item_type == StockItemType.RAW_MATERIAL:
            queryset = RawMaterial.objects
        elif item_type == StockItemType.PACKAGING_MATERIAL:
            queryset = PackagingMaterial.objects
        elif item_type == StockItemType.FINISHED_GOODS:
            queryset = Product.objects
        else:
            raise ValidationError(f"Invalid item_type '{item_type}'")

        if lock:
            queryset = queryset.select_for_update()

        try:
            return queryset.get(pk=item_id)
        except queryset.model.DoesNotExist:
            raise ValidationError(f"Item not found: {item_type} with ID {item_id}")

    @classmethod
    @transaction.atomic
    def record_movement(cls, item_type, item_id, transaction_type, quantity,
                        unit_rate=None, reference_doc='', source_module='',
                        user=None, notes='', allow_negative=False):
        """
        Record an immutable stock movement and update the item's on-hand stock atomically.
        """
        qty = Decimal(str(quantity)).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
        if qty <= Decimal('0') and transaction_type != StockTransactionType.ADJUSTMENT:
            raise ValidationError(f"Quantity must be positive for {transaction_type}, got {quantity}")

        # Determine signed movement (+ for inflow, - for outflow)
        inflow_types = [
            StockTransactionType.OPENING_STOCK,
            StockTransactionType.PURCHASE_RECEIPT,
            StockTransactionType.PRODUCTION_OUTPUT,
            StockTransactionType.SALES_RETURN,
        ]
        outflow_types = [
            StockTransactionType.PRODUCTION_ISSUE,
            StockTransactionType.SALES_DISPATCH,
        ]

        if transaction_type in inflow_types:
            signed_qty = qty
        elif transaction_type in outflow_types:
            signed_qty = -qty
        elif transaction_type == StockTransactionType.ADJUSTMENT:
            signed_qty = qty  # Caller provides signed adjustment
        else:
            raise ValidationError(f"Unknown transaction type '{transaction_type}'")

        # Fetch item with row lock to prevent race conditions
        item = cls.get_item(item_type, item_id, lock=True)
        
        # Get current balance from item or StockBalance
        current_stock = Decimal(str(getattr(item, 'current_stock', Decimal('0'))))
        new_balance = (current_stock + signed_qty).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)

        # Validate against negative stock
        if new_balance < Decimal('0') and not allow_negative:
            shortage = abs(new_balance)
            raise ValidationError(
                f"Insufficient stock for {item.name}: Available = {current_stock}, Required = {abs(signed_qty)}, Shortage = {shortage}"
            )

        # Determine valuation rate
        if unit_rate is None:
            if hasattr(item, 'weighted_average_cost'):
                rate = Decimal(str(item.weighted_average_cost))
            elif hasattr(item, 'purchase_rate'):
                rate = Decimal(str(item.purchase_rate))
            elif hasattr(item, 'selling_price'):
                rate = Decimal(str(item.selling_price))
            else:
                rate = Decimal('0.0000')
        else:
            rate = Decimal(str(unit_rate)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)

        total_val = (abs(signed_qty) * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        uom_str = item.uom.code if hasattr(item, 'uom') else 'units'

        # Update item stock field
        item.current_stock = new_balance
        item.save(update_fields=['current_stock', 'updated_at'])

        # Update or create cached StockBalance
        StockBalance.objects.update_or_create(
            item_type=item_type,
            item_id=item_id,
            defaults={
                'item_name': item.name,
                'current_quantity': new_balance,
                'valuation_rate': rate,
                'uom_code': uom_str,
            }
        )

        # Create immutable StockLedger record
        ledger_entry = StockLedger.objects.create(
            item_type=item_type,
            item_id=item_id,
            item_name=item.name,
            transaction_type=transaction_type,
            quantity_change=signed_qty,
            balance_after=new_balance,
            uom_code=uom_str,
            unit_rate=rate,
            total_value=total_val,
            reference_doc=reference_doc,
            source_module=source_module,
            user_responsible=user,
            notes=notes
        )

        return ledger_entry

    @classmethod
    def get_stock(cls, item_type, item_id):
        """Retrieve current available stock for an item."""
        try:
            balance = StockBalance.objects.get(item_type=item_type, item_id=item_id)
            return balance.current_quantity
        except StockBalance.DoesNotExist:
            item = cls.get_item(item_type, item_id)
            return getattr(item, 'current_stock', Decimal('0.000'))

    @classmethod
    def reconcile_item(cls, item_type, item_id):
        """Reconcile stock ledger history against current cached stock."""
        ledger_entries = StockLedger.objects.filter(item_type=item_type, item_id=item_id).order_by('created_at', 'id')
        computed_balance = Decimal('0.000')
        for entry in ledger_entries:
            computed_balance += Decimal(str(entry.quantity_change))

        computed_balance = computed_balance.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
        item = cls.get_item(item_type, item_id)
        current_cached = Decimal(str(getattr(item, 'current_stock', Decimal('0'))))

        is_reconciled = (computed_balance == current_cached)
        return {
            'item_name': item.name,
            'computed_from_ledger': computed_balance,
            'cached_stock': current_cached,
            'is_reconciled': is_reconciled,
            'discrepancy': computed_balance - current_cached,
        }
