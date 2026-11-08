"""
test_plan02_phase3_currency.py - Verification for Phase 3 of 02_TABLE_EXTRACTION_REGRESSION_PLAN.md
Verifies that:
1. restore_currency_symbols restores Indian Rupee symbol (₹) across standalone cells,
   parentheses, headers, and numeric amounts without altering authentic question marks.
2. extract_table_model on Page 1 tables produces '₹' instead of '天' for currency cells.
"""

import os
import sys
import numpy as np
import cv2
import fitz

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.ocr_engine import restore_currency_symbols, run_single_pass_ocr
from core.layout_engine import analyze_page_layout
from core.table_engine import extract_table_model


def test_restore_currency_symbols_rules():
    print("[1/2] Testing restore_currency_symbols unit rules...")
    cases = [
        ("天", "₹"),
        ("?", "₹"),
        ("？", "₹"),
        ("Particulars | 天 | Particulars | 天", "Particulars | ₹ | Particulars | ₹"),
        ("Particulars 天 Particulars 天", "Particulars ₹ Particulars ₹"),
        ("Amount in 天", "Amount in ₹"),
        ("Balance at 1.3.20X1: 天 35,000", "Balance at 1.3.20X1: ₹ 35,000"),
        ("? 1,20,000", "₹ 1,20,000"),
        ("天 50,000", "₹ 50,000"),
        ("outflow of₹ 25 lakhs", "outflow of ₹ 25 lakhs"),
        ("(天 in lakhs)", "(₹ in lakhs)"),
        ("(?)", "(₹)"),
        ("(? in '000)", "(₹ in '000)"),
        ("What is AS 3?", "What is AS 3?"),
        ("Calculate cash flows?", "Calculate cash flows?"),
    ]

    for inp, expected in cases:
        out = restore_currency_symbols(inp)
        assert out == expected, f"Failed for '{inp}': expected '{expected}', got '{out}'"

    print("  -> Passed: All 15 currency restoration rules verified 100%!")


def test_page1_table_currency_restoration():
    print("[2/2] Testing Page 1 real accounting table currency restoration...")
    pdf_path = os.path.join("samples", "ilovepdf_split", "CA Inter Advanced Accounting Question Bank-2.pdf")
    assert os.path.exists(pdf_path), f"Sample PDF missing: {pdf_path}"

    doc = fitz.open(pdf_path)
    page = doc.load_page(0)
    pix = page.get_pixmap(dpi=150)
    img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.h, pix.w, pix.n))
    if pix.n == 4:
        img_np = cv2.cvtColor(img_np, cv2.COLOR_RGBA2RGB)

    layout = analyze_page_layout(img_np)
    raw_ocr = run_single_pass_ocr(img_np)
    table_boxes = layout.get('table', [])

    # Check Table 0 (T-account) and Table 1 (Cash flow)
    for idx in range(min(2, len(table_boxes))):
        t_box = table_boxes[idx]
        x1, y1, x2, y2 = [int(v) for v in t_box]
        pad = 6
        x1, y1 = max(0, x1 - pad), max(0, y1 - pad)
        x2, y2 = min(img_np.shape[1], x2 + pad), min(img_np.shape[0], y2 + pad)
        crop = img_np[y1:y2, x1:x2]

        t_boxes, t_texts, t_scores = [], [], []
        for dt_box, text, score in raw_ocr:
            cx = sum(p[0] for p in dt_box) / 4.0
            cy = sum(p[1] for p in dt_box) / 4.0
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                shifted = [[p[0] - x1, p[1] - y1] for p in dt_box]
                t_boxes.append(shifted)
                t_texts.append(text)
                t_scores.append(score)

        t_model = extract_table_model(crop, t_boxes, t_texts, t_scores, page_content_width=7.0)
        assert t_model is not None, f"Table {idx} failed to extract"

        all_cell_texts = [cell.text for row in t_model.rows for cell in row]
        # Assert NO '天' exists anywhere in the table cells
        for c_text in all_cell_texts:
            assert "天" not in c_text, f"Table {idx} still contains un-restored '天': '{c_text}'"

        # Assert at least one cell has the restored '₹' symbol
        has_rupee = any("₹" in c_text for c_text in all_cell_texts)
        print(f"  -> Table {idx}: checked {len(all_cell_texts)} cells. Contains '₹': {has_rupee}, Contains '天': False.")
        assert has_rupee, f"Table {idx} expected restored '₹' in header/cells!"

    print("  -> Passed: Real table currency restoration verified on Page 1.")


if __name__ == "__main__":
    test_restore_currency_symbols_rules()
    test_page1_table_currency_restoration()
    print("\n✅ PHASE 3 VERIFICATION PASSED SUCCESSFULLY!")

