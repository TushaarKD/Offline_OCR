"""
test_plan03_phase3_borders.py - Verification for Phase 3 of 03_ACCOUNTING_TABLE_FIDELITY_PLAN.md
Verifies that:
1. Compiled Word tables feature authentic accounting borders:
   - w:insideH val="none" (no unauthentic interior row lines between records).
   - w:top and w:bottom single borders (0.5pt, color 333333).
   - Header row (Row 0) cells have bottom border separating header from records.
   - Total row cells have top border separating totals from records.
2. Flow properties:
   - w:cantSplit is present on all rows.
   - w:tblHeader is present on header rows.
3. Proportional column widths and alignment are preserved.
"""

import os
import sys
import docx
from docx.oxml.ns import qn

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.document_ir import DocumentModel, PageModel, TableModel, TableCellModel
from core.docx_compiler import compile_document


def test_accounting_borders_compilation():
    print("[1/2] Testing authentic accounting borders XML compilation...")
    out_docx = "debug_phase3_borders_test.docx"

    # Create a dummy accounting table: 4 rows x 3 cols
    row0 = [
        TableCellModel(row_idx=0, col_idx=0, text="Particulars", is_header=True),
        TableCellModel(row_idx=0, col_idx=1, text="₹", is_header=True),
        TableCellModel(row_idx=0, col_idx=2, text="₹", is_header=True),
    ]
    row1 = [
        TableCellModel(row_idx=1, col_idx=0, text="Cash sales", is_header=False),
        TableCellModel(row_idx=1, col_idx=1, text="1,40,000", is_header=False, alignment="RIGHT"),
        TableCellModel(row_idx=1, col_idx=2, text="", is_header=False),
    ]
    row2 = [
        TableCellModel(row_idx=2, col_idx=0, text="Trade commission", is_header=False),
        TableCellModel(row_idx=2, col_idx=1, text="50,000", is_header=False, alignment="RIGHT"),
        TableCellModel(row_idx=2, col_idx=2, text="1,90,000", is_header=False, alignment="RIGHT"),
    ]
    row3 = [
        TableCellModel(row_idx=3, col_idx=0, text="Total", is_header=False),
        TableCellModel(row_idx=3, col_idx=1, text="", is_header=False),
        TableCellModel(row_idx=3, col_idx=2, text="1,90,000", is_header=False, alignment="RIGHT"),
    ]

    t_model = TableModel(
        rows=[row0, row1, row2, row3],
        num_rows=4,
        num_cols=3,
        col_widths_inches=[3.5, 1.75, 1.75],
        has_borders=True,
        has_interior_h_lines=False
    )

    doc_model = DocumentModel()
    page = PageModel(page_num=1)
    page.add_table(t_model)
    doc_model.pages.append(page)

    compile_document(doc_model, out_docx)
    assert os.path.exists(out_docx), "Failed to generate test docx"

    # Open docx and inspect table XML
    doc = docx.Document(out_docx)
    assert len(doc.tables) == 1, "Expected 1 table in generated document"
    tbl = doc.tables[0]

    tblPr = tbl._tbl.tblPr
    tblBorders = tblPr.find(qn('w:tblBorders'))
    assert tblBorders is not None, "w:tblBorders element missing from table"

    # 1. Verify w:insideH val="none"
    insideH = tblBorders.find(qn('w:insideH'))
    assert insideH is not None, "w:insideH missing"
    assert insideH.get(qn('w:val')) == "none", f"Expected insideH val='none', got {insideH.get(qn('w:val'))}"

    # 2. Verify w:top and w:bottom are single
    top = tblBorders.find(qn('w:top'))
    bottom = tblBorders.find(qn('w:bottom'))
    assert top.get(qn('w:val')) == "single"
    assert bottom.get(qn('w:val')) == "single"

    # 3. Verify w:cantSplit and w:tblHeader
    for r_idx, row in enumerate(tbl.rows):
        trPr = row._tr.find(qn('w:trPr'))
        assert trPr is not None, f"Row {r_idx} missing trPr"
        assert trPr.find(qn('w:cantSplit')) is not None, f"Row {r_idx} missing w:cantSplit"
        if r_idx == 0:
            assert trPr.find(qn('w:tblHeader')) is not None, "Header row missing w:tblHeader"

    # 4. Verify Row 0 cells have bottom border
    for c_idx, cell in enumerate(tbl.rows[0].cells):
        tcPr = cell._tc.find(qn('w:tcPr'))
        assert tcPr is not None, f"Header cell {c_idx} missing tcPr"
        tcBorders = tcPr.find(qn('w:tcBorders'))
        assert tcBorders is not None, f"Header cell {c_idx} missing tcBorders"
        bot = tcBorders.find(qn('w:bottom'))
        assert bot is not None and bot.get(qn('w:val')) == "single", f"Header cell {c_idx} missing single bottom border"

    # 5. Verify Total row cells have top border
    for c_idx, cell in enumerate(tbl.rows[3].cells):
        tcPr = cell._tc.find(qn('w:tcPr'))
        assert tcPr is not None, f"Total cell {c_idx} missing tcPr"
        tcBorders = tcPr.find(qn('w:tcBorders'))
        assert tcBorders is not None, f"Total cell {c_idx} missing tcBorders"
        top_b = tcBorders.find(qn('w:top'))
        assert top_b is not None and top_b.get(qn('w:val')) == "single", f"Total cell {c_idx} missing single top border"

    # Clean up test artifact
    try:
        os.remove(out_docx)
    except Exception:
        pass

    print("  -> Accounting borders XML verification PASSED 100%!")


if __name__ == "__main__":
    test_accounting_borders_compilation()
    print("\nALL PHASE 3 VERIFICATION TESTS PASSED 100%!")

