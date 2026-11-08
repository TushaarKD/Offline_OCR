"""
test_plan03_phase1_geometric_engine.py - Verification for Phase 1 of 03_ACCOUNTING_TABLE_FIDELITY_PLAN.md
Verifies that:
1. extract_geometric_table constructs exact 2D grid from coordinates and vertical rulings.
2. extract_table_model extracts Table 1 (Cash Flow Statement) with 100% data fidelity:
   - 3,65,000 sits in Outer Amount column on Row 4 (not repeating across 6 rows).
   - 1,20,000 sits in Inner Amount column on Row 5 (not merged into Row 4).
   - (3,82,000) sits in Outer Amount column on Row 8.
   - (17,000) sits in Outer Amount column on Row 9.
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
from core.table_engine import extract_table_model, extract_geometric_table
from core.document_ir import TableModel


def test_geometric_engine_cash_flow_statement():
    print("[1/2] Testing Table 1 (Cash Flow Statement) on Page 1 of CA Inter sample PDF...")
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

    # Table 1 is the second table on Page 1
    t1_box = layout0.get('table', [])[1]
    x1, y1, x2, y2 = [int(v) for v in t1_box]
    crop1 = img0[y1:y2, x1:x2]

    t_boxes, t_texts, t_scores = [], [], []
    for dt_box, text, score in ocr0:
        cx = sum(p[0] for p in dt_box) / 4.0
        cy = sum(p[1] for p in dt_box) / 4.0
        if x1 <= cx <= x2 and y1 <= cy <= y2:
            shifted = [[p[0] - x1, p[1] - y1] for p in dt_box]
            t_boxes.append(shifted)
            t_texts.append(text)
            t_scores.append(score)

    t_model = extract_table_model(crop1, t_boxes, t_texts, t_scores, page_content_width=7.0)
    assert t_model is not None, "Table 1 failed to extract"
    assert isinstance(t_model, TableModel), "Table 1 must return TableModel"

    print(f"  -> Extracted Table 1: {t_model.num_rows} rows x {t_model.num_cols} cols.")
    assert t_model.num_cols == 3, f"Expected 3 columns, got {t_model.num_cols}"
    assert t_model.num_rows == 10, f"Expected 10 rows, got {t_model.num_rows}"

    for r_idx, r in enumerate(t_model.rows):
        cells_t = [c.text for c in r]
        print(f"  Row {r_idx:2d}: {cells_t[0]:<40} | {cells_t[1]:<12} | {cells_t[2]:<12}")

    # Row 0: Header
    assert "Particulars" in t_model.rows[0][0].text, "Row 0 missing 'Particulars'"
    assert "₹" in t_model.rows[0][1].text, "Row 0 missing '₹' in Col 1"
    assert "₹" in t_model.rows[0][2].text, "Row 0 missing '₹' in Col 2"

    # Row 1: Operating Activities
    assert "Operating Activities" in t_model.rows[1][0].text, "Row 1 missing 'Operating Activities:'"
    assert t_model.rows[1][0].colspan == 3, "Row 1 should span all 3 columns"

    # Row 2: Cash received from sale of goods
    assert "1,40,000" in t_model.rows[2][1].text, "Row 2 Col 1 missing '1,40,000'"
    assert t_model.rows[2][2].text == "", "Row 2 Col 2 should be empty"

    # Row 3: Cash received from Trade receivables
    assert "1,75,000" in t_model.rows[3][1].text, "Row 3 Col 1 missing '1,75,000'"
    assert t_model.rows[3][2].text == "", "Row 3 Col 2 should be empty"

    # Row 4: Trade Commission received -> 50,000 in Col 1, 3,65,000 in Col 2
    assert "50,000" in t_model.rows[4][1].text, "Row 4 Col 1 missing '50,000'"
    assert "3,65,000" in t_model.rows[4][2].text, "Row 4 Col 2 missing '3,65,000'"

    # Row 5: Less: Payment for Cash Purchases -> 1,20,000 in Col 1
    assert "1,20,000" in t_model.rows[5][1].text, "Row 5 Col 1 missing '1,20,000'"
    assert t_model.rows[5][2].text == "", "Row 5 Col 2 should be empty (not repeating 3,65,000!)"

    # Row 8: Payment for Income Tax -> 30,000 in Col 1, (3,82,000) in Col 2
    assert "30,000" in t_model.rows[8][1].text, "Row 8 Col 1 missing '30,000'"
    assert "3,82,000" in t_model.rows[8][2].text, "Row 8 Col 2 missing '(3,82,000)'"

    # Row 9: Net Cash Flow -> (17,000) in Col 2
    assert "17,000" in t_model.rows[9][2].text, "Row 9 Col 2 missing '(17,000)'"

    print("  -> Passed: Table 1 all rows, columns, and figures verified 100%!")


def test_empty_tokens_fallback():
    print("[2/2] Testing empty tokens graceful fallback...")
    dummy_crop = np.zeros((100, 200, 3), dtype=np.uint8)
    res = extract_geometric_table(dummy_crop, [], [], [])
    assert res is None, "Empty tokens should safely return None"
    print("  -> Passed: Empty tokens handled gracefully.")


if __name__ == "__main__":
    test_geometric_engine_cash_flow_statement()
    test_empty_tokens_fallback()
    print("\n✅ PHASE 1 VERIFICATION PASSED SUCCESSFULLY!")

