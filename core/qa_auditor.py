"""
qa_auditor.py - Self-Healing Quality Assurance & Verification Engine
Provides automated validation and self-healing for:
1. Table Matrix Topology (detecting ragged rows, out-of-bounds spans, padding missing cells).
2. Accounting & Arithmetic Checksums (verifying financial equations and column totals).
3. OCR Confidence Auditing & Optional Low-Confidence Highlighting (soft yellow for rapid human review).
"""

from typing import List, Tuple, Dict, Any, Optional
import re
import numpy as np

from core.document_ir import (
    DocumentModel, PageModel, ParagraphModel, TableModel,
    TableCellModel, FigureModel, RunModel
)


def validate_and_heal_table(t_model: TableModel, page_content_width: float = 7.0) -> Tuple[TableModel, List[str]]:
    """
    Validates and self-heals table matrix topology.
    Ensures:
    - Every row has the exact same number of columns (no ragged or missing cells).
    - Multi-row and multi-column spans do not exceed table boundary bounds.
    - Column widths are non-empty, proportional, and normalized to page content width.
    """
    healing_actions: List[str] = []
    if not t_model.rows:
        return t_model, healing_actions

    num_rows = len(t_model.rows)
    max_distinct = max(len(row) for row in t_model.rows)

    # 1. Determine baseline column count
    target_cols = max_distinct
    if t_model.col_widths_inches and len(t_model.col_widths_inches) >= max_distinct:
        target_cols = max(target_cols, len(t_model.col_widths_inches))
    elif t_model.num_cols and t_model.num_cols >= max_distinct:
        target_cols = max(target_cols, t_model.num_cols)
    else:
        # Check plausible span sums across rows
        span_sums = []
        for row in t_model.rows:
            rem_cells = len(row) - 1
            s = 0
            for c in row:
                cs = max(1, c.colspan)
                if cs > max_distinct and len(row) > 1 and (cs + rem_cells) > max_distinct * 2:
                    cs = max(1, max_distinct - rem_cells)
                s += cs
            span_sums.append(s)
        if span_sums:
            target_cols = max(target_cols, max(span_sums))

    # 2. Walk the grid and clamp spans against target_cols and num_rows
    occupied: Dict[Tuple[int, int], bool] = {}
    row_col_counts: List[int] = []

    for r_idx, row in enumerate(t_model.rows):
        curr_c = 0
        rem_in_row = len(row)
        for cell_idx, cell in enumerate(row):
            rem_in_row -= 1
            while (r_idx, curr_c) in occupied:
                curr_c += 1

            rs = max(1, cell.rowspan)
            cs = max(1, cell.colspan)

            # Clamp rowspan so it cannot exceed num_rows
            if r_idx + rs > num_rows:
                clamped_rs = max(1, num_rows - r_idx)
                healing_actions.append(f"Clamped cell ({r_idx}, {curr_c}) rowspan from {rs} to {clamped_rs}")
                rs = clamped_rs
                cell.rowspan = rs

            # Clamp colspan so it cannot overshoot target_cols
            max_allowed_cs = max(1, target_cols - curr_c - rem_in_row)
            if cs > max_allowed_cs:
                healing_actions.append(f"Clamped cell ({r_idx}, {curr_c}) colspan from {cs} to {max_allowed_cs}")
                cs = max_allowed_cs
                cell.colspan = cs

            for dr in range(rs):
                for dc in range(cs):
                    occupied[(r_idx + dr, curr_c + dc)] = True

            curr_c += cs
        row_col_counts.append(curr_c)

    max_cols = max(target_cols, max(row_col_counts) if row_col_counts else 1)
    t_model.num_rows = num_rows
    t_model.num_cols = max_cols

    # 3. Heal ragged rows by padding missing trailing cells
    for r_idx, row in enumerate(t_model.rows):
        effective_cols = row_col_counts[r_idx]
        if effective_cols < max_cols:
            missing = max_cols - effective_cols
            healing_actions.append(f"Row {r_idx}: Padded {missing} missing cell(s) to match topology ({max_cols} cols)")
            for i in range(missing):
                new_c_idx = len(row)
                row.append(TableCellModel(
                    row_idx=r_idx,
                    col_idx=new_c_idx,
                    text="",
                    is_header=(r_idx == 0)
                ))

    # 4. Ensure all cells have valid row_idx and col_idx
    for r_idx, row in enumerate(t_model.rows):
        for c_idx, cell in enumerate(row):
            cell.row_idx = r_idx
            cell.col_idx = c_idx
            if c_idx + cell.colspan > max_cols:
                clamped_cs = max(1, max_cols - c_idx)
                healing_actions.append(f"Cell ({r_idx}, {c_idx}): Clamped colspan from {cell.colspan} to {clamped_cs}")
                cell.colspan = clamped_cs

    # 5. Normalize column widths
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

    return t_model, healing_actions


def audit_accounting_table(t_model: TableModel) -> Dict[str, Any]:
    """
    Audits arithmetic and financial consistency within a table.
    Scans for:
    1. Explicit row equations: e.g. [Assets, '-', Liabilities, '=', Equity]
    2. Column sum totals: e.g. verifying that rows sum to 'Total' or 'Closing Balance'
    """
    results: List[Dict[str, Any]] = []

    def clean_num(s: str) -> Optional[float]:
        cleaned = re.sub(r'[^\d.-]', '', s.strip())
        if not cleaned or cleaned in ('-', '.'):
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None

    # Audit explicit row equations
    for r_idx, row in enumerate(t_model.rows):
        row_texts = [cell.text.strip() for cell in row]

        # Check for inline equation pattern like: [..., num1, '-', num2, '=', num3, ...]
        for i in range(len(row_texts) - 4):
            val1 = clean_num(row_texts[i])
            op1 = row_texts[i + 1]
            val2 = clean_num(row_texts[i + 2])
            op2 = row_texts[i + 3]
            val3 = clean_num(row_texts[i + 4])

            if val1 is not None and val2 is not None and val3 is not None and op2 == '=':
                expected = None
                if op1 in ('-', '—', '–'):
                    expected = val1 - val2
                elif op1 in ('+',):
                    expected = val1 + val2

                if expected is not None:
                    diff = abs(expected - val3)
                    passed = diff < 0.05
                    results.append({
                        'type': 'row_equation',
                        'row': r_idx,
                        'expression': f"{val1} {op1} {val2} = {val3}",
                        'expected': round(expected, 2),
                        'actual': round(val3, 2),
                        'diff': round(diff, 4),
                        'passed': passed
                    })

    # Audit column totals (e.g. if a row has "Total" or "Closing")
    total_row_idx = None
    for r_idx, row in enumerate(t_model.rows):
        first_cell_txt = row[0].text.strip().lower() if row else ""
        if any(w in first_cell_txt for w in ['total', 'closing balance', 'grand total', 'net total']):
            total_row_idx = r_idx
            break

    if total_row_idx is not None and total_row_idx > 1:
        for c_idx in range(1, t_model.num_cols):
            col_vals = []
            for r in range(1, total_row_idx):
                if c_idx < len(t_model.rows[r]):
                    v = clean_num(t_model.rows[r][c_idx].text)
                    if v is not None:
                        col_vals.append(v)

            total_val = None
            if c_idx < len(t_model.rows[total_row_idx]):
                total_val = clean_num(t_model.rows[total_row_idx][c_idx].text)

            if len(col_vals) >= 2 and total_val is not None:
                computed_sum = sum(col_vals)
                diff = abs(computed_sum - total_val)
                passed = diff < 0.05
                results.append({
                    'type': 'column_total',
                    'col': c_idx,
                    'expression': f"Sum(Rows 1..{total_row_idx-1}) = {total_val}",
                    'expected': round(computed_sum, 2),
                    'actual': round(total_val, 2),
                    'diff': round(diff, 4),
                    'passed': passed
                })

    passed_count = sum(1 for r in results if r['passed'])
    return {
        'total_audited': len(results),
        'passed_count': passed_count,
        'failed_count': len(results) - passed_count,
        'checks': results
    }


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
    - Self-heals every table matrix topology.
    - Audits accounting calculations.
    - Aggregates confidence metrics.
    """
    total_paragraphs = 0
    total_tables = 0
    total_figures = 0
    all_healing_actions: List[str] = []
    accounting_audits: List[Dict[str, Any]] = []
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
                    all_healing_actions.extend(actions)
                acct_audit = audit_accounting_table(healed_table)
                if acct_audit['total_audited'] > 0:
                    accounting_audits.append(acct_audit)
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

    total_acct_checks = sum(a['total_audited'] for a in accounting_audits)
    passed_acct_checks = sum(a['passed_count'] for a in accounting_audits)

    report = {
        'total_pages': len(doc_model.pages),
        'total_paragraphs': total_paragraphs,
        'total_tables': total_tables,
        'total_figures': total_figures,
        'table_healing_actions': all_healing_actions,
        'table_topology_clean': len(all_healing_actions) == 0,
        'confidence_median': round(median_conf, 3),
        'high_confidence_pct': round(high_conf_pct, 1),
        'low_confidence_tokens': low_conf_count,
        'accounting_checks_total': total_acct_checks,
        'accounting_checks_passed': passed_acct_checks,
        'accounting_audits': accounting_audits
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
        f"| **Tables Reconstructed** | {report['total_tables']} | {'OK' if report['table_topology_clean'] else 'HEALED'} |",
        f"| **Embedded Figures** | {report['total_figures']} | OK |",
        f"| **Median OCR Confidence** | {report['confidence_median'] * 100:.1f}% | {'EXCELLENT' if report['confidence_median'] >= 0.85 else 'REVIEW'} |",
        f"| **High-Confidence Tokens (≥90%)** | {report['high_confidence_pct']:.1f}% | {'HIGH FIDELITY' if report['high_confidence_pct'] >= 85 else 'ACCEPTABLE'} |",
        f"| **Low-Confidence Tokens (<60%)** | {report['low_confidence_tokens']} | {'CLEAN' if report['low_confidence_tokens'] == 0 else 'HIGHLIGHTED'} |",
        f"| **Accounting Checks** | {report['accounting_checks_passed']} / {report['accounting_checks_total']} passed | {'VERIFIED' if report['accounting_checks_total'] > 0 and report['accounting_checks_passed'] == report['accounting_checks_total'] else 'N/A'} |",
        ""
    ]

    if report['table_healing_actions']:
        lines.append("### Table Self-Healing Repairs")
        for act in report['table_healing_actions']:
            lines.append(f"- {act}")
        lines.append("")

    if report['accounting_audits']:
        lines.append("### Accounting Verification Details")
        for audit in report['accounting_audits']:
            for check in audit['checks']:
                status = "PASSED" if check['passed'] else "DISCREPANCY"
                lines.append(f"- **[{status}]** `{check['expression']}` (Calculated: {check['expected']}, Actual: {check['actual']})")
        lines.append("")

    return "\n".join(lines)
