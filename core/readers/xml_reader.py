"""XML → AST reader (fully reversible via CodeBlock)."""
from pathlib import Path
import xml.etree.ElementTree as ET
from core.ast import Document, CodeBlock


def _pretty(elem, indent=0):
    """Recursive pretty-printer for an ElementTree element."""
    pad = "  " * indent
    tag = elem.tag
    attrs = "".join(f' {k}="{v}"' for k, v in elem.attrib.items())
    text = (elem.text or "").strip()
    children = list(elem)

    if not children and not text:
        return [f"{pad}<{tag}{attrs}/>"]

    if not children:
        return [f"{pad}<{tag}{attrs}>{text}</{tag}>"]

    lines = [f"{pad}<{tag}{attrs}>"]
    if text:
        lines.append(f"{pad}  {text}")
    for child in children:
        lines.extend(_pretty(child, indent + 1))
    lines.append(f"{pad}</{tag}>")
    return lines


def read(path: str) -> Document:
    tree = ET.parse(path)
    root = tree.getroot()
    xml_text = "\n".join(_pretty(root))

    ast = Document()
    ast.metadata["title"] = Path(path).stem
    # Store the entire XML as a language-tagged code block.
    # This preserves it perfectly for round-trip.
    ast.children.append(CodeBlock(code=xml_text, language="xml"))
    return ast
