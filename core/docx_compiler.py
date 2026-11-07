"""
docx_compiler.py - Direct Document IR to Microsoft Word (.docx) Flow Synthesizer
Compiles a DocumentModel into a professional Microsoft Word document using native flow elements.
"""

import os
from typing import Optional, Dict
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from core.document_ir import (
    DocumentModel, PageModel, ParagraphModel, TableModel,
    TableCellModel, FigureModel, RunModel
)


def _set_cell_shading(cell, color_hex: str):
    """Set background color of a table cell."""
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), color_hex.lstrip('#'))
    tc_pr.append(shd)


def _apply_alignment(paragraph, alignment_str: str):
    """Map alignment string to WD_ALIGN_PARAGRAPH."""
    align_map = {
        "LEFT": WD_ALIGN_PARAGRAPH.LEFT,
        "CENTER": WD_ALIGN_PARAGRAPH.CENTER,
        "RIGHT": WD_ALIGN_PARAGRAPH.RIGHT,
        "JUSTIFY": WD_ALIGN_PARAGRAPH.JUSTIFY
    }
    paragraph.alignment = align_map.get(alignment_str.upper(), WD_ALIGN_PARAGRAPH.LEFT)


def _compile_run(paragraph, run_model: RunModel):
    """Add a styled run to a Word paragraph."""
    run = paragraph.add_run(run_model.text)
    if run_model.is_code:
        run.font.name = "Consolas"
        run.font.size = Pt(run_model.font_size_pt or 9.5)
    else:
        run.font.name = run_model.font_name or "Calibri"
        if run_model.font_size_pt:
            run.font.size = Pt(run_model.font_size_pt)

    if run_model.is_bold:
        run.bold = True
    if run_model.is_italic:
        run.italic = True

    if run_model.color_hex:
        try:
            hex_clean = run_model.color_hex.lstrip('#')
            run.font.color.rgb = RGBColor.from_string(hex_clean)
        except Exception:
            pass


def _compile_paragraph(doc: Document, p_model: ParagraphModel):
    """Compile ParagraphModel to a native Word paragraph."""
    style_name = p_model.style or "Normal"

    # Add paragraph with specific built-in style
    if style_name.startswith("Heading"):
        try:
            level = int(style_name.split()[-1])
            p = doc.add_heading(level=level)
        except Exception:
            p = doc.add_paragraph(style=style_name)
    else:
        p = doc.add_paragraph(style=style_name)

    _apply_alignment(p, p_model.alignment)
    p.paragraph_format.space_before = Pt(p_model.space_before_pt)
    p.paragraph_format.space_after = Pt(p_model.space_after_pt)
    p.paragraph_format.line_spacing = p_model.line_spacing

    for r_model in p_model.runs:
        _compile_run(p, r_model)


def _compile_table(doc: Document, t_model: TableModel, page_content_width: float = 7.0):
    """Compile TableModel to a native Word table with proportional columns and merged cells."""
    if not t_model.rows:
        return

    num_rows = len(t_model.rows)
    num_cols = t_model.num_cols or max(len(r) for r in t_model.rows)
    if num_cols == 0:
        return

    table = doc.add_table(rows=num_rows, cols=num_cols)
    table.style = t_model.style or "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    # Determine column widths
    if t_model.col_widths_inches and len(t_model.col_widths_inches) == num_cols:
        col_widths = [Inches(w) for w in t_model.col_widths_inches]
    else:
        # Calculate proportional widths based on content lengths
        col_lens = [3.0] * num_cols
        for row in t_model.rows:
            for c_idx, cell in enumerate(row):
                if c_idx < num_cols and cell.colspan == 1:
                    col_lens[c_idx] = max(col_lens[c_idx], float(len(cell.text.strip())))
        total_len = sum(col_lens)
        raw_w = [max(0.5, (l / total_len) * page_content_width) for l in col_lens]
        scale = page_content_width / sum(raw_w)
        col_widths = [Inches(w * scale) for w in raw_w]

    # Explicitly set width on every cell in every row (per python-docx requirement)
    for row in table.rows:
        for c_idx, cell in enumerate(row.cells):
            cell.width = col_widths[c_idx]

    # Track merged regions
    merged_covered = set()

    for r_idx, row in enumerate(t_model.rows):
        for c_idx, cell_data in enumerate(row):
            if (r_idx, c_idx) in merged_covered:
                continue

            target_cell = table.cell(r_idx, c_idx)

            # Handle cell merging (rowspan / colspan)
            if cell_data.rowspan > 1 or cell_data.colspan > 1:
                end_r = min(num_rows - 1, r_idx + cell_data.rowspan - 1)
                end_c = min(num_cols - 1, c_idx + cell_data.colspan - 1)
                target_cell = target_cell.merge(table.cell(end_r, end_c))

                for dr in range(cell_data.rowspan):
                    for dc in range(cell_data.colspan):
                        merged_covered.add((r_idx + dr, c_idx + dc))

            target_cell.text = ""
            p = target_cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.line_spacing = 1.05

            _apply_alignment(p, cell_data.alignment)

            # Add runs
            if cell_data.runs:
                for r in cell_data.runs:
                    _compile_run(p, r)
            else:
                run = p.add_run(cell_data.text)
                run.font.size = Pt(9.5)
                if cell_data.is_header:
                    run.bold = True

            # Background shading
            if cell_data.bg_color_hex:
                _set_cell_shading(target_cell, cell_data.bg_color_hex)
            elif cell_data.is_header:
                _set_cell_shading(target_cell, "EAEAEA")

    # Add spacing after table
    p_after = doc.add_paragraph()
    p_after.paragraph_format.space_before = Pt(2)
    p_after.paragraph_format.space_after = Pt(4)


def _compile_figure(doc: Document, fig_model: FigureModel, page_content_width: float = 7.0):
    """Compile FigureModel to an embedded Word picture."""
    if fig_model.crop_path and os.path.exists(fig_model.crop_path):
        w = min(fig_model.width_inches, page_content_width)
        p = doc.add_paragraph()
        _apply_alignment(p, fig_model.alignment)
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run()
        run.add_picture(fig_model.crop_path, width=Inches(w))

        if fig_model.caption:
            p_cap = doc.add_paragraph(style="Normal")
            _apply_alignment(p_cap, "CENTER")
            p_cap.paragraph_format.space_after = Pt(4)
            r_cap = p_cap.add_run(fig_model.caption)
            r_cap.italic = True
            r_cap.font.size = Pt(9.0)


def compile_document(doc_model: DocumentModel, output_path: str) -> str:
    """
    Main compilation entrypoint. Converts a DocumentModel to a .docx file.
    """
    doc = Document()

    # Base page settings from first page
    if doc_model.pages:
        p0 = doc_model.pages[0]
        section = doc.sections[0]
        section.page_width = Inches(p0.width_inches)
        section.page_height = Inches(p0.height_inches)
        section.top_margin = Inches(p0.margin_top_inches)
        section.bottom_margin = Inches(p0.margin_bottom_inches)
        section.left_margin = Inches(p0.margin_left_inches)
        section.right_margin = Inches(p0.margin_right_inches)
        content_width = p0.width_inches - (p0.margin_left_inches + p0.margin_right_inches)
    else:
        content_width = 7.0

    # Configure base Normal style
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Calibri'
    normal_style.font.size = Pt(10.5)
    normal_style.font.color.rgb = RGBColor(0x22, 0x22, 0x22)
    normal_style.paragraph_format.space_after = Pt(4)
    normal_style.paragraph_format.line_spacing = 1.15

    for p_idx, page in enumerate(doc_model.pages):
        # Insert native page break between pages
        if p_idx > 0:
            doc.add_page_break()

        for block in page.blocks:
            if isinstance(block, ParagraphModel):
                _compile_paragraph(doc, block)
            elif isinstance(block, TableModel):
                _compile_table(doc, block, page_content_width=content_width)
            elif isinstance(block, FigureModel):
                _compile_figure(doc, block, page_content_width=content_width)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    doc.save(output_path)
    return output_path

