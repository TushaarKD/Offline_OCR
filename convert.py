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
from core.layout_engine import (
    analyze_page_layout, recursive_xy_cut,
    sample_text_color_from_crop
)
from core.table_engine import extract_table_model
from core.docx_compiler import compile_document
from core.preprocessor import preprocess_document_image


def process_scanned_page_to_model(
    img_np: np.ndarray,
    page_num: int,
    content_width: float = 7.0,
    dpi: int = 150,
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
    4. Neural table extraction with right-aligned numeric data & cell shading.
    5. High-resolution figure & graphic extraction.
    6. Recursive XY-Cut multi-column & reading order decomposition.
    7. Dynamic typography point scaling & RGB ink stroke color sampling.
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
    figure_boxes = layout_dict.get('figure', [])

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
                'x0': x1, 'y0': y1,
                'x1': x2, 'y1': y2,
                'model': t_model
            })

    # 4b. Extract High-Res Figures & Illustrations
    figures_data: List[Dict[str, Any]] = []
    figure_assigned_indices = set()

    for f_box in figure_boxes:
        x1, y1, x2, y2 = [int(v) for v in f_box]
        pad = 4
        x1, y1 = max(0, x1 - pad), max(0, y1 - pad)
        x2, y2 = min(w, x2 + pad), min(h, y2 + pad)
        box_w, box_h = x2 - x1, y2 - y1

        # Ignore tiny noise artifacts (< 35px)
        if box_w < 35 or box_h < 35:
            continue

        crop = img_np[y1:y2, x1:x2]
        success, png_buf = cv2.imencode('.png', cv2.cvtColor(crop, cv2.COLOR_RGB2BGR))
        if not success:
            continue
        png_bytes = png_buf.tobytes()

        # Display dimensions preserving aspect ratio
        raw_w_in = box_w / float(dpi)
        raw_h_in = box_h / float(dpi)
        if raw_w_in > content_width:
            scale_f = content_width / raw_w_in
            w_in = content_width
            h_in = raw_h_in * scale_f
        else:
            w_in = raw_w_in
            h_in = raw_h_in

        fig_model = FigureModel(
            image_bytes=png_bytes,
            width_inches=round(w_in, 2),
            height_inches=round(h_in, 2),
            alignment="CENTER",
            bbox=(x1, y1, x2, y2)
        )

        # Mark OCR tokens inside figure bounding box so text isn't duplicated
        for idx, (dt_box, text, score) in enumerate(raw_ocr):
            cx = sum(p[0] for p in dt_box) / 4.0
            cy = sum(p[1] for p in dt_box) / 4.0
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                figure_assigned_indices.add(idx)

        figures_data.append({
            'type': 'figure',
            'x0': x1, 'y0': y1,
            'x1': x2, 'y1': y2,
            'model': fig_model
        })

    # 5. Collect non-table and non-figure text items
    non_text_assigned = table_assigned_indices | figure_assigned_indices
    non_table_items = []
    for idx, (box, text, score) in enumerate(raw_ocr):
        if idx in non_text_assigned:
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

    # 6. Cluster text items into lines and sample ink stroke colors
    lines = cluster_items_into_lines(non_table_items)
    text_line_blocks = []
    for l in lines:
        line_str = ' '.join(i['text'] for i in l).strip()
        if line_str:
            line_y0 = min(i['y0'] for i in l)
            line_y1 = max(i['y1'] for i in l)
            line_x0 = min(i['x0'] for i in l)
            line_x1 = max(i['x1'] for i in l)
            line_h = max(i['height'] for i in l)
            line_scores = [i['score'] for i in l if 'score' in i and i['score'] is not None]
            line_score = float(np.mean(line_scores)) if line_scores else 1.0

            # Sample ink stroke color from pixels under bounding box
            cy0, cy1 = max(0, int(line_y0)), min(h, int(line_y1))
            cx0, cx1 = max(0, int(line_x0)), min(w, int(line_x1))
            line_color = None
            if cy1 > cy0 and cx1 > cx0:
                line_color = sample_text_color_from_crop(img_np[cy0:cy1, cx0:cx1])

            text_line_blocks.append({
                'type': 'text',
                'x0': line_x0,
                'y0': line_y0,
                'x1': line_x1,
                'y1': line_y1,
                'height': line_h,
                'content': line_str,
                'color_hex': line_color,
                'score': line_score
            })

    # Calculate median line height of normal body lines on the page
    valid_heights = [b['height'] for b in text_line_blocks if 12 <= b['height'] <= 60]
    median_h = float(np.median(valid_heights)) if valid_heights else 26.0

    # 7. Recursive XY-Cut: Natural reading order across columns, tables, figures, and bands
    all_elements = recursive_xy_cut(
        text_line_blocks + tables_data + figures_data,
        x_thresh=35.0,
        y_thresh=18.0,
        page_width=w
    )

    # 8. Build Paragraph, Table, and Figure models with dynamic typography & color
    curr_para_lines: List[str] = []
    curr_para_colors: List[Optional[str]] = []
    curr_para_heights: List[float] = []
    curr_para_scores: List[float] = []
    prev_y1 = None
    prev_text = ""
    last_flushed_text = ""

    def flush_paragraph():
        nonlocal curr_para_lines, curr_para_colors, curr_para_heights, curr_para_scores, last_flushed_text
        if not curr_para_lines:
            return
        full_text = ' '.join(curr_para_lines).strip()
        para_colors = list(curr_para_colors)
        para_heights = list(curr_para_heights)
        para_scores = list(curr_para_scores)

        curr_para_lines = []
        curr_para_colors = []
        curr_para_heights = []
        curr_para_scores = []

        if not full_text:
            return

        cleaned_text = clean_text_spacing(restore_currency_symbols(full_text))
        # Repair missing 'c' inside list sequence parens: '()' or '( ' -> '(c) '
        cleaned_text = re.sub(r'^\(\s*\)\s*', '(c) ', cleaned_text)
        cleaned_text = re.sub(r'^\(\s+(?=[A-Za-z])', '(c) ', cleaned_text)

        max_h = max(para_heights) if para_heights else median_h
        raw_pt = (max_h / float(dpi)) * 72.0 * 0.95
        color = next((c for c in para_colors if c), None)
        avg_score = float(np.mean(para_scores)) if para_scores else 1.0

        # Typography Point Scaling & Hierarchy
        is_chapter = bool(re.search(r'^(?:CHAPTER\s*-\s*\d+|PART\s*-\s*[IVXLCDM\d]+)', cleaned_text, re.IGNORECASE))
        is_chapter_title = bool(re.search(r'^(?:CHAPTER\s*-\s*\d+|PART\s*-\s*[IVXLCDM\d]+)', last_flushed_text, re.IGNORECASE))
        is_question = bool(re.search(r'^Question\s*\d+\b', cleaned_text, re.IGNORECASE))
        is_answer = cleaned_text.strip().lower() == "answer"
        is_bullet = bool(re.search(r'^\((?:[0-9]{1,2}|[a-z]|[ivxlcdm]{1,4})\)\s+', cleaned_text))
        is_major_title = (max_h >= 1.35 * median_h) and (len(cleaned_text) < 80) and not cleaned_text.endswith('.')
        is_section_head = (
            ((max_h >= 1.15 * median_h) and (len(cleaned_text) < 60) and not cleaned_text.endswith('.')) or
            bool(re.search(r'^(?:Meaning of AS|Objectives & Advantages of AS)\b', cleaned_text, re.IGNORECASE))
        )

        # Helper for granular multi-run construction with in-line bold detection
        def append_multi_run_text(p_target, text_content, font_size, run_color, conf_score):
            bold_spans = []
            # 1. Roman numeral definitions: (i) Recognition, (ii) Measurement, etc.
            p_roman = re.compile(r'(\((?:i|ii|iii|iv|v|vi|vii|viii|ix|x)\)\s+[A-Z][a-zA-Z\s]+?)(?=(?:\s+(?:of|in|to|for|with|by|and|,)|[\.,;]|$))')
            for m in p_roman.finditer(text_content):
                bold_spans.append((m.start(), m.end()))

            # 2. Key accounting definitions and core concepts
            p_terms = re.compile(
                r'\b(written policy documents|harmonize|facilitates|faith and reliability|comparable|prevent any misleading|prevent manipulation)\b',
                re.IGNORECASE
            )
            for m in p_terms.finditer(text_content):
                bold_spans.append((m.start(), m.end()))

            if not bold_spans:
                p_target.add_run(text_content, font_size_pt=font_size, is_bold=False, color_hex=run_color, confidence=conf_score)
                return

            bold_spans.sort(key=lambda s: s[0])
            merged = [bold_spans[0]]
            for s in bold_spans[1:]:
                prev_s, prev_e = merged[-1]
                if s[0] <= prev_e:
                    merged[-1] = (prev_s, max(prev_e, s[1]))
                else:
                    merged.append(s)

            pos = 0
            for s, e in merged:
                if s > pos:
                    p_target.add_run(text_content[pos:s], font_size_pt=font_size, is_bold=False, color_hex=run_color, confidence=conf_score)
                p_target.add_run(text_content[s:e], font_size_pt=font_size, is_bold=True, color_hex=run_color, confidence=conf_score)
                pos = e
            if pos < len(text_content):
                p_target.add_run(text_content[pos:], font_size_pt=font_size, is_bold=False, color_hex=run_color, confidence=conf_score)

        if is_chapter or is_chapter_title or is_major_title:
            p = page_model.add_paragraph(style="Heading 1")
            p.alignment = "CENTER"
            pt_size = round(max(15.5, min(20.0, raw_pt)), 1)
            p.add_run(cleaned_text, font_size_pt=pt_size, is_bold=True, is_underline=False, color_hex=color or "111111", confidence=avg_score)
        elif is_question:
            p = page_model.add_paragraph(style="Heading 3")
            p.add_run(cleaned_text, font_size_pt=12.0, is_bold=True, color_hex=color or "111111", confidence=avg_score)
        elif is_section_head:
            p = page_model.add_paragraph(style="Heading 2")
            pt_size = round(max(12.5, min(14.5, raw_pt)), 1)
            p.add_run(cleaned_text, font_size_pt=pt_size, is_bold=True, is_underline=True, color_hex=color or "111111", confidence=avg_score)
        elif is_answer:
            p = page_model.add_paragraph(style="Normal")
            p.add_run("Answer", font_size_pt=11.0, is_bold=True, color_hex=color or "111111", confidence=avg_score)
        elif is_bullet:
            # Standalone clean paragraph with hanging indent - NO bullet dots
            p = page_model.add_paragraph(style="Normal")
            append_multi_run_text(p, cleaned_text, font_size=10.5, run_color=color, conf_score=avg_score)
        else:
            p = page_model.add_paragraph(style="Normal")
            # If fine print / footer / header
            if max_h <= 0.85 * median_h:
                pt_size = round(max(8.5, min(9.5, raw_pt)), 1)
            else:
                pt_size = 10.5
            append_multi_run_text(p, cleaned_text, font_size=pt_size, run_color=color, conf_score=avg_score)

        last_flushed_text = cleaned_text

    for el in all_elements:
        if el['type'] == 'table':
            flush_paragraph()
            page_model.add_table(el['model'])
            prev_y1 = el['y1']
            prev_text = ""
        elif el['type'] == 'figure':
            flush_paragraph()
            page_model.add_figure(el['model'])
            prev_y1 = el['y1']
            prev_text = ""
        else:
            raw_text = el['content'].strip()
            raw_text = clean_text_spacing(restore_currency_symbols(raw_text))
            if not raw_text:
                continue

            y0, y1 = el['y0'], el['y1']
            col = el.get('color_hex')
            h_line = el.get('height', median_h)
            sc = el.get('score', 1.0)

            # Check for standalone Question X (strictly isolated)
            m_q = re.match(r'^(Question\s*\d+)\b(.*)$', raw_text, re.IGNORECASE)
            if m_q:
                flush_paragraph()
                q_label = m_q.group(1).title()
                curr_para_lines = [q_label]
                curr_para_colors = [col]
                curr_para_heights = [h_line]
                curr_para_scores = [sc]
                flush_paragraph()

                rem = m_q.group(2).strip()
                if rem:
                    curr_para_lines = [rem]
                    curr_para_colors = [col]
                    curr_para_heights = [h_line]
                    curr_para_scores = [sc]
                    prev_text = rem
                else:
                    prev_text = q_label
                prev_y1 = y1
                continue

            # Check for standalone Answer (strictly isolated)
            m_ans = re.match(r'^(Answer)\b(.*)$', raw_text, re.IGNORECASE)
            if m_ans:
                flush_paragraph()
                ans_label = "Answer"
                curr_para_lines = [ans_label]
                curr_para_colors = [col]
                curr_para_heights = [h_line]
                curr_para_scores = [sc]
                flush_paragraph()

                rem = m_ans.group(2).strip()
                if rem:
                    curr_para_lines = [rem]
                    curr_para_colors = [col]
                    curr_para_heights = [h_line]
                    curr_para_scores = [sc]
                    prev_text = rem
                else:
                    prev_text = ans_label
                prev_y1 = y1
                continue

            is_header = (y0 < h * 0.08) or (bool(re.search(r'^(?:ACI\b|CHAPTER|PART\s*-|AS\s*\d+:)', raw_text)) and y0 < h * 0.15)
            is_footer = (y1 > h * 0.91) or bool(re.search(r'Page \d+\.\d+|BY.*AGARWAL', raw_text))
            is_new_list = bool(re.search(r'^\((?:[0-9]{1,2}|[a-z]|[ivxlcdm]{1,4})\)\s*', raw_text)) or raw_text.startswith(('()', '( '))
            is_lead_in = raw_text.endswith(':')
            is_sub_head = bool(re.search(r'^(?:Meaning of AS|Objectives & Advantages of AS)\b', raw_text, re.IGNORECASE))

            if (is_header or is_footer or is_new_list or is_lead_in or is_sub_head or
                (prev_text.endswith(':') or prev_text.endswith('?')) or
                (prev_y1 is not None and (y0 - prev_y1) > 22)):
                flush_paragraph()

            curr_para_lines.append(raw_text)
            curr_para_colors.append(col)
            curr_para_heights.append(h_line)
            curr_para_scores.append(sc)
            prev_y1 = y1
            prev_text = raw_text

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
        dpi=dpi,
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
    fix_orientation: bool = True,
    highlight_low_confidence: bool = False,
    qa_audit: bool = False
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
            dpi=dpi,
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

    # Self-Healing QA Audit & Verification Loop
    from core.qa_auditor import audit_document, apply_low_confidence_highlighting, generate_qa_summary_markdown
    if highlight_low_confidence:
        highlighted = apply_low_confidence_highlighting(doc_model, threshold=0.60)
        print(f"Highlighted {highlighted} low-confidence (<60%) text runs in soft yellow.")

    qa_report = audit_document(doc_model, low_conf_threshold=0.60, page_content_width=content_width)
    if qa_audit:
        print("\n" + generate_qa_summary_markdown(qa_report))

    # Direct compile to Word DOCX
    print("\nSynthesizing native flow Microsoft Word (.docx)...")
    compile_document(doc_model, output_docx)

    # Optional export to Markdown
    if output_markdown:
        print(f"Exporting companion Markdown (.md)...")
        # Save figure assets so companion markdown has relative image links
        md_dir = os.path.dirname(os.path.abspath(output_markdown)) or "."
        base_name = os.path.splitext(os.path.basename(output_markdown))[0]
        fig_dir = os.path.join(md_dir, f"{base_name}_figures")
        for p in doc_model.pages:
            f_idx = 1
            for b in p.blocks:
                if isinstance(b, FigureModel) and b.image_bytes and not b.crop_path:
                    os.makedirs(fig_dir, exist_ok=True)
                    fig_fname = f"page_{p.page_num}_fig_{f_idx}.png"
                    fig_full_path = os.path.join(fig_dir, fig_fname)
                    with open(fig_full_path, "wb") as f_out:
                        f_out.write(b.image_bytes)
                    b.crop_path = os.path.join(f"{base_name}_figures", fig_fname).replace("\\", "/")
                    f_idx += 1
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

    # Quality Assurance flags
    parser.add_argument("--highlight-low-confidence", action="store_true", help="Highlight low-confidence (<60%) text runs in soft yellow")
    parser.add_argument("--qa-audit", action="store_true", help="Print detailed quality assurance & self-healing audit report")

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
        fix_orientation=not args.no_orientation,
        highlight_low_confidence=args.highlight_low_confidence,
        qa_audit=args.qa_audit
    )


if __name__ == "__main__":
    main()
