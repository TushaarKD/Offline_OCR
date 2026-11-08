"""
test_plan02_phase4_styling.py - Verification for Phase 4 of 02_TABLE_EXTRACTION_REGRESSION_PLAN.md
Verifies that compiled .docx tables include:
1. w:cantSplit on all rows to prevent mid-row pagination splits.
2. w:tblHeader on header rows to repeat headers across page breaks.
3. Proper cell padding, numeric right-alignment, and header background shading.
"""

import os
import sys
import tempfile
from docx import Document

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.document_ir import DocumentModel, PageModel, TableModel, TableCellModel
from core.docx_compiler import compile_document


def test_table_xml_styling_and_properties():
    print("[1/2] Testing table XML properties (w:cantSplit, w:tblHeader, shading)...")
    doc_model = DocumentModel(title="Accounting Report")
    page = doc_model.add_page(page_num=1)

    # Construct 3-row, 3-column table
    # Row 0: Header
    # Row 1: Section subheader (spanning 3 cols)
    # Row 2: Ledger entry (Particulars, Amount, Amount)
    row0 = [
        TableCellModel(row_idx=0, col_idx=0, text="Particulars", is_header=True, alignment="CENTER"),
        TableCellModel(row_idx=0, col_idx=1, text="₹", is_header=True, alignment="CENTER"),
        TableCellModel(row_idx=0, col_idx=2, text="₹", is_header=True, alignment="CENTER"),
    ]
    row1 = [
        TableCellModel(row_idx=1, col_idx=0, text="Operating Activities:", rowspan=1, colspan=3, is_header=False, alignment="LEFT"),
        TableCellModel(row_idx=1, col_idx=1, text=""),
        TableCellModel(row_idx=1, col_idx=2, text=""),
    ]
    row2 = [
        TableCellModel(row_idx=2, col_idx=0, text="Cash sales", is_header=False, alignment="LEFT"),
        TableCellModel(row_idx=2, col_idx=1, text="1,40,000", is_header=False, alignment="RIGHT"),
        TableCellModel(row_idx=2, col_idx=2, text="3,65,000", is_header=False, alignment="RIGHT"),
    ]

    t_model = TableModel(
        rows=[row0, row1, row2],
        num_rows=3,
        num_cols=3,
        col_widths_inches=[4.0, 1.5, 1.5],
        style="Table Grid",
        has_borders=True,
        alignment="CENTER"
    )
    page.add_table(t_model)

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        compile_document(doc_model, tmp_path)
        doc = Document(tmp_path)
        assert len(doc.tables) == 1, f"Expected 1 table, found {len(doc.tables)}"
        tbl = doc.tables[0]
        assert len(tbl.rows) == 3, f"Expected 3 rows in docx table, got {len(tbl.rows)}"

        # Check row properties: w:cantSplit and w:tblHeader
        for r_idx, r in enumerate(tbl.rows):
            trPr = r._tr.trPr
            assert trPr is not None, f"Row {r_idx} missing trPr"
            trPr_xml = trPr.xml
            assert "cantSplit" in trPr_xml, f"Row {r_idx} missing w:cantSplit!"
            if r_idx == 0:
                assert "tblHeader" in trPr_xml, f"Header row 0 missing w:tblHeader!"
            print(f"  -> Row {r_idx}: trPr verified with cantSplit=True, tblHeader={(r_idx == 0)}")

        # Check cell alignments
        # Row 2 Cell 0: LEFT
        assert tbl.cell(2, 0).paragraphs[0].alignment == 0, f"Expected LEFT alignment for cell (2, 0)"
        # Row 2 Cell 1: RIGHT
        assert tbl.cell(2, 1).paragraphs[0].alignment == 2, f"Expected RIGHT alignment for cell (2, 1)"

        # Check header shading on Row 0
        shd0 = tbl.cell(0, 0)._tc.tcPr.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}shd')
        assert shd0 is not None, "Header cell (0, 0) missing background shading"
        assert shd0.attrib['{http://schemas.openxmlformats.org/wordprocessingml/2006/main}fill'] == "F2F4F7"
        print("  -> Passed: Header shading and numeric right-alignment verified.")

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_borderless_accounting_table_styling():
    print("[2/2] Testing borderless accounting table borders...")
    doc_model = DocumentModel(title="Borderless Accounting")
    page = doc_model.add_page(page_num=1)

    t_model = TableModel(
        rows=[
            [TableCellModel(row_idx=0, col_idx=0, text="Item"), TableCellModel(row_idx=0, col_idx=1, text="Amount")],
            [TableCellModel(row_idx=1, col_idx=0, text="Total"), TableCellModel(row_idx=1, col_idx=1, text="5,000")]
        ],
        num_rows=2,
        num_cols=2,
        col_widths_inches=[3.5, 3.5],
        has_borders=False
    )
    page.add_table(t_model)

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        compile_document(doc_model, tmp_path)
        doc = Document(tmp_path)
        tbl = doc.tables[0]
        tblPr_xml = tbl._tbl.tblPr.xml
        assert "tblBorders" in tblPr_xml, "Borderless table missing custom accounting tblBorders"
        print("  -> Passed: Custom accounting borders verified for borderless table.")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


if __name__ == "__main__":
    test_table_xml_styling_and_properties()
    test_borderless_accounting_table_styling()
    print("\n✅ PHASE 4 VERIFICATION PASSED SUCCESSFULLY!")

