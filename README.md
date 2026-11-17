# FactoryFlow – Integrated Order-to-Audit Food Manufacturing ERP
### Centre for Digital Infrastructure, National Institute of Technology, Tiruchirappalli
**Internship Assessment Project: Small Packaged Food Manufacturing ERP**

![Django](https://img.shields.io/badge/Django-5.1.15-092E20?style=for-the-badge&logo=django&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![License](https://img.shields.io/badge/License-Proprietary-red?style=for-the-badge)

---

## 1. Executive Summary

**FactoryFlow** is an integrated, production-grade web ERP platform engineered specifically for small packaged food manufacturers (e.g., Murukku, Mixture, Chips, and Traditional South Indian Sweets).

Developed as an individual internship shortlisting assessment for the **Centre for Digital Infrastructure, NIT Tiruchirappalli**, FactoryFlow is a full-featured web application with a complete backend architecture, immutable double-entry stock accounting, dynamic recipe-based production tracking, statutory GST billing, comprehensive costing, and tamper-evident audit logging.

Every business rule, button, calculation, report, and workflow operates on persistent database records with **100% mathematical precision** using Python `Decimal` fixed-point arithmetic (`ROUND_HALF_UP`).

---

## 2. Benchmark Scenario – 100% Exact Numerical Reproduction

FactoryFlow reproduces all parameters of the required benchmark scenario with zero discrepancy:

| Metric / Parameter | Required Benchmark | FactoryFlow Dynamic Result | Status |
| :--- | :--- | :--- | :---: |
| **Flour Opening Stock** | 100.000 kg @ ₹42.0000/kg | 100.000 kg @ ₹42.0000/kg | MATCH |
| **Flour Inward Receipt** | 60.000 kg @ ₹45.0000/kg | 60.000 kg @ ₹45.0000/kg | MATCH |
| **Flour Inward Stock Balance** | 160.000 kg | 160.000 kg | MATCH |
| **Flour Weighted Average Cost** | **₹43.1250 / kg** | **₹43.1250 / kg** | **EXACT MATCH** |
| **Planned Production Run** | 200.000 pkts | 200.000 pkts | MATCH |
| **Actual Good Output** | 188.000 pkts | 188.000 pkts | MATCH |
| **Defective / Scrap Packets** | 12.000 pkts | 12.000 pkts | MATCH |
| **Yield Variance %** | **-6.00%** | **-6.00%** | **EXACT MATCH** |
| **Yield Variance Alert (&gt;3%)** | **True (Alert Triggered)** | **True (Alert Triggered)** | **EXACT MATCH** |
| **Oil Consumption (Plan / Act)** | 10.000 L / 10.500 L | 10.000 L / 10.500 L (+5.00%) | **ALERT TRIGGERED** |
| **Pouches Consumed (Good + Damaged)**| 188 good + 6 damaged = 194 pcs | 194 pcs (damaged: 6 pcs) | MATCH |
| **Cartons Consumed** | 9 pcs (ceil(188/20)) | 9 pcs (-10.00% variance) | **ALERT TRIGGERED** |
| **Direct Material Cost (RM + Pkg)** | **₹4,055.00** | **₹4,055.00** | **EXACT MATCH** |
| **Direct Labour Overheads** | ₹1,200.00 | ₹1,200.00 | MATCH |
| **Power & Fuel Overheads** | ₹600.00 | ₹600.00 | MATCH |
| **Total Production Batch Cost** | **₹5,855.00** | **₹5,855.00** | **EXACT MATCH** |
| **Cost Per Packet** | **₹31.14** | **₹31.14** (₹31.1436) | **EXACT MATCH** |
| **Standard Selling Price** | ₹50.00 / pkt | ₹50.00 / pkt | MATCH |
| **Gross Margin Per Packet** | **₹18.86** (37.71%) | **₹18.86** (37.71%) | **EXACT MATCH** |
| **Finished Goods Stock (Pre-dispatch)**| 238.000 pkts (50 + 188) | 238.000 pkts | MATCH |
| **Retailer A Order (TN Intra-state)**| 150.000 pkts | 150.000 pkts | MATCH |
| **Taxable / CGST / SGST / Total** | ₹7,500 / ₹187.50 / ₹187.50 / **₹7,875** | ₹7,500 / ₹187.50 / ₹187.50 / **₹7,875** | **EXACT MATCH** |
| **Retailer A Payment Received** | ₹4,000.00 | ₹4,000.00 (via NEFT) | MATCH |
| **Retailer A Outstanding Balance**| **₹3,875.00** | **₹3,875.00** | **EXACT MATCH** |
| **Finished Goods Stock (Post-dispatch)**| **88.000 pkts** | **88.000 pkts** | **EXACT MATCH** |
| **Distributor B Order (Karnataka)**| 120.000 pkts | 120.000 pkts | MATCH |
| **Distributor B Stock Shortage** | **32.000 pkts Shortage** | **32.000 pkts Shortage** | **EXACT MATCH** |
| **Distributor B Dispatch Guard** | **Blocked (ValidationError)**| **Blocked (ValidationError)**| **EXACT MATCH** |

*For complete step-by-step mathematical derivations, see [BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md).*

---

## 3. Technology Stack & Architectural Decisions

| Layer / Subsystem | Technology | Rationale & Justification |
| :--- | :--- | :--- |
| **Web Framework** | Django 5.1 (Python 3.12) | Batteries-included web framework with native ORM, robust transaction management (`transaction.atomic`), built-in CSRF/XSS protection, and custom User auth. |
| **Database** | PostgreSQL 16 / SQLite 3 | Row-level locking (`select_for_update()`) prevents concurrent race conditions and negative inventory balances. Zero-configuration SQLite for development; PostgreSQL 16 for production container. |
| **Math Precision** | Python `Decimal` | Eliminates IEEE 754 floating-point inaccuracies. Required for statutory GST invoices, currency valuations, and chemical recipe weights. |
| **PDF Generation** | ReportLab 5.1 | Pixel-perfect, vector A4 GST Tax Invoices and Audit Reports with dynamic tables, borders, amount in words, and authorized signature blocks. |
| **Spreadsheet Export**| openpyxl 3.1 | Generates multi-sheet Excel `.xlsx` audit reports with bold headers, currency formatting, and numeric alignments. |
| **UI & Theme** | Bootstrap 5 + Modern ERP Theme | Clean industrial dashboard styling (Deep Navy `#0F172A`, Slate `#64748B`, Teal `#0D9488`), responsive on mobile and desktop, Chart.js visualizations. |

---

## 4. System Architecture: 12 Modular Apps

FactoryFlow follows a clean modular monolith architecture separated into 12 domain applications:

```
apps/
├── accounts/    # Custom User model, Role-Based Access Control (RBAC), decorators
├── core/        # Abstract models, UnitConverter, Executive Dashboard view
├── masters/     # Master data: Products, Customers, Suppliers, Raw/Packaging Materials, UOMs
├── inventory/   # Immutable signed StockLedger, StockBalance, atomic InventoryService
├── bom/         # Recipe Bill of Materials, dynamic batch requirement scaling
├── purchases/   # Purchase orders, inward goods receipt, automatic WAC recalculation
├── production/  # Batch execution, planned vs actual variance engine, 3% alerts, batch costing
├── sales/       # Sales orders, stock verification, shortage detection, dispatch execution
├── billing/     # GST Tax Invoices (TN Intra vs Interstate), ReportLab PDF, Credit Notes
├── payments/    # Payment recording, FIFO invoice allocation, receivables ageing buckets
├── reports/     # 16 Monthly Audit Reports engine with CSV, Excel, and PDF exporters
└── audit/       # Immutable AuditLog with JSON before/after state diff tracking
```

---

## 5. Core Business Logic & Engineering Highlights

### 1. Immutable Double-Entry Stock Ledger
- Every stock change creates a permanent, signed entry in `StockLedger`.
- **Outflow types** (Production Issue, Sales Dispatch) record negative changes.
- **Inflow types** (Opening Stock, Purchase Inward, Production Output, Sales Return) record positive changes.
- Row-level database locks (`select_for_update()`) ensure that no race condition can ever produce a negative inventory balance.

### 2. Weighted Average Cost (WAC) Inventory Valuation
Raw materials are dynamically valued upon every confirmed inward purchase:
$$\text{New WAC} = \frac{(\text{Current Stock} \times \text{Old WAC}) + (\text{Inward Qty} \times \text{Purchase Rate})}{\text{Current Stock} + \text{Inward Qty}}$$

### 3. Production Variance Engine & 3% Tolerance Threshold
- The system checks both **Yield Variance** and individual **Item Consumption Variances**:
$$\text{Variance \%} = \frac{\text{Actual} - \text{Planned}}{\text{Planned}} \times 100$$
- If $|\text{Variance \%}| > 3.00\%$, the system sets `yield_alert = True` or `variance_alert = True` and surfaces red alerts across the supervisor run view and executive dashboard.
- **Damaged packaging (6 pouches)** is deducted from stock, included in batch production costs, but excluded from good output packet counts.

### 4. Statutory GST Billing Engine
- **Intra-state (Tamil Nadu to Tamil Nadu)**: Splits GST 50/50 into **CGST 2.5%** and **SGST 2.5%** (IGST = 0.00%).
- **Interstate (Tamil Nadu to Karnataka, etc.)**: Full GST rate applied to **IGST 5.0%** (CGST = 0.00%, SGST = 0.00%).
- Sequential fiscal year invoice numbering: `INV/2026-27/0001`.
- Built-in PDF Tax Invoice generator using ReportLab with amount-in-words converter and authorized signature block.

### 5. Sales Verification & Shortage Detection
- Before approving or dispatching an order, the system runs `SalesOrderService.check_stock_availability()`.
- If required quantity > available finished goods, the order flags a **Shortage Warning** (e.g. 32 pkts shortage for Distributor B) and **blocks dispatch**.
- Duplicate dispatches are strictly prevented with validation exceptions.

### 6. Payment Allocation & Receivables Ageing
- Partial payments update invoice `paid_amount` and `outstanding_amount`.
- Overpayments beyond the invoice balance are blocked.
- Ageing engine partitions receivables into 4 standard accounting buckets:
  - **0 – 30 days** (Current)
  - **31 – 60 days** (Overdue Level 1)
  - **61 – 90 days** (Overdue Level 2)
  - **90+ days** (Critical Overdue)

### 7. 16 Comprehensive Monthly Audit Reports
FactoryFlow implements all 16 required reports in the Reports Hub (`/reports/`):
1. Raw Material Stock Ledger
2. Packaging Material Stock Ledger
3. Finished Goods Stock Ledger
4. Production Summary & Yield Reconciliation
5. Production Costing & Unit Cost Sheet
6. Material Consumption Variance Report
7. Customer-Wise Sales Summary
8. Sales Dispatch Register
9. Statutory GST Sales Register (GSTR-1)
10. Statutory GST Purchase Register (GSTR-2)
11. Customer Outstanding Receivables Register
12. Receivables Ageing Analysis Report
13. Payment Collections Register
14. Supplier Purchase Inward Register
15. Reorder Level & Low Stock Warning Report
16. Immutable System Audit Trail & Event Log

*Every report supports date-range filtering and 1-click export to **CSV**, **Excel (.xlsx)**, and **PDF**.*

---

## 6. Role-Based Access Control (RBAC) Matrix

| Module / Action | Administrator | Sales Representative | Production Supervisor | Owner / Auditor |
| :--- | :---: | :---: | :---: | :---: |
| **Executive Dashboard** | Full | Sales View | Production View | Read-Only Audit |
| **Take Mobile Sales Order** | Yes | Yes | No | No |
| **Approve Sales Order** | Yes | No (Blocked) | No (Blocked) | No (Blocked) |
| **Record Sales Dispatch** | Yes | No (Blocked) | No (Blocked) | No (Blocked) |
| **Record Production Run** | Yes | No (Blocked) | Yes | No (Blocked) |
| **Manage BOM Recipes** | Yes | No (Blocked) | Yes | No (Blocked) |
| **Record Purchase Inward** | Yes | No (Blocked) | Yes | No (Blocked) |
| **Record Payment Receipt** | Yes | No (Blocked) | No (Blocked) | No (Blocked) |
| **16 Audit Reports Hub** | Full | Restricted | Restricted | **Full Read-Only** |
| **Audit Logs & JSON Diffs**| Full | No (Blocked) | No (Blocked) | **Full Read-Only** |

---

## 7. Demo Credentials

The login screen features 1-click demo login buttons for rapid evaluator evaluation:

| Role | Username | Password | Purpose |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin` | `admin123` | Full ERP oversight, approvals, dispatches |
| **Salesman (TN)** | `salesman_a` | `sales123` | Retailer order taking, field view |
| **Salesman (KA)** | `salesman_b` | `sales123` | Interstate customer orders |
| **Production Supervisor**| `supervisor` | `super123` | Recipe BOM, batch entry, variance alerts |
| **Owner / Auditor** | `auditor` | `audit123` | Audit reports, financial ledger verification |

---

## 8. Quick Start Guide

### Option A: Local Development (Windows / Linux / macOS)

1. **Clone and enter the directory**:
   ```bash
   git clone https://github.com/<your-username>/factoryflow-erp.git
   cd factoryflow-erp
   ```

2. **Create and activate the virtual environment**:
   - Windows PowerShell:
     ```powershell
     python -m venv .venv
     .venv\Scripts\Activate.ps1
     ```
   - Linux/macOS:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run migrations**:
   ```bash
   python manage.py migrate
   ```

5. **Seed the benchmark scenario** (idempotent):
   ```bash
   python manage.py seed_benchmark
   ```
   *(Optional)* Run the complete 37-point independent audit evaluation:
   ```bash
   python manage.py run_audit_evaluation
   ```

6. **Start the local server**:
   ```bash
   python manage.py runserver
   ```

7. **Open in browser**:
   Navigate to **`http://127.0.0.1:8000/`**.

---

### Option B: Docker Compose Deployment (PostgreSQL 16 + Gunicorn)

1. **Launch containers**:
   ```bash
   docker compose up -d --build
   ```
2. **Access the application**:
   Open **`http://localhost:8000/`**. The database migrations and benchmark scenario seed execute automatically during container startup.

---

## 9. Automated Test Suite

FactoryFlow includes a comprehensive automated test suite of **24 tests** covering all critical operational flows:

```bash
python manage.py test tests
```

### Test Suite Structure:
- `tests/test_benchmark_scenario.py`: Complete end-to-end simulation matching the exact benchmark scenario numbers.
- `tests/test_wac_valuation.py`: Single inward, successive inwards, and zero-stock edge cases for Weighted Average Costing.
- `tests/test_production_variance.py`: 3% variance threshold boundary detection, dynamic BOM recipe scaling, and damaged pouch accounting.
- `tests/test_inventory_ledger.py`: Signed ledger transactions, negative stock prevention, and reconciliation consistency.
- `tests/test_gst_billing.py`: Intra-state CGST/SGST, interstate IGST, FY numbering sequence, ReportLab PDF rendering, and credit notes.
- `tests/test_sales_dispatch.py`: Stock shortage detection, blocking dispatches on shortage, duplicate dispatch prevention, and stock reduction.
- `tests/test_payments_ageing.py`: Partial payment recording, FIFO invoice allocation, overpayment guard, and 4-bucket ageing analysis.
- `tests/test_rbac_permissions.py`: Role enforcement across all 4 system roles.

**Test Run Output**:
```
Creating test database for alias 'default'...
Found 24 test(s).
System check identified no issues (0 silenced).
........................
----------------------------------------------------------------------
Ran 24 tests in 53.752s

OK
Destroying test database for alias 'default'...
```

---

## 10. Project Deliverables Checklist

- [x] **Working Full-Stack Web Application**: All 12 modular apps, templates, forms, calculations, and views operational.
- [x] **Master Benchmark Scenario**: 100% exact numerical match across WAC, yield, variances, costing, GST, payments, and shortage.
- [x] **Statutory GST Billing & PDF Generation**: ReportLab A4 tax invoices with CGST/SGST/IGST and amount in words.
- [x] **16 Monthly Audit Reports**: ReportEngine with CSV, openpyxl Excel, and PDF export capabilities.
- [x] **Tamper-Evident Audit Trail**: JSON before/after state diff logging.
- [x] **Role-Based Access Control**: 4 granular roles enforced with decorators and mixins.
- [x] **Automated Test Suite**: 24 tests passing with zero errors.
- [x] **Containerization**: `Dockerfile` and `docker-compose.yml` with PostgreSQL 16.
- [x] **Comprehensive Documentation**: `README.md`, `BENCHMARK_RESULTS.md`, `DEMO_SCRIPT.md`, and `DESIGN_NOTE.md`.
