from decimal import Decimal
from django.db import models
from apps.core.models import TimeStampedModel

class UnitOfMeasurement(TimeStampedModel):
    class Dimension(models.TextChoices):
        MASS = 'MASS', 'Mass'
        VOLUME = 'VOLUME', 'Volume'
        DISCRETE = 'DISCRETE', 'Discrete'

    code = models.CharField(max_length=20, unique=True, help_text="e.g. kg, g, litre, ml, pieces, packets, cartons")
    name = models.CharField(max_length=50)
    dimension = models.CharField(max_length=20, choices=Dimension.choices, default=Dimension.DISCRETE)

    class Meta:
        verbose_name = 'Unit of Measurement'
        verbose_name_plural = 'Units of Measurement'
        ordering = ['code']

    def __str__(self):
        return f"{self.name} ({self.code})"


class Category(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Product Category'
        verbose_name_plural = 'Product Categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(TimeStampedModel):
    product_code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    pack_size = models.CharField(max_length=50, help_text="e.g. 200 g, 500 g, 1 kg")
    uom = models.ForeignKey(UnitOfMeasurement, on_delete=models.PROTECT, related_name='products', help_text="Default packaging unit (e.g. packets)")
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, help_text="Standard selling price per packet before tax")
    opening_stock = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal('0.000'), help_text="Opening finished goods stock in packets")
    current_stock = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal('0.000'), help_text="Current finished goods stock in packets")
    hsn_code = models.CharField(max_length=20, default='1905', help_text="GST HSN code")
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('5.00'), help_text="GST Percentage (e.g. 5.00 for 5%)")
    packets_per_carton = models.PositiveIntegerField(default=20, help_text="Packets per outer shipping carton")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Product'
        verbose_name_plural = 'Products'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.pack_size})"


class Customer(TimeStampedModel):
    class CustomerType(models.TextChoices):
        RETAILER = 'RETAILER', 'Retailer'
        DISTRIBUTOR = 'DISTRIBUTOR', 'Distributor'

    customer_code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    customer_type = models.CharField(max_length=20, choices=CustomerType.choices, default=CustomerType.RETAILER)
    gstin = models.CharField(max_length=15, blank=True, help_text="15-character GSTIN")
    billing_address = models.TextField()
    state = models.CharField(max_length=100, default='Tamil Nadu')
    state_code = models.CharField(max_length=2, default='33', help_text="2-digit State Code (e.g. 33 for TN, 29 for KA)")
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_customer_type_display()} - {self.state})"

    @property
    def is_interstate(self):
        """Returns True if customer state is outside Tamil Nadu (State Code 33)."""
        return str(self.state_code).strip() != '33'


class Supplier(TimeStampedModel):
    supplier_code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    gstin = models.CharField(max_length=15, blank=True)
    address = models.TextField()
    state = models.CharField(max_length=100, default='Tamil Nadu')
    state_code = models.CharField(max_length=2, default='33')
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Supplier'
        verbose_name_plural = 'Suppliers'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.supplier_code})"


class RawMaterial(TimeStampedModel):
    material_code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    uom = models.ForeignKey(UnitOfMeasurement, on_delete=models.PROTECT, related_name='raw_materials')
    opening_stock = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal('0.000'))
    current_stock = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal('0.000'))
    weighted_average_cost = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0.0000'), help_text="Current weighted average cost per UOM")
    reorder_level = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal('10.000'))
    purchase_rate = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Standard/latest purchase rate")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Raw Material'
        verbose_name_plural = 'Raw Materials'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.uom.code})"

    @property
    def is_low_stock(self):
        return self.current_stock <= self.reorder_level


class PackagingMaterial(TimeStampedModel):
    class PackagingType(models.TextChoices):
        POUCH = 'POUCH', 'Pouch / Primary Container'
        CARTON = 'CARTON', 'Corrugated Box / Carton'
        LABEL = 'LABEL', 'Label'
        OTHER = 'OTHER', 'Other Packaging'

    material_code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    packaging_type = models.CharField(max_length=20, choices=PackagingType.choices, default=PackagingType.POUCH)
    uom = models.ForeignKey(UnitOfMeasurement, on_delete=models.PROTECT, related_name='packaging_materials')
    opening_stock = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal('0.000'))
    current_stock = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal('0.000'))
    purchase_rate = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Cost per unit")
    reorder_level = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal('50.000'))
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Packaging Material'
        verbose_name_plural = 'Packaging Materials'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_packaging_type_display()})"

    @property
    def is_low_stock(self):
        return self.current_stock <= self.reorder_level


class ProductPrice(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='price_rules')
    customer_type = models.CharField(max_length=20, choices=Customer.CustomerType.choices, default=Customer.CustomerType.RETAILER)
    price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = 'Product Price Rule'
        verbose_name_plural = 'Product Price Rules'
        unique_together = ('product', 'customer_type')

    def __str__(self):
        return f"{self.product.name} - {self.customer_type}: ₹{self.price}"
