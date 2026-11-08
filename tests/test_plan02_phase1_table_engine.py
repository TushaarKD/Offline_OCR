"""
test_plan02_phase1_table_engine.py - Verification for Phase 1 of 02_TABLE_EXTRACTION_REGRESSION_PLAN.md
Verifies that:
1. RapidTable is initialized with use_ocr=True.
2. extract_table_model handles empty OCR tokens without crashing.
3. extract_table_model successfully extracts all 3 tables on Page 1 of CA Inter Advanced Accounting Question Bank-2.pdf.
"""

import os
import sys
import numpy as np
import cv2
import fitz

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.model_manager import get_table_engine
from core.table_engine import extract_table_model
from core.ocr_engine import run_single_pass_ocr
from core.layout_engine import analyze_page_layout
from core.document_ir import TableModel


def test_rapid_table_init():
    print("[1/3] Testing RapidTable initialization...")
    engine = get_table_engine()
    assert engine is not None, "RapidTable instance should not be None"
    assert engine.cfg.use_ocr is True, f"RapidTable cfg.use_ocr must be True, got {engine.cfg.use_ocr}"
    print("  -> Passed: RapidTable initialized with use_ocr=True.")


def test_extract_table_model_empty_tokens():
    print("[2/3] Testing extract_table_model with empty OCR tokens (graceful handling)...")
    dummy_crop = np.zeros((120, 240, 3), dtype=np.uint8)
    res = extract_table_model(dummy_crop, [], [], [])
    # Should not raise exception; can return TableModel or None
    print(f"  -> Returned: {type(res).__name__}")
    print("  -> Passed: No crash on empty tokens.")


def test_page1_table_extractions():
    print("[3/3] Testing Page 1 table extraction on CA Inter sample PDF...")
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
    print(f"  -> Detected {len(table_boxes)} table bounding boxes on Page 1.")
    assert len(table_boxes) == 3, f"Expected 3 table boxes on Page 1, got {len(table_boxes)}"

    extracted_models = []
    for idx, t_box in enumerate(table_boxes):
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
        assert t_model is not None, f"Table {idx} failed to extract (returned None)!"
        assert isinstance(t_model, TableModel), f"Table {idx} did not return TableModel"
        assert t_model.num_rows > 0, f"Table {idx} has 0 rows"
        assert t_model.num_cols > 0, f"Table {idx} has 0 columns"

        sample_cell = t_model.rows[0][0].text if t_model.rows and t_model.rows[0] else ""
        print(f"  -> Table {idx}: extracted {t_model.num_rows} rows x {t_model.num_cols} cols. Cell (0,0): '{sample_cell}'")
        extracted_models.append(t_model)

    assert len(extracted_models) == 3, f"Expected 3 extracted tables, got {len(extracted_models)}"
    print("  -> Passed: All 3 tables on Page 1 successfully extracted!")


if __name__ == "__main__":
    test_rapid_table_init()
    test_extract_table_model_empty_tokens()
    test_page1_table_extractions()
    print("\n✅ PHASE 1 VERIFICATION PASSED SUCCESSFULLY!")

