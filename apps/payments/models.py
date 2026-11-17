from decimal import Decimal
from django.db import models
from django.conf import settings
from apps.core.models import TimeStampedModel
from apps.masters.models import Customer

class PaymentMethod(models.TextChoices):
    BANK_TRANSFER = 'BANK_TRANSFER', 'Bank Transfer (NEFT / RTGS / IMPS)'
    UPI = 'UPI', 'UPI'
    CHEQUE = 'CHEQUE', 'Cheque'
    CASH = 'CASH', 'Cash'


class Payment(TimeStampedModel):
    payment_reference = models.CharField(max_length=50, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='payments')
    payment_date = models.DateField()
    payment_method = models.CharField(max_length=30, choices=PaymentMethod.choices, default=PaymentMethod.BANK_TRANSFER)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_reference = models.CharField(max_length=100, blank=True, help_text="UTR / Cheque No / UPI Reference")
    notes = models.TextField(blank=True)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='received_payments')

    class Meta:
        verbose_name = 'Customer Payment'
        verbose_name_plural = 'Customer Payments'
        ordering = ['-payment_date', '-id']

    def __str__(self):
        return f"{self.payment_reference} - {self.customer.name} (₹{self.amount})"


class PaymentAllocation(TimeStampedModel):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='allocations')
    invoice = models.ForeignKey('billing.Invoice', on_delete=models.PROTECT, related_name='payment_allocations')
    allocated_amount = models.DecimalField(max_digits=12, decimal_places=2)
    allocation_date = models.DateField()

    class Meta:
        verbose_name = 'Payment Allocation'
        verbose_name_plural = 'Payment Allocations'

    def __str__(self):
        return f"Allocated ₹{self.allocated_amount} to {self.invoice.invoice_number}"
