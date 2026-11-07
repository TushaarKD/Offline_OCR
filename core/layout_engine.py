"""
layout_engine.py - Neural Document Layout Analysis
Detects page layout regions: tables, figures, headers, footers, titles, and text blocks.
"""

from typing import List, Tuple, Dict, Any, Optional
import numpy as np

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

    if res and res.boxes:
        for box, name in zip(res.boxes, res.class_names):
            if name in categorized:
                categorized[name].append(box)
            else:
                categorized['text'].append(box)

    return categorized

