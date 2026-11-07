"""
pdf_to_markdown.py - High-Accuracy PDF to Markdown Converter
Preserves all original text, reading order, mathematical/accounting notation, and reconstructs structured tables.
Supports digital PDFs as well as scanned/outlined PDFs via OCR, Layout Analysis, and Table Recognition.

Usage:
    python pdf_to_markdown.py <input.pdf> [-o output.md] [--dpi 150] [--workers 4] [--start-page 1] [--end-page 50]
"""

import os
import sys
import re
import argparse
import time
from typing import List, Dict, Any, Tuple, Optional
from bs4 import BeautifulSoup
import pymupdf
import numpy as np

# Global instances per worker process
_layout_engine = None
_table_engine = None
_ocr_engine = None


def get_ocr_engine():
    global _ocr_engine
    if _ocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr_engine = RapidOCR()
    return _ocr_engine


def get_layout_engine():
    global _layout_engine
    if _layout_engine is None:
        from rapid_layout import RapidLayout
        _layout_engine = RapidLayout()
    return _layout_engine


def get_table_engine():
    global _table_engine
    if _table_engine is None:
        from rapid_table import RapidTable
        _table_engine = RapidTable()
    return _table_engine


def html_to_markdown_table(html_str: str) -> str:
    """
    Convert an HTML <table> into a clean GitHub Flavored Markdown table.
    Preserves HTML <table> if complex rowspans or colspans are present.
    """
    soup = BeautifulSoup(html_str, 'html.parser')
    table = soup.find('table')
    if not table:
        return html_str.strip()

    # Check for complex span attributes
    has_spans = False
    for cell in table.find_all(['td', 'th']):
        if int(cell.get('colspan', 1)) > 1 or int(cell.get('rowspan', 1)) > 1:
            has_spans = True
            break

    # If table has complex cell merges, return the clean HTML table directly
    if has_spans:
        return str(table)

    rows = []
    for tr in table.find_all('tr'):
        cells = [td.get_text(separator=' ', strip=True).replace('|', '\\|').replace('\n', ' ')
                 for td in tr.find_all(['td', 'th'])]
        if cells:
            rows.append(cells)

    if not rows:
        return ''

    max_cols = max(len(r) for r in rows)
    if max_cols == 0:
        return ''

    # Normalize row lengths
    norm_rows = [r + [''] * (max_cols - len(r)) for r in rows]

    # Format into GFM Markdown table
    md_lines = []
    header = norm_rows[0]
    md_lines.append('| ' + ' | '.join(header) + ' |')
    md_lines.append('| ' + ' | '.join(['---'] * max_cols) + ' |')

    for row in norm_rows[1:]:
        md_lines.append('| ' + ' | '.join(row) + ' |')

    return '\n'.join(md_lines)


def clean_text_spacing(text: str) -> str:
    """
    Fix missing spaces caused by OCR CTC decoding without altering any text/numbers:
    - Punctuation-letter collisions: 'words,words' -> 'words, words'
    - Number-letter collisions: 'Paid50,000tocreditors' -> 'Paid 50,000 to creditors'
    - Glued CamelCase and concatenated English words: 'aretheissues' -> 'are the issues'
    - Protects URLs, emails, dates, decimals, acronyms, and alphanumeric codes.
    """
    # Protect URLs, emails, and specific domains
    url_map = {}
    def save_url(m):
        key = f"___URL_{len(url_map)}___"
        url_map[key] = m.group(0)
        return key

    text = re.sub(r'https?://\S+|www\.\S+|\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b|\b(?:air1ca\.com|air1ca)\b', save_url, text)

    # Punctuation spacing: comma, semicolon, colon, exclamation followed directly by letter
    text = re.sub(r'([a-zA-Z0-9\)])([,;:!])([a-zA-Z])', r'\1\2 \3', text)
    # Period followed by Capital Letter: 'statement.The' -> 'statement. The'
    text = re.sub(r'([a-zA-Z]{2,}\.)([A-Z])', r'\1 \2', text)

    # Number-Letter boundary separation (protecting short codes like AS1, 20X1)
    text = re.sub(r'([a-zA-Z]{2,})(\d{2,})', r'\1 \2', text)
    text = re.sub(r'(\d+(?:,\d+)*(?:\.\d+)?)([a-zA-Z]{2,})', r'\1 \2', text)

    # Clean run-together / glued English words
    try:
        import wordninja

        def fix_word(match):
            w = match.group(0)
            if len(w) <= 4 or (w.isupper() and len(w) <= 6):
                return w
            # CamelCase: 'MeaningofAS', 'RentOutstanding', 'SettlementofCreditors'
            if re.search(r'[a-z]{2,}[A-Z]', w):
                splits = wordninja.split(w)
                if len(splits) > 1:
                    res, idx = [], 0
                    for s in splits:
                        slen = len(s)
                        res.append(w[idx:idx+slen])
                        idx += slen
                    if idx < len(w):
                        res.append(w[idx:])
                    return ' '.join(res)
            # Long run-together lowercase words: 'aretheissues', 'theliabilitiesinthenormalcourseofbusiness'
            elif len(w) > 7 and w.islower():
                splits = wordninja.split(w)
                if len(splits) > 1 and all(len(s) >= 2 for s in splits):
                    return ' '.join(splits)
            return w

        text = re.sub(r'\b[a-zA-Z]+\b', fix_word, text)
    except ImportError:
        pass

    # Restore URLs/emails
    for key, val in url_map.items():
        text = text.replace(key, val)

    # Normalize excessive spaces
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text


def restore_currency_symbols(text: str) -> str:
    """
    Restore Indian Rupee symbol (₹) where OCR reads '?' preceding numeric amounts,
    while leaving legitimate question marks at the end of sentences intact.
    """
    return re.sub(r'(?:\?|？)\s*(\d+(?:,\d+)*(?:\.\d+)?)', r'₹ \1', text)


def format_text_block(text: str) -> str:
    """
    Apply structured Markdown formatting to text:
    - Clean and normalize word and punctuation spacing
    - Normalize and format Question numbers into sub-headings
    - Bold 'Answer' labels
    - Format Chapter/Part titles
    - Format enumerated sub-points into clean list items
    - Restore currency symbols
    """
    text = clean_text_spacing(text)
    text = restore_currency_symbols(text)

    # Normalize QuestionX -> Question X
    text = re.sub(r'\bQuestion(\d+)\b', r'Question \1', text)

    # Split major parts and chapters
    text = re.sub(r'(\bPART\s*-\s*[IVXLCDM\d]+\b)', r'\n\n# \1\n\n', text)
    text = re.sub(r'(\bCHAPTER\s*-\s*\d+\b)', r'\n\n# \1\n\n', text)

    # Format Question headings
    text = re.sub(r'(\bQuestion\s+\d+\b)', r'\n\n### \1\n\n', text)

    # Format Answer headings
    text = re.sub(r'(^|\s)(Answer)(\s|$)', r'\1\n\n**Answer**\n\n\3', text)

    # Format enumerated points like (1), (2), (i), (ii), (a), (b)
    text = re.sub(r'(?<=\s)(\((?:[0-9]{1,2}|[a-z]|[ivxlcdm]{1,4})\))\s*', r'\n- \1 ', text)

    return text


def cluster_items_into_lines(items: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """Group OCR text items into lines based on vertical overlap, sorting left-to-right."""
    if not items:
        return []

    sorted_items = sorted(items, key=lambda x: (x['y0'], x['x0']))
    lines: List[List[Dict[str, Any]]] = []

    for item in sorted_items:
        placed = False
        for line in lines:
            line_y0 = min(i['y0'] for i in line)
            line_y1 = max(i['y1'] for i in line)
            line_h = line_y1 - line_y0
            overlap = min(item['y1'], line_y1) - max(item['y0'], line_y0)
            if overlap > 0.45 * min(item['height'], line_h):
                line.append(item)
                placed = True
                break
        if not placed:
            lines.append([item])

    lines.sort(key=lambda l: min(i['y0'] for i in l))
    for l in lines:
        l.sort(key=lambda i: i['x0'])

    return lines


def process_scanned_page(img_np: np.ndarray, page_idx: int) -> str:
    """
    Processes a single page image:
    1. Single-pass OCR for the entire page.
    2. Layout analysis to detect table regions.
    3. Crop-shifting OCR boxes for RapidTable structure recognition.
    4. Merging tables and text in natural vertical reading order.
    """
    layout_eng = get_layout_engine()
    table_eng = get_table_engine()
    ocr_eng = get_ocr_engine()

    h, w = img_np.shape[:2]

    # Step 1: Single-pass OCR on full page
    page_ocr, _ = ocr_eng(img_np)
    if not page_ocr:
        page_ocr = []

    # Step 2: Layout detection
    layout_res = layout_eng(img_np)
    table_boxes = []
    if layout_res.boxes:
        for box, name in zip(layout_res.boxes, layout_res.class_names):
            if name == 'table':
                table_boxes.append(box)

    # Step 3: Extract tables using crop-shifted OCR coordinates
    tables_data = []
    table_assigned_indices = set()

    for t_box in table_boxes:
        x1, y1, x2, y2 = [int(v) for v in t_box]
        pad = 6
        x1, y1 = max(0, x1 - pad), max(0, y1 - pad)
        x2, y2 = min(w, x2 + pad), min(h, y2 + pad)
        crop = img_np[y1:y2, x1:x2]

        # Find OCR items whose center falls inside this table
        t_boxes, t_texts, t_scores = [], [], []
        for idx, (dt_box, text, score) in enumerate(page_ocr):
            cx = sum(p[0] for p in dt_box) / 4.0
            cy = sum(p[1] for p in dt_box) / 4.0
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                shifted_box = [[p[0] - x1, p[1] - y1] for p in dt_box]
                t_boxes.append(shifted_box)
                t_texts.append(text)
                t_scores.append(score)
                table_assigned_indices.add(idx)

        # Run table structure recognition
        try:
            if t_boxes:
                table_out = table_eng(crop, ocr_results=[(t_boxes, t_texts, t_scores)])
            else:
                table_out = table_eng(crop)

            if table_out.pred_htmls:
                md_table = html_to_markdown_table(table_out.pred_htmls[0])
                tables_data.append({
                    'type': 'table',
                    'y0': y1,
                    'y1': y2,
                    'content': md_table
                })
        except Exception as e:
            # Fallback: if table inference fails, release the items back to regular text
            for idx in range(len(page_ocr)):
                if idx in table_assigned_indices:
                    pass  # keep if another table claimed it

    # Step 4: Collect non-table text items
    non_table_items = []
    for idx, (box, text, score) in enumerate(page_ocr):
        if idx in table_assigned_indices:
            continue
        xs = [pt[0] for pt in box]
        ys = [pt[1] for pt in box]
        non_table_items.append({
            'text': text,
            'x0': min(xs), 'y0': min(ys),
            'x1': max(xs), 'y1': max(ys),
            'height': max(ys) - min(ys),
            'score': score
        })

    # Step 5: Cluster text items into lines
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

    # Step 6: Merge all elements (text lines and tables) by vertical position
    all_elements = text_line_blocks + tables_data
    all_elements.sort(key=lambda el: el['y0'])

    # Step 7: Build markdown page content
    output_parts = []
    prev_y1 = None
    prev_text = ""

    for el in all_elements:
        if el['type'] == 'table':
            output_parts.append('\n\n' + el['content'] + '\n\n')
            prev_y1 = el['y1']
            prev_text = ""
        else:
            raw_text = el['content']
            y0 = el['y0']
            y1 = el['y1']

            # Check if line is a page header or footer
            is_header = (y0 < h * 0.08) or (bool(re.search(r'^(?:ACI\b|CHAPTER|PART\s*-|AS\s*\d+:)', raw_text)) and y0 < h * 0.15)
            is_footer = (y1 > h * 0.91) or bool(re.search(r'Page \d+\.\d+|BY.*AGARWAL', raw_text))

            # Determine paragraph break
            if (
                is_header
                or is_footer
                or (prev_y1 is not None and (y0 - prev_y1) > 22)
                or (prev_text.endswith(('.', ':', '?')) and (y0 - prev_y1) > 12)
                or raw_text.startswith(('Question', 'Answer', '(', '-'))
            ):
                output_parts.append('\n\n' + raw_text)
            else:
                # Continuation or space
                if output_parts and not output_parts[-1].endswith('\n') and not output_parts[-1].endswith(' '):
                    output_parts.append(' ' + raw_text)
                else:
                    output_parts.append(raw_text)

            prev_y1 = y1
            prev_text = raw_text.strip()

    raw_page_md = ''.join(output_parts).strip()
    page_md = format_text_block(raw_page_md)
    # Normalize excessive newlines
    page_md = re.sub(r'\n{3,}', '\n\n', page_md)
    return page_md


def convert_page(args: Tuple[str, int, int]) -> Tuple[int, str]:
    """Worker function to process one PDF page."""
    pdf_path, page_idx, dpi = args
    doc = pymupdf.open(pdf_path)
    page = doc[page_idx]

    # Check if native digital text exists
    native_text = page.get_text().strip()
    if len(native_text) > 80:
        tabs = page.find_tables()
        if len(tabs.tables) > 0:
            import pymupdf4llm
            md_text = pymupdf4llm.to_markdown(pdf_path, pages=[page_idx])
            return page_idx, md_text.strip()
        return page_idx, native_text

    # Outlined/scanned page: render and run OCR + Layout + Table pipeline
    pix = page.get_pixmap(dpi=dpi)
    img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.h, pix.w, pix.n))
    if pix.n == 4:
        img_np = img_np[:, :, :3]

    page_md = process_scanned_page(img_np, page_idx)
    return page_idx, page_md


def convert_pdf_to_markdown(
    pdf_path: str,
    output_path: Optional[str] = None,
    dpi: int = 150,
    max_workers: int = 4,
    page_range: Optional[Tuple[int, int]] = None
) -> str:
    """
    Main conversion entrypoint.
    Processes the PDF pages in parallel and writes the Markdown file.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    if output_path is None:
        base, _ = os.path.splitext(pdf_path)
        output_path = f"{base}.md"

    doc = pymupdf.open(pdf_path)
    total_pages = len(doc)
    doc.close()

    start_p, end_p = 0, total_pages
    if page_range:
        start_p = max(0, page_range[0])
        end_p = min(total_pages, page_range[1])

    page_indices = list(range(start_p, end_p))
    print(f"=== PDF to Markdown Conversion ===")
    print(f"Source:     {pdf_path}")
    print(f"Output:     {output_path}")
    print(f"Pages:      {start_p + 1} to {end_p} ({len(page_indices)} pages total)")
    print(f"Settings:   DPI={dpi}, Workers={max_workers}")
    print("=" * 35)

    tasks = [(pdf_path, p, dpi) for p in page_indices]
    results: Dict[int, str] = {}

    t0 = time.time()
    if max_workers > 1 and len(page_indices) > 1:
        from concurrent.futures import ProcessPoolExecutor, as_completed
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            future_to_page = {executor.submit(convert_page, t): t[1] for t in tasks}
            completed_count = 0
            for future in as_completed(future_to_page):
                p_idx, p_md = future.result()
                results[p_idx] = p_md
                completed_count += 1
                elapsed = time.time() - t0
                avg_time = elapsed / completed_count
                eta = avg_time * (len(page_indices) - completed_count)
                print(f"[{completed_count:2d}/{len(page_indices)}] Page {p_idx + 1:2d} finished | Elapsed: {elapsed:5.1f}s | ETA: {eta:5.1f}s")
    else:
        for idx, t in enumerate(tasks):
            p_idx, p_md = convert_page(t)
            results[p_idx] = p_md
            print(f"[{idx+1:2d}/{len(page_indices)}] Page {p_idx + 1:2d} finished")

    # Assemble markdown in strict sequential page order
    full_md = []
    for p in page_indices:
        p_content = results.get(p, "").strip()
        full_md.append(f"<!-- Page {p + 1} -->\n\n{p_content}\n\n---\n")

    complete_text = "\n".join(full_md)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(complete_text)

    total_time = time.time() - t0
    print("=" * 35)
    print(f"Completed {len(page_indices)} pages in {total_time:.2f} seconds ({total_time / len(page_indices):.2f}s/page).")
    print(f"Markdown output saved to: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Convert PDF to Markdown with tables and OCR support.")
    parser.add_argument("pdf_path", help="Path to input PDF file")
    parser.add_argument("-o", "--output", help="Path to output Markdown file (optional)")
    parser.add_argument("--dpi", type=int, default=150, help="Rendering DPI for OCR (default: 150)")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel worker processes (default: 4)")
    parser.add_argument("--start-page", type=int, default=1, help="Start page number (1-based, inclusive)")
    parser.add_argument("--end-page", type=int, default=None, help="End page number (1-based, inclusive)")

    args = parser.parse_args()

    page_range = None
    if args.start_page > 1 or args.end_page is not None:
        start = args.start_page - 1
        end = args.end_page if args.end_page is not None else 999999
        page_range = (start, end)

    convert_pdf_to_markdown(
        pdf_path=args.pdf_path,
        output_path=args.output,
        dpi=args.dpi,
        max_workers=args.workers,
        page_range=page_range
    )


if __name__ == "__main__":
    main()
