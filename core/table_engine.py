"""
table_engine.py - Neural Table Structure Extraction & Modeling
Extracts 2D cell matrices, spans, alignments, border styles, and background shading from table image crops into TableModel.
"""

from typing import List, Tuple, Dict, Any, Optional
import re
import numpy as np
import cv2
from bs4 import BeautifulSoup

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


def extract_table_model(crop_img: np.ndarray,
                        table_ocr_boxes: List[Any],
                        table_ocr_texts: List[str],
                        table_ocr_scores: List[float],
                        page_content_width: float = 7.0) -> Optional[TableModel]:
    """Runs SLANet+ neural table extraction and returns a populated TableModel."""
    table_engine = get_table_instance()
    try:
        if table_ocr_boxes:
            out = table_engine(crop_img, ocr_results=[(table_ocr_boxes, table_ocr_texts, table_ocr_scores)])
        else:
            out = table_engine(crop_img)

        if out and out.pred_htmls:
            html = out.pred_htmls[0]
            cell_boxes = out.cell_bboxes[0] if (out.cell_bboxes is not None and len(out.cell_bboxes) > 0) else None
            return parse_html_table_to_model(
                html,
                crop_img=crop_img,
                cell_bboxes=cell_boxes,
                page_content_width=page_content_width
            )
    except Exception:
        pass
    return None
