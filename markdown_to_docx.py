"""
markdown_to_docx.py - Reusable Markdown to DOCX Converter
Converts Markdown documents into professional Microsoft Word (.docx) files.
Preserves all original content, reading order, headings, lists, inline formatting,
and accurately reconstructs both GFM Markdown tables and HTML tables.

Follows python-docx best practices:
- Explicit page geometry and margins.
- Built-in heading styles (Heading 1/2/3/Title) for Word Table of Contents support.
- List Bullet styles for list items.
- Cell width set on every cell in every row for proper rendering.
- HTML table merge support (rowspan / colspan).
- Run-level styling for bold (**), italic (*), and code (`).

Usage:
    python markdown_to_docx.py <input.md> [-o output.docx] [--no-page-breaks]
"""

import os
import sys
import re
import argparse
from typing import List, Tuple, Dict, Any, Optional
from bs4 import BeautifulSoup
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


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

    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text


def set_cell_shading(cell, color_hex: str = "F2F2F2"):
    """Apply background shading color to a table cell."""
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), color_hex)
    tc_pr.append(shd)


def add_formatted_runs(paragraph, text: str):
    """
    Parse inline Markdown formatting (**bold**, *italic*, `code`)
    and add formatted runs to a python-docx paragraph.
    """
    # Pattern to match **bold**, *italic*, and `code`
    pattern = re.compile(r'(\*\*[^*]+?\*\*|\*[^*]+?\*|`[^`]+?`)')
    parts = pattern.split(text)

    for part in parts:
        if not part:
            continue
        if part.startswith('**') and part.endswith('**') and len(part) >= 4:
            run = paragraph.add_run(part[2:-2])
            run.bold = True
        elif part.startswith('*') and part.endswith('*') and len(part) >= 2:
            run = paragraph.add_run(part[1:-1])
            run.italic = True
        elif part.startswith('`') and part.endswith('`') and len(part) >= 2:
            run = paragraph.add_run(part[1:-1])
            run.font.name = 'Consolas'
            run.font.size = Pt(9.5)
        else:
            paragraph.add_run(part)


def add_gfm_table(doc: Document, table_lines: List[str], content_width: float = 7.0):
    """
    Parse a GitHub Flavored Markdown table and add it to the document with proportional column widths.
    """
    rows_data: List[List[str]] = []
    for line in table_lines:
        line_str = line.strip()
        if not line_str or line_str.startswith('| ---') or line_str.startswith('|:---') or line_str.startswith('|---'):
            continue
        cells = [c.strip().replace(r'\|', '|') for c in line_str.strip('|').split('|')]
        if cells:
            rows_data.append(cells)

    if not rows_data:
        return

    num_cols = max(len(r) for r in rows_data)
    if num_cols == 0:
        return

    norm_rows = [r + [''] * (num_cols - len(r)) for r in rows_data]

    table = doc.add_table(rows=len(norm_rows), cols=num_cols)
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    # Proportional column widths based on content length
    col_lens = [3.0] * num_cols
    for row in norm_rows:
        for c_idx, val in enumerate(row):
            col_lens[c_idx] = max(col_lens[c_idx], float(len(val.strip())))

    total_len = sum(col_lens)
    raw_w = [max(0.5, (l / total_len) * content_width) for l in col_lens]
    scale = content_width / sum(raw_w)
    widths = [Inches(w * scale) for w in raw_w]

    for r_idx, row_values in enumerate(norm_rows):
        row = table.rows[r_idx]
        is_header = (r_idx == 0)
        for c_idx, val in enumerate(row_values):
            cell = row.cells[c_idx]
            cell.width = widths[c_idx]
            cell.text = ""
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.line_spacing = 1.05

            cleaned_val = clean_text_spacing(val)
            run = p.add_run(cleaned_val)
            run.font.size = Pt(9.5)
            if is_header:
                run.bold = True
                set_cell_shading(cell, "EAEAEA")


def add_html_table(doc: Document, html_str: str, content_width: float = 7.0):
    """
    Parse an HTML <table> string and add it to the document with colspan/rowspan support
    and proportional column widths.
    """
    soup = BeautifulSoup(html_str, 'html.parser')
    table_soup = soup.find('table')
    if not table_soup:
        return

    raw_rows = table_soup.find_all('tr')
    if not raw_rows:
        return

    occupied: Dict[Tuple[int, int], bool] = {}
    cell_placements: List[Tuple[int, int, int, int, str, bool]] = []
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
            text = cell_elem.get_text(separator=' ', strip=True)

            cell_placements.append((r_idx, curr_c, rs, cs, text, is_hdr))

            for dr in range(rs):
                for dc in range(cs):
                    occupied[(r_idx + dr, curr_c + dc)] = True
                    max_r = max(max_r, r_idx + dr + 1)
                    max_c = max(max_c, curr_c + dc + 1)
            curr_c += cs

    if max_r == 0 or max_c == 0:
        return

    table = doc.add_table(rows=max_r, cols=max_c)
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    # Proportional column widths
    col_lens = [3.0] * max_c
    for r, c, rs, cs, text, is_hdr in cell_placements:
        if cs == 1:
            col_lens[c] = max(col_lens[c], float(len(text.strip())))

    total_len = sum(col_lens)
    raw_w = [max(0.5, (l / total_len) * content_width) for l in col_lens]
    scale = content_width / sum(raw_w)
    widths = [Inches(w * scale) for w in raw_w]

    for row in table.rows:
        for c_idx, cell in enumerate(row.cells):
            cell.width = widths[c_idx]

    for r, c, rs, cs, text, is_hdr in cell_placements:
        start_cell = table.cell(r, c)
        target_cell = start_cell
        if rs > 1 or cs > 1:
            end_r = min(max_r - 1, r + rs - 1)
            end_c = min(max_c - 1, c + cs - 1)
            target_cell = start_cell.merge(table.cell(end_r, end_c))

        target_cell.text = ""
        p = target_cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing = 1.05

        cleaned_text = clean_text_spacing(text)
        run = p.add_run(cleaned_text)
        run.font.size = Pt(9.5)
        if is_hdr:
            run.bold = True
            set_cell_shading(target_cell, "EAEAEA")


def convert_markdown_to_docx(
    md_path: str,
    output_path: Optional[str] = None,
    use_page_breaks: bool = True
) -> str:
    """
    Main conversion function. Reads markdown file and produces a formatted .docx.
    """
    if not os.path.exists(md_path):
        raise FileNotFoundError(f"Markdown file not found: {md_path}")

    if output_path is None:
        base, _ = os.path.splitext(md_path)
        output_path = f"{base}.docx"

    with open(md_path, 'r', encoding='utf-8') as f:
        md_text = f.read()

    doc = Document()

    # Configure page geometry (Standard Letter, 0.75 in margins)
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11.0)
    section.top_margin = Inches(0.75)
    section.bottom_margin = Inches(0.75)
    section.left_margin = Inches(0.75)
    section.right_margin = Inches(0.75)
    content_width = 8.5 - 1.5  # 7.0 inches

    # Set default style font
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Calibri'
    normal_style.font.size = Pt(10.5)
    normal_style.font.color.rgb = RGBColor(0x22, 0x22, 0x22)
    normal_style.paragraph_format.space_after = Pt(4)
    normal_style.paragraph_format.line_spacing = 1.15

    lines = md_text.splitlines()
    idx = 0
    n = len(lines)
    first_page = True

    while idx < n:
        line = lines[idx]
        stripped = line.strip()

        # Handle page breaks & page markers
        page_match = re.match(r'<!--\s*Page\s*(\d+)\s*-->', stripped, re.IGNORECASE)
        if page_match:
            page_num = int(page_match.group(1))
            if use_page_breaks and not first_page:
                doc.add_page_break()
            first_page = False
            idx += 1
            continue

        if stripped == '---':
            # Horizontal rule / page separator
            idx += 1
            continue

        # Skip empty lines
        if not stripped:
            idx += 1
            continue

        # Check for HTML Table
        if '<table' in stripped.lower():
            html_table_lines = [line]
            while idx + 1 < n and '</table>' not in html_table_lines[-1].lower():
                idx += 1
                html_table_lines.append(lines[idx])
            full_html = '\n'.join(html_table_lines)
            add_html_table(doc, full_html, content_width=content_width)
            # Add small breathing room after table
            p_after = doc.add_paragraph()
            p_after.paragraph_format.space_before = Pt(2)
            p_after.paragraph_format.space_after = Pt(4)
            idx += 1
            continue

        # Check for Markdown Table (GFM)
        if stripped.startswith('|') and stripped.endswith('|'):
            table_lines = [line]
            while idx + 1 < n and lines[idx + 1].strip().startswith('|') and lines[idx + 1].strip().endswith('|'):
                idx += 1
                table_lines.append(lines[idx])
            add_gfm_table(doc, table_lines, content_width=content_width)
            p_after = doc.add_paragraph()
            p_after.paragraph_format.space_before = Pt(2)
            p_after.paragraph_format.space_after = Pt(4)
            idx += 1
            continue

        # Check for Headings
        if stripped.startswith('#'):
            level = len(stripped) - len(stripped.lstrip('#'))
            heading_text = clean_text_spacing(stripped[level:].strip())
            # Map Markdown level to Word heading level
            h_level = min(level, 4)
            doc.add_heading(heading_text, level=h_level)
            idx += 1
            continue

        # Check for List Bullet item (- item or * item)
        if stripped.startswith('- ') or stripped.startswith('* '):
            list_text = clean_text_spacing(stripped[2:].strip())
            p = doc.add_paragraph(style='List Bullet')
            p.paragraph_format.space_after = Pt(3)
            p.paragraph_format.line_spacing = 1.15
            add_formatted_runs(p, list_text)
            idx += 1
            continue

        # Regular Paragraph: accumulate multi-line paragraph text
        para_lines = [stripped]
        while idx + 1 < n:
            next_line = lines[idx + 1].strip()
            if not next_line:
                break
            if next_line.startswith('#') or next_line.startswith('|') or next_line.startswith('- ') or \
               next_line.startswith('* ') or next_line.startswith('<!--') or next_line == '---' or \
               '<table' in next_line.lower():
                break
            idx += 1
            para_lines.append(next_line)

        full_para_text = clean_text_spacing(' '.join(para_lines))
        p = doc.add_paragraph()
        add_formatted_runs(p, full_para_text)
        idx += 1

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    doc.save(output_path)
    print(f"Successfully converted '{md_path}' to '{output_path}'")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Convert Markdown to Microsoft Word (.docx) format.")
    parser.add_argument("md_path", help="Path to input Markdown file")
    parser.add_argument("-o", "--output", help="Path to output .docx file (optional)")
    parser.add_argument("--no-page-breaks", action="store_true", help="Disable page breaks on <!-- Page N --> markers")

    args = parser.parse_args()

    convert_markdown_to_docx(
        md_path=args.md_path,
        output_path=args.output,
        use_page_breaks=not args.no_page_breaks
    )


if __name__ == "__main__":
    main()

