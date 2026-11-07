"""
document_ir.py - Central Document Intermediate Representation (DOM)
Defines an in-memory document tree preserving layout, typography, colors,
tables, figures, and structural hierarchy.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any, Union
import re


@dataclass
class RunModel:
    """Represents a span of text sharing uniform typography and styling."""
    text: str
    font_name: str = "Calibri"
    font_size_pt: float = 10.5
    is_bold: bool = False
    is_italic: bool = False
    is_code: bool = False
    color_hex: Optional[str] = None  # e.g. "003366" or None for default
    bbox: Optional[Tuple[float, float, float, float]] = None  # [x0, y0, x1, y1]


@dataclass
class ParagraphModel:
    """Represents a text paragraph, heading, or list item."""
    runs: List[RunModel] = field(default_factory=list)
    style: str = "Normal"  # "Normal", "Heading 1", "Heading 2", "Heading 3", "List Bullet"
    alignment: str = "LEFT"  # "LEFT", "CENTER", "RIGHT", "JUSTIFY"
    space_before_pt: float = 0.0
    space_after_pt: float = 4.0
    line_spacing: float = 1.15
    bbox: Optional[Tuple[float, float, float, float]] = None

    @property
    def plain_text(self) -> str:
        return "".join(r.text for r in self.runs)

    def add_run(self, text: str, font_size_pt: float = 10.5, is_bold: bool = False,
                is_italic: bool = False, is_code: bool = False,
                color_hex: Optional[str] = None) -> RunModel:
        run = RunModel(
            text=text,
            font_size_pt=font_size_pt,
            is_bold=is_bold,
            is_italic=is_italic,
            is_code=is_code,
            color_hex=color_hex
        )
        self.runs.append(run)
        return run


@dataclass
class TableCellModel:
    """Represents a single cell in a TableModel."""
    text: str = ""
    runs: List[RunModel] = field(default_factory=list)
    row_idx: int = 0
    col_idx: int = 0
    rowspan: int = 1
    colspan: int = 1
    is_header: bool = False
    bg_color_hex: Optional[str] = None  # e.g. "EAEAEA"
    alignment: str = "LEFT"  # "LEFT", "RIGHT", "CENTER"


@dataclass
class TableModel:
    """Represents a 2D structured table."""
    rows: List[List[TableCellModel]] = field(default_factory=list)
    num_rows: int = 0
    num_cols: int = 0
    col_widths_inches: List[float] = field(default_factory=list)
    style: str = "Table Grid"
    alignment: str = "CENTER"
    bbox: Optional[Tuple[float, float, float, float]] = None

    def get_cell(self, r: int, c: int) -> Optional[TableCellModel]:
        if 0 <= r < len(self.rows) and 0 <= c < len(self.rows[r]):
            return self.rows[r][c]
        return None


@dataclass
class FigureModel:
    """Represents an embedded graphic, diagram, chart, or logo."""
    image_bytes: Optional[bytes] = None
    crop_path: Optional[str] = None
    width_inches: float = 5.0
    height_inches: float = 3.0
    caption: Optional[str] = None
    alignment: str = "CENTER"
    bbox: Optional[Tuple[float, float, float, float]] = None


BlockModel = Union[ParagraphModel, TableModel, FigureModel]


@dataclass
class PageModel:
    """Represents a single document page."""
    page_num: int
    width_inches: float = 8.5
    height_inches: float = 11.0
    margin_top_inches: float = 0.75
    margin_bottom_inches: float = 0.75
    margin_left_inches: float = 0.75
    margin_right_inches: float = 0.75
    blocks: List[BlockModel] = field(default_factory=list)

    def add_paragraph(self, style: str = "Normal", alignment: str = "LEFT") -> ParagraphModel:
        p = ParagraphModel(style=style, alignment=alignment)
        self.blocks.append(p)
        return p

    def add_table(self, table: TableModel) -> TableModel:
        self.blocks.append(table)
        return table

    def add_figure(self, figure: FigureModel) -> FigureModel:
        self.blocks.append(figure)
        return figure


@dataclass
class DocumentModel:
    """Top-level in-memory document DOM holding all pages and document metadata."""
    title: str = "Document"
    pages: List[PageModel] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_page(self, page_num: int) -> PageModel:
        page = PageModel(page_num=page_num)
        self.pages.append(page)
        return page

    def to_markdown(self) -> str:
        """Export clean GitHub Flavored Markdown from the Document IR."""
        md_pages = []
        for p in self.pages:
            p_parts = [f"<!-- Page {p.page_num} -->\n"]
            for b in p.blocks:
                if isinstance(b, ParagraphModel):
                    text = ""
                    for r in b.runs:
                        r_txt = r.text
                        if r.is_bold and r.is_italic:
                            text += f"***{r_txt}***"
                        elif r.is_bold:
                            text += f"**{r_txt}**"
                        elif r.is_italic:
                            text += f"*{r_txt}*"
                        elif r.is_code:
                            text += f"`{r_txt}`"
                        else:
                            text += r_txt

                    if b.style == "Heading 1":
                        p_parts.append(f"\n# {text}\n")
                    elif b.style == "Heading 2":
                        p_parts.append(f"\n## {text}\n")
                    elif b.style == "Heading 3":
                        p_parts.append(f"\n### {text}\n")
                    elif b.style == "List Bullet":
                        p_parts.append(f"- {text}")
                    else:
                        p_parts.append(f"\n{text}\n")

                elif isinstance(b, TableModel):
                    # Check for complex rowspan/colspan
                    has_spans = any(
                        cell.rowspan > 1 or cell.colspan > 1
                        for row in b.rows for cell in row
                    )
                    if has_spans:
                        # Serialize as HTML table to preserve merges cleanly
                        html_rows = []
                        for row in b.rows:
                            cells_html = []
                            for cell in row:
                                span_attr = ""
                                if cell.rowspan > 1:
                                    span_attr += f' rowspan="{cell.rowspan}"'
                                if cell.colspan > 1:
                                    span_attr += f' colspan="{cell.colspan}"'
                                tag = "th" if cell.is_header else "td"
                                cells_html.append(f"<{tag}{span_attr}>{cell.text}</{tag}>")
                            html_rows.append(f"<tr>{''.join(cells_html)}</tr>")
                        p_parts.append(f"\n<table>\n{''.join(html_rows)}\n</table>\n")
                    else:
                        # Serialize as standard GFM markdown table
                        if b.rows:
                            max_c = b.num_cols or max(len(r) for r in b.rows)
                            hdr = [b.rows[0][c].text.replace("|", "\\|") if c < len(b.rows[0]) else "" for c in range(max_c)]
                            lines = [
                                "| " + " | ".join(hdr) + " |",
                                "| " + " | ".join(["---"] * max_c) + " |"
                            ]
                            for row in b.rows[1:]:
                                r_cells = [row[c].text.replace("|", "\\|") if c < len(row) else "" for c in range(max_c)]
                                lines.append("| " + " | ".join(r_cells) + " |")
                            p_parts.append("\n" + "\n".join(lines) + "\n")

                elif isinstance(b, FigureModel):
                    caption = b.caption or f"Figure"
                    ref = b.crop_path or "embedded_image"
                    p_parts.append(f"\n![{caption}]({ref})\n")

            md_pages.append("\n".join(p_parts).strip())

        full_md = "\n\n---\n\n".join(md_pages)
        full_md = re.sub(r'\n{3,}', '\n\n', full_md)
        return full_md.strip()

    def save_markdown(self, output_path: str):
        md = self.to_markdown()
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md)

