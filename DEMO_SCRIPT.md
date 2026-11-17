# FactoryFlow – Evaluator Demonstration Script & Walkthrough
### Centre for Digital Infrastructure, NIT Tiruchirappalli Internship Assessment

This walkthrough provides a step-by-step guide for testing and validating the **FactoryFlow ERP** system against the benchmark scenario. Every step corresponds directly to real database transactions and dynamic UI calculations.

---

## Prerequisites & Server Launch

1. Open PowerShell or Terminal in the project root:
   ```bash
   cd factoryflow-erp
   ```
2. Activate the virtual environment:
   ```powershell
   .venv\Scripts\Activate.ps1
   ```
3. Run migrations and seed the benchmark data (idempotent):
   ```powershell
   python manage.py migrate
   python manage.py seed_benchmark
   ```
4. Start the Django development server:
   ```powershell
   python manage.py runserver
   ```
5. Open your web browser at **`http://127.0.0.1:8000/`**.

---

## Demo Credentials Table

| Role | Username | Password | Key Permissions |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin` | `admin123` | Full ERP access, Order Approvals, Dispatches, System Config |
| **Salesman (Tamil Nadu)** | `salesman_a` | `sales123` | Mobile Order Entry, My Orders Dashboard, Customer Catalog |
| **Salesman (Interstate)** | `salesman_b` | `sales123` | Interstate Orders, Price Discovery, Customer Catalog |
| **Production Supervisor**| `supervisor`| `super123` | BOM Recipes, Batch Execution, Variance Monitoring |
| **Owner / Auditor** | `auditor` | `audit123` | 16 Audit Reports, Immutable Ledger, Audit Logs (Read-only) |

*Tip: The login page includes 1-click quick-fill buttons for each role.*

---

## Step-by-Step Scenario Walkthrough

### Step 1: Authentication & Executive Dashboard
1. Go to `http://127.0.0.1:8000/accounts/login/`.
2. Click **Admin** (or login with `admin` / `admin123`).
3. You are redirected to the **Executive Dashboard** (`http://127.0.0.1:8000/`):
   - **KPI Cards**: View Total Sales (₹7,875.00), Outstanding Receivables (₹3,875.00), Raw Material Valuation, Finished Goods Packets (88 pkts).
   - **Active Alert Banners**: Notice the red alert: *"Active Production Variance Alerts: 1 production runs exceeded the 3% tolerance threshold"*.
   - **Charts**: View Raw Material Consumption breakdown, Customer Receivables, and Product-wise sales distribution.

---

### Step 2: Raw Material Inward & Weighted Average Cost (WAC)
1. In the sidebar, navigate to **Purchases** (`http://127.0.0.1:8000/purchases/`).
2. Click on **`PUR-BM-0001`** (from Southern Agri Traders / Annapoorna Agro Mills).
3. **Inspect the inward transaction**:
   - Item: **Flour**
   - Quantity Inward: **60.000 kg**
   - Inward Rate: **₹45.0000 / kg**
   - Total Taxable: ₹2,700.00 | GST 5%: ₹135.00 | Total: ₹2,835.00
4. Navigate to **Masters > Catalog > Raw Materials** (`http://127.0.0.1:8000/masters/catalog/`):
   - Look at the row for **Flour**:
     - Opening Stock: `100.000 kg` @ `₹42.0000/kg`
     - Current Stock: `120.000 kg` (post-production consumption of 40 kg from 160 kg)
     - **Weighted Average Cost (WAC)**: **`₹43.1250 / kg`** (Matches $(100 \times 42 + 60 \times 45) / 160 = 43.1250$).

---

### Step 3: Production Execution & 3% Variance Alerts
1. In the sidebar, navigate to **Production > Production Runs** (`http://127.0.0.1:8000/production/`).
2. Click on the completed run **`RUN-202611-0001`** (Murukku 200 g):
   - **Target Batch Size**: 200 pkts
   - **Actual Good Output**: **188 pkts**
   - **Defective / Scrap Output**: **12 pkts**
   - **Yield Variance**: **`-6.00%`** -> **`ALERT TRIGGERED (Exceeds ±3%)`**
3. Scroll down to the **Material Consumption Breakdown**:
   - **Flour**: Planned `40.000 kg` | Actual `40.000 kg` | Variance: `0.00%`
   - **Cooking Oil**: Planned `10.000 L` | Actual **`10.500 L`** | Variance: **`+5.00%`** -> **`ALERT TRIGGERED (>3%)`**
   - **Spice Mix**: Planned `1.200 kg` | Actual `1.200 kg` | Variance: `0.00%`
   - **200 g Pouch**: Planned `200 pcs` | Actual **`194 pcs`** (188 good + **6 damaged in sealing**) | Variance: `-3.00%`
   - **Cartons**: Planned `10 pcs` | Actual **`9 pcs`** | Variance: **`-10.00%`** -> **`ALERT TRIGGERED (>3%)`**
4. Review the **Batch Costing Engine**:
   - Direct Raw Materials: ₹3,435.00 ($40 \times 43.1250 + 10.5 \times 140 + 1.2 \times 200$)
   - Direct Packaging: ₹620.00 ($194 \times 2.50 + 9 \times 15.00$)
   - Total Direct Materials: **`₹4,055.00`**
   - Direct Labour: **`₹1,200.00`**
   - Power & Fuel: **`₹600.00`**
   - **Total Batch Cost**: **`₹5,855.00`**
   - **Cost Per Packet**: **`₹31.14`** ($5855 / 188$)
   - **Selling Price**: **`₹50.00`**
   - **Gross Margin Per Packet**: **`₹18.86`** (**`37.71%`**)

---

### Step 4: Sales Order 1 (Retailer A, Tamil Nadu) - Dispatch & GST Invoice
1. In the sidebar, navigate to **Sales > Orders** (`http://127.0.0.1:8000/sales/orders/`).
2. Click on the first order for **Retailer A**:
   - Customer: Retailer A (State: Tamil Nadu, Code: 33)
   - Product: Murukku 200 g x 150 pkts @ ₹50.00
   - Status: **`DISPATCHED`**
3. Click on the linked **Invoice** (`http://127.0.0.1:8000/billing/invoices/1/`):
   - **Intra-state Tax Breakdown**:
     - Taxable Amount: **`₹7,500.00`**
     - CGST @ 2.5%: **`₹187.50`**
     - SGST @ 2.5%: **`₹187.50`**
     - IGST @ 0.0%: **`₹0.00`**
     - **Grand Total**: **`₹7,875.00`**
   - **Payment Status**:
     - Amount Paid: **`₹4,000.00`** (via NEFT Bank Transfer)
     - **Outstanding Balance**: **`₹3,875.00`**
4. **Download Official GST PDF Invoice**:
   - Click the green **`Download GST Tax Invoice (PDF)`** button.
   - Open the generated PDF: notice company details, GSTIN, HSN table, CGST/SGST breakup, Amount in words (*"Seven Thousand Eight Hundred Seventy Five Rupees Only"*), and Authorized Signatory box.

---

### Step 5: Sales Order 2 (Distributor B, Karnataka) - Shortage Detection
1. In the sidebar, navigate to **Sales > Orders** (`http://127.0.0.1:8000/sales/orders/`).
2. Click on the order for **Distributor B** (120 packets):
   - Notice the prominent **Red Warning Box**:
     - *"Order Shortage Detected: Insufficient finished goods stock to fulfill order."*
     - Product: Murukku 200 g
     - Required: `120.000 pkts`
     - Available: `88.000 pkts` (Opening 50 + Produced 188 - Dispatched 150 = 88)
     - **Shortage**: **`32.000 pkts Shortage`**
3. Notice that the **`Record Dispatch`** action is **BLOCKED**.
   - If an evaluator attempts to post a dispatch programmatically, the system raises a `ValidationError("Dispatch blocked due to insufficient stock")` and prevents duplicate dispatches.

---

### Step 6: 16 Monthly Audit Reports Hub
1. In the sidebar, navigate to **Reports Hub** (`http://127.0.0.1:8000/reports/`).
2. Explore any of the **16 Mandatory Audit Reports**:
   - **1. Raw Material Stock Ledger** (Opening, Receipts, Issues, Closing)
   - **2. Packaging Material Stock Ledger**
   - **3. Finished Goods Stock Ledger**
   - **4. Production Summary & Yield Reconciliation**
   - **5. Production Costing & Unit Cost Sheet**
   - **6. Material Variance Report** (Highlighting >3% variances)
   - **7. Sales Summary by Customer & Product**
   - **8. Sales Dispatch Register**
   - **9. GST Sales Register (GSTR-1 format)**
   - **10. GST Purchase / Inward Register (GSTR-2 format)**
   - **11. Customer Accounts Receivable & Outstanding**
   - **12. Receivables Ageing Report (0-30, 31-60, 61-90, 90+ days)**
   - **13. Customer Payment Collection Register**
   - **14. Supplier Purchase Register**
   - **15. Reorder Level & Low Stock Alert Report**
   - **16. Comprehensive Audit Trail & Change Log**
3. For each report:
   - Filter by date range.
   - Click **`Export CSV`**, **`Export Excel (.xlsx)`**, or **`Export PDF`**.

---

### Step 7: Immutable Double-Entry Audit Trail
1. In the sidebar, navigate to **Audit > Audit Logs** (`http://127.0.0.1:8000/audit/`).
2. View every recorded system event (Purchases, Production Runs, Dispatches, Invoices, Payments).
3. Click the **JSON Diff** icon on any entry to see the structured before/after state diff captured by the tamper-evident audit service.
4. Navigate to **Inventory > Reconciliation** (`http://127.0.0.1:8000/inventory/reconciliation/`):
   - Verify that all ledger sums match current cached stock with **0.000 discrepancy** across all raw materials, packaging items, and finished goods.

---

## Automated Verification

To run all 24 automated unit and integration tests:
```powershell
python manage.py test tests
```
**Expected Result**:
```
Ran 24 tests in ~53s
OK
```
