import io
from decimal import Decimal
from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

def number_to_words(amount):
    """Simple Indian numbering word converter for invoice totals."""
    # Convert Decimal to int
    val = int(amount)
    if val == 0:
        return "Zero Rupees Only"
    
    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
            "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
            "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def convert_below_thousand(n):
        res = ""
        if n >= 100:
            res += ones[n // 100] + " Hundred "
            n %= 100
        if n >= 20:
            res += tens[n // 10] + " "
            n %= 10
        if n > 0:
            res += ones[n] + " "
        return res.strip()

    crore = val // 10000000
    val %= 10000000
    lakh = val // 100000
    val %= 100000
    thousand = val // 1000
    val %= 1000
    remainder = val

    parts = []
    if crore > 0:
        parts.append(convert_below_thousand(crore) + " Crore")
    if lakh > 0:
        parts.append(convert_below_thousand(lakh) + " Lakh")
    if thousand > 0:
        parts.append(convert_below_thousand(thousand) + " Thousand")
    if remainder > 0:
        parts.append(convert_below_thousand(remainder))

    res_str = " ".join(parts).strip() + " Rupees"
    
    # Paise part
    cents = int(round((amount - int(amount)) * 100))
    if cents > 0:
        res_str += f" and {cents}/100 Paise"
    res_str += " Only"
    return res_str


def generate_invoice_pdf(invoice):
    """
    Generate a GST-compliant tax invoice PDF using ReportLab.
    Returns a bytes buffer containing the PDF document.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=25,
        rightMargin=25,
        topMargin=25,
        bottomMargin=25
    )

    company = getattr(settings, 'COMPANY_INFO', {})
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=14,
        leading=16,
        textColor=colors.HexColor('#0F172A'),
        fontName='Helvetica-Bold'
    )
    badge_style = ParagraphStyle(
        'Badge',
        parent=styles['Normal'],
        fontSize=10,
        leading=12,
        textColor=colors.HexColor('#0D9488'),
        fontName='Helvetica-Bold',
        alignment=2 # Right
    )
    meta_style = ParagraphStyle(
        'Meta',
        parent=styles['Normal'],
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#334155')
    )
    cell_style = ParagraphStyle(
        'Cell',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#1E293B')
    )
    cell_bold = ParagraphStyle(
        'CellBold',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#0F172A'),
        fontName='Helvetica-Bold'
    )

    elements = []

    # 1. Header Table
    header_data = [
        [
            Paragraph(f"<b>{company.get('NAME', 'FactoryFlow Foods Pvt. Ltd.')}</b><br/>"
                      f"<font size=8>{company.get('ADDRESS', '')}<br/>"
                      f"GSTIN: <b>{company.get('GSTIN', '')}</b> | State: {company.get('STATE', 'Tamil Nadu')} (Code: {company.get('STATE_CODE', '33')})<br/>"
                      f"Email: {company.get('EMAIL', '')} | Phone: {company.get('PHONE', '')}</font>", meta_style),
            Paragraph("<b>TAX INVOICE</b><br/><font size=8 color='#64748B'>Original for Recipient</font>", badge_style)
        ]
    ]
    header_table = Table(header_data, colWidths=[380, 160])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(header_table)
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#0D9488'), spaceBefore=6, spaceAfter=8))

    # 2. Invoice & Customer Meta Table
    meta_data = [
        [
            Paragraph("<b>BILL TO (BUYER DETAILS):</b>", cell_bold),
            Paragraph("<b>INVOICE DETAILS:</b>", cell_bold)
        ],
        [
            Paragraph(f"<b>{invoice.customer.name}</b><br/>"
                      f"{invoice.billing_address}<br/>"
                      f"State: {invoice.state} (Code: {invoice.state_code})<br/>"
                      f"GSTIN: <b>{invoice.customer_gstin or 'UNREGISTERED'}</b>", meta_style),
            Paragraph(f"Invoice No: <b>{invoice.invoice_number}</b><br/>"
                      f"Invoice Date: <b>{invoice.invoice_date.strftime('%d-%b-%Y')}</b><br/>"
                      f"Financial Year: {invoice.financial_year}<br/>"
                      f"Supply Type: <b>{'INTERSTATE (IGST)' if invoice.is_interstate else 'INTRA-STATE (CGST+SGST)'}</b><br/>"
                      f"Order Ref: {invoice.sales_order.order_number if invoice.sales_order else 'Direct'}", meta_style)
        ]
    ]
    meta_table = Table(meta_data, colWidths=[270, 270])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F1F5F9')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 10))

    # 3. Line Items Table
    if invoice.is_interstate:
        table_headers = ['Sl', 'Product Description', 'HSN', 'Qty', 'Unit Rate', 'Taxable (₹)', 'IGST %', 'IGST (₹)', 'Total (₹)']
        col_widths = [20, 160, 40, 45, 55, 65, 45, 50, 60]
    else:
        table_headers = ['Sl', 'Product Description', 'HSN', 'Qty', 'Rate', 'Taxable (₹)', 'CGST (₹)', 'SGST (₹)', 'Total (₹)']
        col_widths = [20, 160, 40, 45, 55, 65, 50, 50, 55]

    item_rows = [[Paragraph(f"<b>{h}</b>", cell_bold) for h in table_headers]]

    for idx, item in enumerate(invoice.items.all(), 1):
        if invoice.is_interstate:
            row = [
                Paragraph(str(idx), cell_style),
                Paragraph(item.description, cell_style),
                Paragraph(item.hsn_code, cell_style),
                Paragraph(f"{item.quantity:.0f}", cell_style),
                Paragraph(f"{item.unit_price:.2f}", cell_style),
                Paragraph(f"{item.taxable_amount:.2f}", cell_style),
                Paragraph(f"{item.igst_rate:.1f}%", cell_style),
                Paragraph(f"{item.igst_amount:.2f}", cell_style),
                Paragraph(f"{item.total_amount:.2f}", cell_style),
            ]
        else:
            row = [
                Paragraph(str(idx), cell_style),
                Paragraph(item.description, cell_style),
                Paragraph(item.hsn_code, cell_style),
                Paragraph(f"{item.quantity:.0f}", cell_style),
                Paragraph(f"{item.unit_price:.2f}", cell_style),
                Paragraph(f"{item.taxable_amount:.2f}", cell_style),
                Paragraph(f"{item.cgst_amount:.2f}", cell_style),
                Paragraph(f"{item.sgst_amount:.2f}", cell_style),
                Paragraph(f"{item.total_amount:.2f}", cell_style),
            ]
        item_rows.append(row)

    items_table = Table(item_rows, colWidths=col_widths)
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#94A3B8')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 10))

    # 4. Summary & Tax Breakup Table
    words_text = number_to_words(invoice.grand_total)
    
    summary_data = [
        [
            Paragraph(f"<b>Amount in Words:</b><br/>{words_text}<br/><br/>"
                      f"<b>Bank Details for NEFT/RTGS:</b><br/>"
                      f"Bank: State Bank of India | A/C: 12345678901<br/>"
                      f"IFSC: SBIN0001234 | Branch: Thuvakudi, Trichy", meta_style),
            Table([
                [Paragraph("Taxable Amount:", cell_style), Paragraph(f"₹ {invoice.taxable_amount:.2f}", cell_bold)],
                [Paragraph("Total CGST:", cell_style), Paragraph(f"₹ {invoice.cgst_amount:.2f}", cell_style)],
                [Paragraph("Total SGST:", cell_style), Paragraph(f"₹ {invoice.sgst_amount:.2f}", cell_style)],
                [Paragraph("Total IGST:", cell_style), Paragraph(f"₹ {invoice.igst_amount:.2f}", cell_style)],
                [Paragraph("Total Tax Amount:", cell_style), Paragraph(f"₹ {invoice.total_tax:.2f}", cell_bold)],
                [Paragraph("<b>GRAND TOTAL:</b>", cell_bold), Paragraph(f"<b>₹ {invoice.grand_total:.2f}</b>", cell_bold)],
                [Paragraph("Outstanding Balance:", cell_style), Paragraph(f"₹ {invoice.outstanding_amount:.2f}", cell_style)],
            ], colWidths=[130, 110])
        ]
    ]
    summary_table = Table(summary_data, colWidths=[300, 240])
    summary_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 15))

    # 5. Signatures & Footer
    sign_data = [
        [
            Paragraph("<font size=7 color='#64748B'><b>Terms & Conditions:</b><br/>"
                      "1. Goods once sold will not be taken back without prior authorization.<br/>"
                      "2. Interest @ 18% p.a. will be charged if payment is delayed beyond due date.<br/>"
                      "3. Subject to Tiruchirappalli jurisdiction only.</font>", meta_style),
            Paragraph(f"<font size=8>For <b>{company.get('NAME', 'FactoryFlow Foods Pvt. Ltd.')}</b><br/><br/><br/><br/>"
                      "<b>Authorized Signatory</b></font>", ParagraphStyle('Sign', parent=meta_style, alignment=2))
        ]
    ]
    sign_table = Table(sign_data, colWidths=[340, 200])
    sign_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(sign_table)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()
