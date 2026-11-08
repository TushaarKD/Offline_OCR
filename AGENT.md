# AGENT GUIDELINES & CORE PROTOCOL

## ⚠️ STRICT GIT INSTRUCTION (MANDATORY)
- **STRICTLY NO GIT ACTIONS FROM YOUR SIDE UNTIL ASKED EXPLICITLY**: The AI agent must NEVER run `git commit`, `git commit -m`, `git push`, `git rebase`, `git tag`, or create commits of any kind unless the user explicitly asks for it in the prompt.
- **Ask when in doubt**: If you are ever not sure at some places regarding git or project state, ask the user before taking action.
- **Git is managed manually by the user**: The repository was initialized solely for the user to monitor diffs, review changes, and commit at each milestone.
- The agent must only create or edit workspace files, leaving git staging and commit creation exclusively to the user unless explicitly commanded.

---

## 🎯 CORE PROJECT GOAL
To build an industry-standard, commercial-grade (Adobe Acrobat / ABBYY FineReader level) document conversion engine and standalone offline desktop application that converts scanned PDFs, images, and camera photos into **100% flow-editable Microsoft Word (`.docx`)** documents and companion **Markdown (`.md`)** files with **100% fidelity to the original document**.

### Key Tenets of the Core Goal:
1. **100% Original Look & Feel**:
   - The output Word document must look as though the original scanned PDF was exported directly from it: preserving exact typography, fonts, point sizes, colors, inline bolding, paragraph spacing, alignments, and native Word tables.
2. **Absolute Zero-Manipulation Protocol**:
   - **Never manipulate, compute, alter, or hallucinate raw numbers, calculations, ledger balances, currency symbols, or text.**
   - **Never perform destructive "self-healing" or arithmetic recalculation** that clamps, second-guesses, or alters raw OCR table structures or data. Every number and cell must remain 100% authentic to the source document.
3. **Native Word Flow Architecture**:
   - Construct all documents using native Word flow elements (margins, section columns, paragraphs, native tables, inline shapes) rather than fragile floating text-boxes, ensuring natural, non-overlapping editing.
4. **100% Offline & Standalone**:
   - Runs completely offline with bundled local ONNX models, packaged as a portable Windows desktop application.

---

## 📋 RULES FOR `PLAN.md` GENERATION & STEP-BY-STEP IMPLEMENTATION
Whenever new issues, bugs, logs, or visual discrepancies are identified, the agent must strictly adhere to the following workflow:

1. **Plan First Every Time (Divided into Clear Phases)**:
   - **Always create the plan first**: Before writing or modifying any implementation code, a structured, dedicated plan MUST be created.
   - **Phased Division Aligned with Main Goal**: The plan must be broken down into clear, logical phases, with every single task directly serving the core project goal (100% flow-editable output, 100% visual fidelity, Zero-Manipulation Protocol).
2. **One Step / One Phase at a Time Implementation (Mandatory)**:
   - **Strictly one step at once**: While implementing, ONLY ONE STEP OR PHASE MUST BE IMPLEMENTED AT A TIME.
   - **Never bundle or rush multiple phases**: Do not implement multiple phases in a single turn. Complete the active phase, verify it with an automated test, report the results, and pause for user review/confirmation before moving to the next phase.
3. **Dedicated `plans/` Directory with Unique Names**:
   - All plan documents MUST reside in the git-tracked `plans/` folder.
   - Each plan file MUST have a **unique, clearly identifiable name** (e.g. `plans/00_MASTER_ROADMAP.md`, `plans/01_BACKEND_FIDELITY_PLAN.md`, `plans/02_...md`) so progress is structured, unambiguous, and easily tracked over time.
4. **Root-Cause Phasing**:
   - Every issue found must be traced to its exact technical root cause and assigned to a clear, dedicated phase.
5. **Verifiable Quality Gates**:
   - Each phase must conclude with an automated unit/regression or visual verification test before declaring completion.
6. **Living Source of Truth**:
   - The active plan remains the single source of truth across conversation turns to ensure zero context loss and zero drifting.

---

## 📌 PENDING / PARKED PLANS
- **Plan 04 (`plans/04_DOCUMENT_GENERALIZATION_AND_INTEGRITY_PLAN.md`)**: Parked for future implementation (covers generalized header/footer masking, morphological table line snapping, list outdent segmentation, and compound word fusion healing).
