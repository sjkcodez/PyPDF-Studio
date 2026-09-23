"""AST → DXF (AutoCAD) writer.

Writes each Paragraph as a TEXT entity on a single layer.
"""
from core.ast import Document, Paragraph, Heading


def write(ast: Document, output_path: str):
    import ezdxf

    doc = ezdxf.new(dxfversion="R2010")
    msp = doc.modelspace()

    y = 0.0
    line_height = 10.0

    for node in ast.children:
        if isinstance(node, Heading):
            text = node.text
            height = 14.0
        elif isinstance(node, Paragraph):
            text = node.text
            height = 10.0
        else:
            continue

        # Simple word-wrap for very long lines
        max_chars = 90
        chunks = [text[i:i + max_chars] for i in range(0, len(text), max_chars)] or [""]
        for chunk in chunks:
            msp.add_text(
                chunk,
                dxfattribs={"height": height, "insert": (0, y)},
            ).set_placement((0, y))
            y -= line_height
        y -= line_height  # extra space between blocks

    doc.saveas(output_path)
