"""
test_plan02_phase2_fallback.py - Verification for Phase 2 of 02_TABLE_EXTRACTION_REGRESSION_PLAN.md
Verifies that:
1. build_fallback_table_model synthesizes valid TableModel from spatial token clustering.
2. If extract_table_model returns None, fallback constructs the table model.
3. If both neural and fallback table extraction return None, 100% of the candidate tokens are released to the text flow (Zero Data Loss Protocol).
"""

import os
import sys
import numpy as np
from unittest.mock import patch

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.table_engine import build_fallback_table_model
from core.document_ir import TableModel, PageModel, ParagraphModel
from convert import process_scanned_page_to_model


def test_build_fallback_table_model():
    print("[1/3] Testing build_fallback_table_model on synthetic 2-column table...")
    boxes = [
        [[10, 10], [100, 10], [100, 25], [10, 25]],
        [[200, 10], [250, 10], [250, 25], [200, 25]],
        [[10, 35], [80, 35], [80, 50], [10, 50]],
        [[200, 35], [245, 35], [245, 50], [200, 50]],
        [[10, 60], [50, 60], [50, 75], [10, 75]],
        [[200, 60], [245, 60], [245, 75], [200, 75]]
    ]
    texts = ["Particulars", "Amount", "Purchases", "10,000", "Sales", "25,000"]

    t_model = build_fallback_table_model(boxes, texts, crop_img=None, page_content_width=7.0)
    assert t_model is not None, "Fallback model should not be None"
    assert isinstance(t_model, TableModel), "Should return TableModel"
    assert t_model.num_rows == 3, f"Expected 3 rows, got {t_model.num_rows}"
    assert t_model.num_cols == 2, f"Expected 2 cols, got {t_model.num_cols}"

    assert t_model.rows[0][0].text == "Particulars"
    assert t_model.rows[0][1].text == "Amount"
    assert t_model.rows[1][0].text == "Purchases"
    assert t_model.rows[1][1].text == "10,000"
    assert t_model.rows[2][0].text == "Sales"
    assert t_model.rows[2][1].text == "25,000"
    print("  -> Passed: Fallback table model correctly built 3 rows x 2 cols.")


def test_token_release_when_table_fails():
    print("[2/3] Testing Zero Data Loss token release when table extraction fails...")
    # Create a synthetic image
    h, w = 400, 600
    dummy_img = np.full((h, w, 3), 255, dtype=np.uint8)

    mock_raw_ocr = [
        ([[10, 20], [80, 20], [80, 35], [10, 35]], "Header Text", 0.95),
        ([[50, 100], [150, 100], [150, 120], [50, 120]], "Table Token Alpha", 0.99),
        ([[200, 100], [280, 100], [280, 120], [200, 120]], "Table Token Beta", 0.99),
        ([[10, 300], [90, 300], [90, 320], [10, 320]], "Footer Text", 0.95)
    ]
    mock_layout = {
        'table': [[40, 90, 300, 150]]  # Encompasses Token Alpha and Beta
    }

    # Simulate failure of both extract_table_model and build_fallback_table_model
    with patch('convert.run_single_pass_ocr', return_value=mock_raw_ocr), \
         patch('convert.analyze_page_layout', return_value=mock_layout), \
         patch('convert.extract_table_model', return_value=None), \
         patch('convert.build_fallback_table_model', return_value=None):

        page_model = process_scanned_page_to_model(dummy_img, page_num=1)
        paragraphs = [b for b in page_model.blocks if isinstance(b, ParagraphModel)]
        all_para_text = " ".join(p.plain_text for p in paragraphs)

        # Tokens inside the table bounding box MUST NOT be lost!
        assert "Table Token Alpha" in all_para_text, "Token Alpha was lost when table failed!"
        assert "Table Token Beta" in all_para_text, "Token Beta was lost when table failed!"
        assert "Header Text" in all_para_text, "Header Text was lost!"
        assert "Footer Text" in all_para_text, "Footer Text was lost!"
        print("  -> Passed: 100% of tokens preserved in text flow when table extraction fails.")


def test_fallback_activated_when_neural_fails():
    print("[3/3] Testing spatial fallback activation when neural SLANet+ returns None...")
    h, w = 400, 600
    dummy_img = np.full((h, w, 3), 255, dtype=np.uint8)

    mock_raw_ocr = [
        ([[50, 100], [120, 100], [120, 120], [50, 120]], "Debit", 0.99),
        ([[200, 100], [260, 100], [260, 120], [200, 120]], "Credit", 0.99),
        ([[50, 130], [120, 130], [120, 150], [50, 150]], "1000", 0.99),
        ([[200, 130], [260, 130], [260, 150], [200, 150]], "2000", 0.99),
    ]
    mock_layout = {
        'table': [[40, 90, 300, 160]]
    }

    # Neural table returns None, but fallback builds it
    with patch('convert.run_single_pass_ocr', return_value=mock_raw_ocr), \
         patch('convert.analyze_page_layout', return_value=mock_layout), \
         patch('convert.extract_table_model', return_value=None):

        page_model = process_scanned_page_to_model(dummy_img, page_num=1)
        tables = [b for b in page_model.blocks if isinstance(b, TableModel)]
        assert len(tables) == 1, f"Expected 1 fallback table, got {len(tables)}"
        tbl = tables[0]
        assert tbl.num_rows == 2, f"Expected 2 rows, got {tbl.num_rows}"
        assert tbl.num_cols == 2, f"Expected 2 cols, got {tbl.num_cols}"
        assert tbl.rows[0][0].text == "Debit"
        assert tbl.rows[0][1].text == "Credit"
        print("  -> Passed: Fallback table correctly constructed and retained in PageModel.")


if __name__ == "__main__":
    test_build_fallback_table_model()
    test_token_release_when_table_fails()
    test_fallback_activated_when_neural_fails()
    print("\n✅ PHASE 2 VERIFICATION PASSED SUCCESSFULLY!")
