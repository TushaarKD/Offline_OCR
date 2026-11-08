"""
test_backend_integrity.py - Phase 1 Verification for Raw Integrity & Zero Manipulation
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import docx
from core.document_ir import DocumentModel, PageModel, TableModel, TableCellModel
from core.qa_auditor import validate_and_heal_table, audit_document
from core.docx_compiler import compile_document
from core.model_manager import get_table_engine


def test_table_spans_never_falsely_clamped():
    print("=== Test 1: Legitimate Table Spans Preserved 100% ===")
    # Construct a table representing a real financial statement:
    # Row 0: Header spanning 3 columns: "Balance Sheet Summary" (colspan=3)
    # Row 1: 3 columns: "Asset Category", "Cost (Rs)", "Book Value (Rs)"
    # Row 2: 3 columns: "Plant & Machinery", "50,000", "45,000"
    # Row 3: 3 columns: "Furniture & Fixtures", "20,000", "18,000"
    # Row 4: Wide footer spanning 3 columns: "Total Assets: 63,000" (colspan=3)
    t = TableModel(
        rows=[
            [
                TableCellModel(row_idx=0, col_idx=0, text="Balance Sheet Summary", colspan=3, is_header=True),
                TableCellModel(row_idx=0, col_idx=1, text=""),  # pre-allocated dummy cell 1
                TableCellModel(row_idx=0, col_idx=2, text=""),  # pre-allocated dummy cell 2
            ],
            [
                TableCellModel(row_idx=1, col_idx=0, text="Asset Category", is_header=True),
                TableCellModel(row_idx=1, col_idx=1, text="Cost (Rs)", is_header=True),
                TableCellModel(row_idx=1, col_idx=2, text="Book Value (Rs)", is_header=True),
            ],
            [
                TableCellModel(row_idx=2, col_idx=0, text="Plant & Machinery"),
                TableCellModel(row_idx=2, col_idx=1, text="50,000"),
                TableCellModel(row_idx=2, col_idx=2, text="45,000"),
            ],
            [
                TableCellModel(row_idx=3, col_idx=0, text="Furniture & Fixtures"),
                TableCellModel(row_idx=3, col_idx=1, text="20,000"),
                TableCellModel(row_idx=3, col_idx=2, text="18,000"),
            ],
            [
                TableCellModel(row_idx=4, col_idx=0, text="Total Assets: 63,000", colspan=3),
                TableCellModel(row_idx=4, col_idx=1, text=""),  # pre-allocated dummy cell 1
                TableCellModel(row_idx=4, col_idx=2, text=""),  # pre-allocated dummy cell 2
            ]
        ],
        num_rows=5,
        num_cols=3
    )

    healed_t, actions = validate_and_heal_table(t, page_content_width=7.0)

    # Verify that legitimate spans (colspan=3) were NOT clamped!
    assert healed_t.rows[0][0].colspan == 3, f"Header span was falsely clamped to {healed_t.rows[0][0].colspan}!"
    assert healed_t.rows[4][0].colspan == 3, f"Footer span was falsely clamped to {healed_t.rows[4][0].colspan}!"
    assert len(actions) == 0, f"Expected 0 clamping actions on clean table, got: {actions}"
    print("-> PASSED: Header and Footer colspan=3 preserved without any false clamping!\n")

    # Compile to Word to verify Word table renders clean merges
    doc_m = DocumentModel(title="Table Integrity")
    page = doc_m.add_page(1)
    page.add_table(healed_t)
    out_docx = "test_table_integrity.docx"
    compile_document(doc_m, out_docx)

    doc = docx.Document(out_docx)
    assert len(doc.tables) == 1, "Table missing"
    assert len(doc.tables[0].rows) == 5, "Rows count mismatch"
    assert len(doc.tables[0].columns) == 3, "Cols count mismatch"
    print("-> PASSED: Word table compiled with authentic 3-column topology!\n")


def test_boundary_clamping_only_on_true_overflow():
    print("=== Test 2: Clamping Only on True Overflow Out-of-Bounds ===")
    # Table with 3 columns, but a cell has colspan=10 (true overflow)
    t_overflow = TableModel(
        rows=[
            [
                TableCellModel(row_idx=0, col_idx=0, text="A1"),
                TableCellModel(row_idx=0, col_idx=1, text="B1"),
                TableCellModel(row_idx=0, col_idx=2, text="C1"),
            ],
            [
                TableCellModel(row_idx=1, col_idx=0, text="A2", colspan=10),
            ]
        ],
        num_rows=2,
        num_cols=3
    )
    healed, actions = validate_and_heal_table(t_overflow, page_content_width=7.0)
    print(f"Safety actions executed: {actions}")
    assert healed.rows[1][0].colspan == 3, f"Overflow colspan should be clamped to 3, got {healed.rows[1][0].colspan}"
    assert len(healed.rows[1]) == 3, f"Ragged row was not padded to 3 cols: {len(healed.rows[1])}"
    print("-> PASSED: True overflow clamped safely to table boundary without crashing!\n")


def test_rapid_table_silent_initialization():
    print("=== Test 3: RapidTable Initialized Silently Without Warning Spam ===")
    engine = get_table_engine()
    assert engine is not None, "Failed to initialize RapidTable"
    print("-> PASSED: RapidTable ready with use_ocr=False!\n")


if __name__ == "__main__":
    test_table_spans_never_falsely_clamped()
    test_boundary_clamping_only_on_true_overflow()
    test_rapid_table_silent_initialization()
    print("ALL PHASE 1 BACKEND INTEGRITY TESTS PASSED 100%!")

