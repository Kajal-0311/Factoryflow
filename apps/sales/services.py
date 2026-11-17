from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.sales.models import SalesOrder, SalesOrderItem, SalesOrderStatus
from apps.masters.models import Customer, Product, ProductPrice
from apps.inventory.services import InventoryService
from apps.inventory.models import StockItemType, StockTransactionType

class SalesOrderService:
    """Service handling sales order creation, stock verification, and approval."""

    @classmethod
    def get_applicable_price(cls, product, customer):
        """Fetch applicable selling price based on customer-specific price rules or base product price."""
        try:
            rule = ProductPrice.objects.get(product=product, customer_type=customer.customer_type)
            return rule.price
        except ProductPrice.DoesNotExist:
            return product.selling_price

    @classmethod
    @transaction.atomic
    def create_order(cls, customer_id, salesman, items_data, order_date=None, notes=''):
        """Create a new sales order with line items."""
        customer = Customer.objects.get(pk=customer_id)
        if not order_date:
            order_date = timezone.now().date()

        order_count = SalesOrder.objects.count() + 1
        order_number = f"SO-{order_date.strftime('%Y%m')}-{order_count:04d}"

        sales_order = SalesOrder.objects.create(
            order_number=order_number,
            salesman=salesman,
            customer=customer,
            order_date=order_date,
            status=SalesOrderStatus.SUBMITTED,
            notes=notes
        )

        subtotal = Decimal('0.00')
        tax_total = Decimal('0.00')

        for item_data in items_data:
            product = Product.objects.get(pk=item_data['product_id'])
            qty = Decimal(str(item_data['quantity'])).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
            
            # Fetch applicable price or use provided price
            if 'unit_price' in item_data and item_data['unit_price']:
                unit_price = Decimal(str(item_data['unit_price'])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            else:
                unit_price = cls.get_applicable_price(product, customer)

            taxable = (qty * unit_price).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            gst_rate = product.gst_rate
            tax_amount = (taxable * (gst_rate / Decimal('100.0'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            line_total = taxable + tax_amount

            SalesOrderItem.objects.create(
                sales_order=sales_order,
                product=product,
                quantity=qty,
                unit_price=unit_price,
                gst_rate=gst_rate,
                taxable_amount=taxable,
                tax_amount=tax_amount,
                line_total=line_total
            )

            subtotal += taxable
            tax_total += tax_amount

        sales_order.subtotal_amount = subtotal
        sales_order.tax_amount = tax_total
        sales_order.grand_total = subtotal + tax_total
        sales_order.save(update_fields=['subtotal_amount', 'tax_amount', 'grand_total'])

        return sales_order

    @classmethod
    def check_stock_availability(cls, sales_order):
        """
        Check finished goods inventory against ordered quantities.
        Identifies any shortages before approval or dispatch.
        """
        items_analysis = []
        overall_shortage = False
        total_shortage_qty = Decimal('0.000')

        for item in sales_order.items.select_related('product').all():
            available_stock = InventoryService.get_stock(StockItemType.FINISHED_GOODS, item.product.id)
            required_qty = item.quantity
            shortage = max(Decimal('0.000'), required_qty - available_stock)

            if shortage > Decimal('0.000'):
                overall_shortage = True
                total_shortage_qty += shortage

            items_analysis.append({
                'item_id': item.id,
                'product_name': item.product.name,
                'required_quantity': required_qty,
                'available_stock': available_stock,
                'shortage_quantity': shortage,
                'is_sufficient': shortage == Decimal('0.000'),
            })

        return {
            'sales_order_id': sales_order.id,
            'order_number': sales_order.order_number,
            'has_shortage': overall_shortage,
            'total_shortage_quantity': total_shortage_qty,
            'items': items_analysis,
        }

    @classmethod
    @transaction.atomic
    def approve_order(cls, sales_order_id, admin_user, modified_items=None, verification_notes=''):
        """Approve sales order, optionally modifying quantities/prices."""
        order = SalesOrder.objects.select_for_update().get(pk=sales_order_id)
        if not order.can_be_approved:
            raise ValidationError(f"Order {order.order_number} cannot be approved in status {order.status}")

        if modified_items:
            subtotal = Decimal('0.00')
            tax_total = Decimal('0.00')

            for mod in modified_items:
                item = order.items.get(pk=mod['item_id'])
                if 'quantity' in mod:
                    item.quantity = Decimal(str(mod['quantity'])).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
                if 'unit_price' in mod:
                    item.unit_price = Decimal(str(mod['unit_price'])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

                taxable = (item.quantity * item.unit_price).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                tax_amount = (taxable * (item.gst_rate / Decimal('100.0'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                item.taxable_amount = taxable
                item.tax_amount = tax_amount
                item.line_total = taxable + tax_amount
                item.save()

                subtotal += taxable
                tax_total += tax_amount

            order.subtotal_amount = subtotal
            order.tax_amount = tax_total
            order.grand_total = subtotal + tax_total

        order.status = SalesOrderStatus.APPROVED
        order.verified_by = admin_user
        order.verification_notes = verification_notes
        order.approved_at = timezone.now()
        order.save()

        return order

    @classmethod
    @transaction.atomic
    def reject_order(cls, sales_order_id, admin_user, reason=''):
        """Reject sales order."""
        order = SalesOrder.objects.select_for_update().get(pk=sales_order_id)
        order.status = SalesOrderStatus.REJECTED
        order.verified_by = admin_user
        order.verification_notes = reason
        order.save(update_fields=['status', 'verified_by', 'verification_notes', 'updated_at'])
        return order


class DispatchService:
    """Service handling stock validation and sales order dispatch."""

    @classmethod
    @transaction.atomic
    def record_dispatch(cls, sales_order_id, invoice_id=None, user=None,
                        dispatch_date=None, transporter_name='', vehicle_number='',
                        lr_number='', notes=''):
        from apps.sales.models import Dispatch, DispatchItem
        from apps.billing.models import Invoice
        
        order = SalesOrder.objects.select_for_update().get(pk=sales_order_id)
        if order.status == SalesOrderStatus.DISPATCHED:
            raise ValidationError(f"Order {order.order_number} has already been dispatched.")

        if not dispatch_date:
            dispatch_date = timezone.now().date()

        # Check stock availability for all items
        availability = SalesOrderService.check_stock_availability(order)
        if availability['has_shortage']:
            shortage_details = "; ".join([
                f"{item['product_name']}: shortage of {item['shortage_quantity']} pkts (available: {item['available_stock']}, required: {item['required_quantity']})"
                for item in availability['items'] if not item['is_sufficient']
            ])
            raise ValidationError(f"Dispatch blocked due to insufficient stock: {shortage_details}")

        dispatch_count = Dispatch.objects.count() + 1
        dispatch_number = f"DSP-{dispatch_date.strftime('%Y%m')}-{dispatch_count:04d}"

        invoice = None
        if invoice_id:
            invoice = Invoice.objects.get(pk=invoice_id)
        elif order.invoices.exists():
            invoice = order.invoices.first()

        dispatch = Dispatch.objects.create(
            dispatch_number=dispatch_number,
            sales_order=order,
            invoice=invoice,
            dispatch_date=dispatch_date,
            transporter_name=transporter_name,
            vehicle_number=vehicle_number,
            lr_number=lr_number,
            dispatched_by=user,
            notes=notes
        )

        for item in order.items.all():
            qty = item.quantity
            product = item.product

            # Reduce finished goods inventory atomically via InventoryService
            InventoryService.record_movement(
                item_type=StockItemType.FINISHED_GOODS,
                item_id=product.id,
                transaction_type=StockTransactionType.SALES_DISPATCH,
                quantity=qty,
                unit_rate=product.selling_price,
                reference_doc=dispatch_number,
                source_module='SALES_DISPATCH',
                user=user,
                notes=f"Dispatched for Order {order.order_number} to {order.customer.name}"
            )

            DispatchItem.objects.create(
                dispatch=dispatch,
                product=product,
                quantity=qty
            )

        order.status = SalesOrderStatus.DISPATCHED
        order.save(update_fields=['status', 'updated_at'])

        if invoice:
            invoice.is_dispatched = True
            invoice.save(update_fields=['is_dispatched', 'updated_at'])

        return dispatch

