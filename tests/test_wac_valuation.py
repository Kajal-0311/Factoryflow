from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from apps.accounts.models import User
from apps.masters.models import UnitOfMeasurement, RawMaterial, Supplier
from apps.purchases.models import Purchase, PurchaseItem
from apps.purchases.services import PurchaseService
from apps.inventory.models import StockLedger, StockTransactionType, StockItemType


class WeightedAverageCostTestCase(TestCase):
    """
    Unit and integration tests for Weighted Average Cost (WAC) formula:
    New WAC = (Existing Stock * Old WAC + Inward Qty * Purchase Rate) / (Existing Stock + Inward Qty)
    """

    def setUp(self):
        self.user = User.objects.create_superuser('admin_wac', 'admin@wac.com', 'pass123')
        self.uom_kg = UnitOfMeasurement.objects.create(code='kg', name='Kilogram', dimension=UnitOfMeasurement.Dimension.MASS)
        self.supplier = Supplier.objects.create(
            name='TN Agri Mill', supplier_code='SUP-WAC-01', state='Tamil Nadu', state_code='33',
            address='Madurai Main Road', phone='+91 94432 00000'
        )
        self.raw_material = RawMaterial.objects.create(
            name='Gram Flour',
            material_code='RM-GF-01',
            uom=self.uom_kg,
            opening_stock=Decimal('100.000'),
            current_stock=Decimal('100.000'),
            weighted_average_cost=Decimal('42.0000'),
            purchase_rate=Decimal('42.00'),
        )

    def test_single_inward_wac_recalculation(self):
        """Inward of 60 kg @ Rs. 45/kg increases WAC to Rs. 43.1250/kg."""
        purchase = Purchase.objects.create(
            purchase_number='PUR-WAC-001',
            supplier=self.supplier,
            purchase_date=timezone.now().date(),
            taxable_amount=Decimal('2700.00'),
            gst_amount=Decimal('135.00'),
            total_amount=Decimal('2835.00'),
            created_by=self.user,
        )
        PurchaseItem.objects.create(
            purchase=purchase,
            item_type=PurchaseItem.ItemType.RAW_MATERIAL,
            raw_material=self.raw_material,
            quantity=Decimal('60.000'),
            uom=self.uom_kg,
            purchase_rate=Decimal('45.0000'),
            gst_rate=Decimal('5.00'),
            taxable_amount=Decimal('2700.00'),
            gst_amount=Decimal('135.00'),
            total_amount=Decimal('2835.00'),
        )
        PurchaseService.confirm_purchase(purchase.id, user=self.user)

        self.raw_material.refresh_from_db()
        self.assertEqual(self.raw_material.current_stock, Decimal('160.000'))
        # Total cost = (100 * 42) + (60 * 45) = 4200 + 2700 = 6900
        # WAC = 6900 / 160 = 43.1250
        self.assertEqual(self.raw_material.weighted_average_cost, Decimal('43.1250'))

    def test_successive_inwards_wac_progression(self):
        """Test multiple successive purchases at varying rates."""
        # Inward 1: 50 kg @ Rs. 50/kg
        # Current: 100 kg @ 42 = 4200. Inward: 50 kg @ 50 = 2500. Total = 6700 / 150 = 44.6667
        pur1 = Purchase.objects.create(
            purchase_number='PUR-WAC-002', supplier=self.supplier,
            purchase_date=timezone.now().date(), created_by=self.user
        )
        PurchaseItem.objects.create(
            purchase=pur1, item_type=PurchaseItem.ItemType.RAW_MATERIAL,
            raw_material=self.raw_material, quantity=Decimal('50.000'),
            uom=self.uom_kg, purchase_rate=Decimal('50.0000')
        )
        PurchaseService.confirm_purchase(pur1.id, user=self.user)
        self.raw_material.refresh_from_db()
        self.assertEqual(self.raw_material.current_stock, Decimal('150.000'))
        self.assertEqual(self.raw_material.weighted_average_cost, Decimal('44.6667'))

        # Inward 2: 50 kg @ Rs. 40/kg (price drop)
        # Previous: 150 kg @ 44.6667 = 6700. Inward: 50 kg @ 40 = 2000. Total = 8700 / 200 = 43.5000
        pur2 = Purchase.objects.create(
            purchase_number='PUR-WAC-003', supplier=self.supplier,
            purchase_date=timezone.now().date(), created_by=self.user
        )
        PurchaseItem.objects.create(
            purchase=pur2, item_type=PurchaseItem.ItemType.RAW_MATERIAL,
            raw_material=self.raw_material, quantity=Decimal('50.000'),
            uom=self.uom_kg, purchase_rate=Decimal('40.0000')
        )
        PurchaseService.confirm_purchase(pur2.id, user=self.user)
        self.raw_material.refresh_from_db()
        self.assertEqual(self.raw_material.current_stock, Decimal('200.000'))
        self.assertEqual(self.raw_material.weighted_average_cost, Decimal('43.5000'))

    def test_zero_opening_stock_inward(self):
        """When initial stock is zero, WAC equals the purchase rate."""
        new_rm = RawMaterial.objects.create(
            name='Sesame Seeds',
            material_code='RM-SES-01',
            uom=self.uom_kg,
            opening_stock=Decimal('0.000'),
            current_stock=Decimal('0.000'),
            weighted_average_cost=Decimal('0.0000'),
            purchase_rate=Decimal('0.00'),
        )
        pur = Purchase.objects.create(
            purchase_number='PUR-WAC-004', supplier=self.supplier,
            purchase_date=timezone.now().date(), created_by=self.user
        )
        PurchaseItem.objects.create(
            purchase=pur, item_type=PurchaseItem.ItemType.RAW_MATERIAL,
            raw_material=new_rm, quantity=Decimal('25.000'),
            uom=self.uom_kg, purchase_rate=Decimal('180.0000')
        )
        PurchaseService.confirm_purchase(pur.id, user=self.user)
        new_rm.refresh_from_db()
        self.assertEqual(new_rm.current_stock, Decimal('25.000'))
        self.assertEqual(new_rm.weighted_average_cost, Decimal('180.0000'))
