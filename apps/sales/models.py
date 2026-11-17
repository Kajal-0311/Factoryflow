from decimal import Decimal
from django.db import models
from django.conf import settings
from apps.core.models import TimeStampedModel
from apps.masters.models import Customer, Product

class SalesOrderStatus(models.TextChoices):
    SUBMITTED = 'SUBMITTED', 'Submitted'
    UNDER_VERIFICATION = 'UNDER_VERIFICATION', 'Under Verification'
    APPROVED = 'APPROVED', 'Approved'
    REJECTED = 'REJECTED', 'Rejected'
    INVOICED = 'INVOICED', 'Invoiced'
    DISPATCHED = 'DISPATCHED', 'Dispatched'


class SalesOrder(TimeStampedModel):
    order_number = models.CharField(max_length=50, unique=True)
    salesman = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='sales_orders')
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='orders')
    order_date = models.DateField()
    status = models.CharField(max_length=30, choices=SalesOrderStatus.choices, default=SalesOrderStatus.SUBMITTED)
    
    subtotal_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    notes = models.TextField(blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_orders'
    )
    verification_notes = models.TextField(blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Sales Order'
        verbose_name_plural = 'Sales Orders'
        ordering = ['-order_date', '-id']

    def __str__(self):
        return f"{self.order_number} - {self.customer.name} (₹{self.grand_total})"

    @property
    def can_be_approved(self):
        return self.status in (SalesOrderStatus.SUBMITTED, SalesOrderStatus.UNDER_VERIFICATION)

    @property
    def can_be_invoiced(self):
        return self.status == SalesOrderStatus.APPROVED


class SalesOrderItem(TimeStampedModel):
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='order_items')
    quantity = models.DecimalField(max_digits=12, decimal_places=3, help_text="Quantity in packets")
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, help_text="Selling price per packet before tax")
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('5.00'))
    taxable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        verbose_name = 'Sales Order Item'
        verbose_name_plural = 'Sales Order Items'

    def __str__(self):
        return f"{self.product.name} x {self.quantity} pkts @ ₹{self.unit_price}"


class Dispatch(TimeStampedModel):
    dispatch_number = models.CharField(max_length=50, unique=True)
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.PROTECT, related_name='dispatches')
    invoice = models.ForeignKey('billing.Invoice', null=True, blank=True, on_delete=models.SET_NULL, related_name='dispatches')
    dispatch_date = models.DateField()
    transporter_name = models.CharField(max_length=150, blank=True)
    vehicle_number = models.CharField(max_length=50, blank=True)
    lr_number = models.CharField(max_length=50, blank=True, help_text="Lorry Receipt / Consignment Note Number")
    dispatched_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conducted_dispatches'
    )
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Sales Dispatch'
        verbose_name_plural = 'Sales Dispatches'
        ordering = ['-dispatch_date', '-id']

    def __str__(self):
        return f"{self.dispatch_number} for {self.sales_order.order_number}"


class DispatchItem(TimeStampedModel):
    dispatch = models.ForeignKey(Dispatch, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)

    class Meta:
        verbose_name = 'Dispatch Item'
        verbose_name_plural = 'Dispatch Items'

    def __str__(self):
        return f"{self.product.name}: {self.quantity} pkts"

