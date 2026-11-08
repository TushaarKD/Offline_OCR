"""
test_plan03_phase4_healing.py - Verification for Phase 4 of 03_ACCOUNTING_TABLE_FIDELITY_PLAN.md
Verifies that:
1. heal_financial_text eliminates CTC zero-confusions ('oo' -> '00', 'o' -> '0') in amounts.
2. Corrects header unit typos like (3'000) -> ('000).
3. Restores compound accounting word spacing (e.g. Tradereceivables -> Trade receivables).
4. Page 1 Table 0 extracted numbers are cleanly healed:
   - Row 1: 1,00,000 (was 1,00,0 oo)
   - Row 3: 1,75,000 (was 1,75,0 oo)
   - Row 4: 50,000 (was 50,00 o)
   - Row 5: 30,000 (was 30,00o)
   - Row 6: 1,00,000 (was 1,00,0 oo)
   - Row 7: 1,000 (was 1,00o)
5. Page 3 Table 0 extracted numbers are cleanly healed:
   - Row 2: 10,000 (was 10,00o)
   - Row 3: 70,000 (was 70,0 oo)
   - Row 5: 3,50,000 (was 3,50,0 oo)
"""

import os
import sys
import numpy as np
import cv2
import fitz

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.ocr_engine import heal_financial_text, clean_text_spacing, run_single_pass_ocr
from core.layout_engine import analyze_page_layout
from core.table_engine import extract_table_model


def test_unit_healing_rules():
    print("[1/3] Testing unit financial number and typography healing rules...")
    test_cases = [
        ('1,00,0 oo', '1,00,000'),
        ('70,0 oo', '70,000'),
        ('30,00o', '30,000'),
        ('50,00 o', '50,000'),
        ('1,00o', '1,000'),
        ('10,00o', '10,000'),
        ('1,75,0 oo', '1,75,000'),
        ('3,50,0 oo', '3,50,000'),
        ("(3'000)", "('000)"),
        ("(₹ in 3'000)", "(₹ in '000)"),
        ('Tradereceivables', 'Trade receivables'),
        ('Payment forAccountPayables', 'Payment for Account Payables'),
        ('accountoftradepayables', 'account of trade payables'),
        ('NetCashFlowusedinOperatingActivities', 'Net Cash Flow used in Operating Activities'),
        ('Payment ofoverheads', 'Payment of overheads'),
        ('Debenturesredeemed', 'Debentures redeemed')
    ]

    for raw, expected in test_cases:
        healed = clean_text_spacing(raw)
        assert healed == expected, f"Failed healing on {raw!r}: expected {expected!r}, got {healed!r}"

    print("  -> Unit healing rules PASSED 100%!")


def test_page1_table0_healed_amounts():
    print("[2/3] Testing Page 1 Table 0 (Cash Account T-Account) with healed numbers...")
    pdf_path = os.path.join("samples", "ilovepdf_split", "CA Inter Advanced Accounting Question Bank-2.pdf")
    doc = fitz.open(pdf_path)
    page0 = doc.load_page(0)
    pix0 = page0.get_pixmap(dpi=150)
    img0 = np.frombuffer(pix0.samples, dtype=np.uint8).reshape((pix0.h, pix0.w, pix0.n))
    if pix0.n == 4:
        img0 = cv2.cvtColor(img0, cv2.COLOR_RGBA2RGB)

    layout0 = analyze_page_layout(img0)
    ocr0 = run_single_pass_ocr(img0)

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

    # Row 1: 1,00,000 (was 1,00,0 oo)
    assert t_model.rows[1][1].text == "1,00,000", f"Row 1 Col 1 expected '1,00,000', got {t_model.rows[1][1].text!r}"

    # Row 2: 1,40,000
    assert t_model.rows[2][1].text == "1,40,000"

    # Row 3: 1,75,000 (was 1,75,0 oo)
    assert t_model.rows[3][1].text == "1,75,000", f"Row 3 Col 1 expected '1,75,000', got {t_model.rows[3][1].text!r}"

    # Row 4: 50,000 (was 50,00 o)
    assert t_model.rows[4][1].text == "50,000", f"Row 4 Col 1 expected '50,000', got {t_model.rows[4][1].text!r}"

    # Row 5: 30,000 (was 30,00o)
    assert t_model.rows[5][1].text == "30,000", f"Row 5 Col 1 expected '30,000', got {t_model.rows[5][1].text!r}"

    # Row 6: 1,00,000 (was 1,00,0 oo)
    assert t_model.rows[6][1].text == "1,00,000", f"Row 6 Col 1 expected '1,00,000', got {t_model.rows[6][1].text!r}"

    # Row 7: 1,000 (was 1,00o)
    assert t_model.rows[7][1].text == "1,000", f"Row 7 Col 1 expected '1,000', got {t_model.rows[7][1].text!r}"

    # Row 9: 5,96,000
    assert t_model.rows[9][1].text == "5,96,000"
    assert t_model.rows[9][3].text == "5,96,000"

    print("  -> Page 1 Table 0 healed amounts PASSED 100%!")


def test_page3_table0_healed_amounts():
    print("[3/3] Testing Page 3 Table 0 (Inflows / Outflows) with healed numbers...")
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

    # Row 2: 10,000 (was 10,00o)
    assert t_model.rows[2][1].text == "10,000", f"Row 2 Col 1 expected '10,000', got {t_model.rows[2][1].text!r}"

    # Row 3: 70,000 (was 70,0 oo)
    assert t_model.rows[3][1].text == "70,000", f"Row 3 Col 1 expected '70,000', got {t_model.rows[3][1].text!r}"

    # Row 5: 3,50,000 (was 3,50,0 oo)
    assert t_model.rows[5][1].text == "3,50,000", f"Row 5 Col 1 expected '3,50,000', got {t_model.rows[5][1].text!r}"

    # Row 12: 10,00,000
    assert t_model.rows[12][1].text == "10,00,000"
    assert t_model.rows[12][3].text == "10,00,000"

    print("  -> Page 3 Table 0 healed amounts PASSED 100%!")


if __name__ == "__main__":
    test_unit_healing_rules()
    test_page1_table0_healed_amounts()
    test_page3_table0_healed_amounts()
    print("\nALL PHASE 4 VERIFICATION TESTS PASSED 100%!")

