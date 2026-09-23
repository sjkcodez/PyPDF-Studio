"""DXF (AutoCAD) → AST reader (extracts text entities)."""
from pathlib import Path
from core.ast import Document, Paragraph, Heading


def read(path: str) -> Document:
    import ezdxf

    doc = ezdxf.readfile(path)
    msp = doc.modelspace()

    ast = Document()
    ast.metadata["title"] = Path(path).stem

    for entity in msp:
        dxftype = entity.dxftype()
        if dxftype == "TEXT":
            ast.children.append(Paragraph(text=entity.dxf.text))
        elif dxftype == "MTEXT":
            ast.children.append(Paragraph(text=entity.text))
        elif dxftype in ("ATTRIB", "ATTDEF"):
            ast.children.append(Paragraph(text=entity.dxf.text))

    if not ast.children:
        ast.children.append(Paragraph(text="[No text entities found in DXF]"))
    return ast
