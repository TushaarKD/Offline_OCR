# MASTER PLAN: Commercial-Grade Scanned PDF/Image to Editable DOCX Engine

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

### Phase 2: Computer Vision Preprocessing & Artifact Suppression
* **Objective**: Ensure photos from phone cameras, tilted scans, and photocopies convert with maximum character accuracy.
* **Tasks**:
  1. Define `core/preprocessor.py`:
     - **Auto-Orientation**: Detect $0^\circ, 90^\circ, 180^\circ, 270^\circ$ and rotate upright.
     - **Sub-Degree Deskew**: Hough line & Radon transform to detect tilt angles within $\pm 0.1^\circ$ and straighten.
     - **Illumination & Shadow Removal**: Morphological background subtraction to eliminate camera shadows and dark scanner edges.
     - **Watermark Suppression**: Luminance thresholding to suppress faint diagonal institution watermarks from interfering with text OCR.
  2. Multi-Input Support: Allow `.pdf`, `.png`, `.jpg`, `.jpeg`, `.tiff`, `.bmp`.
* **Quality Gate**: A deliberately rotated ($3^\circ$) and shadowed photocopy scan converts upright and clean with zero watermark bleed.

---

### Phase 3: High-Fidelity Typography, Palette & Multi-Column Layout
* **Objective**: Replicate the exact visual styling (fonts, sizes, colors, columns) of the original document.
* **Tasks**:
  1. **Dynamic Font-Size Point Scaling**:
     $$\text{Font Size (Pt)} = \frac{\text{BBox Height (px)}}{\text{DPI}} \times 72 \times \text{Typography Scale}$$
     Automatically detects titles ($18-22\text{pt}$), headings ($13-15\text{pt}$), body text ($10-11\text{pt}$), and footnotes ($8-9\text{pt}$).
  2. **RGB Color Extraction**:
     Sample pixel color values under text bounding boxes using OpenCV/PIL. Preserve blue headings (`#003366`), dark grey body text, and red warning labels in Word (`w:color`).
  3. **Recursive XY-Cut++ Multi-Column Flow**:
     Detect multi-column pages. Split columns cleanly so Word generates native multi-column sections (`w:cols num="2"`). Text flows down Column 1, then Column 2.
* **Quality Gate**: 2-column pages flow naturally in Word without text jumping horizontally across columns.

---

### Phase 4: Commercial-Grade Table Engine & High-Res Figure Embeds
* **Objective**: Perfect financial tables, ledgers, balance sheets, and embedded visual illustrations.
* **Tasks**:
  1. **Accounting Data-Type Alignment**:
     - Numeric balances, currencies, percentages $\rightarrow$ **Right-Aligned**.
     - Descriptions (`Particulars`, `Transactions`) $\rightarrow$ **Left-Aligned**.
     - Codes, dates, mathematical operators ($=, -$) $\rightarrow$ **Centered**.
  2. **Cell Shading & Border Styles**:
     - Sample cell background colors to replicate grey/colored header fills (`w:shd`).
     - Detect borderless tables (whitespace alignment) vs bordered grid tables.
  3. **High-Res Graphic & Figure Cropping**:
     - Detect `figure` layout regions (diagrams, logos, signatures, QR codes).
     - Crop native image at 300 DPI and insert as centered Word pictures (`doc.add_picture`).
* **Quality Gate**: Accounting balance sheets have right-aligned numbers that sum correctly, shaded header rows, and all logos/diagrams embedded in place.

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

