from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from apps.accounts.models import User
from apps.masters.models import UnitOfMeasurement, Category, Product, RawMaterial, PackagingMaterial
from apps.bom.models import BOM, BOMItem
from apps.bom.services import BOMService
from apps.production.models import ProductionRun, ProductionConsumption, Overhead, CostingRecord
from apps.production.services import ProductionService


class ProductionVarianceTestCase(TestCase):
    """
    Tests production calculations, 3% variance threshold alerts,
    damaged packaging accounting, and dynamic recipe scaling.
    """

    def setUp(self):
        self.user = User.objects.create_user('super_pv', 'pv@factory.com', 'pass123', role=User.Role.PRODUCTION_SUPERVISOR)
        self.uom_kg = UnitOfMeasurement.objects.create(code='kg', name='Kilogram', dimension=UnitOfMeasurement.Dimension.MASS)
        self.uom_l = UnitOfMeasurement.objects.create(code='litre', name='Litre', dimension=UnitOfMeasurement.Dimension.VOLUME)
        self.uom_pcs = UnitOfMeasurement.objects.create(code='pieces', name='Pieces', dimension=UnitOfMeasurement.Dimension.DISCRETE)
        self.uom_pkts = UnitOfMeasurement.objects.create(code='packets', name='Packets', dimension=UnitOfMeasurement.Dimension.DISCRETE)

        self.cat = Category.objects.create(name='Snacks')
        self.product = Product.objects.create(
            name='Mixture 200 g', product_code='PRD-MIX-200G', category=self.cat,
            pack_size='200 g', uom=self.uom_pkts, selling_price=Decimal('60.00'),
            opening_stock=Decimal('0.000'), current_stock=Decimal('0.000'),
            packets_per_carton=20,
        )

        self.rm_flour = RawMaterial.objects.create(
            name='Besan', material_code='RM-BES-01', uom=self.uom_kg,
            opening_stock=Decimal('100.000'), current_stock=Decimal('100.000'),
            weighted_average_cost=Decimal('70.0000'), purchase_rate=Decimal('70.00')
        )
        self.rm_oil = RawMaterial.objects.create(
            name='Refined Oil', material_code='RM-OIL-02', uom=self.uom_l,
            opening_stock=Decimal('100.000'), current_stock=Decimal('100.000'),
            weighted_average_cost=Decimal('120.0000'), purchase_rate=Decimal('120.00')
        )
        self.pm_pouch = PackagingMaterial.objects.create(
            name='Mixture Pouch 200g', material_code='PM-POUCH-MIX', packaging_type=PackagingMaterial.PackagingType.POUCH,
            uom=self.uom_pcs, opening_stock=Decimal('1000.000'), current_stock=Decimal('1000.000'),
            purchase_rate=Decimal('2.00')
        )

        # Standard BOM for 100 pkts
        self.bom = BOM.objects.create(
            product=self.product, bom_code='BOM-MIX-100', batch_size=Decimal('100.000'),
            expected_output=Decimal('100.000'), standard_yield_percent=Decimal('100.00'), is_active=True
        )
        BOMItem.objects.create(bom=self.bom, item_type=BOMItem.ItemType.RAW_MATERIAL, raw_material=self.rm_flour, standard_quantity=Decimal('20.000'), uom=self.uom_kg)
        BOMItem.objects.create(bom=self.bom, item_type=BOMItem.ItemType.RAW_MATERIAL, raw_material=self.rm_oil, standard_quantity=Decimal('5.000'), uom=self.uom_l)
        BOMItem.objects.create(bom=self.bom, item_type=BOMItem.ItemType.PACKAGING_MATERIAL, packaging_material=self.pm_pouch, standard_quantity=Decimal('100.000'), uom=self.uom_pcs)

    def test_dynamic_bom_scaling(self):
        """Scaling BOM requirements dynamically for a 250 packet batch."""
        reqs = BOMService.calculate_requirements(self.bom, Decimal('250.000'))
        # Standard: 100 pkts requires 20 kg besan, 5 L oil, 100 pouches
        # Scaled: 250 pkts requires 50 kg besan, 12.5 L oil, 250 pouches
        all_items = {item['name']: item['planned_quantity'] for item in reqs['raw_materials'] + reqs['packaging_materials']}
        self.assertEqual(all_items['Besan'], Decimal('50.000'))
        self.assertEqual(all_items['Refined Oil'], Decimal('12.500'))
        self.assertEqual(all_items['Mixture Pouch 200g'], Decimal('250.000'))

    def test_variance_threshold_boundary_logic(self):
        """Test the 3% boundary: <= 3% no alert, > 3% alert."""
        # Exact 3.00% -> No alert (must strictly exceed 3%)
        var, alert = ProductionService.calculate_variance(Decimal('103.00'), Decimal('100.00'))
        self.assertEqual(var, Decimal('3.00'))
        self.assertFalse(alert)

        # 3.01% -> Alert True
        var, alert = ProductionService.calculate_variance(Decimal('103.01'), Decimal('100.00'))
        self.assertEqual(var, Decimal('3.01'))
        self.assertTrue(alert)

        # -2.5% -> No alert
        var, alert = ProductionService.calculate_variance(Decimal('97.50'), Decimal('100.00'))
        self.assertEqual(var, Decimal('-2.50'))
        self.assertFalse(alert)

        # -3.1% -> Alert True
        var, alert = ProductionService.calculate_variance(Decimal('96.90'), Decimal('100.00'))
        self.assertEqual(var, Decimal('-3.10'))
        self.assertTrue(alert)

    def test_damaged_packaging_accounting(self):
        """Damaged packaging is deducted from stock and factored into batch cost."""
        consumptions_data = [
            {'item_type': 'RAW_MATERIAL', 'raw_material_id': self.rm_flour.id, 'planned_quantity': '20.000', 'actual_quantity': '20.000'},
            {'item_type': 'RAW_MATERIAL', 'raw_material_id': self.rm_oil.id, 'planned_quantity': '5.000', 'actual_quantity': '5.000'},
            {'item_type': 'PACKAGING_MATERIAL', 'packaging_material_id': self.pm_pouch.id, 'planned_quantity': '100.000', 'actual_quantity': '105.000', 'damaged_quantity': '7.000'},
        ]
        run, costing = ProductionService.execute_production_run(
            product_id=self.product.id,
            batch_quantity=Decimal('100.000'),
            actual_good_output=Decimal('98.000'),
            consumptions_data=consumptions_data,
            production_date=timezone.now().date(),
            supervisor=self.user,
        )

        self.pm_pouch.refresh_from_db()
        # Initial 1000 - 105 consumed = 895
        self.assertEqual(self.pm_pouch.current_stock, Decimal('895.000'))
        
        # Packaging cost includes the damaged pouches: 105 * 2.00 = 210.00
        self.assertEqual(costing.packaging_material_cost, Decimal('210.00'))
        # Good output is 98 pkts
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, Decimal('98.000'))
