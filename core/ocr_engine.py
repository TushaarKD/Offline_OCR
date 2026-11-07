"""
ocr_engine.py - High-Precision OCR & Line Clustering Engine
Provides single-pass OCR, token extraction, line clustering, and word boundary normalization.
"""

import re
from typing import List, Dict, Any, Tuple, Optional
import numpy as np

# Lazy OCR instance
_ocr_instance = None


def get_ocr_instance():
    global _ocr_instance
    if _ocr_instance is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr_instance = RapidOCR()
    return _ocr_instance


def clean_text_spacing(text: str) -> str:
    """
    Fix missing spaces caused by OCR CTC decoding without altering any text/numbers:
    - Punctuation-letter collisions: 'words,words' -> 'words, words'
    - Number-letter collisions: 'Paid50,000tocreditors' -> 'Paid 50,000 to creditors'
    - Glued CamelCase and concatenated English words: 'aretheissues' -> 'are the issues'
    - Protects URLs, emails, dates, decimals, acronyms, and alphanumeric codes.
    """
    url_map = {}
    def save_url(m):
        key = f"___URL_{len(url_map)}___"
        url_map[key] = m.group(0)
        return key

    text = re.sub(
        r'https?://\S+|www\.\S+|\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b|\b(?:air1ca\.com|air1ca)\b',
        save_url,
        text
    )

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

    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text


def restore_currency_symbols(text: str) -> str:
    """Restore Indian Rupee symbol (₹) where OCR reads '?' preceding numeric amounts."""
    return re.sub(r'(?:\?|？)\s*(\d+(?:,\d+)*(?:\.\d+)?)', r'₹ \1', text)


def cluster_items_into_lines(items: List[Dict[str, Any]], max_h_gap: float = 65.0) -> List[List[Dict[str, Any]]]:
    """
    Group OCR text items into lines based on vertical overlap,
    respecting horizontal column boundaries so adjacent columns are never merged.
    """
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
                line_x0 = min(i['x0'] for i in line)
                line_x1 = max(i['x1'] for i in line)
                if item['x0'] >= line_x1:
                    h_gap = item['x0'] - line_x1
                elif item['x1'] <= line_x0:
                    h_gap = line_x0 - item['x1']
                else:
                    h_gap = 0.0

                if h_gap < max_h_gap:
                    line.append(item)
                    placed = True
                    break
        if not placed:
            lines.append([item])

    lines.sort(key=lambda l: min(i['y0'] for i in l))
    for l in lines:
        l.sort(key=lambda i: i['x0'])

    return lines


def run_single_pass_ocr(img_np: np.ndarray) -> List[Tuple[Any, str, float]]:
    """Runs OCR on the page image once and returns all raw detections."""
    engine = get_ocr_instance()
    results, _ = engine(img_np)
    return results or []

