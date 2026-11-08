# PLAN: 02_TABLE_EXTRACTION_REGRESSION_PLAN.md

## 🎯 Executive Summary & Core Objective
Resolve the severe table extraction regression observed in `samples/CA Inter Advanced Accounting Question Bank-2-1-5.docx` where **14 accounting tables were completely dropped** (resulting in 55 paragraphs and 0 tables). Restore full, native Microsoft Word table extraction with **100% data fidelity**, adhering strictly to the **Zero-Manipulation Protocol** and **Native Word Flow Architecture** outlined in `AGENT.md`.

---

## 🔍 Root Cause Analysis & Findings

### Finding 1: RapidTable `use_ocr=False` Disables Table Synthesis Completely
- **Location**: `core/model_manager.py` (line 85)
- **Root Cause**: During Phase 1 of `01_BACKEND_FIDELITY_PLAN.md`, `RapidTableInput(..., use_ocr=False)` was introduced under the assumption that it would prevent RapidTable from loading a secondary OCR model. However, in RapidTable's internal architecture (`rapid_table/main.py`), `if not self.cfg.use_ocr: continue` explicitly bypasses `self.table_matcher` and leaves `pred_htmls = []`.
- **Impact**: `extract_table_model(...)` in `core/table_engine.py` checks `if out and out.pred_htmls:`. Because `pred_htmls` is empty, `extract_table_model` immediately returns `None` for every single table.

### Finding 2: Premature Token Consumption in `convert.py` (Complete Text Loss)
- **Location**: `convert.py` (lines 103-121)
- **Root Cause**: In `convert.py`, OCR token indices inside detected table bounding boxes are added to `table_assigned_indices` **before** calling `extract_table_model`. When `extract_table_model` returns `None`, `if t_model:` evaluates to `False`, so no table is created. Later, in line 178, all tokens in `table_assigned_indices` are excluded from paragraph generation.
- **Impact**: Every number, account title, ledger balance, and header inside the table region was discarded from the document completely.

### Finding 3: Silent Exception Suppression in `core/table_engine.py`
- **Location**: `core/table_engine.py` (line 199)
- **Root Cause**: `extract_table_model` wraps execution in a blanket `try ... except Exception: pass`, concealing any model mismatches, parsing issues, or missing outputs without logging.

### Finding 4: Absence of Table Fallback Mechanism (Violation of Zero-Manipulation)
- **Location**: `core/table_engine.py` and `convert.py`
- **Root Cause**: If SLANet+ or RapidTable fails to parse complex borderless or multi-split tables, there was no fallback to synthesize a grid table from OCR row/column alignment or to release tokens back into the normal text stream.

### Finding 5: Currency Symbol Misrecognition (`₹` -> `天` / `?`) in Headers
- **Location**: `core/ocr_engine.py`
- **Root Cause**: Chinese-character-based recognition engines frequently recognize the Indian Rupee symbol `₹` as `天` (U+5929) or `?` / `？`. In accounting headers (e.g. `Particulars | ₹ | Particulars | ₹`), cells containing only `天` or `?` were not restored to `₹`.

---

## 📋 Implementation Roadmap (Strictly Step-by-Step)

### Phase 1: Re-activate Table Engine & Single-Pass OCR Coupling
- [x] Configure `core/model_manager.py` with `use_ocr=True` in `RapidTableInput`.
  - When `use_ocr=True`, RapidTable checks if `rapidocr` is installed; if not, it skips internal OCR and relies strictly on the caller-provided `ocr_results=[(t_boxes, t_texts, t_scores)]`.
- [x] Eliminate silent exception swallowing in `core/table_engine.py`: log detailed error traces if RapidTable fails.
- [x] **Verification Quality Gate**: Automated test script verifying that calling `extract_table_model` on Page 1 table crops produces valid `TableModel` instances with expected rows and columns (`tests/test_plan02_phase1_table_engine.py` passed).

---

### Phase 2: Fail-Safe Token Preservation & Fallback Mechanism (Zero Data Loss)
- [x] Refactor `convert.py` table token assignment:
  - Do NOT commit tokens to `table_assigned_indices` until `t_model` is verified non-null and successfully created.
  - If `extract_table_model` fails, release OCR tokens back into the page flow so no raw data or ledger text is lost.
- [x] Implement a spatial tabular fallback constructor in `core/table_engine.py`:
  - If neural SLANet+ fails to produce a structure but layout analysis detected a table and OCR items exist, cluster items by horizontal line and vertical columns into a native `TableModel`.
- [x] **Verification Quality Gate**: Unit test verifying that even if `extract_table_model` returns `None`, 100% of the OCR tokens are preserved in the document output (`tests/test_plan02_phase2_fallback.py` passed).

---

### Phase 3: Currency Symbol Restoration (`₹` vs `天` / `?`) in Tabular Context
- [x] Enhance `restore_currency_symbols()` in `core/ocr_engine.py`:
  - Replace `天` (`\u5929`) and `?` / `？` with `₹` when preceding numeric amounts (e.g. `天 1,20,000` -> `₹ 1,20,000`).
  - Recognize standalone column headers where the cell text is simply `天` or `?` and convert them to `₹`.
- [x] Apply `restore_currency_symbols()` systematically during cell text extraction in `core/table_engine.py`.
- [x] **Verification Quality Gate**: Test on accounting ledger headers ensuring `Particulars | 天 | Particulars | 天` becomes `Particulars | ₹ | Particulars | ₹` (`tests/test_plan02_phase3_currency.py` passed).

---

### Phase 4: Native Word Table Styling & Flow Fidelity
- [x] Ensure `core/docx_compiler.py` applies robust Word table formatting:
  - Add `w:cantSplit` to prevent individual table rows from splitting across page breaks.
  - Add `w:tblHeader` to table header rows so headers repeat seamlessly if a ledger spans pages.
  - Align numeric cells to the right and text cells to the left.
  - Apply clean borders (`Table Grid`) and header shading (`F2F4F7`).
- [x] **Verification Quality Gate**: Verify generated `.docx` table XML has proper borders, header flags, and row split prevention (`tests/test_plan02_phase4_styling.py` passed).

---

### Phase 5: Full 5-Page Regression & End-to-End Quality Gate
- [x] Run `convert_document` on `samples/ilovepdf_split/CA Inter Advanced Accounting Question Bank-2.pdf` (pages 1 to 5).
- [x] Assert that `len(doc.tables) >= 14` (Verified: exactly 14 native Word tables compiled).
- [x] Verify all Cash Flow statements, T-accounts, and ledger balances appear with exact figures.
- [x] Deliver a complete fidelity comparison report to the user (`tests/test_plan02_phase5_integration.py` passed 100%).

---

## 🔒 Standing Operating Protocol (Reminder)
- **STRICTLY NO GIT ACTIONS**: No commits, staging, or pushes.
- **SINGLE-STEP EXECUTION**: Implement only one phase at a time; test and pause for user feedback before proceeding.

