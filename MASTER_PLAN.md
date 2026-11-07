# MASTER PLAN: Commercial-Grade Scanned PDF/Image to Editable DOCX Engine

# Critical: If anywhere you found we are drifting away, unable to achieve goals or getting bottlenecked then let the user know about it. 

> **Project North Star**:  
> To produce a **100% accurate, fully editable Microsoft Word (`.docx`) document** from any scanned PDF, photo, or document image. The output must visually look as if the source PDF was directly exported from Microsoft Word, while remaining completely reflowable and natively editable (adding text, modifying tables, or changing layouts will never break or overlap content).

---

## 1. Architectural Philosophy: The "Native Flow" Principle

Traditional PDF-to-Word tools fail because they choose one of two extremes:
1. **The Floating Box Trap (Fragile Clones)**: They place every text line into absolute floating text boxes (`<w:drawing>`). It looks identical at first glance, but editing is impossible: adding a single word causes boxes to collide and overlap.
2. **The Plain Text Trap**: They strip all formatting and dump unstyled text. It is easy to edit, but loses original layout, typography, colors, and identity.

### Our Architecture: The Native Semantic Flow
We reconstruct the document using **Word's native desktop publishing features**:
* **Native Margins & Sections**: Match physical scan geometry ($0.65" - 0.75"$).
* **Native Multi-Column Sections (`w:cols`)**: 2-column or 3-column layouts flow down Column 1, then Column 2, naturally reflowable.
* **Point-Scaled Typography**: Dynamic font points ($18\text{pt}$ Title, $14\text{pt}$ Section, $10.5\text{pt}$ Body, $8.5\text{pt}$ Footnote) calculated directly from scan pixel heights.
* **Proportional Word Tables**: Real table grids with proportional column widths, right-aligned accounting figures, left-aligned descriptions, and cell background shading.
* **Inline Graphic Anchors**: Native centered figures (`doc.add_picture`) for charts, logos, and signatures.
* **Dual Output Capability**: While Word (`.docx`) is the primary visual output, a clean, semantic Markdown (`.md`) file can be generated simultaneously from the same Document Model.

---

## 2. Modular Script Architecture (Zero Accuracy Loss)

To maintain clean code without monolithic scripts, the architecture is divided into specialized, decoupled modules. Each module has a single responsibility and is independently testable:

```
D:\Work_dsi\2026\OCR_Setup\
├── core/
│   ├── __init__.py
│   ├── document_ir.py       # Central In-Memory Document DOM (Pages, Blocks, Tables, Runs)
│   ├── preprocessor.py      # OpenCV Auto-Deskew, Shadow Removal, Watermark Suppression
│   ├── layout_engine.py     # PP-CDLA Layout & Recursive XY-Cut Multi-Column Analysis
│   ├── ocr_engine.py        # Single-Pass OCR & Token-Level Reading Order Extraction
│   ├── table_engine.py      # SLANet+ Neural Table Synthesis, Cell Alignment & Shading
│   └── docx_compiler.py     # Direct Document IR to Native Word (.docx) Flow Synthesizer
│
├── models/                  # Bundled offline ONNX model weights (Zero internet required)
├── convert.py               # Unified 1-Click CLI & Python API Entrypoint
├── MASTER_PLAN.md           # This persistent execution roadmap
├── AGENT.md                 # Strict Agent Guidelines (Never commit, user manages git)
└── requirements.txt         # Clean dependency list
```

---

## 3. Phased Execution Roadmap

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                             6-PHASE MASTER ROADMAP                               │
├─────────┬──────────────────────────────────────┬─────────────────────────────────┤
│ Phase 1 │ Document IR & Direct Flow Compiler   │ Eliminate intermediate Markdown │
│         │                                      │ bottleneck; Direct DOM -> DOCX  │
├─────────┼──────────────────────────────────────┼─────────────────────────────────┤
│ Phase 2 │ Vision Preprocessor & Cleaners       │ Auto-Deskew, Shadow removal,    │
│         │                                      │ Watermark suppression           │
├─────────┼──────────────────────────────────────┼─────────────────────────────────┤
│ Phase 3 │ Typography, Colors & Multi-Columns   │ Point scaling, RGB sampling,    │
│         │                                      │ Recursive XY-Cut Column Flow    │
├─────────┼──────────────────────────────────────┼─────────────────────────────────┤
│ Phase 4 │ Commercial Tables & Figure Embeds    │ Right-aligned numbers, cell     │
│         │                                      │ shading, embedded illustrations │
├─────────┼──────────────────────────────────────┼─────────────────────────────────┤
│ Phase 5 │ Self-Healing QA & Validation         │ Checksums, balance-sheet audit, │
│         │                                      │ table grid integrity check      │
├─────────┼──────────────────────────────────────┼─────────────────────────────────┤
│ Phase 6 │ Desktop Application & Standalone EXE │ PyInstaller/Nuitka build, 100%  │
│         │                                      │ offline bundled models, GUI     │
└─────────┴──────────────────────────────────────┴─────────────────────────────────┘
```

---

### Phase 1: Core Document IR & Direct Flow Compiler
* **Objective**: Remove the Markdown bottleneck for DOCX generation while keeping Markdown export optional.
* **Tasks**:
  1. Define `core/document_ir.py`:
     - Dataclasses: `DocumentModel`, `PageModel`, `SectionModel`, `ColumnModel`, `BlockModel` (`Paragraph`, `Table`, `Figure`), `RunModel`.
  2. Implement `core/docx_compiler.py`:
     - Maps `DocumentModel` directly into native `python-docx` elements.
     - Preserves headings (`Heading 1`, `Heading 2`, `Heading 3`), native bullet lists, and page breaks.
  3. Implement `.to_markdown()` on `DocumentModel` so clean `.md` is always exportable on demand.
* **Quality Gate**: Converting `CA Inter Advanced Accounting Question Bank-1.pdf` produces identical text and table output with faster execution and zero loss of structure.

---

### Phase 2: Computer Vision Preprocessing & Artifact Suppression [COMPLETED & VERIFIED]
* **Objective**: Ensure photos from phone cameras, tilted scans, and photocopies convert with maximum character accuracy.
* **Tasks Completed**:
  1. Implemented [`core/preprocessor.py`](file:///d:/Work_dsi/2026/OCR_Setup/core/preprocessor.py):
     - **360° Auto-Orientation**: Aspect-ratio analysis + text orientation classification to detect $0^\circ, 90^\circ, 180^\circ, 270^\circ$ and rotate upright.
     - **Sub-Degree Deskew**: Hough Line Transform on horizontal text line baselines to straighten tilt ($< 0.1^\circ$ residual error).
     - **Adaptive Shadow & Illumination Flattening**: Morphological background division (`cv2.dilate` + `medianBlur` + division normalization) to eliminate uneven phone lighting and dark scanner margins while preserving color and contrast.
     - **Watermark Suppression**: High-luminance thresholding to suppress faint diagonal institution watermarks.
  2. Multi-Input Support in [`convert.py`](file:///d:/Work_dsi/2026/OCR_Setup/convert.py):
     - Added native support for `.png`, `.jpg`, `.jpeg`, `.tiff`, `.tif`, `.bmp`, `.webp` direct image inputs as well as multi-page PDFs.
* **Quality Gate Verification**:
  - Tested on +3.5° tilted image: accurately detected $-3.22^\circ$ skew and restored to 0.00° residual.
  - Tested on simulated mobile camera shadow: detected non-uniformity and flattened background illumination.
  - Tested on 90° sideways scan: detected orientation, rotated upright (270° CW), and extracted all tables and text.
  - All extracted Word (.docx) elements verified via read-back test.

---

### Phase 3: High-Fidelity Typography, Palette & Multi-Column Layout [COMPLETED & VERIFIED]
* **Objective**: Replicate the exact visual styling (fonts, sizes, colors, columns) of the original document.
* **Tasks Completed**:
  1. **Dynamic Font-Size Point Scaling**:
     $$\text{Font Size (Pt)} = \frac{\text{BBox Height (px)}}{\text{DPI}} \times 72 \times \text{Typography Scale}$$
     Implemented in [`convert.py`](file:///d:/Work_dsi/2026/OCR_Setup/convert.py) and [`core/docx_compiler.py`](file:///d:/Work_dsi/2026/OCR_Setup/core/docx_compiler.py): Automatically scales titles ($18-22\text{pt}$ Heading 1), section heads ($13-16\text{pt}$ Heading 2), questions ($12\text{pt}$ Heading 3), bullet lists ($10.5\text{pt}$), body text ($10.5\text{pt}$), and fine print / footers ($8.5-9.5\text{pt}$).
  2. **RGB Color Extraction & Cell Background Tinting**:
     Implemented [`sample_text_color_from_crop`](file:///d:/Work_dsi/2026/OCR_Setup/core/layout_engine.py#L125-L162) and [`sample_cell_background_color`](file:///d:/Work_dsi/2026/OCR_Setup/core/layout_engine.py#L165-L188): Samples exact ink stroke colors (e.g. navy blue `#004059`, warm brown, slate grey) and applies them to Word text runs (`w:color`), as well as `#F2F4F7` cell background fills (`w:shd`).
  3. **Recursive XY-Cut++ Multi-Column Flow**:
     Implemented in [`core/layout_engine.py`](file:///d:/Work_dsi/2026/OCR_Setup/core/layout_engine.py#L50-L122) and [`core/ocr_engine.py`](file:///d:/Work_dsi/2026/OCR_Setup/core/ocr_engine.py#L95-L135): Decomposes full-width spanning headers/footers and vertical column gutters so 2-column and multi-column documents flow down Column 1, then Column 2, with zero interleaving.
* **Quality Gate Verification**:
  - Page 1 cover: Verified navy blue branding `#004059` at 22pt Heading 1 and subtitle hierarchy.
  - Page 18: Verified Heading 2 (15.5pt), Heading 3 (12.0pt), bullets (10.5pt), and table with shaded `#F2F4F7` headers and right-aligned numeric data.
  - Synthetic 2-column document: Verified reading order flows Column 1 (Q1, Answer 1, Q2, Answer 2) then Column 2 (Q3, Answer 3, Q4, Answer 4), cleanly bounded by spanning header and footer.

---

### Phase 4: Commercial-Grade Table Engine & High-Res Figure Embeds [COMPLETED & VERIFIED]
* **Objective**: Perfect financial tables, ledgers, balance sheets, and embedded visual illustrations.
* **Tasks Completed**:
  1. **Accounting Data-Type Alignment**:
     - Numeric balances, currencies, percentages $\rightarrow$ **Right-Aligned** (`w:jc="right"`).
     - Descriptions (`Particulars`, `Transactions`) $\rightarrow$ **Left-Aligned** (`w:jc="left"`).
     - Codes, dates, mathematical operators ($=, -$) $\rightarrow$ **Centered** (`w:jc="center"`).
     - Implemented in [`_detect_cell_alignment`](file:///d:/Work_dsi/2026/OCR_Setup/core/table_engine.py#L51-L64) and verified on balance sheet on Page 18.
  2. **Cell Shading, Padding & Accounting Border Styles**:
     - Sample cell background colors to replicate header fills (`w:shd="F2F4F7"`).
     - Set cell padding margins (`w:tcMar`: top/bottom 3pt, left/right 5pt) across all table cells in [`_set_cell_padding`](file:///d:/Work_dsi/2026/OCR_Setup/core/docx_compiler.py#L65-L88).
     - Morphological border detection in [`detect_table_borders`](file:///d:/Work_dsi/2026/OCR_Setup/core/table_engine.py#L27-L49): Distinguishes grid tables from borderless whitespace-aligned tables.
     - Accounting rule border styling in [`_compile_table`](file:///d:/Work_dsi/2026/OCR_Setup/core/docx_compiler.py#L149-L168): Emits clean top/bottom rules (`#B0B0B0`), subtle horizontal dividers (`#E0E0E0`), and suppresses vertical borders.
  3. **High-Res Graphic & Figure Cropping**:
     - Detected `figure` layout regions (logos, cover artwork, diagrams) in [`convert.py`](file:///d:/Work_dsi/2026/OCR_Setup/convert.py#L123-L176).
     - Cropped native image at 300 DPI, encoded to in-memory PNG bytes, and embedded directly as native Word inline shape (`WD_INLINE_SHAPE_TYPE.PICTURE`) preserving aspect ratios in [`_compile_figure`](file:///d:/Work_dsi/2026/OCR_Setup/core/docx_compiler.py#L240-L263).
     - Added companion markdown figure export: saves figures to a dedicated `{stem}_figures/` directory with relative links.
* **Quality Gate Verification**:
  - Page 1 Cover Graphic: Successfully extracted cover illustration and embedded it as an inline picture shape into Word (`width=6400800`, `height=5963446`), with companion markdown referencing `test_p1_figures/page_1_fig_1.png`.
  - Page 18 Financial Table: Successfully compiled 6-column accounting table with `#F2F4F7` shaded centered headers, right-aligned numbers (`8.00`, `3.00`, `5.00`), centered operators (`-`, `=`), left-aligned labels (`Opening`), and 3pt/5pt cell padding (`tcMar=True`).
  - Borderless Table Detection: Verified `detect_table_borders` on grid vs borderless images; verified accounting XML rule borders (`tblBorders` top/bottom single `#B0B0B0`, insideH `#E0E0E0`, vertical none).

---

### Phase 5: Self-Healing QA & Verification Loop
* **Objective**: Automatically detect and flag potential errors before handing the file to the user.
* **Tasks**:
  1. **Table Matrix Consistency Check**:
     Verify that every row in a table matches the column topology (no mismatched cell counts).
  2. **Accounting Checksums (Optional Audit)**:
     In financial statements, verify basic arithmetic consistency ($\text{Assets} = \text{Liabilities} + \text{Equity}$).
  3. **Low-Confidence Highlighting**:
     Optionally highlight characters with low OCR confidence ($<60\%$) in soft yellow so human review is fast and effortless.
* **Quality Gate**: Automated test suite runs on 10 diverse document samples and passes all consistency audits.

---

### Phase 6: Packaging, Local Model Bundling & Standalone App
* **Objective**: Compile the entire engine into a standalone, 100% offline Windows desktop application.
* **Tasks**:
  1. **Local Model Bundling**:
     Download and store all ONNX model binaries (`ch_PP-OCRv4_det`, `ch_PP-OCRv4_rec`, `layout_cdla`, `slanet-plus`) in a local `models/` directory. Zero internet connection required.
  2. **Modern Desktop GUI**:
     Build a clean, modern drag-and-drop desktop UI (using CustomTkinter or PyQt6):
     - Drag-and-drop box for PDFs and photos.
     - Output format checkboxes: `[X] Microsoft Word (.docx)`, `[ ] Markdown (.md)`.
     - Real-time progress bar, page counter, and ETA.
     - One-click "Open in Word" button.
  3. **Standalone Executable**:
     Package using PyInstaller / Nuitka into a portable Windows `.exe` installer requiring **no Python installation**.
* **Quality Gate**: The compiled `.exe` runs on a fresh Windows machine with internet disabled and converts any PDF/Image to Word in seconds.

---

## 4. Current vs Target State Comparison

| Feature | Current State | Target Finished Product |
| :--- | :--- | :--- |
| **Intermediate Pipeline** | PDF $\rightarrow$ MD $\rightarrow$ DOCX | Direct PDF/Image $\rightarrow$ Document IR $\rightarrow$ DOCX (+ optional MD) |
| **Typography Scaling** | Fixed 10.5pt for all body | Dynamic point scaling ($18\text{pt}$ Title, $14\text{pt}$ Heading, $10.5\text{pt}$ Body) |
| **Color Support** | Monochrome black/white | Exact RGB color sampling for text, headings, and cell shading |
| **Table Formatting** | Basic table grid | Proportional widths, numeric right-alignment, cell background fill |
| **Visual Elements** | Tables only | Tables + embedded high-res diagrams, logos, and signatures |
| **Multi-Column Flow** | Top-to-bottom line order | Recursive XY-Cut with native Word 2/3-column sections |
| **Input Formats** | PDF only | PDF, PNG, JPG, JPEG, TIFF, BMP |
| **Image Preprocessing** | Direct rendering | Auto-Deskew, Shadow Removal, Watermark Suppression |
| **Packaging** | Python virtual environment | 1-Click Standalone Windows `.exe` Desktop App |

---

## 5. Execution Protocol
* **Strict Git Policy**: In accordance with `AGENT.md`, the AI assistant will **strictly never make git commits**. All file updates remain in the working directory for manual user review and staging.
* **Zero Content Alteration**: Accuracy is sacred. No numbers, formulas, ledger balances, or text will ever be altered, hallucinated, or discarded.

