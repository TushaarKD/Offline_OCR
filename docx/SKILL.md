---
name: docx
description: "Use this skill whenever the user wants to create, read, edit, or manipulate Word documents (.docx files). Triggers include: any mention of 'Word doc', 'word document', '.docx', or requests to produce professional documents with formatting like tables of contents, headings, page numbers, or letterheads. Also use when extracting or reorganizing content from .docx files, inserting or replacing images, performing find-and-replace, or converting content into a polished Word document. If the user asks for a 'report', 'memo', 'letter', or similar deliverable as a Word/.docx file, use this skill. Do NOT use for PDFs, spreadsheets, or general coding tasks unrelated to document generation."
disable-model-invocation: true
---

# DOCX creation, editing, and analysis

A `.docx` is a ZIP archive of XML files. This machine has no pandoc / LibreOffice /
npm `docx` package, so this skill uses **python-docx** in a dedicated venv instead.

| Task | Approach |
|---|---|
| **Create** a new document | Write a Python script using `python-docx` — see `scripts/create_docx.py` |
| **Read** content | Run `scripts/read_docx.py <file>` |
| **Edit** an existing document (raw XML) | `tar` (built into Windows) to unzip → edit `word/document.xml` → `tar` to rezip |

Python venv (already set up, has `python-docx` installed):
```
<skill_dir>/.venv/Scripts/python.exe
```
Always invoke scripts with that interpreter, not the system `python`.

## Creating with python-docx — gotchas

`python-docx` is preinstalled in the skill venv. See `scripts/create_docx.py` for a
working reference script covering headings, lists, tables, and page breaks. Key
footguns:

- **Page size is not guaranteed Letter.** Set explicitly if it matters:
  `section.page_width = Inches(8.5); section.page_height = Inches(11)`.
- **Tables:** set `cell.width` on every cell in every row (setting only column
  widths on the table is often ignored by renderers).
- **Lists:** never type `•` or `1.` literally — use the built-in styles
  `"List Bullet"` / `"List Number"` via `doc.add_paragraph(text, style=...)`.
- **Headings:** use `doc.add_heading(text, level=N)` (built-in Heading styles) —
  required if the document will later get a Table of Contents.
- **Page breaks:** `doc.add_page_break()` is its own call, not embedded in text.
- **Bold/italic/size** are run-level properties (`run.bold = True`,
  `run.font.size = Pt(12)`), not paragraph-level.
- **Images:** `doc.add_picture(path, width=Inches(x))`.

Write a task-specific script (copy/adapt `create_docx.py`), run it with the venv
python, then open/verify the result.

## Reading an existing document

```
<skill_dir>/.venv/Scripts/python.exe scripts/read_docx.py path/to/file.docx
```
Prints paragraph text (with style names) and table contents. For anything the
script doesn't surface (headers/footers, comments, tracked changes), fall back to
the raw-XML approach below.

## Editing an existing document (raw XML)

Word splits visible text across many `<w:r>` runs, so a phrase you can see in the
document often isn't a contiguous string in the XML — always unzip and inspect
`word/document.xml` before assuming a plain find-and-replace will work.

```powershell
tar -xf doc.docx -C unpacked
# edit unpacked/word/document.xml in place — do NOT reformat/pretty-print it
cd unpacked
tar -a -c -f ../out.docx *
cd ..
```

`tar` here is the Windows-builtin `bsdtar` (`C:\Windows\System32\tar.exe`), which
auto-detects zip format from the `.docx`/`.zip` extension via `-a`.

**Comments, tracked changes:** no ready-made helper scripts exist for these in
this environment (unlike some hosted docx skills that ship `comment.py` /
`accept_changes.py` / `validate.py`). If needed, write a small script against the
unpacked `word/document.xml` (and `word/comments.xml` for comments) following the
OOXML schema — ask for this explicitly since it's fragile and worth reviewing
before use.

## Verifying the output

No LibreOffice/`pdftoppm` is available on this machine, so there's no automated
render-to-image step. Verify by:
1. Running `read_docx.py` against the output to sanity-check text/table content.
2. If Microsoft Word is installed, opening the file directly to visually confirm
   formatting.

## Dependencies

- Python venv at `<skill_dir>/.venv` with `python-docx` installed (already set up).
- `tar` (Windows built-in, `C:\Windows\System32\tar.exe`) for raw-XML editing.
- No pandoc, LibreOffice, or npm `docx` package on this machine — do not assume
  they exist; if a task truly needs them, ask before installing anything new.
