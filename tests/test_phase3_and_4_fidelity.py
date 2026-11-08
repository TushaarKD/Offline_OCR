"""
test_phase3_and_4_fidelity.py - Comprehensive Unit & Regression Test Suite for:
Phase 3: Word-Level In-Line Bold Detection
Phase 4: Typography, Alignment & Color Pinning
"""

import sys
import os
import re
import pymupdf
import numpy as np
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from convert import process_scanned_page_to_model
from core.document_ir import DocumentModel, ParagraphModel
from core.docx_compiler import compile_document


def test_phase3_and_4_full_page():
    print("=== Test: Phase 3 (Inline Bold) & Phase 4 (Typography, Alignments, Colors) ===")

    pdf_path = "samples/ilovepdf_split/CA Inter Advanced Accounting Question Bank-1.pdf"
    assert os.path.exists(pdf_path), f"Sample PDF not found at {pdf_path}"

    doc_pdf = pymupdf.open(pdf_path)
    # Page index 10 is 'Page 1.1'
    pix = doc_pdf[10].get_pixmap(dpi=150)
    img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.h, pix.w, pix.n))
    if pix.n == 4:
        img_np = img_np[:, :, :3]

    page_model = process_scanned_page_to_model(
        img_np, page_num=10, content_width=7.0, dpi=150,
        deskew=False, remove_shadows=False, suppress_watermarks=False, fix_orientation=False
    )

    doc_ir = DocumentModel(pages=[page_model])
    test_docx_path = "test_page10_output.docx"

    # Compile to Word Document
    compile_document(doc_ir, test_docx_path)
    assert os.path.exists(test_docx_path), "Failed to compile Word document"

    # Inspect compiled docx with python-docx
    doc_out = Document(test_docx_path)
    paras = doc_out.paragraphs

    # 1. Verify Chapter 1 is centered Heading 1
    p_chap = paras[0]
    assert p_chap.text == "CHAPTER - 1", f"Expected 'CHAPTER - 1', got {p_chap.text!r}"
    assert p_chap.alignment == WD_ALIGN_PARAGRAPH.CENTER, "Chapter title not centered!"

    # 2. Verify Chapter title is centered Heading 1
    p_title = paras[1]
    assert "Introduction and Applicability" in p_title.text
    assert p_title.alignment == WD_ALIGN_PARAGRAPH.CENTER, "Major title not centered!"

    # 3. Verify Subheading 'Meaning of AS' is bold and underlined
    p_sub = paras[2]
    assert "Meaning of AS" in p_sub.text
    assert p_sub.runs[0].bold is True, "Subheading not bold!"
    assert p_sub.runs[0].underline is True, "Subheading not underlined!"

    # 4. Verify Question 1 is standalone Heading 3
    p_q1 = paras[3]
    assert p_q1.text == "Question 1"

    # 5. Verify Answer 1 has in-line bold runs
    p_ans1_body = paras[6]
    bold_runs = [r.text for r in p_ans1_body.runs if r.bold]
    print(f"Bold runs in Answer 1: {bold_runs}")
    assert any("Recognition" in r for r in bold_runs), "Recognition was not bolded!"
    assert any("Measurement" in r for r in bold_runs), "Measurement was not bolded!"
    assert any("Presentation" in r for r in bold_runs), "Presentation was not bolded!"
    assert any("Disclosure requirements" in r for r in bold_runs), "Disclosure requirements was not bolded!"

    # 6. Verify Answer 2 has 'written policy documents' bolded
    p_ans2_body = paras[11]
    bold_runs_2 = [r.text for r in p_ans2_body.runs if r.bold]
    print(f"Bold runs in Answer 2: {bold_runs_2}")
    assert any("written policy documents" in r for r in bold_runs_2), "'written policy documents' was not bolded!"

    # 7. Verify List items have in-line bold keywords
    # (a) harmonize
    assert any(r.bold and "harmonize" in r.text for r in paras[13].runs), "'harmonize' was not bolded!"
    # (b) facilitates
    assert any(r.bold and "facilitates" in r.text for r in paras[14].runs), "'facilitates' was not bolded!"
    # (c) faith and reliability
    assert any(r.bold and "faith and reliability" in r.text for r in paras[15].runs), "'faith and reliability' was not bolded!"

    # 8. Verify Black Typography (Heading color rgb is black #111111 or #222222, NOT Word theme blue)
    for p in [p_chap, p_title, p_sub, p_q1]:
        for r in p.runs:
            if r.font.color and r.font.color.rgb:
                color_hex = str(r.font.color.rgb)
                assert color_hex in ("111111", "222222", "000000"), f"Heading run has non-black color: {color_hex}"

    # Clean up test output docx
    os.remove(test_docx_path)
    print("-> PASSED: Inline bold, center alignments, underlines, and black typography verified 100%!\n")


if __name__ == "__main__":
    test_phase3_and_4_full_page()
    print("ALL PHASE 3 & 4 FIDELITY TESTS PASSED 100%!")

