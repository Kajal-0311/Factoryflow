from decimal import Decimal
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils import timezone

from apps.reports.services import ReportEngine, ReportExporter
from apps.masters.models import Customer, Product, Supplier

REPORTS_REGISTRY = {
    '1': {'id': '1', 'name': 'Sales Register', 'category': 'Sales & GST', 'desc': 'Complete invoice listing with customer, taxable, tax and total amounts.'},
    '2': {'id': '2', 'name': 'Customer-wise Sales', 'category': 'Sales & GST', 'desc': 'Aggregated sales volume and invoice values by customer.'},
    '3': {'id': '3', 'name': 'Product-wise Sales', 'category': 'Sales & GST', 'desc': 'Units sold, realized prices, and revenue by product.'},
    '4': {'id': '4', 'name': 'GST Outward Supply Summary', 'category': 'Sales & GST', 'desc': 'Prototype reconciliation summary for GSTR-1 and GSTR-3B filings.'},
    '5': {'id': '5', 'name': 'Purchase Register', 'category': 'Inventory & Procurement', 'desc': 'Raw material and packaging procurement register by supplier.'},
    '6': {'id': '6', 'name': 'Raw Material Stock Report', 'category': 'Inventory & Procurement', 'desc': 'On-hand quantities, reorder levels, and WAC valuations.'},
    '7': {'id': '7', 'name': 'Packaging Stock Report', 'category': 'Inventory & Procurement', 'desc': 'Pouches and cartons stock levels with procurement valuations.'},
    '8': {'id': '8', 'name': 'Finished Goods Stock Report', 'category': 'Inventory & Procurement', 'desc': 'Warehouse packet counts and inventory valuations at selling price.'},
    '9': {'id': '9', 'name': 'Stock Ledger', 'category': 'Inventory & Procurement', 'desc': 'Comprehensive audit ledger of every stock movement.'},
    '10': {'id': '10', 'name': 'Production Report', 'category': 'Manufacturing & Costing', 'desc': 'Batch runs history, expected vs good outputs, and status.'},
    '11': {'id': '11', 'name': 'Planned vs Actual Consumption', 'category': 'Manufacturing & Costing', 'desc': 'Material variances and alerts exceeding 3% tolerance.'},
    '12': {'id': '12', 'name': 'Yield and Wastage Report', 'category': 'Manufacturing & Costing', 'desc': 'Batch output efficiencies, packet scrap counts, and yield variances.'},
    '13': {'id': '13', 'name': 'Product-wise Costing Report', 'category': 'Manufacturing & Costing', 'desc': 'Unit cost per packet, overhead allocations, and gross margin.'},
    '14': {'id': '14', 'name': 'Customer Collections Report', 'category': 'Finance & Receivables', 'desc': 'Payment transactions, bank reference numbers, and invoice allocations.'},
    '15': {'id': '15', 'name': 'Outstanding Receivables', 'category': 'Finance & Receivables', 'desc': 'Current customer dues and credit exposure.'},
    '16': {'id': '16', 'name': 'Receivables Ageing', 'category': 'Finance & Receivables', 'desc': 'Overdue analysis across 0-30, 31-60, 61-90, and >90 day buckets.'},
}


@login_required
def report_hub(request):
    categorized = {}
    for r_id, r in REPORTS_REGISTRY.items():
        cat = r['category']
        if cat not in categorized:
            categorized[cat] = []
        categorized[cat].append(r)

    return render(request, 'reports/report_hub.html', {'categories': categorized})


@login_required
def view_report(request, report_id):
    report_info = REPORTS_REGISTRY.get(str(report_id))
    if not report_info:
        return redirect('reports:report_hub')

    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    export_format = request.GET.get('export')

    start_date = timezone.datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
    end_date = timezone.datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None

    headers = []
    rows = []
    extra_context = {}

    # Query matching report
    if report_id == '1':
        qs = ReportEngine.get_sales_register(start_date, end_date)
        headers = ['Invoice #', 'Customer', 'Date', 'Type', 'Taxable (₹)', 'CGST (₹)', 'SGST (₹)', 'IGST (₹)', 'Grand Total (₹)', 'Outstanding (₹)']
        for inv in qs:
            rows.append([
                inv.invoice_number, inv.customer.name, inv.invoice_date.strftime('%d-%b-%Y'),
                'Interstate' if inv.is_interstate else 'Intra-State',
                inv.taxable_amount, inv.cgst_amount, inv.sgst_amount, inv.igst_amount, inv.grand_total, inv.outstanding_amount
            ])

    elif report_id == '2':
        data = ReportEngine.get_customer_wise_sales(start_date, end_date)
        headers = ['Customer Name', 'Type', 'State', 'Invoices Count', 'Taxable (₹)', 'Total Tax (₹)', 'Total Sales (₹)', 'Outstanding (₹)']
        for r in data:
            rows.append([
                r['customer__name'], r['customer__customer_type'], r['customer__state'],
                r['invoice_count'], r['total_taxable'], r['total_tax'], r['total_sales'], r['total_outstanding']
            ])

    elif report_id == '3':
        data = ReportEngine.get_product_wise_sales(start_date, end_date)
        headers = ['Product Name', 'Pack Size', 'Total Qty Sold (pkts)', 'Taxable Revenue (₹)', 'Total Sales (₹)', 'Avg Price (₹)']
        for r in data:
            rows.append([
                r['product__name'], r['product__pack_size'], r['total_quantity'],
                r['total_taxable'], r['total_amount'], f"{r['avg_price']:.2f}"
            ])

    elif report_id == '4':
        data = ReportEngine.get_gst_outward_summary(start_date, end_date)
        headers = ['Category', 'Invoice Count', 'Taxable Value (₹)', 'CGST (₹)', 'SGST (₹)', 'IGST (₹)', 'Total Value (₹)']
        b2b = data['b2b']
        b2c = data['b2c']
        rows.append(['B2B Outward Supplies (Registered)', b2b['count'], b2b['taxable'], b2b['cgst'], b2b['sgst'], b2b['igst'], b2b['total']])
        rows.append(['B2C Outward Supplies (Unregistered)', b2c['count'], b2c['taxable'], b2c['cgst'], b2c['sgst'], b2c['igst'], b2c['total']])
        ov = data['overall']
        rows.append(['TOTAL ELIGIBLE SUPPLIES', ov['count'], ov['taxable'], ov['cgst'], ov['sgst'], ov['igst'], ov['grand_total']])
        extra_context['is_gst_summary'] = True

    elif report_id == '5':
        qs = ReportEngine.get_purchase_register(start_date, end_date)
        headers = ['Purchase #', 'Supplier', 'Invoice Ref', 'Date', 'Taxable (₹)', 'GST (₹)', 'Total Amount (₹)']
        for p in qs:
            rows.append([
                p.purchase_number, p.supplier.name, p.supplier_invoice_ref,
                p.purchase_date.strftime('%d-%b-%Y'), p.taxable_amount, p.gst_amount, p.total_amount
            ])

    elif report_id == '6':
        data = ReportEngine.get_raw_material_stock()
        headers = ['Code', 'Material Name', 'Current Stock', 'UOM', 'Reorder Level', 'WAC Rate (₹)', 'Valuation (₹)']
        for item in data['items']:
            rm = item['material']
            rows.append([
                rm.material_code, rm.name, rm.current_stock, rm.uom.code,
                rm.reorder_level, rm.weighted_average_cost, item['valuation']
            ])

    elif report_id == '7':
        data = ReportEngine.get_packaging_stock()
        headers = ['Code', 'Packaging Name', 'Type', 'Current Stock', 'UOM', 'Rate (₹)', 'Valuation (₹)']
        for item in data['items']:
            pm = item['material']
            rows.append([
                pm.material_code, pm.name, pm.get_packaging_type_display(),
                pm.current_stock, pm.uom.code, pm.purchase_rate, item['valuation']
            ])

    elif report_id == '8':
        data = ReportEngine.get_finished_goods_stock()
        headers = ['Code', 'Product Name', 'Category', 'Pack Size', 'Available Stock (pkts)', 'Selling Price (₹)', 'Valuation (₹)']
        for item in data['items']:
            p = item['product']
            rows.append([
                p.product_code, p.name, p.category.name, p.pack_size,
                p.current_stock, p.selling_price, item['valuation']
            ])

    elif report_id == '9':
        qs = ReportEngine.get_stock_ledger(start_date=start_date, end_date=end_date)
        headers = ['Timestamp', 'Item Name', 'Inventory Type', 'Movement Type', 'Qty Change', 'Balance After', 'Unit Rate (₹)', 'Ref Doc']
        for entry in qs:
            rows.append([
                entry.created_at.strftime('%d-%b-%Y %H:%M'), entry.item_name,
                entry.get_item_type_display(), entry.get_transaction_type_display(),
                entry.quantity_change, entry.balance_after, entry.unit_rate, entry.reference_doc
            ])

    elif report_id == '10':
        qs = ReportEngine.get_production_report(start_date, end_date)
        headers = ['Run #', 'Product', 'Date', 'Target Batch', 'Good Output', 'Yield Variance %', 'Total Cost (₹)', 'Supervisor']
        for r in qs:
            cost = getattr(r, 'costing', None)
            rows.append([
                r.run_number, r.product.name, r.production_date.strftime('%d-%b-%Y'),
                r.batch_quantity, r.actual_good_output, f"{r.yield_variance_percent}%",
                cost.total_production_cost if cost else '0.00', r.supervisor.username if r.supervisor else 'System'
            ])

    elif report_id == '11':
        qs = ReportEngine.get_consumption_report(start_date, end_date)
        headers = ['Run #', 'Item Consumed', 'Planned Qty', 'Actual Qty', 'Damaged', 'Variance %', 'Alert (>3%)', 'Cost (₹)']
        for c in qs:
            rows.append([
                c.production_run.run_number, c.item_name, c.planned_quantity,
                c.actual_quantity, c.damaged_quantity, f"{c.variance_percent}%",
                'ALERT' if c.variance_alert else 'Normal', c.total_cost
            ])

    elif report_id == '12':
        qs = ReportEngine.get_yield_wastage_report(start_date, end_date)
        headers = ['Run #', 'Product', 'Batch Size', 'Expected Output', 'Good Output', 'Wastage / Scrap', 'Yield Variance %']
        for r in qs:
            rows.append([
                r.run_number, r.product.name, r.batch_quantity, r.expected_output,
                r.actual_good_output, r.wastage_quantity, f"{r.yield_variance_percent}%"
            ])

    elif report_id == '13':
        qs = ReportEngine.get_costing_report(start_date, end_date)
        headers = ['Run #', 'Product', 'Direct RM (₹)', 'Packaging (₹)', 'Labour (₹)', 'Power/Gas (₹)', 'Total Cost (₹)', 'Cost/Pkt (₹)', 'Selling Price (₹)', 'Gross Margin (₹)']
        for c in qs:
            rows.append([
                c.production_run.run_number, c.product.name, c.raw_material_cost,
                c.packaging_material_cost, c.labour_cost, c.power_and_gas_cost,
                c.total_production_cost, f"{c.cost_per_packet:.2f}", c.selling_price_per_packet, f"{c.gross_margin_per_packet:.2f}"
            ])

    elif report_id == '14':
        qs = ReportEngine.get_collections_report(start_date, end_date)
        headers = ['Payment Ref', 'Customer', 'Date', 'Method', 'Allocated Invoice', 'UTR / Cheque Ref', 'Allocated Amount (₹)']
        for a in qs:
            rows.append([
                a.payment.payment_reference, a.payment.customer.name, a.payment.payment_date.strftime('%d-%b-%Y'),
                a.payment.get_payment_method_display(), a.invoice.invoice_number,
                a.payment.transaction_reference, a.allocated_amount
            ])

    elif report_id == '15':
        data = ReportEngine.get_outstanding_receivables()
        headers = ['Customer Name', 'Type', 'State', 'Total Billed (₹)', 'Total Paid (₹)', 'Current Outstanding (₹)']
        for r in data['customers']:
            c = r['customer']
            rows.append([
                c.name, c.get_customer_type_display(), c.state,
                r['total_billed'], r['total_paid'], r['outstanding']
            ])

    elif report_id == '16':
        data = ReportEngine.get_receivables_ageing()
        headers = ['Customer Name', 'Type', 'State', '0-30 Days (₹)', '31-60 Days (₹)', '61-90 Days (₹)', '>90 Days (₹)', 'Total Due (₹)']
        for r in data['customers']:
            rows.append([
                r['customer_name'], r['customer_type'], r['state'],
                r['b_0_30'], r['b_31_60'], r['b_61_90'], r['b_90_plus'], r['total']
            ])

    # Check for file exports
    title = f"Report_{report_id}_{report_info['name'].replace(' ', '_')}"
    if export_format == 'csv':
        csv_data = ReportExporter.export_csv(report_info['name'], headers, rows)
        resp = HttpResponse(csv_data, content_type='text/csv')
        resp['Content-Disposition'] = f'attachment; filename="{title}.csv"'
        return resp
    elif export_format == 'excel':
        excel_bytes = ReportExporter.export_excel(report_info['name'], headers, rows)
        resp = HttpResponse(excel_bytes, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        resp['Content-Disposition'] = f'attachment; filename="{title}.xlsx"'
        return resp
    elif export_format == 'pdf':
        pdf_bytes = ReportExporter.export_pdf(report_info['name'], headers, rows)
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = f'attachment; filename="{title}.pdf"'
        return resp

    context = {
        'report': report_info,
        'headers': headers,
        'rows': rows,
        'start_date': start_date_str,
        'end_date': end_date_str,
        **extra_context
    }
    return render(request, 'reports/view_report.html', context)
