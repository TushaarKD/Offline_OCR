# AGENT GUIDELINES & CORE PROTOCOL

## ⚠️ STRICT GIT INSTRUCTION (MANDATORY)
- **STRICTLY NEVER MAKE COMMITS**: The AI agent must NEVER run `git commit`, `git commit -m`, `git push`, `git rebase`, or create commits of any kind.
- **Git is managed manually by the user**: The repository was initialized solely for the user to monitor diffs, review changes, and commit at each milestone.
- The agent must only create or edit workspace files, leaving git staging and commit creation exclusively to the user.

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

## 📋 RULES FOR `PLAN.md` GENERATION & EXECUTION
Whenever new issues, bugs, logs, or visual discrepancies are identified, the agent must generate and maintain a structured, phased roadmap in `PLAN.md` adhering to the following rules:

1. **Root-Cause Phasing**:
   - Every issue found must be traced to its exact technical root cause and assigned to a clear, dedicated phase.
2. **Strict Phase-by-Phase Execution**:
   - Always execute the plan step-by-step in sequential order. Never skip steps, rush ahead, or drift away from the active plan.
3. **Alignment with Core Goal**:
   - Every task in `PLAN.md` must directly serve the core goal: raw authenticity, zero computation tampering, exact visual formatting, and native flow editability.
4. **Verifiable Quality Gates**:
   - Each phase must conclude with an automated or visual quality verification test before declaring completion.
5. **Living Source of Truth**:
   - `PLAN.md` remains the active guiding document across conversation turns to ensure zero context loss and zero drifting.
