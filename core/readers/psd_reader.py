"""PSD (Photoshop) → AST reader.

Extracts text from text layers via psd-tools.
"""
from pathlib import Path
from core.ast import Document, Paragraph, Heading


def read(path: str) -> Document:
    from psd_tools import PSDImage

    psd = PSDImage.open(path)
    ast = Document()
    ast.metadata["title"] = Path(path).stem

    def walk(layer, depth=0):
        # Recurse into groups
        if layer.is_group():
            for child in layer:
                walk(child, depth + 1)
            return
        # Text layer?
        if layer.kind == "type":
            try:
                txt = layer.text
                if txt and txt.strip():
                    ast.children.append(Heading(level=min(depth + 2, 6), text=f"Layer: {layer.name}"))
                    for line in txt.splitlines():
                        if line.strip():
                            ast.children.append(Paragraph(text=line.strip()))
            except Exception:
                pass

    for layer in psd:
        walk(layer)

    if not ast.children:
        ast.children.append(Paragraph(text="[No text layers found in PSD]"))
    return ast
