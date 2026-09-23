"""XPS (XML Paper Specification) → AST reader.

XPS is an OPC package (ZIP) containing fixed-page XML. Text is stored
inside <Glyphs UnicodeString="..."/> elements.
"""
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET
from core.ast import Document, Paragraph


XPS_NS = "{http://schemas.microsoft.com/xps/2005/06}"


def read(path: str) -> Document:
    ast = Document()
    ast.metadata["title"] = Path(path).stem

    with zipfile.ZipFile(path) as zf:
        # Find all .fpage files (fixed pages)
        page_files = sorted(
            n for n in zf.namelist()
            if n.endswith(".fpage") and "/Pages/" in n
        )
        for page_name in page_files:
            data = zf.read(page_name)
            try:
                root = ET.fromstring(data)
            except ET.ParseError:
                continue
            # Find Glyphs elements in any namespace
            for elem in root.iter():
                tag = elem.tag.split("}")[-1]
                if tag == "Glyphs":
                    text = elem.get("UnicodeString", "")
                    if text.strip():
                        ast.children.append(Paragraph(text=text.strip()))

    if not ast.children:
        ast.children.append(Paragraph(text="[No text extracted from XPS]"))
    return ast
