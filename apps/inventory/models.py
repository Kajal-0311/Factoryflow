from decimal import Decimal
from django.db import models
from django.conf import settings
from apps.core.models import TimeStampedModel

class StockItemType(models.TextChoices):
    RAW_MATERIAL = 'RAW_MATERIAL', 'Raw Material'
    PACKAGING_MATERIAL = 'PACKAGING_MATERIAL', 'Packaging Material'
    FINISHED_GOODS = 'FINISHED_GOODS', 'Finished Goods'


class StockTransactionType(models.TextChoices):
    OPENING_STOCK = 'OPENING_STOCK', 'Opening Stock'
    PURCHASE_RECEIPT = 'PURCHASE_RECEIPT', 'Purchase Receipt'
    PRODUCTION_ISSUE = 'PRODUCTION_ISSUE', 'Production Issue'
    PRODUCTION_OUTPUT = 'PRODUCTION_OUTPUT', 'Production Output'
    SALES_DISPATCH = 'SALES_DISPATCH', 'Sales Dispatch'
    SALES_RETURN = 'SALES_RETURN', 'Sales Return'
    ADJUSTMENT = 'ADJUSTMENT', 'Stock Adjustment'


class StockLedger(TimeStampedModel):
    """
    Immutable ledger recording every stock movement across Raw Materials,
    Packaging, and Finished Goods.
    """
    item_type = models.CharField(max_length=30, choices=StockItemType.choices, db_index=True)
    item_id = models.PositiveIntegerField(db_index=True)
    item_name = models.CharField(max_length=200)
    transaction_type = models.CharField(max_length=30, choices=StockTransactionType.choices, db_index=True)
    
    # Signed quantity: positive for inflow, negative for outflow
    quantity_change = models.DecimalField(max_digits=14, decimal_places=3)
    balance_after = models.DecimalField(max_digits=14, decimal_places=3)
    uom_code = models.CharField(max_length=20)
    
    # Financial valuation at time of transaction
    unit_rate = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0.0000'))
    total_value = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    
    # Audit & Traceability
    reference_doc = models.CharField(max_length=100, db_index=True, help_text="e.g. PO-001, PROD-001, INV-001")
    source_module = models.CharField(max_length=50, help_text="Purchases, Production, Sales, Masters")
    user_responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_movements'
    )
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Stock Ledger Entry'
        verbose_name_plural = 'Stock Ledger'
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['item_type', 'item_id', 'created_at']),
            models.Index(fields=['reference_doc']),
        ]

    def __str__(self):
        sign = '+' if self.quantity_change > 0 else ''
        return f"[{self.get_transaction_type_display()}] {self.item_name}: {sign}{self.quantity_change} {self.uom_code} (Bal: {self.balance_after})"


class StockBalance(TimeStampedModel):
    """
    Transactionally updated cache of stock balances, verified against the ledger.
    """
    item_type = models.CharField(max_length=30, choices=StockItemType.choices, db_index=True)
    item_id = models.PositiveIntegerField(db_index=True)
    item_name = models.CharField(max_length=200)
    current_quantity = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0.000'))
    valuation_rate = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0.0000'))
    uom_code = models.CharField(max_length=20)

    class Meta:
        verbose_name = 'Stock Balance'
        verbose_name_plural = 'Stock Balances'
        unique_together = ('item_type', 'item_id')

    def __str__(self):
        return f"{self.item_name}: {self.current_quantity} {self.uom_code}"
