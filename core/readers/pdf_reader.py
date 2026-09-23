"""PDF → AST reader (extracts text using PyMuPDF)."""
from pathlib import Path
from core.ast import Document, Paragraph, Heading


def read(path: str) -> Document:
    """Extract text from a PDF into the universal AST.

    Note: this is a best-effort text extraction. Complex layouts,
    images, and multi-column text may not be perfectly preserved.
    """
    import fitz  # PyMuPDF

    doc = fitz.open(path)
    ast = Document()
    ast.metadata["title"] = Path(path).stem

    for pno, page in enumerate(doc, start=1):
        text = page.get_text().strip()
        if not text:
            continue
        # Page marker as a heading
        ast.children.append(Heading(level=2, text=f"Page {pno}"))
        for line in text.splitlines():
            line = line.strip()
            if line:
                ast.children.append(Paragraph(text=line))

    doc.close()

    if not ast.children:
        ast.children.append(Paragraph(text="[No extractable text found in PDF]"))

    return ast
