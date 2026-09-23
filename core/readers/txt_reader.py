"""Plain text → AST reader."""
from pathlib import Path
from core.ast import Document, Paragraph, Heading


def read(path: str) -> Document:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    ast = Document()
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Simple heuristic: ALL-CAPS short lines become headings
        if len(line) < 80 and line.isupper():
            ast.children.append(Heading(level=2, text=line))
        else:
            ast.children.append(Paragraph(text=line))
    return ast
