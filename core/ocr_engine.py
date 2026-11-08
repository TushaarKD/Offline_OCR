"""
ocr_engine.py - High-Precision OCR & Line Clustering Engine
Provides single-pass OCR, token extraction, line clustering, and word boundary normalization.
"""

import re
from typing import List, Dict, Any, Tuple, Optional
import numpy as np

def get_ocr_instance():
    from core.model_manager import get_ocr_engine
    return get_ocr_engine()


def clean_text_spacing(text: str) -> str:
    """
    Fix missing spaces caused by OCR CTC decoding without altering any authentic text/numbers:
    - Label and chapter boundaries: 'Question1' -> 'Question 1', 'CHAPTER-1' -> 'CHAPTER - 1'
    - Ampersand spacing: 'Objectives&Advantages' -> 'Objectives & Advantages'
    - Punctuation-letter collisions: 'words,words' -> 'words, words'
    - Parentheses boundaries: '(i)Recognition' -> '(i) Recognition', 'Institute(ACI)' -> 'Institute (ACI)'
    - Run-together English words: 'Disclosurerequirements' -> 'Disclosure requirements', 'asense' -> 'a sense'
    - Protects URLs, emails, dates, decimals, acronyms, and proper nouns.
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

    # 1. Labels with numbers & general letter-digit boundaries
    text = re.sub(r'\b(Question|Answer|Chapter|Page|Part|Section|Sec|AS)\s*[-:]?\s*(\d+)', r'\1 \2', text, flags=re.IGNORECASE)
    text = re.sub(r'\bCHAPTER\s*[-–—]?\s*(\d+)\b', r'CHAPTER - \1', text, flags=re.IGNORECASE)
    text = re.sub(r'([a-zA-Z]{3,})(\d+)', r'\1 \2', text)
    text = re.sub(r'(\d+(?:,\d+)*(?:\.\d+)?)([a-zA-Z]{2,})', r'\1 \2', text)

    # 2. Ampersand spacing
    text = re.sub(r'([a-zA-Z0-9])&', r'\1 & ', text)
    text = re.sub(r'&([a-zA-Z0-9])', r' & \1', text)

    # 3. Parentheses, brackets & punctuation spacing
    text = re.sub(r'([a-zA-Z0-9\)])([,;:!])([a-zA-Z\(])', r'\1\2 \3', text)
    text = re.sub(r'([a-zA-Z]{2,}\.)([A-Z])', r'\1 \2', text)
    text = re.sub(r'\)([a-zA-Z0-9])', r') \1', text)
    text = re.sub(r'([a-zA-Z0-9])\(', r'\1 (', text)
    text = re.sub(r'(\w)"([A-Z])', r'\1 "\2', text)
    text = re.sub(r'([a-zA-Z0-9\.\?!])"([a-zA-Z])', r'\1" \2', text)

    # 4. Clean run-together / glued English words
    try:
        import wordninja

        def smart_split(match):
            w = match.group(0)
            if len(w) <= 3 or (w.isupper() and len(w) <= 6):
                return w
            splits = wordninja.split(w)
            if len(splits) <= 1:
                return w
            # Check that every split token is >= 2 letters, OR is 'a' or 'i'
            if not all(len(s) >= 2 or s.lower() in ('a', 'i') for s in splits):
                return w
            res = []
            idx = 0
            for s in splits:
                slen = len(s)
                res.append(w[idx:idx+slen])
                idx += slen
            if idx < len(w):
                res.append(w[idx:])
            return ' '.join(res)

        text = re.sub(r'\b[a-zA-Z]+\b', smart_split, text)
    except ImportError:
        pass

    # 5. Known author tokens & headers (clean up any over-splits in proper names)
    text = re.sub(r'BY\s*HP\s*AGAR\s*WAL', 'BY HP AGARWAL', text, flags=re.IGNORECASE)
    text = re.sub(r'AJAY\s*AGAR\s*WAL', 'AJAY AGARWAL', text, flags=re.IGNORECASE)
    text = re.sub(r'\bA\s*JAY\b', 'AJAY', text, flags=re.IGNORECASE)
    text = re.sub(r'AGAR\s*WAL', 'AGARWAL', text, flags=re.IGNORECASE)
    text = re.sub(r'AIR\s*1\s*CA', 'AIR1 CA', text, flags=re.IGNORECASE)
    text = re.sub(r'Career\s*Institute', 'Career Institute', text, flags=re.IGNORECASE)

    # Restore URLs/emails
    for key, val in url_map.items():
        text = text.replace(key, val)

    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text.strip()


def restore_currency_symbols(text: str) -> str:
    """
    Restore Indian Rupee symbol (₹) where OCR reads '?' or '天' (U+5929):
    - Standalone table cell/column headers: '天', '?', '？' -> '₹'
    - Units in parentheses: '(天)', '(?)', '(天 in lakhs)', '(? in '000)' -> '(₹ in ...)'
    - Standalone or delimiter-bound '天' -> '₹' (e.g. 'Particulars | 天 | Particulars')
    - Preceding numeric amounts: '? 1,20,000', '天 50,000' -> '₹ 1,20,000'
    - Word-Rupee boundary spacing: 'of₹ 25' -> 'of ₹ 25', '₹100' -> '₹ 100'
    - Preserves authentic interrogative question marks ('What is AS 3?').
    """
    s = text.strip()
    if s in ('天', '?', '？'):
        return '₹'

    # Currency inside parentheses e.g. (天), (?), (天 in '000), (? in Lakhs)
    text = re.sub(r'\(\s*[?？天]\s*\)', '(₹)', text)
    text = re.sub(r'\(\s*[?？天]\s+in\s+([^\)]+)\)', r'(₹ in \1)', text, flags=re.IGNORECASE)

    # Any '天' in English documents represents ₹
    text = re.sub(r'天', '₹', text)

    # '?' preceding numeric amounts e.g. '? 1,20,000'
    text = re.sub(r'(?:[?？])\s*(\d+(?:,\d+)*(?:\.\d+)?)', r'₹ \1', text)

    # Missing space before ₹ e.g. 'outflow of₹ 25' -> 'outflow of ₹ 25'
    text = re.sub(r'([a-zA-Z])₹', r'\1 ₹', text)

    # Ensure space after ₹ before digits e.g. '₹25' -> '₹ 25'
    text = re.sub(r'₹(\d)', r'₹ \1', text)

    return text


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

