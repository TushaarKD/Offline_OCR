"""
Reference helper for building a new .docx with python-docx.

Not meant to be run as-is for every request — read it, then write a
task-specific script (or copy/adapt this one) that produces the exact
document the user asked for.

Run with the skill's venv:
    <skill_dir>/.venv/Scripts/python.exe create_docx.py
"""
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn

doc = Document()

# US Letter is NOT the python-docx default (default is also Letter-ish A4
# depends on locale template) — always set explicitly if it matters:
section = doc.sections[0]
section.page_width = Inches(8.5)
section.page_height = Inches(11)

# Headings must use the built-in styles for a Table of Contents to pick
# them up later (Heading 1 / Heading 2 / ...).
doc.add_heading("Document Title", level=0)
doc.add_heading("Section Heading", level=1)

p = doc.add_paragraph()
run = p.add_run("Body text. ")
run.font.size = Pt(11)
bold_run = p.add_run("Bold text.")
bold_run.bold = True

# Bullet / numbered lists: use the built-in styles, don't type bullet
# characters manually.
doc.add_paragraph("First bullet", style="List Bullet")
doc.add_paragraph("Second bullet", style="List Bullet")
doc.add_paragraph("First item", style="List Number")

# Tables: set column widths on every cell (widths on the table alone are
# often ignored by renderers).
table = doc.add_table(rows=1, cols=2)
table.alignment = WD_TABLE_ALIGNMENT.CENTER
widths = (Inches(2), Inches(4))
hdr = table.rows[0].cells
hdr[0].text = "Key"
hdr[1].text = "Value"
for cell, w in zip(hdr, widths):
    cell.width = w
row = table.add_row().cells
row[0].text = "Example"
row[1].text = "Row"
for cell, w in zip(row, widths):
    cell.width = w

# Page break must be its own paragraph/run.
doc.add_page_break()
doc.add_paragraph("Content after the page break.")

doc.save("output.docx")
print("Wrote output.docx")
