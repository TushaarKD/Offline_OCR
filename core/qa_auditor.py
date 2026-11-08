"""
qa_auditor.py - Quality Assurance & Boundary Safety Engine
Provides non-destructive validation and structural safety for:
1. Table Matrix Boundary Safety (ensuring rectangular arrays for Word API safety without clamping legitimate spans).
2. OCR Confidence Auditing & Optional Low-Confidence Highlighting (soft yellow for rapid human review).
3. Zero-Manipulation Protocol: strictly avoids modifying numbers, calculations, or authentic table layout.
"""

from typing import List, Tuple, Dict, Any, Optional
import numpy as np

from core.document_ir import (
    DocumentModel, PageModel, ParagraphModel, TableModel,
    TableCellModel, FigureModel, RunModel
)


def validate_and_heal_table(t_model: TableModel, page_content_width: float = 7.0) -> Tuple[TableModel, List[str]]:
    """
    Validates and preserves table matrix topology without altering raw data or legitimate spans.
    Ensures:
    - python-docx safety: row and column indices never overshoot table bounds.
    - Every row has the exact same number of cell objects in memory (padding missing trailing cells if ragged).
    - Proportional column widths are properly scaled to printable page content width.
    """
    safety_actions: List[str] = []
    if not t_model.rows:
        return t_model, safety_actions

    num_rows = len(t_model.rows)

    # Determine authentic column count
    if t_model.num_cols and t_model.num_cols > 0:
        max_cols = t_model.num_cols
    elif t_model.col_widths_inches and len(t_model.col_widths_inches) > 0:
        max_cols = len(t_model.col_widths_inches)
    else:
        max_cols = max((len(r) for r in t_model.rows), default=1)
        for row in t_model.rows:
            row_span_sum = sum(max(1, cell.colspan) for cell in row)
            max_cols = max(max_cols, row_span_sum)

    max_cols = max(1, max_cols)
    t_model.num_rows = num_rows
    t_model.num_cols = max_cols

    # 1. Pad any ragged rows with empty cells so every row has exact max_cols length
    for r_idx, row in enumerate(t_model.rows):
        if len(row) < max_cols:
            missing = max_cols - len(row)
            safety_actions.append(f"Row {r_idx}: Padded {missing} trailing cell(s) to match width ({max_cols} cols)")
            for c in range(len(row), max_cols):
                row.append(TableCellModel(
                    row_idx=r_idx,
                    col_idx=c,
                    text="",
                    is_header=(r_idx == 0)
                ))

    # 2. Safety bounds check for python-docx (only clamp if span exceeds physical table boundary)
    for r_idx, row in enumerate(t_model.rows):
        for c_idx, cell in enumerate(row):
            cell.row_idx = r_idx
            cell.col_idx = c_idx

            # Only clamp if the merge would extend past the bottom of the table
            if r_idx + cell.rowspan > num_rows:
                clamped_rs = max(1, num_rows - r_idx)
                safety_actions.append(f"Boundary safety: Clamped cell ({r_idx}, {c_idx}) rowspan from {cell.rowspan} to {clamped_rs}")
                cell.rowspan = clamped_rs

            # Only clamp if the merge would extend past the right edge of the table
            if c_idx + cell.colspan > max_cols:
                clamped_cs = max(1, max_cols - c_idx)
                safety_actions.append(f"Boundary safety: Clamped cell ({r_idx}, {c_idx}) colspan from {cell.colspan} to {clamped_cs}")
                cell.colspan = clamped_cs

    # 3. Normalize column widths
    if not t_model.col_widths_inches or len(t_model.col_widths_inches) != max_cols:
        col_lens = [3.0] * max_cols
        for row in t_model.rows:
            for c_idx, cell in enumerate(row):
                if c_idx < max_cols and cell.colspan == 1:
                    col_lens[c_idx] = max(col_lens[c_idx], float(len(cell.text.strip())))
        total_len = sum(col_lens)
        raw_w = [max(0.5, (l / total_len) * page_content_width) for l in col_lens]
        scale = page_content_width / sum(raw_w)
        t_model.col_widths_inches = [w * scale for w in raw_w]

    return t_model, safety_actions


def apply_low_confidence_highlighting(doc_model: DocumentModel, threshold: float = 0.60) -> int:
    """
    Scans runs across paragraphs and tables. Highlights any text run whose
    OCR confidence score is below threshold in soft yellow for effortless human review.
    Returns the total count of highlighted runs.
    """
    highlighted_count = 0
    for page in doc_model.pages:
        for block in page.blocks:
            if isinstance(block, ParagraphModel):
                for run in block.runs:
                    if run.confidence is not None and run.confidence < threshold:
                        run.highlight_color = "YELLOW"
                        highlighted_count += 1
            elif isinstance(block, TableModel):
                for row in block.rows:
                    for cell in row:
                        if cell.runs:
                            for run in cell.runs:
                                if run.confidence is not None and run.confidence < threshold:
                                    run.highlight_color = "YELLOW"
                                    highlighted_count += 1
                        elif cell.confidence is not None and cell.confidence < threshold:
                            cell.highlight_color = "YELLOW"
                            highlighted_count += 1
    return highlighted_count


def audit_document(doc_model: DocumentModel,
                   low_conf_threshold: float = 0.60,
                   page_content_width: float = 7.0) -> Dict[str, Any]:
    """
    Performs full Document QA audit:
    - Validates table matrix boundaries non-destructively.
    - Aggregates confidence metrics.
    - Operates under the Zero-Manipulation Protocol.
    """
    total_paragraphs = 0
    total_tables = 0
    total_figures = 0
    all_safety_actions: List[str] = []
    all_confidences: List[float] = []

    for page in doc_model.pages:
        for block in page.blocks:
            if isinstance(block, ParagraphModel):
                total_paragraphs += 1
                for r in block.runs:
                    if r.confidence is not None:
                        all_confidences.append(r.confidence)
            elif isinstance(block, TableModel):
                total_tables += 1
                healed_table, actions = validate_and_heal_table(block, page_content_width=page_content_width)
                if actions:
                    all_safety_actions.extend(actions)
                for row in block.rows:
                    for cell in row:
                        for r in cell.runs:
                            if r.confidence is not None:
                                all_confidences.append(r.confidence)
                        if cell.confidence is not None:
                            all_confidences.append(cell.confidence)
            elif isinstance(block, FigureModel):
                total_figures += 1

    # Confidence statistics
    if all_confidences:
        median_conf = float(np.median(all_confidences))
        high_conf_pct = float(np.mean([1.0 if c >= 0.90 else 0.0 for c in all_confidences]) * 100.0)
        low_conf_count = sum(1 for c in all_confidences if c < low_conf_threshold)
    else:
        median_conf = 1.0
        high_conf_pct = 100.0
        low_conf_count = 0

    report = {
        'total_pages': len(doc_model.pages),
        'total_paragraphs': total_paragraphs,
        'total_tables': total_tables,
        'total_figures': total_figures,
        'table_safety_actions': all_safety_actions,
        'table_topology_clean': len(all_safety_actions) == 0,
        'confidence_median': round(median_conf, 3),
        'high_confidence_pct': round(high_conf_pct, 1),
        'low_confidence_tokens': low_conf_count
    }
    return report


def generate_qa_summary_markdown(report: Dict[str, Any]) -> str:
    """Generates a clean GFM markdown quality assurance summary from the audit report."""
    lines = [
        "## Document Quality Assurance (QA) Audit Report",
        "",
        "| Metric | Value | Status |",
        "| :--- | :--- | :--- |",
        f"| **Pages Audited** | {report['total_pages']} | OK |",
        f"| **Paragraphs & Headings** | {report['total_paragraphs']} | OK |",
        f"| **Tables Reconstructed** | {report['total_tables']} | {'OK' if report['table_topology_clean'] else 'VERIFIED'} |",
        f"| **Embedded Figures** | {report['total_figures']} | OK |",
        f"| **Median OCR Confidence** | {report['confidence_median'] * 100:.1f}% | {'EXCELLENT' if report['confidence_median'] >= 0.85 else 'REVIEW'} |",
        f"| **High-Confidence Tokens (≥90%)** | {report['high_confidence_pct']:.1f}% | {'HIGH FIDELITY' if report['high_confidence_pct'] >= 85 else 'ACCEPTABLE'} |",
        f"| **Low-Confidence Tokens (<60%)** | {report['low_confidence_tokens']} | {'CLEAN' if report['low_confidence_tokens'] == 0 else 'HIGHLIGHTED'} |",
        ""
    ]

    if report.get('table_safety_actions'):
        lines.append("### Table Boundary Safety Actions")
        for act in report['table_safety_actions']:
            lines.append(f"- {act}")
        lines.append("")

    return "\n".join(lines)
