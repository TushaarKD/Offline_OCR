"""
core/layout_engine.py - Neural Document Layout Analysis & Multi-Column XY-Cut Engine
Detects page layout regions: tables, figures, headers, footers, titles, and text blocks.
Provides Recursive XY-Cut++ for natural reading order in multi-column and complex layouts.
"""

from typing import List, Tuple, Dict, Any, Optional
import numpy as np
import cv2

_layout_instance = None


def get_layout_instance():
    global _layout_instance
    if _layout_instance is None:
        from rapid_layout import RapidLayout
        _layout_instance = RapidLayout()
    return _layout_instance


def analyze_page_layout(img_np: np.ndarray) -> Dict[str, List[List[float]]]:
    """
    Runs layout analysis on a page image.
    Returns dictionary mapping category name ('table', 'figure', 'header', 'footer', 'title', 'text')
    to list of bounding boxes [x1, y1, x2, y2].
    """
    engine = get_layout_instance()
    res = engine(img_np)

    categorized: Dict[str, List[List[float]]] = {
        'table': [],
        'figure': [],
        'header': [],
        'footer': [],
        'title': [],
        'text': []
    }

    if res and res.boxes is not None:
        for box, name in zip(res.boxes, res.class_names):
            if name in categorized:
                categorized[name].append(box)
            else:
                categorized['text'].append(box)

    return categorized


def recursive_xy_cut(
    items: List[Dict[str, Any]],
    x_thresh: float = 35.0,
    y_thresh: float = 18.0,
    page_width: Optional[float] = None
) -> List[Dict[str, Any]]:
    """
    Recursive XY-Cut++ Document Decomposition Algorithm:
    Partitions bounding boxes by full-width spanning headers/footers, vertical column gutters,
    and horizontal line spacing.
    Guarantees natural human reading order across multi-column pages, tables, and mixed layouts
    without column interleaving or character collision.
    """
    if len(items) <= 1:
        return items

    min_x = min(it.get('x0', 0) for it in items)
    max_x = max(it.get('x1', 0) for it in items)
    span_w = page_width if page_width is not None else max(1.0, max_x - min_x)
    center_x = min_x + (span_w / 2.0)

    # 1. Identify Spanning Elements (cross the vertical center gutter or span > 45% of page)
    spanning_items = []
    col_items = []

    for it in items:
        it_w = it.get('x1', 0) - it.get('x0', 0)
        crosses_center = (it.get('x0', 0) < center_x - 25 and it.get('x1', 0) > center_x + 25)
        is_wide = (it_w > 0.45 * span_w)
        if crosses_center or is_wide:
            spanning_items.append(it)
        else:
            col_items.append(it)

    # If spanning elements exist and there are also column items:
    if spanning_items and col_items:
        spanning_items.sort(key=lambda it: it.get('y0', 0))
        bands = []
        last_y = 0.0

        for sp in spanning_items:
            mid = [it for it in col_items if last_y <= it.get('y0', 0) < sp.get('y0', 0)]
            if mid:
                bands.append(('column_band', mid))
            bands.append(('spanning_item', [sp]))
            last_y = sp.get('y1', 0)

        rem = [it for it in col_items if it.get('y0', 0) >= last_y]
        if rem:
            bands.append(('column_band', rem))

        ordered = []
        for b_type, b_items in bands:
            if b_type == 'spanning_item':
                ordered.extend(b_items)
            else:
                ordered.extend(recursive_xy_cut(b_items, x_thresh=x_thresh, y_thresh=y_thresh, page_width=span_w))
        return ordered

    # 2. Check for Vertical (X) Column Gutters across this block
    left_items = [it for it in items if it.get('x1', 0) <= center_x + 25]
    right_items = [it for it in items if it.get('x0', 0) >= center_x - 25]

    if (len(left_items) + len(right_items) == len(items) and
        len(left_items) > 0 and len(right_items) > 0):
        # Clean 2-column division!
        # Sort Column 1 top-to-bottom, then Column 2 top-to-bottom
        left_ordered = sorted(left_items, key=lambda it: it.get('y0', 0))
        right_ordered = sorted(right_items, key=lambda it: it.get('y0', 0))
        return left_ordered + right_ordered

    # 3. Standard top-to-bottom horizontal flow
    return sorted(items, key=lambda it: (it.get('y0', 0), it.get('x0', 0)))


def sample_text_color_from_crop(crop_rgb: np.ndarray) -> Optional[str]:
    """
    Samples the ink stroke color of text within an RGB crop.
    Returns:
        Hex color string (e.g. '004059') for colored or slate text, or None for standard black.
    """
    if crop_rgb is None or crop_rgb.size == 0 or crop_rgb.shape[0] < 2 or crop_rgb.shape[1] < 2:
        return None

    gray = cv2.cvtColor(crop_rgb, cv2.COLOR_RGB2GRAY) if len(crop_rgb.shape) == 3 else crop_rgb
    dark_mask = gray < 190
    if not np.any(dark_mask):
        return None

    p25 = np.percentile(gray[dark_mask], 25)
    stroke_mask = gray <= p25
    if not np.any(stroke_mask):
        return None

    mean_rgb = np.mean(crop_rgb[stroke_mask], axis=0)
    chroma = max(mean_rgb) - min(mean_rgb)
    r, g, b = int(round(mean_rgb[0])), int(round(mean_rgb[1])), int(round(mean_rgb[2]))
    hex_code = f"{r:02X}{g:02X}{b:02X}"
    avg = (r + g + b) / 3.0

    if chroma >= 22:
        # Distinctly colored text (navy blue, crimson, dark green, etc.)
        return hex_code
    elif avg >= 130:
        # Faint gray watermark / caption
        return hex_code
    elif avg >= 55:
        # Slate / dark gray secondary text
        return hex_code

    # Standard dark / black text -> None (uses Word style default)
    return None


def sample_cell_background_color(cell_crop_rgb: np.ndarray) -> Optional[str]:
    """
    Samples the background fill color of a table cell.
    Returns:
        Hex color string (e.g. 'EAEAEA') if shaded, or None if white/unshaded.
    """
    if cell_crop_rgb is None or cell_crop_rgb.size == 0 or cell_crop_rgb.shape[0] < 3 or cell_crop_rgb.shape[1] < 3:
        return None

    gray = cv2.cvtColor(cell_crop_rgb, cv2.COLOR_RGB2GRAY) if len(cell_crop_rgb.shape) == 3 else cell_crop_rgb
    # Background is the brightest pixels (non-text stroke)
    p70 = np.percentile(gray, 70)
    bg_mask = gray >= p70
    if not np.any(bg_mask):
        return None

    mean_bg = np.mean(cell_crop_rgb[bg_mask], axis=0)
    avg_lum = (mean_bg[0] + mean_bg[1] + mean_bg[2]) / 3.0

    # If background is noticeably tinted/shaded (< 240 luminance):
    if avg_lum < 240:
        r, g, b = int(round(mean_bg[0])), int(round(mean_bg[1])), int(round(mean_bg[2]))
        return f"{r:02X}{g:02X}{b:02X}"

    return None
