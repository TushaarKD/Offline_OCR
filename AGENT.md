# AGENT GUIDELINES & PROJECT INSTRUCTIONS

## ⚠️ STRICT GIT INSTRUCTION (MANDATORY)
- **STRICTLY NEVER MAKE COMMITS**: The AI agent must NEVER run `git commit`, `git commit -m`, `git push`, `git rebase`, or create commits of any kind.
- **Git is managed manually by the user**: The repository was initialized (`git init`) solely for the user to monitor, review diffs, and track changes.
- The agent should only create or edit workspace files as requested by the user, leaving the git stage and commit history untouched.

---

## Project Overview

This repository (`OCR_Setup`) provides an automated, high-fidelity pipeline to convert complex, scanned or vector-outlined accounting PDFs into Markdown and Microsoft Word (`.docx`) documents with zero content loss.

### Available Scripts & Tools

1. **`pdf_to_markdown.py`**
   - **Purpose**: Converts PDF documents into clean, structured Markdown.
   - **Capabilities**:
     - Dual-mode extraction: uses digital text extraction for native PDFs, and an ONNX-based neural OCR + Layout + Table pipeline for scanned/outlined PDFs.
     - Single-pass OCR (`rapidocr_onnxruntime`) with line clustering and reading order reconstruction.
     - Neural layout parsing (`rapid_layout`) to detect table regions, headers, and footers.
     - Neural table structure recognition (`rapid_table` / `SLANet+`) to reconstruct complex accounting tables, balance sheets, and ledgers.
     - Automatically restores Indian Rupee notation (`₹`) and formats headings (`# CHAPTER`, `### Question N`, `**Answer**`, list items `- (1)`).
     - Multi-process parallelism (`ProcessPoolExecutor`) for fast multi-page batch conversion.
   - **Usage**:
     ```powershell
     .\venv\Scripts\python.exe pdf_to_markdown.py <input.pdf> [-o output.md] [--dpi 150] [--workers 4] [--start-page 1] [--end-page 50]
     ```

2. **`markdown_to_docx.py`**
   - **Purpose**: Converts Markdown files into professional Microsoft Word documents (`.docx`).
   - **Capabilities**:
     - Follows `python-docx` best practices (explicit letter/A4 geometry, 0.75" margins).
     - Full table support: converts both GFM Markdown tables (`| ... |`) and HTML `<table>` elements with cell merges (`colspan` / `rowspan`).
     - Sets column widths across every cell in every row for uniform rendering.
     - Uses Word built-in styles (`Heading 1`, `Heading 2`, `Heading 3`, `List Bullet`) for native Word Table of Contents and navigation pane support.
     - Preserves all text, questions, answers, amounts, and original pagination via page breaks (`<!-- Page N -->`).
   - **Usage**:
     ```powershell
     .\venv\Scripts\python.exe markdown_to_docx.py <input.md> [-o output.docx] [--no-page-breaks]
     ```

3. **`docx/` Skill**:
   - Contains reference scripts (`scripts/create_docx.py`, `scripts/read_docx.py`) and a dedicated venv for Word document manipulation and verification.

---

## Python Environment
- Primary venv: `D:\Work_dsi\2026\OCR_Setup\venv` (Python 3.11)
- Installed dependencies: `pymupdf`, `pymupdf4llm`, `rapidocr_onnxruntime`, `rapid_layout`, `rapid_table`, `beautifulsoup4`, `python-docx`, `onnxruntime`, `opencv-python`.

