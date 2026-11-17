from decimal import Decimal
from django.db import models
from django.conf import settings
from apps.core.models import TimeStampedModel
from apps.masters.models import Supplier, RawMaterial, PackagingMaterial, UnitOfMeasurement

class PurchaseStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    CONFIRMED = 'CONFIRMED', 'Confirmed & Received'
    CANCELLED = 'CANCELLED', 'Cancelled'


class Purchase(TimeStampedModel):
    purchase_number = models.CharField(max_length=50, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='purchases')
    supplier_invoice_ref = models.CharField(max_length=100, blank=True, help_text="Supplier's Invoice / Challan Number")
    purchase_date = models.DateField()
    status = models.CharField(max_length=20, choices=PurchaseStatus.choices, default=PurchaseStatus.DRAFT)
    
    taxable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    gst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_purchases')
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='confirmed_purchases')
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Purchase Order / Inward'
        verbose_name_plural = 'Purchases'
        ordering = ['-purchase_date', '-id']

    def __str__(self):
        return f"{self.purchase_number} - {self.supplier.name} (₹{self.total_amount})"


class PurchaseItem(TimeStampedModel):
    class ItemType(models.TextChoices):
        RAW_MATERIAL = 'RAW_MATERIAL', 'Raw Material'
        PACKAGING_MATERIAL = 'PACKAGING_MATERIAL', 'Packaging Material'

    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='items')
    item_type = models.CharField(max_length=30, choices=ItemType.choices)
    raw_material = models.ForeignKey(RawMaterial, null=True, blank=True, on_delete=models.PROTECT, related_name='purchases')
    packaging_material = models.ForeignKey(PackagingMaterial, null=True, blank=True, on_delete=models.PROTECT, related_name='purchases')
    
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    uom = models.ForeignKey(UnitOfMeasurement, on_delete=models.PROTECT)
    purchase_rate = models.DecimalField(max_digits=12, decimal_places=4, help_text="Rate per UOM before tax")
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('5.00'))
    
    taxable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    gst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        verbose_name = 'Purchase Item'
        verbose_name_plural = 'Purchase Items'

    def __str__(self):
        name = self.raw_material.name if self.item_type == self.ItemType.RAW_MATERIAL else self.packaging_material.name
        return f"{name}: {self.quantity} {self.uom.code} @ ₹{self.purchase_rate}"
