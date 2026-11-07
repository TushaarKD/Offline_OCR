"""
table_engine.py - Neural Table Structure Extraction & Modeling
Extracts 2D cell matrices, spans, and alignments from table image crops into TableModel.
"""

from typing import List, Tuple, Dict, Any, Optional
import re
import numpy as np
from bs4 import BeautifulSoup

from core.document_ir import TableModel, TableCellModel
from core.ocr_engine import clean_text_spacing, restore_currency_symbols

_table_instance = None


def get_table_instance():
    global _table_instance
    if _table_instance is None:
        from rapid_table import RapidTable
        _table_instance = RapidTable()
    return _table_instance


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


def parse_html_table_to_model(html_str: str, page_content_width: float = 7.0) -> Optional[TableModel]:
    """Parse HTML table into a structured TableModel."""
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

            cell_records.append({
                'r': r_idx, 'c': curr_c,
                'rs': rs, 'cs': cs,
                'text': cleaned_t,
                'is_hdr': is_hdr,
                'alignment': align
            })

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

    # Calculate proportional column widths
    col_lens = [3.0] * max_c
    for rec in cell_records:
        if rec['cs'] == 1:
            col_lens[rec['c']] = max(col_lens[rec['c']], float(len(rec['text'])))
    total_len = sum(col_lens)
    raw_w = [max(0.5, (l / total_len) * page_content_width) for l in col_lens]
    scale = page_content_width / sum(raw_w)
    widths = [w * scale for w in raw_w]

    t_model = TableModel(
        rows=grid,
        num_rows=max_r,
        num_cols=max_c,
        col_widths_inches=widths,
        style="Table Grid",
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
            return parse_html_table_to_model(html, page_content_width=page_content_width)
    except Exception:
        pass
    return None

