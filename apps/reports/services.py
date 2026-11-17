import csv
import io
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Count, Avg, F, Q
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from apps.billing.models import Invoice, InvoiceItem, InvoiceStatus
from apps.sales.models import SalesOrder, SalesOrderItem
from apps.purchases.models import Purchase, PurchaseItem, PurchaseStatus
from apps.inventory.models import StockLedger, StockBalance, StockItemType
from apps.masters.models import RawMaterial, PackagingMaterial, Product, Customer, Supplier
from apps.production.models import ProductionRun, ProductionConsumption, CostingRecord
from apps.payments.models import Payment, PaymentAllocation
from apps.payments.services import PaymentService

class ReportEngine:
    """Core reporting engine generating all 16 business and audit reports."""

    @classmethod
    def get_sales_register(cls, start_date=None, end_date=None, customer_id=None):
        qs = Invoice.objects.filter(status=InvoiceStatus.POSTED).select_related('customer')
        if start_date:
            qs = qs.filter(invoice_date__gte=start_date)
        if end_date:
            qs = qs.filter(invoice_date__lte=end_date)
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        return qs.order_by('-invoice_date', '-id')

    @classmethod
    def get_customer_wise_sales(cls, start_date=None, end_date=None):
        qs = Invoice.objects.filter(status=InvoiceStatus.POSTED)
        if start_date:
            qs = qs.filter(invoice_date__gte=start_date)
        if end_date:
            qs = qs.filter(invoice_date__lte=end_date)

        return qs.values('customer__id', 'customer__name', 'customer__customer_type', 'customer__state').annotate(
            invoice_count=Count('id'),
            total_taxable=Sum('taxable_amount'),
            total_tax=Sum('total_tax'),
            total_sales=Sum('grand_total'),
            total_outstanding=Sum('outstanding_amount')
        ).order_by('-total_sales')

    @classmethod
    def get_product_wise_sales(cls, start_date=None, end_date=None):
        qs = InvoiceItem.objects.filter(invoice__status=InvoiceStatus.POSTED)
        if start_date:
            qs = qs.filter(invoice__invoice_date__gte=start_date)
        if end_date:
            qs = qs.filter(invoice__invoice_date__lte=end_date)

        return qs.values('product__id', 'product__name', 'product__pack_size').annotate(
            total_quantity=Sum('quantity'),
            total_taxable=Sum('taxable_amount'),
            total_amount=Sum('total_amount'),
            avg_price=Avg('unit_price')
        ).order_by('-total_amount')

    @classmethod
    def get_gst_outward_summary(cls, start_date=None, end_date=None):
        """Prototype reconciliation report structured for GSTR-1 and GSTR-3B."""
        qs = Invoice.objects.filter(status=InvoiceStatus.POSTED)
        if start_date:
            qs = qs.filter(invoice_date__gte=start_date)
        if end_date:
            qs = qs.filter(invoice_date__lte=end_date)

        b2b = qs.filter(customer__gstin__gt='').aggregate(
            taxable=Sum('taxable_amount') or Decimal('0.00'),
            cgst=Sum('cgst_amount') or Decimal('0.00'),
            sgst=Sum('sgst_amount') or Decimal('0.00'),
            igst=Sum('igst_amount') or Decimal('0.00'),
            total=Sum('grand_total') or Decimal('0.00'),
            count=Count('id')
        )
        b2c = qs.filter(Q(customer__gstin='') | Q(customer__gstin__isnull=True)).aggregate(
            taxable=Sum('taxable_amount') or Decimal('0.00'),
            cgst=Sum('cgst_amount') or Decimal('0.00'),
            sgst=Sum('sgst_amount') or Decimal('0.00'),
            igst=Sum('igst_amount') or Decimal('0.00'),
            total=Sum('grand_total') or Decimal('0.00'),
            count=Count('id')
        )

        overall = qs.aggregate(
            taxable=Sum('taxable_amount') or Decimal('0.00'),
            cgst=Sum('cgst_amount') or Decimal('0.00'),
            sgst=Sum('sgst_amount') or Decimal('0.00'),
            igst=Sum('igst_amount') or Decimal('0.00'),
            total_tax=Sum('total_tax') or Decimal('0.00'),
            grand_total=Sum('grand_total') or Decimal('0.00'),
            count=Count('id')
        )

        return {
            'b2b': b2b,
            'b2c': b2c,
            'overall': overall,
            'is_prototype': True,
        }

    @classmethod
    def get_purchase_register(cls, start_date=None, end_date=None, supplier_id=None):
        qs = Purchase.objects.filter(status=PurchaseStatus.CONFIRMED).select_related('supplier')
        if start_date:
            qs = qs.filter(purchase_date__gte=start_date)
        if end_date:
            qs = qs.filter(purchase_date__lte=end_date)
        if supplier_id:
            qs = qs.filter(supplier_id=supplier_id)
        return qs.order_by('-purchase_date', '-id')

    @classmethod
    def get_raw_material_stock(cls):
        materials = RawMaterial.objects.select_related('uom').filter(is_active=True).order_by('name')
        data = []
        total_valuation = Decimal('0.00')
        for rm in materials:
            val = (rm.current_stock * rm.weighted_average_cost).quantize(Decimal('0.01'))
            total_valuation += val
            data.append({
                'material': rm,
                'valuation': val,
                'is_low_stock': rm.is_low_stock,
            })
        return {'items': data, 'total_valuation': total_valuation}

    @classmethod
    def get_packaging_stock(cls):
        pkgs = PackagingMaterial.objects.select_related('uom').filter(is_active=True).order_by('packaging_type', 'name')
        data = []
        total_valuation = Decimal('0.00')
        for pm in pkgs:
            val = (pm.current_stock * pm.purchase_rate).quantize(Decimal('0.01'))
            total_valuation += val
            data.append({
                'material': pm,
                'valuation': val,
                'is_low_stock': pm.is_low_stock,
            })
        return {'items': data, 'total_valuation': total_valuation}

    @classmethod
    def get_finished_goods_stock(cls):
        products = Product.objects.select_related('category', 'uom').filter(is_active=True).order_by('name')
        data = []
        total_valuation = Decimal('0.00')
        for p in products:
            val = (p.current_stock * p.selling_price).quantize(Decimal('0.01'))
            total_valuation += val
            data.append({
                'product': p,
                'valuation': val,
            })
        return {'items': data, 'total_valuation': total_valuation}

    @classmethod
    def get_stock_ledger(cls, item_type=None, item_id=None, start_date=None, end_date=None):
        qs = StockLedger.objects.all()
        if item_type:
            qs = qs.filter(item_type=item_type)
        if item_id:
            qs = qs.filter(item_id=item_id)
        if start_date:
            qs = qs.filter(created_at__date__gte=start_date)
        if end_date:
            qs = qs.filter(created_at__date__lte=end_date)
        return qs.order_by('-created_at', '-id')

    @classmethod
    def get_production_report(cls, start_date=None, end_date=None, product_id=None):
        qs = ProductionRun.objects.select_related('product', 'bom', 'supervisor')
        if start_date:
            qs = qs.filter(production_date__gte=start_date)
        if end_date:
            qs = qs.filter(production_date__lte=end_date)
        if product_id:
            qs = qs.filter(product_id=product_id)
        return qs.order_by('-production_date', '-id')

    @classmethod
    def get_consumption_report(cls, start_date=None, end_date=None):
        qs = ProductionConsumption.objects.select_related('production_run', 'raw_material', 'packaging_material')
        if start_date:
            qs = qs.filter(production_run__production_date__gte=start_date)
        if end_date:
            qs = qs.filter(production_run__production_date__lte=end_date)
        return qs.order_by('-production_run__production_date', '-id')

    @classmethod
    def get_yield_wastage_report(cls, start_date=None, end_date=None):
        qs = ProductionRun.objects.select_related('product')
        if start_date:
            qs = qs.filter(production_date__gte=start_date)
        if end_date:
            qs = qs.filter(production_date__lte=end_date)
        return qs.order_by('-production_date', '-id')

    @classmethod
    def get_costing_report(cls, start_date=None, end_date=None, product_id=None):
        qs = CostingRecord.objects.select_related('production_run__product')
        if start_date:
            qs = qs.filter(production_run__production_date__gte=start_date)
        if end_date:
            qs = qs.filter(production_run__production_date__lte=end_date)
        if product_id:
            qs = qs.filter(product_id=product_id)
        return qs.order_by('-production_run__production_date', '-id')

    @classmethod
    def get_collections_report(cls, start_date=None, end_date=None, customer_id=None):
        qs = PaymentAllocation.objects.select_related('payment__customer', 'invoice')
        if start_date:
            qs = qs.filter(payment__payment_date__gte=start_date)
        if end_date:
            qs = qs.filter(payment__payment_date__lte=end_date)
        if customer_id:
            qs = qs.filter(payment__customer_id=customer_id)
        return qs.order_by('-payment__payment_date', '-id')

    @classmethod
    def get_outstanding_receivables(cls):
        customers = Customer.objects.filter(is_active=True).order_by('name')
        data = []
        total_billed_all = Decimal('0.00')
        total_paid_all = Decimal('0.00')
        total_outstanding_all = Decimal('0.00')

        for c in customers:
            invs = c.invoices.filter(status=InvoiceStatus.POSTED)
            billed = sum(inv.grand_total for inv in invs)
            paid = sum(inv.paid_amount for inv in invs)
            outstanding = sum(inv.outstanding_amount for inv in invs)

            if billed > Decimal('0.00') or outstanding > Decimal('0.00'):
                total_billed_all += billed
                total_paid_all += paid
                total_outstanding_all += outstanding
                data.append({
                    'customer': c,
                    'total_billed': billed,
                    'total_paid': paid,
                    'outstanding': outstanding,
                    'credit_limit': c.credit_limit,
                })

        return {
            'customers': data,
            'total_billed': total_billed_all,
            'total_paid': total_paid_all,
            'total_outstanding': total_outstanding_all,
        }

    @classmethod
    def get_receivables_ageing(cls, as_of_date=None):
        return PaymentService.get_receivables_ageing(as_of_date)


class ReportExporter:
    """Exports structured report tables into Excel (.xlsx), CSV, and PDF."""

    @classmethod
    def export_csv(cls, title, headers, rows):
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow([f"Report: {title}"])
        writer.writerow([f"Generated at: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"])
        writer.writerow([])
        writer.writerow(headers)
        for r in rows:
            writer.writerow(r)
        return buffer.getvalue()

    @classmethod
    def export_excel(cls, title, headers, rows):
        wb = Workbook()
        ws = wb.active
        ws.title = title[:31]

        # Header styling
        navy_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
        white_bold = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        title_font = Font(name="Calibri", size=14, bold=True, color="0F172A")

        ws.cell(row=1, column=1, value=f"FactoryFlow ERP - {title}").font = title_font
        ws.cell(row=2, column=1, value=f"Generated: {timezone.now().strftime('%d-%b-%Y %H:%M:%S')}")
        
        # Table headers
        for col_idx, header in enumerate(headers, 1):
            c = ws.cell(row=4, column=col_idx, value=header)
            c.fill = navy_fill
            c.font = white_bold
            c.alignment = Alignment(horizontal="center")

        # Rows
        thin_border = Border(
            left=Side(style='thin', color='E2E8F0'),
            right=Side(style='thin', color='E2E8F0'),
            top=Side(style='thin', color='E2E8F0'),
            bottom=Side(style='thin', color='E2E8F0')
        )

        for row_idx, r in enumerate(rows, 5):
            for col_idx, val in enumerate(r, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=str(val) if isinstance(val, Decimal) else val)
                cell.border = thin_border

        # Adjust column widths
        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = col[0].column_letter
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer.getvalue()

    @classmethod
    def export_pdf(cls, title, headers, rows):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(letter),
            leftMargin=20,
            rightMargin=20,
            topMargin=20,
            bottomMargin=20
        )
        styles = getSampleStyleSheet()
        elements = []

        elements.append(Paragraph(f"<b>FactoryFlow ERP - {title}</b>", styles['Heading2']))
        elements.append(Paragraph(f"<font size=8 color='#64748B'>Generated: {timezone.now().strftime('%d-%b-%Y %H:%M:%S')}</font>", styles['Normal']))
        elements.append(Spacer(1, 10))

        table_data = [[Paragraph(f"<b>{h}</b>", styles['Normal']) for h in headers]]
        for r in rows:
            table_data.append([Paragraph(str(val), styles['Normal']) for val in r])

        t = Table(table_data)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ]))
        elements.append(t)
        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()
