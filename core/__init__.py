"""
Core package for High-Fidelity Document Processing & Conversion.
"""

from .document_ir import DocumentModel, PageModel, ParagraphModel, TableModel, TableCellModel, FigureModel, RunModel
from .ocr_engine import run_single_pass_ocr, cluster_items_into_lines, clean_text_spacing, restore_currency_symbols
from .layout_engine import analyze_page_layout, recursive_xy_cut, sample_text_color_from_crop, sample_cell_background_color
from .table_engine import extract_table_model
from .docx_compiler import compile_document
from .qa_auditor import (
    validate_and_heal_table,
    audit_document,
    apply_low_confidence_highlighting,
    generate_qa_summary_markdown
)
from .preprocessor import (
    preprocess_document_image,
    auto_deskew_image,
    detect_and_fix_orientation,
    remove_shadows_and_illumination,
    suppress_faint_watermarks
)
