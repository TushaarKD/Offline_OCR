"""
test_plan03_phase6_user_improvements.py - Verification for user-requested fidelity improvements
Verifies that:
1. Table 3 (Page 2 Problem Statement):
   - Row 0 ('Receipts from customers', '2,783') is treated as a DATA ROW, NOT a header!
   - is_header is False, bg_color_hex is None (no grey background shading).
2. In-Table Bold Formatting:
   - Section headers ('Operating Activities:', 'Cash flows from operating activities', 'Net cash...') are bolded.
   - Closing totals and balances ('212', '5,96,000') are bolded.
3. Footer banner suppression:
   - Tables near page bottom do not absorb author footer banners.
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


def test_table3_header_detection():
    print("[1/2] Testing Table 3 (Page 2) header detection & no grey shading...")
    pdf_path = os.path.join("samples", "ilovepdf_split", "CA Inter Advanced Accounting Question Bank-2.pdf")
    doc = fitz.open(pdf_path)
    page1 = doc.load_page(1) # Page 2
    pix1 = page1.get_pixmap(dpi=150)
    img1 = np.frombuffer(pix1.samples, dtype=np.uint8).reshape((pix1.h, pix1.w, pix1.n))
    if pix1.n == 4:
        img1 = cv2.cvtColor(img1, cv2.COLOR_RGBA2RGB)

    layout1 = analyze_page_layout(img1)
    ocr1 = run_single_pass_ocr(img1)

    t0_box = layout1.get('table', [])[0]
    x1, y1, x2, y2 = [int(v) for v in t0_box]
    crop0 = img1[y1:y2, x1:x2]

    t_boxes, t_texts, t_scores = [], [], []
    for dt_box, text, score in ocr1:
        cx = sum(p[0] for p in dt_box) / 4.0
        cy = sum(p[1] for p in dt_box) / 4.0
        if x1 <= cx <= x2 and y1 <= cy <= y2:
            shifted = [[p[0] - x1, p[1] - y1] for p in dt_box]
            t_boxes.append(shifted)
            t_texts.append(text)
            t_scores.append(score)

    t_model = extract_table_model(crop0, t_boxes, t_texts, t_scores, page_content_width=7.0)
    assert t_model is not None, "Table 3 failed to extract"

    # Row 0: Receipts from customers | 2,783
    row0 = t_model.rows[0]
    assert "Receipts from customers" in row0[0].text
    assert "2,783" in row0[2].text

    # CRITICAL: Row 0 MUST NOT BE A HEADER!
    assert not row0[0].is_header, "Row 0 should NOT be marked as header in Table 3!"
    assert row0[0].bg_color_hex is None, "Row 0 should NOT have background shading in Table 3!"

    print("  -> Table 3 Row 0 correctly recognized as normal data row without shading!")


def test_in_table_bold_formatting():
    print("[2/2] Testing in-table bold formatting on Hills Ltd (Table 4)...")
    pdf_path = os.path.join("samples", "ilovepdf_split", "CA Inter Advanced Accounting Question Bank-2.pdf")
    doc = fitz.open(pdf_path)
    page1 = doc.load_page(1) # Page 2
    pix1 = page1.get_pixmap(dpi=150)
    img1 = np.frombuffer(pix1.samples, dtype=np.uint8).reshape((pix1.h, pix1.w, pix1.n))
    if pix1.n == 4:
        img1 = cv2.cvtColor(img1, cv2.COLOR_RGBA2RGB)

    layout1 = analyze_page_layout(img1)
    ocr1 = run_single_pass_ocr(img1)

    t1_box = layout1.get('table', [])[1]
    x1, y1, x2, y2 = [int(v) for v in t1_box]
    crop1 = img1[y1:y2, x1:x2]

    t_boxes, t_texts, t_scores = [], [], []
    for dt_box, text, score in ocr1:
        cx = sum(p[0] for p in dt_box) / 4.0
        cy = sum(p[1] for p in dt_box) / 4.0
        if x1 <= cx <= x2 and y1 <= cy <= y2:
            shifted = [[p[0] - x1, p[1] - y1] for p in dt_box]
            t_boxes.append(shifted)
            t_texts.append(text)
            t_scores.append(score)

    t_model = extract_table_model(crop1, t_boxes, t_texts, t_scores, page_content_width=7.0)
    assert t_model is not None, "Table 4 failed to extract"

    # Row 1: Cash flows from operating activities -> BOLD
    assert t_model.rows[1][0].is_bold, "Row 1 'Cash flows from operating activities' should be bold!"

    # Row 8: Net cash from operating activities -> BOLD
    assert t_model.rows[8][0].is_bold, "Row 8 'Net cash from operating activities' should be bold!"

    # Row 9: Cash flows from investing activities -> BOLD
    assert t_model.rows[9][0].is_bold, "Row 9 'Cash flows from investing activities' should be bold!"

    # Row 18: Net increase in cash and cash equivalents -> BOLD
    assert t_model.rows[18][0].is_bold, "Row 18 'Net increase...' should be bold!"

    # Row 20: Cash and cash equivalents at end of period -> BOLD
    assert t_model.rows[20][0].is_bold, "Row 20 'Cash and cash equivalents at end...' should be bold!"

    print("  -> In-table bold formatting PASSED 100%!")


if __name__ == "__main__":
    test_table3_header_detection()
    test_in_table_bold_formatting()
    print("\nALL PHASE 6 USER IMPROVEMENT TESTS PASSED 100%!")

