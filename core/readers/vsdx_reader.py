"""VSDX (Visio) → AST reader.

VSDX is a ZIP archive containing XML. We extract text from shapes.
"""
from pathlib import Path
from core.ast import Document, Paragraph, Heading


def read(path: str) -> Document:
    from vsdx import VisioFile

    ast = Document()
    ast.metadata["title"] = Path(path).stem

    with VisioFile(path) as vis:
        for page in vis.pages:
            ast.children.append(Heading(level=1, text=f"Page: {page.name}"))
            for shape in page.all_shapes:
                try:
                    txt = shape.text
                    if txt and txt.strip():
                        ast.children.append(Paragraph(text=txt.strip()))
                except Exception:
                    continue

    if not ast.children:
        ast.children.append(Paragraph(text="[No text found in VSDX]"))
    return ast
