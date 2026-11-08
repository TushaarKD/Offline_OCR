"""
table_engine.py - Neural Table Structure Extraction & Modeling
Extracts 2D cell matrices, spans, alignments, border styles, and background shading from table image crops into TableModel.
"""

from typing import List, Tuple, Dict, Any, Optional
import re
import logging
import numpy as np
import cv2
from bs4 import BeautifulSoup

logger = logging.getLogger("OCRTableEngine")

from core.document_ir import TableModel, TableCellModel
from core.ocr_engine import clean_text_spacing, restore_currency_symbols
from core.layout_engine import sample_cell_background_color

def get_table_instance():
    from core.model_manager import get_table_engine
    return get_table_engine()


def detect_table_borders(crop_img: np.ndarray) -> bool:
    """
    Detects whether a table has visible printed grid lines or is borderless (aligned via whitespace).
    """
    if crop_img is None or crop_img.size == 0:
        return True
    gray = cv2.cvtColor(crop_img, cv2.COLOR_RGB2GRAY) if len(crop_img.shape) == 3 else crop_img
    h, w = gray.shape
    if h < 20 or w < 20:
        return True

    bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 3)
    k_w = max(10, int(w * 0.15))
    k_h = max(10, int(h * 0.15))
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k_w, 1))
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, k_h))

    h_lines = cv2.morphologyEx(bw, cv2.MORPH_OPEN, h_kernel)
    v_lines = cv2.morphologyEx(bw, cv2.MORPH_OPEN, v_kernel)
    total_line_pixels = int(np.sum(h_lines > 0) + np.sum(v_lines > 0))

    return total_line_pixels > 150


def _detect_cell_alignment(text: str, is_header: bool) -> str:
    """Detect whether cell content should be LEFT, RIGHT, or CENTER aligned."""
    s = text.strip()
    if is_header:
        return "CENTER"
    if s in ("=", "-", "+", "/", "x", "X", "Nil", "NIL", "—", "–"):
        return "CENTER"
    # Pure numbers, amounts, currencies, or calculations: e.g. "50,000", "₹ 10,000", "(12 - 0.49)"
    num_chars = sum(c.isdigit() for c in s)
    total_alpha = sum(c.isalpha() for c in s)
    if num_chars > 0 and num_chars >= total_alpha:
        return "RIGHT"
    return "LEFT"


def parse_html_table_to_model(
    html_str: str,
    crop_img: Optional[np.ndarray] = None,
    cell_bboxes: Optional[List[Any]] = None,
    page_content_width: float = 7.0
) -> Optional[TableModel]:
    """Parse HTML table and cell bounding boxes into a structured TableModel."""
    soup = BeautifulSoup(html_str, 'html.parser')
    table_soup = soup.find('table')
    if not table_soup:
        return None

    raw_rows = table_soup.find_all('tr')
    if not raw_rows:
        return None

    # Track grid placement
    occupied: Dict[Tuple[int, int], bool] = {}
    cell_records: List[Dict[str, Any]] = []
    max_c = 0
    max_r = len(raw_rows)
    cell_idx = 0

    for r_idx, tr in enumerate(raw_rows):
        curr_c = 0
        for cell_elem in tr.find_all(['td', 'th']):
            while (r_idx, curr_c) in occupied:
                curr_c += 1

            rs = int(cell_elem.get('rowspan', 1))
            cs = int(cell_elem.get('colspan', 1))
            is_hdr = (cell_elem.name == 'th' or r_idx == 0)
            raw_t = cell_elem.get_text(separator=' ', strip=True)
            cleaned_t = clean_text_spacing(restore_currency_symbols(raw_t))
            align = _detect_cell_alignment(cleaned_t, is_hdr)

            # Sample cell background shading if crop and cell_bboxes are available
            bg_color = None
            if crop_img is not None and cell_bboxes is not None and len(cell_bboxes) > 0 and cell_idx < len(cell_bboxes):
                b = cell_bboxes[cell_idx]
                if len(b) >= 4:
                    if len(b) == 8:
                        xs = [b[0], b[2], b[4], b[6]]
                        ys = [b[1], b[3], b[5], b[7]]
                    else:
                        xs = [b[0], b[2]]
                        ys = [b[1], b[3]]
                    bx0, by0 = max(0, int(min(xs))), max(0, int(min(ys)))
                    bx1, by1 = min(crop_img.shape[1], int(max(xs))), min(crop_img.shape[0], int(max(ys)))
                    if bx1 > bx0 and by1 > by0:
                        cell_crop = crop_img[by0:by1, bx0:bx1]
                        bg_color = sample_cell_background_color(cell_crop)

            if bg_color is None and is_hdr:
                bg_color = "F2F4F7"

            cell_records.append({
                'r': r_idx, 'c': curr_c,
                'rs': rs, 'cs': cs,
                'text': cleaned_t,
                'is_hdr': is_hdr,
                'alignment': align,
                'bg_color': bg_color
            })
            cell_idx += 1

            for dr in range(rs):
                for dc in range(cs):
                    occupied[(r_idx + dr, curr_c + dc)] = True
                    max_r = max(max_r, r_idx + dr + 1)
                    max_c = max(max_c, curr_c + dc + 1)
            curr_c += cs

    if max_r == 0 or max_c == 0:
        return None

    # Initialize empty grid
    grid: List[List[TableCellModel]] = [
        [TableCellModel(row_idx=r, col_idx=c) for c in range(max_c)]
        for r in range(max_r)
    ]

    # Populate grid with cell records
    for rec in cell_records:
        r, c = rec['r'], rec['c']
        cell = grid[r][c]
        cell.text = rec['text']
        cell.rowspan = rec['rs']
        cell.colspan = rec['cs']
        cell.is_header = rec['is_hdr']
        cell.alignment = rec['alignment']
        cell.bg_color_hex = rec['bg_color']

    # Calculate proportional column widths
    col_lens = [3.0] * max_c
    for rec in cell_records:
        if rec['cs'] == 1:
            col_lens[rec['c']] = max(col_lens[rec['c']], float(len(rec['text'])))
    total_len = sum(col_lens)
    raw_w = [max(0.5, (l / total_len) * page_content_width) for l in col_lens]
    scale = page_content_width / sum(raw_w)
    widths = [w * scale for w in raw_w]

    has_borders = detect_table_borders(crop_img) if crop_img is not None else True

    t_model = TableModel(
        rows=grid,
        num_rows=max_r,
        num_cols=max_c,
        col_widths_inches=widths,
        style="Table Grid" if has_borders else "Light Shading",
        has_borders=has_borders,
        alignment="CENTER"
    )
    return t_model


def extract_geometric_table(crop_img: Optional[np.ndarray],
                            table_ocr_boxes: List[Any],
                            table_ocr_texts: List[str],
                            table_ocr_scores: List[float],
                            page_content_width: float = 7.0) -> Optional[TableModel]:
    """
    Industry-standard deterministic geometric table extraction.
    Replaces neural sequence models by using physical ruling lines and whitespace gutter analysis
    to reconstruct tables with 100% data fidelity and zero hallucinated rowspans.
    """
    if not table_ocr_boxes or not table_ocr_texts:
        return None

    items = []
    for box, text in zip(table_ocr_boxes, table_ocr_texts):
        cleaned_t = clean_text_spacing(restore_currency_symbols(text.strip()))
        if not cleaned_t:
            continue
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        items.append({
            'x0': x0, 'x1': x1,
            'y0': y0, 'y1': y1,
            'cx': (x0 + x1) / 2.0,
            'cy': (y0 + y1) / 2.0,
            'h': max(1.0, y1 - y0),
            'text': cleaned_t
        })

    if not items:
        return None

    crop_h = crop_img.shape[0] if crop_img is not None else int(max(it['y1'] for it in items) + 10)
    crop_w = crop_img.shape[1] if crop_img is not None else int(max(it['x1'] for it in items) + 10)

    # 1. Detect column boundaries
    col_intervals = []

    # Method A: Physical vertical ruling lines
    if crop_img is not None and crop_img.size > 0:
        gray = cv2.cvtColor(crop_img, cv2.COLOR_RGB2GRAY) if len(crop_img.shape) == 3 else crop_img
        bw = cv2.adaptiveThreshold(~gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, -2)
        v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(20, int(crop_h * 0.15))))
        v_lines = cv2.morphologyEx(bw, cv2.MORPH_OPEN, v_kernel)
        v_proj = np.sum(v_lines, axis=0)
        v_peaks = np.where(v_proj > max(50 * 255, 0.20 * crop_h * 255))[0]
        if len(v_peaks) > 0:
            clusters = np.split(v_peaks, np.where(np.diff(v_peaks) > 8)[0] + 1)
            line_x = [int(np.mean(c)) for c in clusters]
            if len(line_x) >= 2:
                pts = line_x[:]
                if pts[0] > 35:
                    pts.insert(0, 0)
                if crop_w - pts[-1] > 35:
                    pts.append(crop_w)
                for i in range(len(pts) - 1):
                    if pts[i+1] - pts[i] > 20:
                        col_intervals.append((pts[i], pts[i+1]))

    # Method B: Whitespace gutters (if no physical vertical lines or < 2 intervals)
    if len(col_intervals) < 2:
        col_intervals = []
        occ = np.zeros(crop_w, dtype=np.int32)
        for it in items:
            x0 = max(0, min(crop_w - 1, int(it['x0'])))
            x1 = max(0, min(crop_w, int(it['x1'])))
            occ[x0:x1] += 1

        min_x = int(min(it['x0'] for it in items))
        max_x = int(max(it['x1'] for it in items))

        gutters = []
        in_gutter = False
        g_start = 0
        for x in range(min_x, max_x):
            if occ[x] == 0:
                if not in_gutter:
                    in_gutter = True
                    g_start = x
            else:
                if in_gutter:
                    in_gutter = False
                    if x - g_start >= 12:  # At least 12px whitespace gap
                        gutters.append(int((g_start + x) / 2))

        cuts = [0] + gutters + [crop_w]
        for i in range(len(cuts) - 1):
            if cuts[i+1] - cuts[i] > 20:
                col_intervals.append((cuts[i], cuts[i+1]))

    if not col_intervals:
        col_intervals = [(0, crop_w)]

    num_cols = len(col_intervals)

    # 2. Cluster tokens into horizontal rows
    items.sort(key=lambda it: it['y0'])
    rows: List[List[Dict[str, Any]]] = []
    for it in items:
        placed = False
        for r in rows:
            r_y0 = min(x['y0'] for x in r)
            r_y1 = max(x['y1'] for x in r)
            r_h = max(1.0, r_y1 - r_y0)
            overlap = min(it['y1'], r_y1) - max(it['y0'], r_y0)
            if overlap > 0.45 * min(it['h'], r_h):
                r.append(it)
                placed = True
                break
        if not placed:
            rows.append([it])

    rows.sort(key=lambda r: min(x['y0'] for x in r))
    for r in rows:
        r.sort(key=lambda x: x['x0'])

    # 3. Construct TableCellModel grid
    grid: List[List[TableCellModel]] = []
    for r_idx, r in enumerate(rows):
        is_hdr = (r_idx == 0)

        # Check if single spanning row (e.g. section title like 'Operating Activities:')
        is_span = False
        if len(r) == 1 and num_cols > 1 and r_idx > 0:
            if r[0]['text'].endswith(':') or (r[0]['x1'] - r[0]['x0']) > (0.45 * crop_w):
                is_span = True

        if is_span:
            cell = TableCellModel(
                row_idx=r_idx,
                col_idx=0,
                rowspan=1,
                colspan=num_cols,
                text=r[0]['text'],
                is_header=False,
                alignment=_detect_cell_alignment(r[0]['text'], False),
                bg_color_hex=None
            )
            row_cells = [cell]
            for c_idx in range(1, num_cols):
                row_cells.append(TableCellModel(row_idx=r_idx, col_idx=c_idx, text="", is_header=False))
            grid.append(row_cells)
            continue

        # Normal row: initialize empty cells for every column
        row_cells = [
            TableCellModel(
                row_idx=r_idx,
                col_idx=c,
                text="",
                is_header=is_hdr,
                bg_color_hex="F2F4F7" if is_hdr else None
            )
            for c in range(num_cols)
        ]

        for it in r:
            best_c = 0
            for c_idx, (c_start, c_end) in enumerate(col_intervals):
                if c_start <= it['cx'] < c_end:
                    best_c = c_idx
                    break
                elif it['cx'] >= col_intervals[-1][0]:
                    best_c = num_cols - 1

            if row_cells[best_c].text:
                row_cells[best_c].text += " " + it['text']
            else:
                row_cells[best_c].text = it['text']

        for c_cell in row_cells:
            c_cell.alignment = _detect_cell_alignment(c_cell.text, is_hdr)

        grid.append(row_cells)

    if not grid:
        return None

    # 4. Proportional widths
    col_lens = [3.0] * num_cols
    for row in grid:
        for c_cell in row:
            if c_cell.colspan == 1:
                col_lens[c_cell.col_idx] = max(col_lens[c_cell.col_idx], float(len(c_cell.text)))
    total_len = sum(col_lens)
    raw_w = [max(0.5, (l / total_len) * page_content_width) for l in col_lens]
    scale = page_content_width / sum(raw_w)
    widths = [w * scale for w in raw_w]

    has_borders = detect_table_borders(crop_img) if crop_img is not None else True

    return TableModel(
        rows=grid,
        num_rows=len(grid),
        num_cols=num_cols,
        col_widths_inches=widths,
        style="Table Grid" if has_borders else "Light Shading",
        has_borders=has_borders,
        alignment="CENTER"
    )


def extract_table_model(crop_img: np.ndarray,
                        table_ocr_boxes: List[Any],
                        table_ocr_texts: List[str],
                        table_ocr_scores: List[float],
                        page_content_width: float = 7.0) -> Optional[TableModel]:
    """
    Extracts table structure.
    Uses deterministic geometric extraction first (guaranteeing 100% token preservation,
    zero hallucinated rowspans, and accurate numeric column alignment).
    Falls back to SLANet+ only if geometric extraction yields empty grid.
    """
    # 1. Primary: Deterministic Geometric Grid Extraction
    if table_ocr_boxes and len(table_ocr_boxes) > 0:
        geom_model = extract_geometric_table(
            crop_img=crop_img,
            table_ocr_boxes=table_ocr_boxes,
            table_ocr_texts=table_ocr_texts,
            table_ocr_scores=table_ocr_scores,
            page_content_width=page_content_width
        )
        if geom_model is not None and geom_model.num_rows > 0:
            return geom_model

    # 2. Auxiliary Fallback: Neural SLANet+
    table_engine = get_table_instance()
    try:
        if table_ocr_boxes and len(table_ocr_boxes) > 0:
            boxes = table_ocr_boxes
            texts = [restore_currency_symbols(t) for t in table_ocr_texts]
            scores = table_ocr_scores
        else:
            # Provide dummy single box with empty text so format_ocr_results has valid 2D array
            boxes = [[[0, 0], [1, 0], [1, 1], [0, 1]]]
            texts = [""]
            scores = [0.0]

        out = table_engine(crop_img, ocr_results=[(boxes, texts, scores)])

        if out and out.pred_htmls and len(out.pred_htmls) > 0:
            html = out.pred_htmls[0]
            cell_boxes = out.cell_bboxes[0] if (out.cell_bboxes is not None and len(out.cell_bboxes) > 0) else None
            return parse_html_table_to_model(
                html,
                crop_img=crop_img,
                cell_bboxes=cell_boxes,
                page_content_width=page_content_width
            )
        else:
            logger.warning("RapidTable returned empty pred_htmls")
    except Exception as exc:
        logger.warning(f"Table extraction failed: {exc}", exc_info=True)
    return None


def build_fallback_table_model(table_ocr_boxes: List[Any],
                               table_ocr_texts: List[str],
                               crop_img: Optional[np.ndarray] = None,
                               page_content_width: float = 7.0) -> Optional[TableModel]:
    """
    Synthesizes a TableModel directly from spatial clustering of OCR tokens
    when neural SLANet+ cannot produce a structure, ensuring zero data loss.
    """
    if not table_ocr_boxes or not table_ocr_texts:
        return None

    items = []
    for box, text in zip(table_ocr_boxes, table_ocr_texts):
        cleaned_t = clean_text_spacing(restore_currency_symbols(text.strip()))
        if not cleaned_t:
            continue
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        items.append({
            'x0': x0, 'x1': x1,
            'y0': y0, 'y1': y1,
            'cx': (x0 + x1) / 2.0,
            'cy': (y0 + y1) / 2.0,
            'h': max(1.0, y1 - y0),
            'text': cleaned_t
        })

    if not items:
        return None

    # 1. Cluster tokens vertically into rows
    sorted_items = sorted(items, key=lambda it: (it['y0'], it['x0']))
    rows: List[List[Dict[str, Any]]] = []
    for it in sorted_items:
        placed = False
        for r in rows:
            r_y0 = min(x['y0'] for x in r)
            r_y1 = max(x['y1'] for x in r)
            r_h = max(1.0, r_y1 - r_y0)
            overlap = min(it['y1'], r_y1) - max(it['y0'], r_y0)
            if overlap > 0.4 * min(it['h'], r_h):
                r.append(it)
                placed = True
                break
        if not placed:
            rows.append([it])

    rows.sort(key=lambda r: min(x['y0'] for x in r))
    for r in rows:
        r.sort(key=lambda x: x['x0'])

    max_cols = max(len(r) for r in rows)
    if max_cols <= 0:
        return None

    # 2. Determine column anchors
    if max_cols == 1:
        col_centers = [sum(it['cx'] for r in rows for it in r) / len(items)]
    else:
        full_rows = [r for r in rows if len(r) == max_cols]
        if not full_rows:
            full_rows = rows
        col_centers = []
        for c in range(max_cols):
            c_vals = [r[c]['cx'] for r in full_rows if len(r) > c]
            col_centers.append(sum(c_vals) / len(c_vals) if c_vals else 0.0)

    # 3. Build TableCellModel grid
    grid: List[List[TableCellModel]] = []
    for r_idx, r in enumerate(rows):
        is_hdr = (r_idx == 0)
        if len(r) == 1 and max_cols > 1:
            # Single spanning cell across all columns
            cell = TableCellModel(
                row_idx=r_idx,
                col_idx=0,
                rowspan=1,
                colspan=max_cols,
                text=r[0]['text'],
                is_header=is_hdr,
                alignment=_detect_cell_alignment(r[0]['text'], is_hdr),
                bg_color_hex="F2F4F7" if is_hdr else None
            )
            row_cells = [cell]
            for c_idx in range(1, max_cols):
                row_cells.append(TableCellModel(row_idx=r_idx, col_idx=c_idx, text="", is_header=is_hdr))
            grid.append(row_cells)
            continue

        row_cells = [
            TableCellModel(row_idx=r_idx, col_idx=c, text="", is_header=is_hdr,
                           bg_color_hex="F2F4F7" if is_hdr else None)
            for c in range(max_cols)
        ]
        for it in r:
            best_c = min(range(max_cols), key=lambda c: abs(it['cx'] - col_centers[c]))
            if row_cells[best_c].text:
                row_cells[best_c].text += " " + it['text']
            else:
                row_cells[best_c].text = it['text']

        for c_cell in row_cells:
            c_cell.alignment = _detect_cell_alignment(c_cell.text, is_hdr)
        grid.append(row_cells)

    # 4. Proportional widths
    col_lens = [3.0] * max_cols
    for row in grid:
        for c_cell in row:
            if c_cell.colspan == 1:
                col_lens[c_cell.col_idx] = max(col_lens[c_cell.col_idx], float(len(c_cell.text)))
    total_len = sum(col_lens)
    raw_w = [max(0.5, (l / total_len) * page_content_width) for l in col_lens]
    scale = page_content_width / sum(raw_w)
    widths = [w * scale for w in raw_w]

    has_borders = detect_table_borders(crop_img) if crop_img is not None else True

    return TableModel(
        rows=grid,
        num_rows=len(grid),
        num_cols=max_cols,
        col_widths_inches=widths,
        style="Table Grid" if has_borders else "Light Shading",
        has_borders=has_borders,
        alignment="CENTER"
    )
