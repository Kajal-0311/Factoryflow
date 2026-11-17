from decimal import Decimal
from django.db import models
from django.core.exceptions import ValidationError
from apps.core.models import TimeStampedModel
from apps.masters.models import Product, RawMaterial, PackagingMaterial, UnitOfMeasurement

class BOM(TimeStampedModel):
    """
    Configurable Bill of Materials for a finished product.
    Defines standard recipe and packaging requirements per batch.
    """
    bom_code = models.CharField(max_length=50, unique=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='boms')
    batch_size = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=Decimal('200.000'),
        help_text="Standard batch size in finished product units (e.g. 200 packets)"
    )
    expected_output = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=Decimal('200.000'),
        help_text="Expected good output packets for this batch size"
    )
    standard_yield_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('100.00'),
        help_text="Standard yield percentage"
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Bill of Materials (BOM)'
        verbose_name_plural = 'Bills of Materials (BOMs)'
        ordering = ['product__name']

    def __str__(self):
        return f"{self.bom_code} - {self.product.name} ({self.batch_size} pkts)"

    def clean(self):
        if self.batch_size <= Decimal('0'):
            raise ValidationError("Batch size must be greater than zero.")
        if self.expected_output <= Decimal('0'):
            raise ValidationError("Expected output must be greater than zero.")


class BOMItem(TimeStampedModel):
    class ItemType(models.TextChoices):
        RAW_MATERIAL = 'RAW_MATERIAL', 'Raw Material'
        PACKAGING_MATERIAL = 'PACKAGING_MATERIAL', 'Packaging Material'

    bom = models.ForeignKey(BOM, on_delete=models.CASCADE, related_name='items')
    item_type = models.CharField(max_length=30, choices=ItemType.choices)
    raw_material = models.ForeignKey(RawMaterial, null=True, blank=True, on_delete=models.PROTECT, related_name='bom_usages')
    packaging_material = models.ForeignKey(PackagingMaterial, null=True, blank=True, on_delete=models.PROTECT, related_name='bom_usages')
    standard_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        help_text="Standard required quantity for the standard batch size"
    )
    uom = models.ForeignKey(UnitOfMeasurement, on_delete=models.PROTECT)
    loss_allowance_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Expected handling or process loss percentage"
    )

    class Meta:
        verbose_name = 'BOM Item'
        verbose_name_plural = 'BOM Items'
        ordering = ['item_type', 'id']

    def __str__(self):
        name = self.raw_material.name if self.item_type == self.ItemType.RAW_MATERIAL else self.packaging_material.name
        return f"{self.bom.product.name} -> {name}: {self.standard_quantity} {self.uom.code}"

    def clean(self):
        if self.item_type == self.ItemType.RAW_MATERIAL and not self.raw_material:
            raise ValidationError("Raw material must be selected for RAW_MATERIAL item type.")
        if self.item_type == self.ItemType.PACKAGING_MATERIAL and not self.packaging_material:
            raise ValidationError("Packaging material must be selected for PACKAGING_MATERIAL item type.")
        if self.standard_quantity <= Decimal('0'):
            raise ValidationError("Standard quantity must be strictly greater than zero.")
