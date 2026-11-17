from django.test import TestCase, Client
from django.urls import reverse
from apps.accounts.models import User


class RBACPermissionsTestCase(TestCase):
    """
    Role-Based Access Control (RBAC) tests:
    - Admin: Full system access across all modules
    - Salesman: Field order entry only; restricted from production execution & order approval
    - Production Supervisor: Recipe & batch entry; restricted from financial approval & billing
    - Owner / Auditor: Read-only ledger audit access; restricted from operational mutations
    """

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser('admin_rbac', 'admin@rbac.com', 'pass123')
        self.salesman = User.objects.create_user('salesman_rbac', 'sales@rbac.com', 'pass123', role=User.Role.SALESMAN)
        self.supervisor = User.objects.create_user('super_rbac', 'super@rbac.com', 'pass123', role=User.Role.PRODUCTION_SUPERVISOR)
        self.auditor = User.objects.create_user('audit_rbac', 'audit@rbac.com', 'pass123', role=User.Role.OWNER_AUDITOR)

    def test_salesman_blocked_from_production_execution(self):
        """Salesman attempting to access production run creation receives 403 Forbidden."""
        self.client.force_login(self.salesman)
        response = self.client.get(reverse('production:create_run'))
        self.assertEqual(response.status_code, 403)

    def test_supervisor_blocked_from_sales_approval(self):
        """Production supervisor attempting to approve sales orders receives 403 Forbidden."""
        self.client.force_login(self.supervisor)
        # Using a dummy PK 999 - the decorator runs before object lookup
        response = self.client.post(reverse('sales:approve_order', kwargs={'pk': 999}))
        self.assertEqual(response.status_code, 403)

    def test_auditor_blocked_from_production_and_sales_approval(self):
        """Auditor attempting mutation actions receives 403 Forbidden."""
        self.client.force_login(self.auditor)
        res_prod = self.client.get(reverse('production:create_run'))
        self.assertEqual(res_prod.status_code, 403)

        res_appr = self.client.post(reverse('sales:approve_order', kwargs={'pk': 999}))
        self.assertEqual(res_appr.status_code, 403)

    def test_admin_has_full_access(self):
        """Admin has permission to access production create and dashboard."""
        self.client.force_login(self.admin)
        res_dashboard = self.client.get(reverse('dashboard'))
        self.assertEqual(res_dashboard.status_code, 200)

        res_prod = self.client.get(reverse('production:create_run'))
        self.assertEqual(res_prod.status_code, 200)

        res_orders = self.client.get(reverse('sales:order_list'))
        self.assertEqual(res_orders.status_code, 200)
