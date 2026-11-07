"""
convert.py - Unified Document Conversion CLI & Orchestrator
Converts scanned/vectorized PDFs and document images into 100% editable Microsoft Word (.docx) documents
and clean Markdown (.md) using the unified Document IR architecture.

Supported Inputs:
    - PDF documents (.pdf)
    - High-resolution scans and photos (.png, .jpg, .jpeg, .tiff, .tif, .bmp, .webp)

Usage:
    python convert.py <input.pdf|image.jpg> [-o output.docx] [--markdown output.md] [--workers 4] [--dpi 150]
"""

import os
import sys
import argparse
import time
import re
from typing import List, Dict, Any, Tuple, Optional
import pymupdf
import numpy as np
import cv2

from core.document_ir import (
    DocumentModel, PageModel, ParagraphModel, TableModel,
    TableCellModel, FigureModel, RunModel
)
from core.ocr_engine import (
    run_single_pass_ocr, cluster_items_into_lines,
    clean_text_spacing, restore_currency_symbols
)
from core.layout_engine import analyze_page_layout
from core.table_engine import extract_table_model
from core.docx_compiler import compile_document
from core.preprocessor import preprocess_document_image


def process_scanned_page_to_model(
    img_np: np.ndarray,
    page_num: int,
    content_width: float = 7.0,
    deskew: bool = True,
    remove_shadows: bool = True,
    suppress_watermarks: bool = False,
    fix_orientation: bool = True
) -> PageModel:
    """
    Processes a single page image and returns a fully populated PageModel:
    1. Computer Vision Preprocessing (Auto-orientation, Deskew, Shadow removal, Watermark suppression).
    2. Single-pass OCR across the entire page image.
    3. Layout analysis to detect tables, figures, headers, footers.
    4. Neural table extraction with right-aligned numeric data.
    5. Reading order clustering and paragraph/heading synthesis.
    """
    # 1. Computer Vision Preprocessing
    img_np, prep_meta = preprocess_document_image(
        img_np,
        fix_orientation=fix_orientation,
        deskew=deskew,
        remove_shadows=remove_shadows,
        suppress_watermarks=suppress_watermarks
    )
    if (prep_meta['rotation_applied_deg'] != 0 or
        abs(prep_meta['deskew_angle']) > 0 or
        prep_meta['shadows_removed'] or
        prep_meta['watermarks_suppressed']):
        print(f"  [Page {page_num:2d} Preprocessing] "
              f"rot={prep_meta['rotation_applied_deg']}° | "
              f"deskew={prep_meta['deskew_angle']:+.2f}° | "
              f"shadow_cleaned={prep_meta['shadows_removed']} | "
              f"watermark_suppressed={prep_meta['watermarks_suppressed']}")

    h, w = img_np.shape[:2]
    page_model = PageModel(page_num=page_num, width_inches=8.5, height_inches=11.0)

    # 2. Single-pass OCR
    raw_ocr = run_single_pass_ocr(img_np)

    # 3. Layout Analysis
    layout_dict = analyze_page_layout(img_np)
    table_boxes = layout_dict.get('table', [])

    # 4. Extract Tables
    tables_data: List[Dict[str, Any]] = []
    table_assigned_indices = set()

    for t_box in table_boxes:
        x1, y1, x2, y2 = [int(v) for v in t_box]
        pad = 6
        x1, y1 = max(0, x1 - pad), max(0, y1 - pad)
        x2, y2 = min(w, x2 + pad), min(h, y2 + pad)
        crop = img_np[y1:y2, x1:x2]

        # Collect and shift OCR items inside table
        t_boxes, t_texts, t_scores = [], [], []
        for idx, (dt_box, text, score) in enumerate(raw_ocr):
            cx = sum(p[0] for p in dt_box) / 4.0
            cy = sum(p[1] for p in dt_box) / 4.0
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                shifted = [[p[0] - x1, p[1] - y1] for p in dt_box]
                t_boxes.append(shifted)
                t_texts.append(text)
                t_scores.append(score)
                table_assigned_indices.add(idx)

        t_model = extract_table_model(crop, t_boxes, t_texts, t_scores, page_content_width=content_width)
        if t_model:
            t_model.bbox = (x1, y1, x2, y2)
            tables_data.append({
                'type': 'table',
                'y0': y1,
                'y1': y2,
                'model': t_model
            })

    # 5. Collect non-table text items
    non_table_items = []
    for idx, (box, text, score) in enumerate(raw_ocr):
        if idx in table_assigned_indices:
            continue
        xs = [pt[0] for pt in box]
        ys = [pt[1] for pt in box]
        bx0, by0, bx1, by1 = min(xs), min(ys), max(xs), max(ys)
        non_table_items.append({
            'text': text,
            'x0': bx0, 'y0': by0,
            'x1': bx1, 'y1': by1,
            'height': by1 - by0,
            'score': score
        })

    # 6. Cluster text items into lines
    lines = cluster_items_into_lines(non_table_items)
    text_line_blocks = []
    for l in lines:
        line_str = ' '.join(i['text'] for i in l).strip()
        if line_str:
            line_y0 = min(i['y0'] for i in l)
            line_y1 = max(i['y1'] for i in l)
            text_line_blocks.append({
                'type': 'text',
                'y0': line_y0,
                'y1': line_y1,
                'content': line_str
            })

    # 7. Merge text lines and tables by vertical y0 coordinate
    all_elements = text_line_blocks + tables_data
    all_elements.sort(key=lambda el: el['y0'])

    # 8. Build Paragraph and Table models
    curr_para_lines = []
    prev_y1 = None
    prev_text = ""

    def flush_paragraph():
        nonlocal curr_para_lines
        if not curr_para_lines:
            return
        full_text = ' '.join(curr_para_lines).strip()
        curr_para_lines = []
        if not full_text:
            return

        cleaned_text = clean_text_spacing(restore_currency_symbols(full_text))

        # Check for Heading hierarchy
        if re.search(r'^(?:CHAPTER\s*-\s*\d+|PART\s*-\s*[IVXLCDM\d]+)', cleaned_text, re.IGNORECASE):
            p = page_model.add_paragraph(style="Heading 1")
            p.add_run(cleaned_text, font_size_pt=16.0, is_bold=True)
        elif re.search(r'^Question\s*\d+', cleaned_text, re.IGNORECASE):
            p = page_model.add_paragraph(style="Heading 3")
            p.add_run(cleaned_text, font_size_pt=12.0, is_bold=True)
        elif cleaned_text.strip() == "Answer" or cleaned_text.startswith("Answer\n"):
            p = page_model.add_paragraph(style="Normal")
            p.add_run("Answer", font_size_pt=11.0, is_bold=True)
            rem = cleaned_text[len("Answer"):].strip()
            if rem:
                p2 = page_model.add_paragraph(style="Normal")
                p2.add_run(rem, font_size_pt=10.5)
        elif re.search(r'^\((?:[0-9]{1,2}|[a-z]|[ivxlcdm]{1,4})\)\s+', cleaned_text):
            p = page_model.add_paragraph(style="List Bullet")
            p.add_run(cleaned_text, font_size_pt=10.5)
        else:
            p = page_model.add_paragraph(style="Normal")
            p.add_run(cleaned_text, font_size_pt=10.5)

    for el in all_elements:
        if el['type'] == 'table':
            flush_paragraph()
            page_model.add_table(el['model'])
            prev_y1 = el['y1']
            prev_text = ""
        else:
            raw_text = el['content']
            y0, y1 = el['y0'], el['y1']

            is_header = (y0 < h * 0.08) or (bool(re.search(r'^(?:ACI\b|CHAPTER|PART\s*-|AS\s*\d+:)', raw_text)) and y0 < h * 0.15)
            is_footer = (y1 > h * 0.91) or bool(re.search(r'Page \d+\.\d+|BY.*AGARWAL', raw_text))
            is_new_section = raw_text.startswith(('Question', 'Answer', '(', '-'))

            if (is_header or is_footer or is_new_section or
                (prev_y1 is not None and (y0 - prev_y1) > 22) or
                (prev_text.endswith(('.', ':', '?')) and (y0 - prev_y1) > 12)):
                flush_paragraph()

            curr_para_lines.append(raw_text)
            prev_y1 = y1
            prev_text = raw_text.strip()

    flush_paragraph()
    return page_model


def _worker_page_job(args: Tuple[str, int, int, float, bool, bool, bool, bool]) -> Tuple[int, PageModel]:
    """Process a single PDF page inside a ProcessPoolExecutor worker."""
    pdf_path, page_idx, dpi, content_width, deskew, remove_shadows, suppress_watermarks, fix_orientation = args
    doc = pymupdf.open(pdf_path)
    page = doc[page_idx]

    pix = page.get_pixmap(dpi=dpi)
    img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.h, pix.w, pix.n))
    if pix.n == 4:
        img_np = img_np[:, :, :3]
    doc.close()

    page_model = process_scanned_page_to_model(
        img_np,
        page_num=page_idx + 1,
        content_width=content_width,
        deskew=deskew,
        remove_shadows=remove_shadows,
        suppress_watermarks=suppress_watermarks,
        fix_orientation=fix_orientation
    )
    return page_idx, page_model


def convert_document(
    input_path: str,
    output_docx: Optional[str] = None,
    output_markdown: Optional[str] = None,
    dpi: int = 150,
    max_workers: int = 4,
    start_page: int = 1,
    end_page: Optional[int] = None,
    deskew: bool = True,
    remove_shadows: bool = True,
    suppress_watermarks: bool = False,
    fix_orientation: bool = True
) -> Tuple[str, Optional[str]]:
    """
    Unified conversion entrypoint:
    Builds the complete DocumentModel and compiles directly to .docx (and optionally .md).
    Supports PDFs as well as standalone images (.png, .jpg, .jpeg, .tiff, .bmp, .webp).
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    base, ext = os.path.splitext(input_path)
    ext_lower = ext.lower()
    if output_docx is None:
        output_docx = f"{base}.docx"
    if output_markdown is None:
        output_markdown = f"{base}.md"

    content_width = 8.5 - 1.5  # 7.0 inches standard printable width

    print(f"=== Unified Document Conversion Engine ===")
    print(f"Input:          {input_path}")
    print(f"Output DOCX:    {output_docx}")
    if output_markdown:
        print(f"Output MD:      {output_markdown}")
    print(f"Preprocessing:  Orientation={fix_orientation} | Deskew={deskew} | Shadows={remove_shadows} | Watermarks={suppress_watermarks}")

    t0 = time.time()
    doc_model = DocumentModel(title=os.path.basename(base))

    # Check if input is a direct image format
    image_extensions = {'.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp', '.webp'}
    if ext_lower in image_extensions:
        print(f"Mode:           Single Document Image")
        print("=" * 43)

        # Read image safely handling unicode filepaths on Windows
        with open(input_path, 'rb') as f:
            bytes_data = f.read()
        img_bgr = cv2.imdecode(np.frombuffer(bytes_data, np.uint8), cv2.IMREAD_COLOR)
        if img_bgr is None:
            raise ValueError(f"Failed to decode image: {input_path}")
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

        page_model = process_scanned_page_to_model(
            img_rgb,
            page_num=1,
            content_width=content_width,
            deskew=deskew,
            remove_shadows=remove_shadows,
            suppress_watermarks=suppress_watermarks,
            fix_orientation=fix_orientation
        )
        doc_model.pages.append(page_model)
        num_pages = 1

    else:
        # PDF Document flow
        doc = pymupdf.open(input_path)
        total_pages = len(doc)
        doc.close()

        s_idx = max(0, start_page - 1)
        e_idx = min(total_pages, end_page) if end_page else total_pages
        page_indices = list(range(s_idx, e_idx))
        num_pages = len(page_indices)

        print(f"Pages:          {s_idx + 1} to {e_idx} ({num_pages} pages)")
        print(f"Workers:        {max_workers} | Rendering DPI: {dpi}")
        print("=" * 43)

        tasks = [
            (input_path, p, dpi, content_width, deskew, remove_shadows, suppress_watermarks, fix_orientation)
            for p in page_indices
        ]
        page_results: Dict[int, PageModel] = {}

        if max_workers > 1 and num_pages > 1:
            from concurrent.futures import ProcessPoolExecutor, as_completed
            with ProcessPoolExecutor(max_workers=max_workers) as executor:
                future_to_page = {executor.submit(_worker_page_job, t): t[1] for t in tasks}
                done_count = 0
                for future in as_completed(future_to_page):
                    p_idx, p_model = future.result()
                    page_results[p_idx] = p_model
                    done_count += 1
                    elapsed = time.time() - t0
                    avg = elapsed / done_count
                    eta = avg * (num_pages - done_count)
                    print(f"[{done_count:2d}/{num_pages}] Page {p_idx + 1:2d} completed | Elapsed: {elapsed:5.1f}s | ETA: {eta:5.1f}s")
        else:
            for idx, t in enumerate(tasks):
                p_idx, p_model = _worker_page_job(t)
                page_results[p_idx] = p_model
                print(f"[{idx+1:2d}/{num_pages}] Page {p_idx + 1:2d} completed")

        # Assemble DocumentModel in sequential page order
        for p in page_indices:
            if p in page_results:
                doc_model.pages.append(page_results[p])

    # Direct compile to Word DOCX
    print("\nSynthesizing native flow Microsoft Word (.docx)...")
    compile_document(doc_model, output_docx)

    # Optional export to Markdown
    if output_markdown:
        print(f"Exporting companion Markdown (.md)...")
        doc_model.save_markdown(output_markdown)

    total_time = time.time() - t0
    print("=" * 43)
    print(f"Done! Processed {num_pages} page(s) in {total_time:.2f}s ({total_time/max(1, num_pages):.2f}s/page).")
    print(f"DOCX saved to: {output_docx}")
    if output_markdown:
        print(f"MD   saved to: {output_markdown}")

    return output_docx, output_markdown


def main():
    parser = argparse.ArgumentParser(description="Unified High-Fidelity Document Conversion Engine.")
    parser.add_argument("input_path", help="Path to input PDF or document image (.png, .jpg, .tiff, etc.)")
    parser.add_argument("-o", "--output", help="Path to output .docx file (optional)")
    parser.add_argument("--markdown", help="Path to output .md file (optional)")
    parser.add_argument("--dpi", type=int, default=150, help="Rendering DPI for OCR (default: 150)")
    parser.add_argument("--workers", type=int, default=4, help="Parallel worker processes (default: 4)")
    parser.add_argument("--start-page", type=int, default=1, help="Start page (1-based, inclusive)")
    parser.add_argument("--end-page", type=int, default=None, help="End page (1-based, inclusive)")

    # Preprocessing flags
    parser.add_argument("--no-deskew", action="store_true", help="Disable automatic deskewing")
    parser.add_argument("--no-shadow-removal", action="store_true", help="Disable shadow and illumination flattening")
    parser.add_argument("--suppress-watermarks", action="store_true", help="Enable faint watermark suppression")
    parser.add_argument("--no-orientation", action="store_true", help="Disable 360-degree orientation detection")

    args = parser.parse_args()

    convert_document(
        input_path=args.input_path,
        output_docx=args.output,
        output_markdown=args.markdown,
        dpi=args.dpi,
        max_workers=args.workers,
        start_page=args.start_page,
        end_page=args.end_page,
        deskew=not args.no_deskew,
        remove_shadows=not args.no_shadow_removal,
        suppress_watermarks=args.suppress_watermarks,
        fix_orientation=not args.no_orientation
    )


if __name__ == "__main__":
    main()
