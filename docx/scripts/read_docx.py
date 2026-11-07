"""
Dump the text content (and table contents) of a .docx for reading/review.

Usage:
    <skill_dir>/.venv/Scripts/python.exe read_docx.py path/to/file.docx
"""
import sys
from docx import Document


def main(path: str) -> None:
    doc = Document(path)

    for para in doc.paragraphs:
        if para.text.strip():
            style = para.style.name if para.style else ""
            prefix = f"[{style}] " if style and style != "Normal" else ""
            print(prefix + para.text)

    for i, table in enumerate(doc.tables):
        print(f"\n--- Table {i + 1} ---")
        for row in table.rows:
            print(" | ".join(cell.text for cell in row.cells))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python read_docx.py path/to/file.docx")
        sys.exit(1)
    main(sys.argv[1])
