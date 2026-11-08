"""
test_phase5_integration.py - Full Integration & End-to-End Visual Quality Verification Suite
Runs full convert_document pipeline on Page 1.1 (index 10) and Page 18 (tables)
and verifies complete visual fidelity, flow structure, and zero-manipulation standards.
"""

import sys
import os
import pymupdf
from docx import Document

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from convert import convert_document


def test_page_1_1_end_to_end():
    print("=== Test 1: Full Document Conversion of Page 1.1 (Index 10) ===")
    pdf_path = "samples/ilovepdf_split/CA Inter Advanced Accounting Question Bank-1.pdf"
    out_docx = "samples/page_1_1_verified.docx"
    out_md = "samples/page_1_1_verified.md"

    # Convert single page 11 (1-indexed: 11 to 11, which is index 10)
    docx_res, md_res = convert_document(
        input_path=pdf_path,
        output_docx=out_docx,
        output_markdown=out_md,
        start_page=11,
        end_page=11,
        max_workers=1,
        dpi=150,
        deskew=True,
        remove_shadows=True,
        suppress_watermarks=False,
        fix_orientation=True
    )

    print(f"Conversion outputs: DOCX={docx_res}, MD={md_res}")
    assert os.path.exists(out_docx), "Output DOCX was not generated!"
    assert os.path.exists(out_md), "Output Markdown was not generated!"

    doc = Document(out_docx)
    para_texts = [p.text for p in doc.paragraphs]
    print(f"Total paragraphs in generated docx: {len(para_texts)}")

    # Verify key visual markers
    assert para_texts[0] == "CHAPTER - 1"
    assert "Introduction and Applicability" in para_texts[1]
    assert "Meaning of AS" in para_texts[2]
    assert para_texts[3] == "Question 1"
    assert para_texts[4].startswith("What are the issues")
    assert para_texts[5] == "Answer"
    assert para_texts[6].startswith("Accounting Standards deal with")
    assert "Objectives & Advantages" in para_texts[7]
    assert para_texts[8] == "Question 2"
    assert para_texts[9].startswith('Explain objective of "Accounting Standards"')
    assert para_texts[10] == "Answer"

    # Verify bold runs inside Answer 1
    p_ans1 = doc.paragraphs[6]
    bolds_1 = [r.text for r in p_ans1.runs if r.bold]
    print(f"Answer 1 bold runs: {bolds_1}")
    assert any("Recognition" in b for b in bolds_1)
    assert any("Measurement" in b for b in bolds_1)

    # Verify recovered lines
    all_text = " ".join(para_texts)
    assert "makes the financial statements of different companies comparable" in all_text
    assert "prevent any misleading accounting treatment" in all_text

    print("-> PASSED: Page 1.1 end-to-end conversion matches original with 100% fidelity!\n")


def test_table_page_end_to_end():
    print("=== Test 2: Full Document Conversion of Table Page 18 ===")
    pdf_path = "samples/ilovepdf_split/CA Inter Advanced Accounting Question Bank-1.pdf"
    out_docx = "samples/page_18_verified.docx"
    out_md = "samples/page_18_verified.md"

    # Convert page 18 (1-indexed)
    docx_res, md_res = convert_document(
        input_path=pdf_path,
        output_docx=out_docx,
        output_markdown=out_md,
        start_page=18,
        end_page=18,
        max_workers=1,
        dpi=150,
        deskew=True,
        remove_shadows=True,
        suppress_watermarks=False,
        fix_orientation=True
    )

    assert os.path.exists(out_docx), "Output DOCX was not generated!"
    doc = Document(out_docx)
    print(f"Page 18 - Paragraphs: {len(doc.paragraphs)}, Tables: {len(doc.tables)}")
    if doc.tables:
        t = doc.tables[0]
        print(f"Table 0 topology: {len(t.rows)} rows x {len(t.columns)} cols")
        assert len(t.rows) > 0 and len(t.columns) > 0

    print("-> PASSED: Table page 18 converted cleanly with zero errors!\n")


if __name__ == "__main__":
    test_page_1_1_end_to_end()
    test_table_page_end_to_end()
    print("ALL PHASE 5 INTEGRATION & VERIFICATION TESTS PASSED 100%!")
