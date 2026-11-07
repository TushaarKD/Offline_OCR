"""
test_phase5_runner.py - Comprehensive Verification for Phase 5 QA Loop
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import docx
from docx.oxml.ns import qn

from core.document_ir import (
    DocumentModel, PageModel, ParagraphModel, TableModel,
    TableCellModel, FigureModel, RunModel
)
from core.qa_auditor import (
    validate_and_heal_table,
    audit_accounting_table,
    apply_low_confidence_highlighting,
    audit_document,
    generate_qa_summary_markdown
)
from core.docx_compiler import compile_document


def test_table_topology_healing():
    print("=== Test 1: Table Matrix Topology Self-Healing ===")
    # Create an intentionally corrupted ragged table:
    # Row 0: 4 cells
    # Row 1: 2 cells (missing 2 cells)
    # Row 2: 3 cells, with cell 0 having illegal colspan=10 and cell 1 having illegal rowspan=10
    t = TableModel(
        rows=[
            [
                TableCellModel(row_idx=0, col_idx=0, text="A1"),
                TableCellModel(row_idx=0, col_idx=1, text="B1"),
                TableCellModel(row_idx=0, col_idx=2, text="C1"),
                TableCellModel(row_idx=0, col_idx=3, text="D1"),
            ],
            [
                TableCellModel(row_idx=1, col_idx=0, text="A2"),
                TableCellModel(row_idx=1, col_idx=1, text="B2"),
                # missing C2, D2
            ],
            [
                TableCellModel(row_idx=2, col_idx=0, text="A3", colspan=10),
                TableCellModel(row_idx=2, col_idx=1, text="B3", rowspan=10),
                TableCellModel(row_idx=2, col_idx=2, text="C3"),
            ]
        ],
        num_rows=3,
        num_cols=2  # intentionally wrong
    )

    healed_t, actions = validate_and_heal_table(t, page_content_width=7.0)
    print(f"Healing actions executed: {len(actions)}")
    for a in actions:
        print(f"  - {a}")

    assert healed_t.num_rows == 3, f"Expected 3 rows, got {healed_t.num_rows}"
    assert healed_t.num_cols == 4, f"Expected 4 cols, got {healed_t.num_cols}"
    assert len(healed_t.rows[1]) == 4, f"Expected Row 1 to have 4 cells, got {len(healed_t.rows[1])}"
    assert healed_t.rows[2][0].colspan <= 4, f"Colspan not clamped: {healed_t.rows[2][0].colspan}"
    assert healed_t.rows[2][1].rowspan <= 1, f"Rowspan not clamped: {healed_t.rows[2][1].rowspan}"
    assert len(healed_t.col_widths_inches) == 4, f"Widths count mismatch: {len(healed_t.col_widths_inches)}"
    assert abs(sum(healed_t.col_widths_inches) - 7.0) < 0.01, f"Total width != 7.0: {sum(healed_t.col_widths_inches)}"

    # Compile into Word to verify zero exceptions
    doc_m = DocumentModel(title="Topology Test")
    p = doc_m.add_page(1)
    p.add_table(healed_t)
    out_docx = "test_healed_table.docx"
    compile_document(doc_m, out_docx)
    
    doc = docx.Document(out_docx)
    assert len(doc.tables) == 1, "Table not compiled"
    assert len(doc.tables[0].rows) == 3, "Word table row count mismatch"
    assert len(doc.tables[0].columns) == 4, "Word table col count mismatch"
    print("-> PASSED: Ragged table successfully healed and compiled to Word!\n")


def test_accounting_checksum_auditor():
    print("=== Test 2: Accounting Checksums & Arithmetic Verification ===")
    # 1. Row equation test (Assets - Liabilities = Equity)
    t_eqn = TableModel(
        rows=[
            [
                TableCellModel(row_idx=0, col_idx=0, text="Particulars", is_header=True),
                TableCellModel(row_idx=0, col_idx=1, text="Assets", is_header=True),
                TableCellModel(row_idx=0, col_idx=2, text="-", is_header=True),
                TableCellModel(row_idx=0, col_idx=3, text="Liabilities", is_header=True),
                TableCellModel(row_idx=0, col_idx=4, text="=", is_header=True),
                TableCellModel(row_idx=0, col_idx=5, text="Equity", is_header=True),
            ],
            [
                TableCellModel(row_idx=1, col_idx=0, text="Opening"),
                TableCellModel(row_idx=1, col_idx=1, text="8.00"),
                TableCellModel(row_idx=1, col_idx=2, text="-"),
                TableCellModel(row_idx=1, col_idx=3, text="3.00"),
                TableCellModel(row_idx=1, col_idx=4, text="="),
                TableCellModel(row_idx=1, col_idx=5, text="5.00"),
            ]
        ],
        num_rows=2,
        num_cols=6
    )

    audit_res = audit_accounting_table(t_eqn)
    print("Equation audit result:", audit_res)
    assert audit_res['total_audited'] == 1, f"Expected 1 check, got {audit_res['total_audited']}"
    assert audit_res['passed_count'] == 1, f"Expected check to pass, failed: {audit_res}"
    print("-> PASSED: Row arithmetic (8.00 - 3.00 = 5.00) verified!\n")

    # 2. Column total test
    t_col = TableModel(
        rows=[
            [TableCellModel(text="Account"), TableCellModel(text="Amount (Rs)")],
            [TableCellModel(text="Rent"), TableCellModel(text="1,500.00")],
            [TableCellModel(text="Salaries"), TableCellModel(text="3,500.00")],
            [TableCellModel(text="Supplies"), TableCellModel(text="1,000.00")],
            [TableCellModel(text="Total Expenses"), TableCellModel(text="6,000.00")]
        ],
        num_rows=5,
        num_cols=2
    )
    col_audit = audit_accounting_table(t_col)
    print("Column total audit result:", col_audit)
    assert col_audit['total_audited'] == 1, "Expected 1 column total check"
    assert col_audit['passed_count'] == 1, "Column total check failed"
    print("-> PASSED: Column sum total (1500 + 3500 + 1000 = 6000) verified!\n")


def test_low_confidence_highlighting():
    print("=== Test 3: Low-Confidence OCR Highlighting ===")
    doc_m = DocumentModel(title="Low Conf Test")
    page = doc_m.add_page(1)
    p = page.add_paragraph()
    # High confidence run
    p.add_run("This text is crisp and clear. ", confidence=0.98)
    # Low confidence run (e.g. smudged text)
    p.add_run("SmudgedText123", confidence=0.45)

    highlighted = apply_low_confidence_highlighting(doc_m, threshold=0.60)
    print(f"Tokens highlighted: {highlighted}")
    assert highlighted == 1, f"Expected 1 highlighted token, got {highlighted}"
    assert p.runs[0].highlight_color is None, "High confidence run was incorrectly highlighted"
    assert p.runs[1].highlight_color == "YELLOW", "Low confidence run was not highlighted"

    out_docx = "test_highlighted.docx"
    compile_document(doc_m, out_docx)

    doc = docx.Document(out_docx)
    para = doc.paragraphs[0]
    assert len(para.runs) == 2, "Runs count mismatch"
    run_hi = para.runs[1]
    highlight_xml = run_hi._r.rPr.find(qn('w:highlight'))
    assert highlight_xml is not None, "w:highlight XML tag missing"
    assert highlight_xml.get(qn('w:val')) == 'yellow', f"Expected yellow highlight, got {highlight_xml.get(qn('w:val'))}"
    print("-> PASSED: Low confidence run rendered with Word native w:highlight w:val='yellow'!\n")


def test_full_document_audit():
    print("=== Test 4: Full Document Audit Report Generation ===")
    doc_m = DocumentModel(title="Full Audit Test")
    page = doc_m.add_page(1)
    p = page.add_paragraph()
    p.add_run("Document title", confidence=0.96)
    
    t = TableModel(
        rows=[
            [TableCellModel(text="A"), TableCellModel(text="B")],
            [TableCellModel(text="1"), TableCellModel(text="2")]
        ],
        num_rows=2,
        num_cols=2
    )
    page.add_table(t)

    report = audit_document(doc_m, low_conf_threshold=0.60)
    print("Audit Report Metrics:")
    for k, v in report.items():
        if k != 'accounting_audits':
            print(f"  {k}: {v}")
    
    md_report = generate_qa_summary_markdown(report)
    print("\nGenerated Markdown Report:\n", md_report)
    assert report['total_pages'] == 1
    assert report['total_paragraphs'] == 1
    assert report['total_tables'] == 1
    assert report['confidence_median'] == 0.96
    print("-> PASSED: Full document audit report generated successfully!\n")


if __name__ == "__main__":
    test_table_topology_healing()
    test_accounting_checksum_auditor()
    test_low_confidence_highlighting()
    test_full_document_audit()
    print("ALL PHASE 5 TESTS PASSED WITH 100% SUCCESS!")
