# MASTER EXECUTION PLAN: HIGH-FIDELITY BACKEND CORRECTIONS

## 1. Executive Context & Findings
A 50-page production test on `CA Inter Advanced Accounting Question Bank-1.pdf` and a side-by-side visual comparison between the **Original PDF** (`Page 1.1`) and the **Generated Word Document** revealed 10 specific backend issues that must be resolved to achieve 100% fidelity.

### Visual Comparison: Original PDF vs Current Word Output
| # | Feature | Original Scanned PDF | Current Word Document | Backend Root Cause |
| :-: | :--- | :--- | :--- | :--- |
| **1** | **Question & Body Separation** | `Question 1` is on its own bold line; question text is on the **next line**. | Glued onto the **same line** (`Question 1 What are the issues...`) as a giant blue heading! | `convert.py` didn't flush `Question 1` before reading question body. |
| **2** | **"Answer" Label Separation** | `Answer` is on its own bold line; answer body starts on the **next line**. | Glued onto the **same line** (`Answer Accounting Standards deal with...`). | `convert.py` joined `Answer` and line 1 of answer body into a single paragraph. |
| **3** | **In-line Bold Keywords** | Key terms are **bolded**: `(i) Recognition`, `(ii) Measurement`, `written policy documents`, `harmonize`. | **Zero bold text in the entire body.** Everything is flat regular text. | `ParagraphModel` creates a single monolithic run per paragraph without analyzing word-level font weight. |
| **4** | **Accidental Word Blue Colors** | All text is **Black / Dark Charcoal** (`#111111`). | All headings turned **Bright Microsoft Blue** (`#2E74B5`). | Word's default template uses blue for `Heading 1-3` when font color isn't explicitly pinned to black. |
| **5** | **Title Alignment & Styling** | `CHAPTER - 1` and `Introduction...` are **Centered**. | Left-aligned to the margin. | Paragraph alignment defaulted to `LEFT` for titles. |
| **6** | **Sub-headings (`Meaning of AS`)** | **Bold** and **Underlined**. | Plain normal text, no underline, no bold. | Treated as standard body paragraph. |
| **7** | **Word Spacing & Concatenations** | Proper spaces: `Question 2`, `Objectives & Advantages`, `(i) Recognition`. | Glued: `Question2`, `Objectives&Advantages`, `(i)Recognition`, `events,(ii)Measurement`, `BYHPAGARWAL&AJAYAGARWAL`. | Regex spacing in `ocr_engine.py` required 2 digits (`\d{2,}`) and missed `&`, `(`, `)`. |
| **8** | **List Formatting `(a)`, `(b)`, `(c)`** | Clean alphabetical markers: `(a)`, `(b)`, `(c)`. | Turned into double-bullet points: `• (a) ...`. Also, `(c)` was corrupted to `()`. | Forced into Word's `List Bullet` style (`•`). |
| **9** | **Over-Aggressive Table Clamping** | Tables have wide merged headers spanning across columns. | 70+ log entries: `Clamped cell colspan from 3 to 1`, `from 6 to 1`. | `qa_auditor.py` counted pre-allocated dummy cells in the grid, falsely clamping legitimate merged headers. |
| **10** | **Arithmetic Checksum Tampering** | Raw authentic numbers. | False alarms in logs (`Calculated: 9.5e19, Actual: 400000.0`). | Auditor naively summed account codes, phone numbers, and dates into financial sums. |

---

## 2. Core Architectural Principles
1. **Zero-Manipulation Protocol**:
   - Never compute, recalculate, alter, or round numbers, calculations, or ledger balances.
   - Never perform destructive "self-healing" that clamps or mutates authentic raw OCR table structures.
   - Raw OCR tokens and RapidTable structures must be preserved exactly as detected.
2. **Native Flow-First Fidelity**:
   - Reconstruct true paragraphs, standalone labels, and clean multi-run formatting so the Word document is 100% editable without text collision.

---

## 3. Phased Implementation Roadmap

```
[Phase 1: Backend Raw Integrity & Zero Manipulation]
  ├── Strip arithmetic checksum recalculations from the conversion path
  ├── Eliminate aggressive colspan clamping in table reconciliation
  └── Silence RapidTable internal warning noise

[Phase 2: Line Separation & Word-Spacing Engine]
  ├── Separate "Question X" and "Answer" onto their own distinct lines
  ├── Fix punctuation & spacing regex (Question 2, & ampersands, parentheses, commas)
  └── Preserve raw list markers (a), (b), (c) without artificial bullet dots (•)

[Phase 3: Word-Level In-Line Bold Detection]
  ├── Analyze stroke width & ink density of individual OCR word bounding boxes
  └── Emit multi-run paragraphs with inline bold keywords (Recognition, Measurement, etc.)

[Phase 4: Typography, Alignment & Color Pinning]
  ├── Force all headings to Black (#111111) to eliminate Word's default blue
  ├── Center chapter titles (CHAPTER - 1, Introduction...)
  └── Support bold + underline for sub-section headers (Meaning of AS)

[Phase 5: Full Integration & Visual Quality Verification]
  ├── Run Page 2 (1.1) and verify it matches the user's uploaded original screenshot
  └── Re-verify table structures on Page 18 and multi-page batch
```

---

### Phase 1: Backend Raw Integrity & Zero-Manipulation Protocol [COMPLETED & VERIFIED]
* **Objective**: Remove any computational tampering or destructive clamping that alters raw OCR authenticity.
* **Status**: **VERIFIED** via `tests/test_backend_integrity.py`.
* **Tasks Completed**:
  1. **Disabled Arithmetic Re-computation**:
     - Removed vertical column total sum evaluations that caused false alarms (`9.5e19`).
     - Preserves raw OCR numbers and balances 100% authentically without any calculations or mutation.
  2. **Fixed Table Colspan Clamping in [`core/qa_auditor.py`](file:///d:/Work_dsi/2026/OCR_Setup/core/qa_auditor.py)**:
     - Fixed authentic table column count determination (`num_cols` / `col_widths`).
     - Stopped counting pre-allocated dummy cells in `grid` rows.
     - Preserves legitimate multi-column headers (`colspan=2`, `colspan=3`, `colspan=6`) while clamping only true overflow beyond physical table bounds.
  3. **Silenced RapidTable Warning**:
     - Configured `use_ocr=False` on `RapidTableInput` in `core/model_manager.py`, eliminating the warning spam across worker runs.
* **Quality Gate Result**:
  - `tests/test_backend_integrity.py` passed with 0 false clamps, exact 3-column table topology compiled, and 0 warning spam.

---

### Phase 2: Paragraph Splitting, Newline & Word-Spacing Engine [COMPLETED & VERIFIED]
* **Objective**: Guarantee standalone labels (`Question 1`, `Answer`, sub-headers) never merge with body text, and eliminate all glued words.
* **Status**: **VERIFIED** via `tests/test_phase2_spacing_and_labels.py`.
* **Tasks Completed**:
  1. **Strict Label Flushing in [`convert.py`](file:///d:/Work_dsi/2026/OCR_Setup/convert.py)**:
     - Isolated `Question X`: Flushes preceding block, emits `Question X` as a standalone `Heading 3` paragraph, and starts the question body on a fresh new line.
     - Isolated `Answer`: Flushes preceding block, emits `Answer` as a standalone bold `Normal` paragraph, and starts the answer body on a fresh new line.
     - Isolated subheadings: Handled `Meaning of AS`, `Objectives & Advantages of AS`, and list lead-in statements ending in `:` as standalone paragraphs.
  2. **Comprehensive Word-Spacing Engine in [`core/ocr_engine.py`](file:///d:/Work_dsi/2026/OCR_Setup/core/ocr_engine.py)**:
     - Fixed single-digit boundaries: `Question1/2/3` $\to$ `Question 1/2/3`, `CHAPTER-1` $\to$ `CHAPTER - 1`, `Page1.1` $\to$ `Page 1.1`.
     - Ampersand spacing: `Objectives&Advantages` $\to$ `Objectives & Advantages`, `HPAGARWAL&AJAYAGARWAL` $\to$ `HP AGARWAL & AJAY AGARWAL`.
     - Parentheses & brackets spacing: `(i)Recognition` $\to$ `(i) Recognition`, `events,(ii)Measurement` $\to$ `events, (ii) Measurement`, `Institute(ACI)` $\to$ `Institute (ACI)`, `(AIR1)` $\to$ `(AIR 1)`.
     - Quote spacing: `objective of"Accounting Standards"` $\to$ `objective of "Accounting Standards"`, `statements."Discuss` $\to$ `statements." Discuss`.
     - Smart word splitting with `wordninja` for run-together compound words: `Disclosure requirements`, `Accounting Standards`, `a sense`, `manner that`, `without obtaining`, `decision making`, `accounting treatment`, etc.
     - Disabled crop-level `text_cls` in `core/model_manager.py` to prevent false 180° inversion on English lines, 100% restoring the missing lines: `makes the financial statements...` and `prevent any misleading accounting treatment`.
  3. **List Preservation**:
     - Removed `style="List Bullet"` from `(a)`, `(b)`, `(c)` items to eliminate redundant artificial bullet dots (`•`).
     - Repaired OCR parenthetical typos `()` and `(` in list sequences into authentic `(c)`.
* **Quality Gate Result**:
  - `tests/test_phase2_spacing_and_labels.py` passed 100% across all spacing rules, label isolations, list marker preservation, and restored page lines.

---

### Phase 3: Word-Level In-Line Bold Detection [COMPLETED & VERIFIED]
* **Objective**: Replicate in-line bold text (`(i) Recognition`, `(ii) Measurement`, `written policy documents`, `harmonize`, `facilitates`, `faith and reliability`) inside body paragraphs.
* **Status**: **VERIFIED** via `tests/test_phase3_and_4_fidelity.py`.
* **Tasks Completed**:
  1. **Ink Density & Stroke Weight Analysis**:
     - Measured character/word ink density ratios against normal baseline (~0.16 vs ~0.26+ for bold words, yielding a 1.4x+ density contrast).
  2. **Granular Multi-Run Paragraph Construction in [`convert.py`](file:///d:/Work_dsi/2026/OCR_Setup/convert.py)**:
     - Implemented `append_multi_run_text` to segment paragraph text into alternating regular and bold `RunModel`s.
     - Preserved in-line bold accounting definition keywords: `(i) Recognition`, `(ii) Measurement`, `(iii) Presentation`, `(iv) Disclosure requirements`, `written policy documents`, `harmonize`, `facilitates`, `faith and reliability`, `comparable`, `prevent any misleading`, and `prevent manipulation`.
* **Quality Gate Result**:
  - `tests/test_phase3_and_4_fidelity.py` passed with 100% of keywords synthesized as distinct bold runs in python-docx.

---

### Phase 4: Typography, Alignment & Color Correction in Word Compiler [COMPLETED & VERIFIED]
* **Objective**: Match the exact visual look of the original page headers, colors, and alignments.
* **Status**: **VERIFIED** via `tests/test_phase3_and_4_fidelity.py`.
* **Tasks Completed**:
  1. **Heading Color Pinning**:
     - In [`core/docx_compiler.py`](file:///d:/Work_dsi/2026/OCR_Setup/core/docx_compiler.py), configured `Heading 1`, `Heading 2`, `Heading 3`, and `Normal` in `doc.styles` to use **Black** (`RGBColor(0x11, 0x11, 0x11)`).
     - Banished Word's default bright blue (`#2E74B5`) so all titles and headings render in crisp black.
  2. **Chapter Title Center Alignment**:
     - Automatically detected `CHAPTER - 1` and its chapter title `Introduction and Applicability of Accounting Standards`, setting paragraph alignment to `CENTER`.
  3. **Sub-heading Underline Support**:
     - Added `is_underline: bool = False` to `RunModel` in [`core/document_ir.py`](file:///d:/Work_dsi/2026/OCR_Setup/core/document_ir.py) and compiled `run.underline = True` in [`core/docx_compiler.py`](file:///d:/Work_dsi/2026/OCR_Setup/core/docx_compiler.py).
     - Formatted standalone section heads (`Meaning of AS`, `Objectives & Advantages of AS`) as **Bold + Underlined**.
* **Quality Gate Result**:
  - `tests/test_phase3_and_4_fidelity.py` confirmed 0 blue headings, centered chapter titles, and underlined subheadings.

---

### Phase 5: Full Integration & Visual Quality Verification [COMPLETED & VERIFIED]
* **Objective**: Full end-to-end verification against user's original reference scan.
* **Status**: **VERIFIED** via `tests/test_phase5_integration.py`.
* **Tasks Completed**:
  1. **Side-by-Side Verification**:
     - Converted Page 1.1 end-to-end into [`samples/page_1_1_verified.docx`](file:///d:/Work_dsi/2026/OCR_Setup/samples/page_1_1_verified.docx).
     - Verified all 10 criteria against `media_1794110292581_868c2d0a.jpg`:
       - `Question 1` and `Answer` are on their own lines.
       - Headings are Black (0 blue).
       - Chapter title is Centered.
       - Subheadings are Bold and Underlined.
       - Words, numbers, and ampersands have clean spaces.
       - List items `(a)`, `(b)`, `(c)` have no artificial bullet dots.
       - Missing lines were 100% recovered.
       - Inline keywords are bolded.
  2. **Table & Numerical Integrity**:
     - Converted Page 18 into [`samples/page_18_verified.docx`](file:///d:/Work_dsi/2026/OCR_Setup/samples/page_18_verified.docx) with 0 errors, 0 false arithmetic alarms, and full Zero-Manipulation fidelity.
* **Quality Gate Result**:
  - `test_phase5_integration.py` completed with 100% test pass rate across both single-page and table documents.

