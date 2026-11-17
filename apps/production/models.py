from decimal import Decimal
from django.db import models
from django.conf import settings
from apps.core.models import TimeStampedModel
from apps.masters.models import Product, RawMaterial, PackagingMaterial
from apps.bom.models import BOM

class ProductionRunStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    COMPLETED = 'COMPLETED', 'Completed & Stock Posted'
    CANCELLED = 'CANCELLED', 'Cancelled'


class ProductionRun(TimeStampedModel):
    run_number = models.CharField(max_length=50, unique=True)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='production_runs')
    bom = models.ForeignKey(BOM, on_delete=models.PROTECT, related_name='production_runs')
    
    batch_quantity = models.DecimalField(
        max_digits=12, decimal_places=3,
        help_text="Target batch quantity in finished packets (e.g. 200)"
    )
    expected_output = models.DecimalField(
        max_digits=12, decimal_places=3,
        help_text="Expected good output in packets"
    )
    actual_good_output = models.DecimalField(
        max_digits=12, decimal_places=3,
        help_text="Actual good packets produced"
    )
    wastage_quantity = models.DecimalField(
        max_digits=12, decimal_places=3, default=Decimal('0.000'),
        help_text="Rejected / scrap packets or physical loss"
    )
    
    yield_variance_percent = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('0.00'),
        help_text="((Actual Output - Expected Output) / Expected Output) * 100"
    )
    yield_alert = models.BooleanField(
        default=False,
        help_text="True if absolute yield variance exceeds 3%"
    )
    
    status = models.CharField(max_length=20, choices=ProductionRunStatus.choices, default=ProductionRunStatus.DRAFT)
    production_date = models.DateField()
    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='supervised_runs'
    )
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Production Run'
        verbose_name_plural = 'Production Runs'
        ordering = ['-production_date', '-id']

    def __str__(self):
        return f"{self.run_number} - {self.product.name} ({self.actual_good_output} pkts)"


class ProductionConsumption(TimeStampedModel):
    class ItemType(models.TextChoices):
        RAW_MATERIAL = 'RAW_MATERIAL', 'Raw Material'
        PACKAGING_MATERIAL = 'PACKAGING_MATERIAL', 'Packaging Material'

    production_run = models.ForeignKey(ProductionRun, on_delete=models.CASCADE, related_name='consumptions')
    item_type = models.CharField(max_length=30, choices=ItemType.choices)
    raw_material = models.ForeignKey(RawMaterial, null=True, blank=True, on_delete=models.PROTECT)
    packaging_material = models.ForeignKey(PackagingMaterial, null=True, blank=True, on_delete=models.PROTECT)
    
    item_name = models.CharField(max_length=200)
    uom_code = models.CharField(max_length=20)
    
    planned_quantity = models.DecimalField(max_digits=12, decimal_places=3)
    actual_quantity = models.DecimalField(max_digits=12, decimal_places=3, help_text="Total physical units consumed")
    damaged_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal('0.000'), help_text="Damaged or scrap packaging")
    
    variance_percent = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'))
    variance_alert = models.BooleanField(default=False, help_text="True if absolute variance exceeds 3%")
    
    unit_rate = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0.0000'))
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        verbose_name = 'Production Consumption'
        verbose_name_plural = 'Production Consumptions'

    def __str__(self):
        return f"{self.item_name}: Act {self.actual_quantity} / Plan {self.planned_quantity} {self.uom_code}"


class Overhead(TimeStampedModel):
    class OverheadType(models.TextChoices):
        LABOUR = 'LABOUR', 'Direct Labour'
        POWER_GAS = 'POWER_GAS', 'Gas & Electricity'
        MAINTENANCE = 'MAINTENANCE', 'Factory Maintenance'
        OTHER = 'OTHER', 'Other Overheads'

    production_run = models.ForeignKey(ProductionRun, on_delete=models.CASCADE, related_name='overheads')
    overhead_type = models.CharField(max_length=30, choices=OverheadType.choices)
    description = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = 'Production Overhead'
        verbose_name_plural = 'Production Overheads'

    def __str__(self):
        return f"{self.get_overhead_type_display()}: ₹{self.amount}"


class CostingRecord(TimeStampedModel):
    production_run = models.OneToOneField(ProductionRun, on_delete=models.CASCADE, related_name='costing')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='costing_records')
    
    raw_material_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    packaging_material_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    labour_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    power_and_gas_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    other_overheads_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    total_production_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    cost_per_packet = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0.0000'))
    selling_price_per_packet = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    gross_margin_per_packet = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0.0000'))
    gross_margin_percent = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        verbose_name = 'Costing Record'
        verbose_name_plural = 'Costing Records'

    def __str__(self):
        return f"{self.production_run.run_number} Costing: ₹{self.cost_per_packet}/pkt (Margin: ₹{self.gross_margin_per_packet})"
