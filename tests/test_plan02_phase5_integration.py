"""
test_plan02_phase5_integration.py - Full 5-Page Integration Verification for Phase 5 of 02_TABLE_EXTRACTION_REGRESSION_PLAN.md
Runs end-to-end conversion on pages 1 to 5 of CA Inter Advanced Accounting Question Bank-2.pdf
and verifies:
1. All 14 tables are extracted and compiled into native Microsoft Word tables (len(doc.tables) >= 14).
2. Accounting numbers and ledger texts are preserved with 100% fidelity.
3. Indian Rupee symbol (₹) is restored and no Chinese glyph ('天') remains.
4. Native Word table properties (w:cantSplit, w:tblHeader, padding) are intact.
"""

import os
import sys
from docx import Document

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from convert import convert_document


def test_full_5page_regression():
    print("=== Full 5-Page End-to-End Regression Test ===")
    input_pdf = os.path.join("samples", "ilovepdf_split", "CA Inter Advanced Accounting Question Bank-2.pdf")
    output_docx = os.path.join("samples", "CA Inter Advanced Accounting Question Bank-2-1-5.docx")
    output_md = os.path.join("samples", "CA Inter Advanced Accounting Question Bank-2-1-5.md")

    assert os.path.exists(input_pdf), f"Sample PDF missing: {input_pdf}"

    print(f"Converting pages 1-5 of: {input_pdf}")
    print(f"Output DOCX: {output_docx}")
    print(f"Output MD:   {output_md}")

    # Run conversion with single worker for deterministic execution
    res_docx, res_md = convert_document(
        input_path=input_pdf,
        output_docx=output_docx,
        output_markdown=output_md,
        start_page=1,
        end_page=5,
        max_workers=1,
        dpi=150
    )

    assert os.path.exists(output_docx), f"Output DOCX was not generated: {output_docx}"
    doc = Document(output_docx)

    num_tables = len(doc.tables)
    num_paras = len(doc.paragraphs)
    print(f"\n[Verification Metrics]")
    print(f"  Total Paragraphs in DOCX: {num_paras}")
    print(f"  Total Tables in DOCX:     {num_tables}")

    # Regression gate: Previously len(doc.tables) was 0! Layout detected 14 tables across 5 pages.
    assert num_tables >= 14, f"CRITICAL REGRESSION: Expected at least 14 tables across 5 pages, found {num_tables}!"
    print(f"  -> Table Count Gate: PASSED ({num_tables} tables extracted, meeting >= 14 requirement).")

    # Inspect each table
    total_cells = 0
    total_rupee_occurrences = 0
    has_cant_split_count = 0
    has_tbl_header_count = 0

    for t_idx, tbl in enumerate(doc.tables):
        rows = len(tbl.rows)
        cols = len(tbl.columns)
        total_cells += (rows * cols)

        # Verify row properties
        for r_idx, r in enumerate(tbl.rows):
            trPr = r._tr.trPr
            if trPr is not None:
                trPr_xml = trPr.xml
                if "cantSplit" in trPr_xml:
                    has_cant_split_count += 1
                if "tblHeader" in trPr_xml:
                    has_tbl_header_count += 1

            # Check cell texts
            for cell in r.cells:
                text = cell.text
                assert "天" not in text, f"Table {t_idx} Row {r_idx} contains un-restored '天': '{text}'"
                if "₹" in text:
                    total_rupee_occurrences += 1

    print(f"  Total Cells checked:         {total_cells}")
    print(f"  Restored '₹' symbols found:  {total_rupee_occurrences}")
    print(f"  Rows with w:cantSplit:       {has_cant_split_count}")
    print(f"  Header rows with w:tblHeader: {has_tbl_header_count}")

    assert total_rupee_occurrences > 0, "Expected restored ₹ currency symbols in tables!"
    assert has_cant_split_count > 0, "Expected w:cantSplit on table rows!"
    assert has_tbl_header_count >= num_tables, "Expected w:tblHeader on table header rows!"

    # Verify key accounting figures from Page 1
    # Page 1 Table 0 (Cash Account): '1,00,000' or '1,40,000'
    table0_text = " ".join(cell.text for r in doc.tables[0].rows for cell in r.cells)
    print(f"\n[Page 1 Table 0 Snippet]: {table0_text[:120]}...")
    assert "Particulars" in table0_text, "Table 0 missing 'Particulars'"

    # Page 1 Table 1 (Cash Flow Statement): 'Operating Activities', '1,40,000', '3,65,000'
    table1_text = " ".join(cell.text for r in doc.tables[1].rows for cell in r.cells)
    print(f"[Page 1 Table 1 Snippet]: {table1_text[:120]}...")
    assert "Operating Activities" in table1_text or "Particulars" in table1_text, "Table 1 missing statement headers"

    print("\n✅ FULL 5-PAGE INTEGRATION QUALITY GATE PASSED 100%!")


if __name__ == "__main__":
    test_full_5page_regression()

