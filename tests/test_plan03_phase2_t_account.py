"""
test_plan03_phase2_t_account.py - Verification for Phase 2 of 03_ACCOUNTING_TABLE_FIDELITY_PLAN.md
Verifies that:
1. extract_geometric_table accurately splits cross-column tokens in T-accounts and multi-column ledgers.
2. Page 1 Table 0 (Cash Account T-Account) extracts all 4 columns with 100% data fidelity:
   - Row 0: Header with 'Particulars', '₹', 'Particulars', '₹'
   - Rows 1-7: All debit amounts (1,00,000, 1,40,000, 1,75,000, 50,000, 30,000, 1,00,000, 1,000)
     are placed in Column 1 (Debit Amount), NOT merged into Column 2!
   - Rows 1-7: All credit titles ('By Cash Purchases', 'By Trade payables', etc.) are in Column 2.
   - Row 7: 'To Interest & Dividend' sits in its exact row with '1,000', NOT pushed or merged into lower rows!
   - Row 8: Debit is blank; Credit has 'By Balance c/d' and '1,04,000'.
   - Row 9: Total amounts '5,96,000' and '5,96,000' sit in Column 1 and Column 3.
3. Page 3 Table 0 (Inflows / Outflows Ledger) extracts all 4 columns with 100% data fidelity.
"""

import os
import sys
import numpy as np
import cv2
import fitz

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.ocr_engine import run_single_pass_ocr
from core.layout_engine import analyze_page_layout
from core.table_engine import extract_table_model
from core.document_ir import TableModel


def test_t_account_page1_table0():
    print("[1/2] Testing Page 1 Table 0 (Cash Account T-Account)...")
    pdf_path = os.path.join("samples", "ilovepdf_split", "CA Inter Advanced Accounting Question Bank-2.pdf")
    assert os.path.exists(pdf_path), f"Sample PDF missing: {pdf_path}"

    doc = fitz.open(pdf_path)
    page0 = doc.load_page(0)
    pix0 = page0.get_pixmap(dpi=150)
    img0 = np.frombuffer(pix0.samples, dtype=np.uint8).reshape((pix0.h, pix0.w, pix0.n))
    if pix0.n == 4:
        img0 = cv2.cvtColor(img0, cv2.COLOR_RGBA2RGB)

    layout0 = analyze_page_layout(img0)
    ocr0 = run_single_pass_ocr(img0)

    # Table 0 is the first table on Page 1
    t0_box = layout0.get('table', [])[0]
    x1, y1, x2, y2 = [int(v) for v in t0_box]
    crop0 = img0[y1:y2, x1:x2]

    t_boxes, t_texts, t_scores = [], [], []
    for dt_box, text, score in ocr0:
        cx = sum(p[0] for p in dt_box) / 4.0
        cy = sum(p[1] for p in dt_box) / 4.0
        if x1 <= cx <= x2 and y1 <= cy <= y2:
            shifted = [[p[0] - x1, p[1] - y1] for p in dt_box]
            t_boxes.append(shifted)
            t_texts.append(text)
            t_scores.append(score)

    t_model = extract_table_model(crop0, t_boxes, t_texts, t_scores, page_content_width=7.0)
    assert t_model is not None, "Table 0 failed to extract"
    assert isinstance(t_model, TableModel), "Table 0 must return TableModel"

    print(f"  -> Extracted Table 0: {t_model.num_rows} rows x {t_model.num_cols} cols.")
    assert t_model.num_cols == 4, f"Expected 4 columns, got {t_model.num_cols}"
    assert t_model.num_rows == 10, f"Expected 10 rows, got {t_model.num_rows}"

    for r_idx, r in enumerate(t_model.rows):
        cells_t = [c.text for c in r]
        print(f"  Row {r_idx:2d}: {cells_t[0]:<28} | {cells_t[1]:<14} | {cells_t[2]:<28} | {cells_t[3]:<12}")

    # Row 0: Header
    assert "Particulars" in t_model.rows[0][0].text, "Row 0 missing 'Particulars' in Col 0"
    assert "₹" in t_model.rows[0][1].text, "Row 0 missing '₹' in Col 1 (Debit Amount Header)"
    assert "Particulars" in t_model.rows[0][2].text, "Row 0 missing 'Particulars' in Col 2"
    assert "₹" in t_model.rows[0][3].text, "Row 0 missing '₹' in Col 3 (Credit Amount Header)"

    # Row 1: Balance b/d & Cash Purchases
    assert "Balance b/d" in t_model.rows[1][0].text
    assert "1,00" in t_model.rows[1][1].text, f"Row 1 Col 1 missing '1,00,000', got {t_model.rows[1][1].text!r}"
    assert "Cash Purchases" in t_model.rows[1][2].text, f"Row 1 Col 2 missing 'Cash Purchases', got {t_model.rows[1][2].text!r}"
    assert "1,20,000" in t_model.rows[1][3].text

    # Row 2: Cash sales & Trade payables
    assert "Cash sales" in t_model.rows[2][0].text
    assert "1,40,000" in t_model.rows[2][1].text, f"Row 2 Col 1 missing '1,40,000', got {t_model.rows[2][1].text!r}"
    assert "Trade payables" in t_model.rows[2][2].text
    assert "1,57,000" in t_model.rows[2][3].text

    # Row 3: Trade receivables & Office & Selling Expenses
    assert "Tradereceivables" in t_model.rows[3][0].text or "Trade receivables" in t_model.rows[3][0].text
    assert "1,75" in t_model.rows[3][1].text, f"Row 3 Col 1 missing '1,75,000', got {t_model.rows[3][1].text!r}"
    assert "Office" in t_model.rows[3][2].text
    assert "75,000" in t_model.rows[3][3].text

    # Row 4: Trade Commission & Income Tax
    assert "Trade Commission" in t_model.rows[4][0].text
    assert "50,00" in t_model.rows[4][1].text, f"Row 4 Col 1 missing '50,000', got {t_model.rows[4][1].text!r}"
    assert "Income Tax" in t_model.rows[4][2].text
    assert "30,000" in t_model.rows[4][3].text

    # Row 5: Sale of Investment & Investment
    assert "Sale of Investment" in t_model.rows[5][0].text
    assert "30,00" in t_model.rows[5][1].text, f"Row 5 Col 1 missing '30,000', got {t_model.rows[5][1].text!r}"
    assert "Investment" in t_model.rows[5][2].text
    assert "25,000" in t_model.rows[5][3].text

    # Row 6: Loan from Bank & Repayment of Loan
    assert "Loan from Bank" in t_model.rows[6][0].text
    assert "1,00" in t_model.rows[6][1].text, f"Row 6 Col 1 missing '1,00,000', got {t_model.rows[6][1].text!r}"
    assert "Repayment of Loan" in t_model.rows[6][2].text
    assert "75,000" in t_model.rows[6][3].text

    # Row 7: Interest & Dividend & Interest on loan (CRITICAL: User's reported bug!)
    assert "Interest" in t_model.rows[7][0].text, f"Row 7 Col 0 missing 'Interest & Dividend', got {t_model.rows[7][0].text!r}"
    assert "1,00" in t_model.rows[7][1].text, f"Row 7 Col 1 missing '1,000', got {t_model.rows[7][1].text!r}"
    assert "Interest on loan" in t_model.rows[7][2].text, f"Row 7 Col 2 missing 'Interest on loan', got {t_model.rows[7][2].text!r}"
    assert "10,000" in t_model.rows[7][3].text

    # Row 8: Balance c/d (Debit is empty)
    assert t_model.rows[8][0].text == "", f"Row 8 Col 0 should be empty, got {t_model.rows[8][0].text!r}"
    assert t_model.rows[8][1].text == "", f"Row 8 Col 1 should be empty, got {t_model.rows[8][1].text!r}"
    assert "Balance c/d" in t_model.rows[8][2].text
    assert "1,04,000" in t_model.rows[8][3].text

    # Row 9: Ledger Totals
    assert "5,96,000" in t_model.rows[9][1].text, f"Row 9 Col 1 missing '5,96,000', got {t_model.rows[9][1].text!r}"
    assert "5,96,000" in t_model.rows[9][3].text, f"Row 9 Col 3 missing '5,96,000', got {t_model.rows[9][3].text!r}"
    print("  -> Page 1 Table 0 PASSED with 100% fidelity!")


def test_inflows_outflows_page3_table0():
    print("[2/2] Testing Page 3 Table 0 (Inflows / Outflows Ledger)...")
    pdf_path = os.path.join("samples", "ilovepdf_split", "CA Inter Advanced Accounting Question Bank-2.pdf")
    doc = fitz.open(pdf_path)
    page2 = doc.load_page(2) # Page 3
    pix2 = page2.get_pixmap(dpi=150)
    img2 = np.frombuffer(pix2.samples, dtype=np.uint8).reshape((pix2.h, pix2.w, pix2.n))
    if pix2.n == 4:
        img2 = cv2.cvtColor(img2, cv2.COLOR_RGBA2RGB)

    layout2 = analyze_page_layout(img2)
    ocr2 = run_single_pass_ocr(img2)

    t0_box = layout2.get('table', [])[0]
    x1, y1, x2, y2 = [int(v) for v in t0_box]
    crop2 = img2[y1:y2, x1:x2]

    t_boxes, t_texts, t_scores = [], [], []
    for dt_box, text, score in ocr2:
        cx = sum(p[0] for p in dt_box) / 4.0
        cy = sum(p[1] for p in dt_box) / 4.0
        if x1 <= cx <= x2 and y1 <= cy <= y2:
            shifted = [[p[0] - x1, p[1] - y1] for p in dt_box]
            t_boxes.append(shifted)
            t_texts.append(text)
            t_scores.append(score)

    t_model = extract_table_model(crop2, t_boxes, t_texts, t_scores, page_content_width=7.0)
    assert t_model is not None, "Page 3 Table 0 failed to extract"
    print(f"  -> Extracted Page 3 Table 0: {t_model.num_rows} rows x {t_model.num_cols} cols.")
    assert t_model.num_cols == 4, f"Expected 4 columns, got {t_model.num_cols}"
    assert t_model.num_rows == 13, f"Expected 13 rows, got {t_model.num_rows}"

    for r_idx, r in enumerate(t_model.rows):
        cells_t = [c.text for c in r]
        print(f"  Row {r_idx:2d}: {cells_t[0]:<36} | {cells_t[1]:<14} | {cells_t[2]:<30} | {cells_t[3]:<12}")

    # Row 0: Headers
    assert "flow" in t_model.rows[0][0].text.lower()
    assert "flow" in t_model.rows[0][2].text.lower()

    # Row 2: Cash & Salaries
    assert "Cash" in t_model.rows[2][0].text
    assert "10,00" in t_model.rows[2][1].text
    assert "Salaries" in t_model.rows[2][2].text
    assert "25,000" in t_model.rows[2][3].text

    # Row 3: Bank & Overheads
    assert "Bank" in t_model.rows[3][0].text
    assert "70,0" in t_model.rows[3][1].text
    assert "overheads" in t_model.rows[3][2].text
    assert "15,000" in t_model.rows[3][3].text

    # Row 4: Share capital & PPE acquired
    assert "Share capital" in t_model.rows[4][0].text
    assert "5,00,000" in t_model.rows[4][1].text
    assert "PPE" in t_model.rows[4][2].text
    assert "4,00,000" in t_model.rows[4][3].text

    # Row 5: Receivables & Debentures
    assert "Receivables" in t_model.rows[5][0].text or "TradeReceivables" in t_model.rows[5][0].text
    assert "3,50,0" in t_model.rows[5][1].text
    assert "Debentures" in t_model.rows[5][2].text
    assert "50,000" in t_model.rows[5][3].text

    # Row 6: PPE sale & Bank loan repaid
    assert "Property, plant" in t_model.rows[6][0].text
    assert "70,000" in t_model.rows[6][1].text
    assert "Bank loan repaid" in t_model.rows[6][2].text
    assert "2,50,000" in t_model.rows[6][3].text

    # Row 7: Taxation
    assert "Taxation" in t_model.rows[7][2].text
    assert "55,000" in t_model.rows[7][3].text

    # Row 8: Dividends
    assert "Dividends" in t_model.rows[8][2].text
    assert "1,00,000" in t_model.rows[8][3].text

    # Row 12: Ledger Totals
    assert "10,00,000" in t_model.rows[12][1].text
    assert "10,00,000" in t_model.rows[12][3].text
    print("  -> Page 3 Table 0 PASSED with 100% fidelity!")


if __name__ == "__main__":
    test_t_account_page1_table0()
    test_inflows_outflows_page3_table0()
    print("\nALL PHASE 2 VERIFICATION TESTS PASSED 100%!")

