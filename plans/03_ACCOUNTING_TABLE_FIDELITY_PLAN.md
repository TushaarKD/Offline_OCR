# PLAN: 03_ACCOUNTING_TABLE_FIDELITY_PLAN.md

## 🎯 Executive Summary & Core Objective
Achieve **100% table accuracy and fidelity** across all scanned accounting and financial documents. Eliminate neural table hallucinations (such as SLANet+'s fake multi-row spans, dropped figures, and merged numbers) by implementing a **deterministic, industry-standard Geometric Table Engine**. Guarantee that **every single raw number, account title, currency symbol, and ledger balance is placed in its exact physical row and column** with authentic accounting styling, adhering strictly to the **Zero-Manipulation Protocol** and **Native Word Flow Architecture** in `AGENT.md`.

---

## 🔍 Root Cause Analysis & Problem Scope

### 1. The Neural SLANet+ "Rowspan Hallucination" Failure
- **Root Cause**: Neural table models (SLANet+/RapidTable) are trained on scientific papers and bordered forms. When presented with borderless financial statements (where details sit in Column 1 and subtotals sit in Column 2), the network misinterprets whitespace as empty multi-row spans (`<td rowspan="6">`, `<td rowspan="8">`).
- **Impact**: Subtotals like `3,65,000` repeat across 6 rows, adjacent numbers are squashed together (e.g. `50,000 1,20,000`), and critical net figures (`(3,82,000)` and `(17,000)`) are completely dropped.

### 2. Cross-Column Token Grouping in T-Accounts
- **Root Cause**: In 4-column T-accounts (Debit Particulars, Debit ₹, Credit Particulars, Credit ₹), the Debit Amount column ends right against the vertical divider where Credit Particulars begin. The OCR text detector groups both across the divider into one box (e.g. `1,00,0 oo|By Cash Purchases`).
- **Impact**: Column 1 (Debit Amount) becomes completely blank, while Column 2 receives both the number and the credit title. In rows where Debit has fewer items than Credit, the last Debit item (`To Interest & Dividend`) is pushed and repeated down the table.

### 3. Ugly Gridlines vs. Authentic Textbook Formatting
- **Root Cause**: Applying Word's `Table Grid` style draws heavy black border boxes around every single cell. In the original book, there are **no interior horizontal row lines**—only a top border, header underline, and total underline.
- **Impact**: Cluttered, unauthentic Excel-like grid appearance.

### 4. OCR Digit Confusion on Financial Zeros
- **Root Cause**: CTC decoding frequently recognizes `00` as `oo` (lowercase letter 'o') or `0 oo` in numbers like `1,00,0 oo`, `70,0 oo`, `30,00o`, `50,00 o`.

### 5. Non-Table Elements Misclassified as Tables
- **Root Cause**: Outline boxes around problem text or numbered question points (e.g. Question 11's 15 points) are misclassified by layout analysis as tables instead of native Word paragraphs/lists.

---

## 📋 Implementation Roadmap (Strictly Step-by-Step)

### Phase 1: Deterministic Geometric Table Engine (Primary Grid Reconstruction)
- [x] Implement `extract_geometric_table(...)` in `core/table_engine.py`:
  - Automatically detect vertical column boundaries:
    - Extract printed vertical ruling lines via OpenCV morphological kernels.
    - If vertical lines are absent, detect vertical whitespace gutters (projection profiling across OCR tokens).
  - Cluster OCR tokens into rows based on vertical overlap ($y_0, y_1$).
  - Map each token directly into cell $(r, c)$ based on horizontal column intervals $(x_{start}, x_{end})$.
  - Mark single-item title rows (e.g. `Operating Activities:`) as spanning all columns (`colspan = num_cols`).
  - Leave empty cells genuinely empty (`""`) without any hallucinated rowspans.
- [x] Connect the Geometric Table Engine as the primary extractor for all tables in `core/table_engine.py` and `convert.py`.
- [x] **Verification Quality Gate**: Automated unit test verifying that Table 1 (Cash Flow Statement) on Page 1 extracts with 100% accuracy: `3,65,000` on Row 4, `1,20,000` on Row 5, `(3,82,000)` on Row 8, and `(17,000)` on Row 9 (`tests/test_plan03_phase1_geometric_engine.py` passed 100%).

---

### Phase 2: T-Account Cross-Column Token Splitting & Row Alignment
- [ ] Implement `split_cross_column_tokens(...)` in `core/table_engine.py`:
  - Identify tokens containing column dividers:
    - Tokens containing pipe characters: `[Amount] | By [Text]` or `[Amount] | [Text]`.
    - Tokens containing numbers followed immediately by `By ` or `To `: `1,40,000By Trade payables`, `50,00 oBy Income Tax`.
  - Split text and bounding boxes horizontally at the column boundary into two distinct tokens:
    - Left token assigned to Debit Amount (Column 1).
    - Right token assigned to Credit Particulars (Column 2).
- [ ] Implement independent debit/credit row alignment:
  - If Debit has 7 items and Credit has 8 items, align Debit items to rows 1..7 and leave rows 8..9 empty on the Debit side.
  - Fix "To Interest & Dividend" so it occupies exactly its one row without being pushed or repeated.
- [ ] **Verification Quality Gate**: Automated test on Page 1 Table 0 verifying all 4 columns: Debit Particulars, Debit Amount, Credit Particulars, and Credit Amount populated with exact numbers.

---

### Phase 3: Authentic Accounting Border & Flow Styling
- [ ] Update `_compile_table` in `core/docx_compiler.py`:
  - Set `w:insideH` to `none` (invisible interior horizontal lines) for tables that do not have printed interior row lines in the original document.
  - Draw borders only where they exist:
    - Top single border (`0.5pt`).
    - Header bottom border under `Particulars | ₹ | ₹` (`0.5pt`).
    - Total row double bottom border or single border.
    - Vertical column lines (`0.5pt`) where physical dividers exist.
  - Preserve `w:cantSplit` on all rows and `w:tblHeader` on header rows.
  - Enforce right-alignment for numeric cells, left-alignment for text, center for headers.
- [ ] **Verification Quality Gate**: Verify compiled Word XML contains `w:insideH val="none"`, `w:cantSplit`, and `w:tblHeader`.

---

### Phase 4: Financial Number & Digit Healing & Layout De-noising
- [ ] Enhance `core/ocr_engine.py` with `heal_financial_numbers(...)`:
  - Replace `oo` and trailing `o` with `00` and `0` when inside numeric amounts (e.g. `1,00,0 oo` $\rightarrow$ `1,00,000`, `70,0 oo` $\rightarrow$ `70,000`, `30,00o` $\rightarrow$ `30,000`, `50,00 o` $\rightarrow$ `50,000`, `1,00o` $\rightarrow$ `1,000`).
  - Fix header typos: `(3'000)` $\rightarrow$ `('000)`.
  - Fix compound accounting word spacing: `Tradereceivables` $\rightarrow$ `Trade receivables`, `Payment forAccountPayables` $\rightarrow$ `Payment for Account Payables`, `accountoftradepayables` $\rightarrow$ `account of trade payables`, `NetCashFlowusedinOperatingActivities` $\rightarrow$ `Net Cash Flow used in Operating Activities`.
- [ ] De-noise table bounding boxes:
  - Exclude author footer banners (`BY CA AJAY AGARWAL...`) from table crops.
  - Suppress false-positive 1-column single-paragraph "tables" (convert to normal text).
- [ ] **Verification Quality Gate**: Unit test asserting 100% healing of financial numbers and zero author footer banners inside tables.

---

### Phase 5: Full 5-Page Integration Verification & Quality Gate
- [ ] Run full end-to-end conversion on `samples/ilovepdf_split/CA Inter Advanced Accounting Question Bank-2.pdf` (pages 1 to 5).
- [ ] Verify all 14 tables in `samples/CA Inter Advanced Accounting Question Bank-2-1-5.docx`:
  - Table 0 (Cash Account T-Account): 4 clean columns, all debit and credit amounts in place.
  - Table 1 (Cash Flow Statement): 3 clean columns, all numbers in place, zero fake rowspans.
  - Table 3 & 4 (Hills Ltd): All receipts, payments, and net figures in place.
  - Table 5, 7, 8, 10, 11, 12, 13: 100% verified.
- [ ] Deliver a complete fidelity comparison report to the user.

---

## 🔒 Standing Operating Protocol (Reminder)
- **STRICTLY NO GIT ACTIONS**: No commits, staging, or pushes.
- **SINGLE-STEP EXECUTION**: Implement only one phase at a time; test and pause for user review before proceeding.

