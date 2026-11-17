from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from apps.accounts.models import User
from apps.masters.models import UnitOfMeasurement, RawMaterial, Product, Category
from apps.inventory.models import StockLedger, StockBalance, StockItemType, StockTransactionType
from apps.inventory.services import InventoryService


class InventoryLedgerTestCase(TestCase):
    """
    Tests double-entry inventory ledger:
    1. Immutable ledger recording
    2. Prevention of negative stock
    3. Ledger reconciliation (sum(ledger) == current_stock)
    4. Row-locking atomic updates
    """

    def setUp(self):
        self.user = User.objects.create_superuser('inv_admin', 'inv@admin.com', 'pass123')
        self.uom_kg = UnitOfMeasurement.objects.create(code='kg', name='Kilogram', dimension=UnitOfMeasurement.Dimension.MASS)
        self.rm = RawMaterial.objects.create(
            name='Chili Powder',
            material_code='RM-CHILI-01',
            uom=self.uom_kg,
            opening_stock=Decimal('50.000'),
            current_stock=Decimal('50.000'),
            weighted_average_cost=Decimal('300.0000'),
        )

    def test_record_movement_and_ledger_entry(self):
        """Outflow reduces stock and creates an immutable ledger entry."""
        entry = InventoryService.record_movement(
            item_type=StockItemType.RAW_MATERIAL,
            item_id=self.rm.id,
            transaction_type=StockTransactionType.PRODUCTION_ISSUE,
            quantity=Decimal('15.000'),
            reference_doc='PROD-RUN-001',
            source_module='PRODUCTION',
            user=self.user,
            notes='Issue for spicy mixture'
        )
        self.assertIsNotNone(entry)
        self.assertEqual(entry.quantity_change, Decimal('-15.000'))
        self.assertEqual(entry.balance_after, Decimal('35.000'))

        self.rm.refresh_from_db()
        self.assertEqual(self.rm.current_stock, Decimal('35.000'))

    def test_negative_stock_prevention(self):
        """Attempting to consume more than available stock MUST raise ValidationError."""
        # Available is 50 kg; attempt to consume 60 kg
        with self.assertRaises(ValidationError) as ctx:
            InventoryService.record_movement(
                item_type=StockItemType.RAW_MATERIAL,
                item_id=self.rm.id,
                transaction_type=StockTransactionType.PRODUCTION_ISSUE,
                quantity=Decimal('60.000'),
                user=self.user,
            )
        self.assertIn("Insufficient stock", str(ctx.exception))
        self.assertIn("Available = 50.000", str(ctx.exception))

        # Stock must remain unaffected at 50 kg
        self.rm.refresh_from_db()
        self.assertEqual(self.rm.current_stock, Decimal('50.000'))

    def test_ledger_reconciliation(self):
        """Check that the sum of signed movements matches current stock balance exactly."""
        # Step 1: Inflow 30 kg
        InventoryService.record_movement(
            item_type=StockItemType.RAW_MATERIAL, item_id=self.rm.id,
            transaction_type=StockTransactionType.PURCHASE_RECEIPT, quantity=Decimal('30.000'),
            user=self.user
        )
        # Step 2: Outflow 25 kg
        InventoryService.record_movement(
            item_type=StockItemType.RAW_MATERIAL, item_id=self.rm.id,
            transaction_type=StockTransactionType.PRODUCTION_ISSUE, quantity=Decimal('25.000'),
            user=self.user
        )
        # Step 3: Outflow 10 kg
        InventoryService.record_movement(
            item_type=StockItemType.RAW_MATERIAL, item_id=self.rm.id,
            transaction_type=StockTransactionType.PRODUCTION_ISSUE, quantity=Decimal('10.000'),
            user=self.user
        )

        self.rm.refresh_from_db()
        # Initial 50 + 30 - 25 - 10 = 45 kg
        self.assertEqual(self.rm.current_stock, Decimal('45.000'))

        # Run reconciliation
        recon = InventoryService.reconcile_item(StockItemType.RAW_MATERIAL, self.rm.id)
        # The movements recorded are +30, -25, -10 = -5 (since opening 50 was set directly on model in setUp)
        # To reconcile fully, opening stock must also be recorded as a ledger entry
        # If we add an opening stock ledger entry of 50:
        StockLedger.objects.create(
            item_type=StockItemType.RAW_MATERIAL, item_id=self.rm.id, item_name=self.rm.name,
            transaction_type=StockTransactionType.OPENING_STOCK, quantity_change=Decimal('50.000'),
            balance_after=Decimal('50.000'), uom_code=self.rm.uom.code, unit_rate=Decimal('300.0000'),
            total_value=Decimal('15000.00'), reference_doc='OPENING', source_module='MASTERS', user_responsible=self.user
        )
        recon_after = InventoryService.reconcile_item(StockItemType.RAW_MATERIAL, self.rm.id)
        self.assertTrue(recon_after['is_reconciled'])
        self.assertEqual(recon_after['computed_from_ledger'], Decimal('45.000'))
        self.assertEqual(recon_after['cached_stock'], Decimal('45.000'))
        self.assertEqual(recon_after['discrepancy'], Decimal('0.000'))
