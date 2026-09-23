"""AI (Adobe Illustrator) → AST reader.

Modern .ai files contain an embedded PDF stream, so we read them with PyMuPDF.
"""
from pathlib import Path
from core.ast import Document, Paragraph


def read(path: str) -> Document:
    import fitz  # PyMuPDF

    ast = Document()
    ast.metadata["title"] = Path(path).stem

    doc = fitz.open(path)
    for page in doc:
        text = page.get_text().strip()
        if text:
            for line in text.splitlines():
                line = line.strip()
                if line:
                    ast.children.append(Paragraph(text=line))
    doc.close()

    if not ast.children:
        ast.children.append(Paragraph(text="[No text extracted from .ai file]"))
    return ast
