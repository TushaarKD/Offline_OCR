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

### Phase 1: Backend Raw Integrity & Zero-Manipulation Protocol
* **Objective**: Remove any computational tampering or destructive clamping that alters raw OCR authenticity.
* **Tasks**:
  1. **Disable Arithmetic Re-computation**:
     - Remove vertical column total sum evaluations that cause false alarms (`9.5e19`).
     - Remove any calculation that second-guesses or mutates raw OCR numbers.
  2. **Fix Table Colspan Clamping in [`core/qa_auditor.py`](file:///d:/Work_dsi/2026/OCR_Setup/core/qa_auditor.py)**:
     - Stop counting pre-allocated dummy cells in `grid` rows.
     - Only apply safety bounds to prevent python-docx `IndexError` without shrinking legitimate multi-column headers (`colspan=2`, `colspan=3`, `colspan=6`).
  3. **Silence RapidTable Warning**:
     - Pass `use_ocr=False` to `RapidTableInput` so the cosmetic `rapidocr package is not installed` warning is eliminated.
* **Quality Gate**:
  - Test on synthetic tables and Page 18 table; confirm **0** false `Clamped cell colspan` warnings in logs.

---

### Phase 2: Paragraph Splitting, Newline & Word-Spacing Engine
* **Objective**: Guarantee standalone labels (`Question 1`, `Answer`, sub-headers) never merge with body text, and eliminate all glued words.
* **Tasks**:
  1. **Strict Label Flushing in [`convert.py`](file:///d:/Work_dsi/2026/OCR_Setup/convert.py)**:
     - When a line matches `r'^Question\s*\d+'`:
       - Flush previous paragraph immediately.
       - Create a standalone `Heading 3` paragraph with text `Question X` (and only `Question X`).
       - Flush immediately so the subsequent question body begins on a clean, new paragraph.
     - When a line matches `r'^Answer\b'`:
       - Flush previous paragraph immediately.
       - Create a standalone bold paragraph `Answer`.
       - Flush immediately so the answer body text begins on a clean, new paragraph.
     - When a short standalone line matches section heads (`Meaning of AS`, `Objectives & Advantages of AS`):
       - Flush immediately as its own paragraph.
  2. **Comprehensive Word-Spacing Engine in [`core/ocr_engine.py`](file:///d:/Work_dsi/2026/OCR_Setup/core/ocr_engine.py)**:
     - Separate single-digit boundaries: `r'([a-zA-Z]{2,})(\d+)' \to r'\1 \2'` (`Question2` $\to$ `Question 2`).
     - Separate ampersands: `r'([a-zA-Z0-9])&'` $\to$ `r'\1 & '` and `r'&([a-zA-Z0-9])'` $\to$ `r' & \1'` (`Objectives&Advantages` $\to$ `Objectives & Advantages`).
     - Separate parentheses & brackets: `r'\)([a-zA-Z])'` $\to$ `r') \1'` (`(i)Recognition` $\to$ `(i) Recognition`) and `r'([a-zA-Z])\('` $\to$ `r'\1 ('` (`Institute(ACI)` $\to$ `Institute (ACI)`).
     - Separate punctuation-parenthesis collisions: `r',(\()'` $\to$ `r', \1'` (`events,(ii)` $\to$ `events, (ii)`).
     - Footer token spacing: Clean separation for `BY HP AGARWAL & AJAY AGARWAL (AIR 1)`.
  3. **List Preservation**:
     - Remove `style="List Bullet"` from `(a)`, `(b)`, `(c)` items. Output them as clean hanging-indent paragraphs without redundant bullet dots (`•`).
* **Quality Gate**:
  - Process Page 2; verify `Question 1` is on its own line, `Answer` is on its own line, `(a)`, `(b)`, `(c)` have no bullet dots, and words are cleanly separated.

---

### Phase 3: Word-Level In-Line Bold Detection
* **Objective**: Replicate in-line bold text (`(i) Recognition`, `(ii) Measurement`, `written policy documents`, `harmonize`, `facilitates`, `faith and reliability`) inside body paragraphs.
* **Tasks**:
  1. **Ink Density & Stroke Weight Analyzer**:
     - For each word bounding box within a text line, crop the corresponding region from the preprocessed grayscale page image.
     - Compute the ink fill density (ratio of dark foreground pixels to bounding box area).
     - Calculate the median ink density of normal body text on the line.
     - Words with an ink density $\ge 1.25\times$ the line baseline are classified as `is_bold = True`.
  2. **Granular Multi-Run Paragraph Construction**:
     - Instead of emitting a single monolithic `RunModel` per paragraph, split the paragraph text into alternating regular and bold `RunModel` segments.
     - In Word compilation, each run inherits its specific bold weight.
* **Quality Gate**:
  - Test on Page 2 Answer 1 and Answer 2; verify keywords (`Recognition`, `written policy documents`, `harmonize`) are compiled as bold runs in Word.

---

### Phase 4: Typography, Alignment & Color Correction in Word Compiler
* **Objective**: Match the exact visual look of the original page headers, colors, and alignments.
* **Tasks**:
  1. **Heading Color Pinning**:
     - In [`core/docx_compiler.py`](file:///d:/Work_dsi/2026/OCR_Setup/core/docx_compiler.py), explicitly configure `Heading 1`, `Heading 2`, `Heading 3`, and `Normal` styles to use **Black** (`RGBColor(0x11, 0x11, 0x11)`).
     - Banish Word's default bright blue (`#2E74B5`) so all titles and headings render in crisp black.
  2. **Chapter Title Center Alignment**:
     - For `CHAPTER - 1` and `Introduction and Applicability of Accounting Standards`, evaluate the horizontal bounding center. If centered on page, set paragraph alignment to `CENTER`.
  3. **Sub-heading Underline Support**:
     - Add `is_underline: bool = False` to `RunModel` and compile `<w:u w:val="single"/>` in `_compile_run`.
     - Detect underline strokes or rule lines under section heads (`Meaning of AS`, `Objectives & Advantages of AS`) and format them as **Bold + Underlined**.
* **Quality Gate**:
  - Inspect compiled Word document: confirm 0 blue headings, centered chapter title, and underlined subheadings.

---

### Phase 5: Full Integration & Visual Quality Verification
* **Objective**: Full end-to-end verification against user's original reference scan.
* **Tasks**:
  1. **Side-by-Side Visual Inspection**:
     - Convert Page 2 (`Page 1.1`) and compare against `media_1794110292581_868c2d0a.jpg` across all 10 criteria.
  2. **Multi-Page & Table Regression Audit**:
     - Re-run Page 18 and multi-page batch.
     - Verify 0 table merges clamped, 0 false arithmetic warnings, and 100% raw numerical authenticity.
* **Quality Gate**:
  - Output Word document matches the original scan visual layout, preserves all raw numbers, and is 100% flow-editable.

