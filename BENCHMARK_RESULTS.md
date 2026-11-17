# FactoryFlow – Benchmark Scenario Verification Results
### Centre for Digital Infrastructure, NIT Tiruchirappalli Internship Assessment

This document provides a quantitative audit comparing the **Required Benchmark Scenario** with the **Actual Values Computed Dynamically** by the FactoryFlow ERP application.

All values are computed from persistent database records using Python `Decimal` arithmetic with strict standard Indian accounting rounding (`ROUND_HALF_UP`). No floats or hardcoded strings are used in any business logic calculations.

---

## 1. Summary Comparison Table

| Metric / Parameter | Required Benchmark | FactoryFlow Dynamic Result | Status | Verification Source |
| :--- | :--- | :--- | :---: | :--- |
| **Flour Opening Stock** | 100.000 kg | 100.000 kg | MATCH | `RawMaterial.opening_stock` |
| **Flour Opening Rate** | ₹42.0000 / kg | ₹42.0000 / kg | MATCH | `RawMaterial.weighted_average_cost` |
| **Flour Purchase Inward** | 60.000 kg @ ₹45.00/kg | 60.000 kg @ ₹45.00/kg | MATCH | `PurchaseItem.quantity` & `purchase_rate` |
| **Flour Inward Stock Balance** | 160.000 kg | 160.000 kg | MATCH | `RawMaterial.current_stock` |
| **Flour Recomputed WAC** | **₹43.1250 / kg** | **₹43.1250 / kg** | **EXACT MATCH** | `RawMaterial.weighted_average_cost` |
| **Planned Production Quantity** | 200.000 pkts | 200.000 pkts | MATCH | `ProductionRun.batch_quantity` |
| **Actual Good Packets Produced** | 188.000 pkts | 188.000 pkts | MATCH | `ProductionRun.actual_good_output` |
| **Defective / Scrap Packets** | 12.000 pkts | 12.000 pkts | MATCH | `ProductionRun.wastage_quantity` |
| **Yield Variance %** | **-6.00%** | **-6.00%** | **EXACT MATCH** | `ProductionRun.yield_variance_percent` |
| **Yield Variance Alert (&gt;3%)** | **True (Alert Triggered)** | **True (Alert Triggered)** | **EXACT MATCH** | `ProductionRun.yield_alert` |
| **Flour Consumption (Plan/Act)** | 40.000 kg / 40.000 kg | 40.000 kg / 40.000 kg | MATCH | `ProductionConsumption` (Var: 0.00%) |
| **Cooking Oil Consumption** | 10.000 L / 10.500 L | 10.000 L / 10.500 L | MATCH | `ProductionConsumption` (Var: +5.00%) |
| **Cooking Oil Variance Alert** | **True (+5.00% &gt; 3%)** | **True (+5.00% &gt; 3%)** | **EXACT MATCH** | `ProductionConsumption.variance_alert` |
| **Spice Mix Consumption** | 1.200 kg / 1.200 kg | 1.200 kg / 1.200 kg | MATCH | `ProductionConsumption` (Var: 0.00%) |
| **Good Pouches Consumed** | 188 pcs | 188 pcs | MATCH | Calculated from good output |
| **Damaged Pouches (Sealer Loss)**| 6 pcs | 6 pcs | MATCH | `ProductionConsumption.damaged_quantity` |
| **Total Pouches Deducted** | 194 pcs | 194 pcs | MATCH | `ProductionConsumption.actual_quantity` |
| **Cartons Consumed** | 9 pcs (ceil(188/20)) | 9 pcs (Var: -10.00%) | MATCH | `ProductionConsumption.actual_quantity` |
| **Cartons Variance Alert** | **True (-10.00% &gt; 3%)** | **True (-10.00% &gt; 3%)** | **EXACT MATCH** | `ProductionConsumption.variance_alert` |
| **Direct Raw Material Cost** | ₹3,435.00 | ₹3,435.00 | MATCH | Flour ₹1725 + Oil ₹1470 + Spice ₹240 |
| **Packaging Material Cost** | ₹620.00 | ₹620.00 | MATCH | Pouches ₹485 + Cartons ₹135 |
| **Total Direct Material Cost** | **₹4,055.00** | **₹4,055.00** | **EXACT MATCH** | `CostingRecord.raw_mat + pkg_mat` |
| **Direct Labour Overheads** | ₹1,200.00 | ₹1,200.00 | MATCH | `CostingRecord.labour_cost` |
| **Power & Fuel (LPG/Power)** | ₹600.00 | ₹600.00 | MATCH | `CostingRecord.power_and_gas_cost` |
| **Total Production Batch Cost** | **₹5,855.00** | **₹5,855.00** | **EXACT MATCH** | `CostingRecord.total_production_cost` |
| **Cost Per Packet** | **₹31.14** | **₹31.14** (₹31.1436) | **EXACT MATCH** | `CostingRecord.cost_per_packet` |
| **Standard Selling Price** | ₹50.00 / pkt | ₹50.00 / pkt | MATCH | `Product.selling_price` |
| **Gross Margin Per Packet** | **₹18.86** | **₹18.86** (₹18.8564) | **EXACT MATCH** | `CostingRecord.gross_margin_per_packet` |
| **Gross Margin %** | **37.71%** | **37.71%** | **EXACT MATCH** | `CostingRecord.gross_margin_percent` |
| **Post-Production Flour Stock** | 120.000 kg | 120.000 kg | MATCH | 160.000 - 40.000 kg |
| **Post-Production Oil Stock** | 19.500 L | 19.500 L | MATCH | 30.000 - 10.500 L |
| **Post-Production Spice Stock** | 3.800 kg | 3.800 kg | MATCH | 5.000 - 1.200 kg |
| **Post-Production Pouch Stock** | 306.000 pcs | 306.000 pcs | MATCH | 500.000 - 194.000 pcs |
| **Post-Production Carton Stock**| 21.000 pcs | 21.000 pcs | MATCH | 30.000 - 9.000 pcs |
| **FG Stock Before Dispatch** | 238.000 pkts | 238.000 pkts | MATCH | Opening 50 + Produced 188 |
| **Retailer A Order (TN Intra)** | 150.000 pkts | 150.000 pkts | MATCH | `SalesOrder.items` |
| **Retailer A Taxable Value** | ₹7,500.00 | ₹7,500.00 | MATCH | 150 pkts * ₹50.00 |
| **Retailer A CGST (2.5%)** | ₹187.50 | ₹187.50 | MATCH | `Invoice.cgst_amount` |
| **Retailer A SGST (2.5%)** | ₹187.50 | ₹187.50 | MATCH | `Invoice.sgst_amount` |
| **Retailer A IGST (0.0%)** | ₹0.00 | ₹0.00 | MATCH | `Invoice.igst_amount` |
| **Retailer A Invoice Grand Total**| **₹7,875.00** | **₹7,875.00** | **EXACT MATCH** | `Invoice.grand_total` |
| **FG Stock After Dispatch** | **88.000 pkts** | **88.000 pkts** | **EXACT MATCH** | 238.000 - 150.000 pkts |
| **Retailer A Payment Received** | ₹4,000.00 | ₹4,000.00 | MATCH | `Payment.amount` |
| **Retailer A Outstanding Balance**| **₹3,875.00** | **₹3,875.00** | **EXACT MATCH** | `Invoice.outstanding_amount` |
| **Distributor B Order (KA)** | 120.000 pkts | 120.000 pkts | MATCH | `SalesOrder.items` |
| **Distributor B Stock Shortage** | **32.000 pkts Shortage** | **32.000 pkts Shortage** | **EXACT MATCH** | Required 120 - Available 88 |
| **Distributor B Dispatch Block** | **Blocked (ValidationError)**| **Blocked (ValidationError)**| **EXACT MATCH** | `DispatchService.record_dispatch` |

---

## 2. Mathematical Proofs

### A. Flour Weighted Average Cost (WAC)
$$\text{Existing Stock Value} = 100\text{ kg} \times ₹42.0000 = ₹4,200.00$$
$$\text{Inward Stock Value} = 60\text{ kg} \times ₹45.0000 = ₹2,700.00$$
$$\text{Total Post-Inward Stock} = 100\text{ kg} + 60\text{ kg} = 160\text{ kg}$$
$$\text{New WAC} = \frac{₹4,200.00 + ₹2,700.00}{160\text{ kg}} = \frac{₹6,900.00}{160} = \mathbf{₹43.1250/\text{kg}}$$

### B. Production Variances & 3% Threshold
$$\text{Yield Variance} = \frac{188 - 200}{200} \times 100 = \mathbf{-6.00\%} \quad (|-6.00\%| > 3.00\% \implies \text{ALERT: TRUE})$$
$$\text{Cooking Oil Variance} = \frac{10.5 - 10.0}{10.0} \times 100 = \mathbf{+5.00\%} \quad (|+5.00\%| > 3.00\% \implies \text{ALERT: TRUE})$$
$$\text{Carton Variance} = \frac{9 - 10}{10} \times 100 = \mathbf{-10.00\%} \quad (|-10.00\%| > 3.00\% \implies \text{ALERT: TRUE})$$
$$\text{Pouch Variance} = \frac{194 - 200}{200} \times 100 = \mathbf{-3.00\%} \quad (|-3.00\%| \le 3.00\% \implies \text{ALERT: FALSE})$$

### C. Batch Costing Breakdown
$$\begin{aligned}
\text{Direct RM Cost} &= (40 \times ₹43.1250) + (10.5 \times ₹140.00) + (1.2 \times ₹200.00) \\
&= ₹1,725.00 + ₹1,470.00 + ₹240.00 = ₹3,435.00 \\
\text{Packaging Cost} &= (194 \times ₹2.50) + (9 \times ₹15.00) \\
&= ₹485.00 + ₹135.00 = ₹620.00 \\
\text{Total Direct Material} &= ₹3,435.00 + ₹620.00 = \mathbf{₹4,055.00} \\
\text{Direct Labour Overheads} &= ₹1,200.00 \\
\text{Power \& Fuel Overheads} &= ₹600.00 \\
\text{Total Production Cost} &= ₹4,055.00 + ₹1,200.00 + ₹600.00 = \mathbf{₹5,855.00} \\
\text{Cost Per Packet} &= \frac{₹5,855.00}{188\text{ pkts}} = \mathbf{₹31.1436 \implies ₹31.14} \\
\text{Gross Margin Per Packet} &= ₹50.00 - ₹31.1436 = \mathbf{₹18.8564 \implies ₹18.86} \\
\text{Gross Margin Percentage} &= \frac{₹18.8564}{₹50.00} \times 100 = \mathbf{37.71\%}
\end{aligned}$$

### D. GST Tax Invoice (Intra-state Tamil Nadu)
$$\text{Taxable Amount} = 150 \times ₹50.00 = ₹7,500.00$$
$$\text{CGST @ 2.5\%} = ₹7,500.00 \times 0.025 = \mathbf{₹187.50}$$
$$\text{SGST @ 2.5\%} = ₹7,500.00 \times 0.025 = \mathbf{₹187.50}$$
$$\text{IGST @ 0.0\%} = \mathbf{₹0.00}$$
$$\text{Invoice Grand Total} = ₹7,500.00 + ₹187.50 + ₹187.50 = \mathbf{₹7,875.00}$$
$$\text{Partial Payment Received} = ₹4,000.00$$
$$\text{Outstanding Balance} = ₹7,875.00 - ₹4,000.00 = \mathbf{₹3,875.00}$$

### E. Stock Shortage Analysis (Distributor B)
$$\text{Finished Goods Opening Stock} = 50\text{ pkts}$$
$$\text{Production Good Output} = +188\text{ pkts}$$
$$\text{Dispatched to Retailer A} = -150\text{ pkts}$$
$$\text{Available Stock at Time of Verification} = 50 + 188 - 150 = \mathbf{88\text{ pkts}}$$
$$\text{Distributor B Order Quantity} = 120\text{ pkts}$$
$$\text{Stock Shortage} = 120 - 88 = \mathbf{32\text{ pkts Shortage}}$$
$$\text{System Action} \implies \textbf{Dispatch Blocked (ValidationError Raised)}$$
