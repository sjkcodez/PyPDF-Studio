"""AST → XML writer.

If the AST contains a CodeBlock with language='xml', we write it verbatim
(this makes XML ↔ XML round-trip lossless). Otherwise, we build a simple
XML structure from the AST nodes.
"""
import xml.etree.ElementTree as ET
from xml.dom import minidom
from core.ast import (
    Document, Heading, Paragraph, BulletList, NumberedList,
    CodeBlock, BlockQuote, Table, HorizontalRule,
)


def _indent(elem, level=0):
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for child in elem:
            _indent(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = i
    if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = i


def write(ast: Document, output_path: str):
    # Round-trip fast path: if we have a language='xml' code block, restore it.
    for node in ast.children:
        if isinstance(node, CodeBlock) and node.language.lower() == "xml":
            content = node.code
            # Basic validation, then pretty-print
            try:
                elem = ET.fromstring(content)
                _indent(elem)
                pretty = ET.tostring(elem, encoding="unicode")
            except ET.ParseError:
                pretty = content  # write as-is
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(pretty)
            return

    # Generic: build a <document> XML from AST
    root = ET.Element("document")
    if ast.metadata.get("title"):
        title_el = ET.SubElement(root, "title")
        title_el.text = ast.metadata["title"]

    body = ET.SubElement(root, "body")

    for node in ast.children:
        if isinstance(node, Heading):
            el = ET.SubElement(body, "heading", {"level": str(node.level)})
            el.text = node.text
        elif isinstance(node, Paragraph):
            el = ET.SubElement(body, "paragraph")
            el.text = node.text
        elif isinstance(node, BulletList):
            el = ET.SubElement(body, "bullet-list")
            for item in node.items:
                li = ET.SubElement(el, "item")
                li.text = item
        elif isinstance(node, NumberedList):
            el = ET.SubElement(body, "numbered-list")
            for item in node.items:
                li = ET.SubElement(el, "item")
                li.text = item
        elif isinstance(node, CodeBlock):
            el = ET.SubElement(body, "code", {"language": node.language})
            el.text = node.code
        elif isinstance(node, BlockQuote):
            el = ET.SubElement(body, "blockquote")
            el.text = node.text
        elif isinstance(node, HorizontalRule):
            ET.SubElement(body, "hr")
        elif isinstance(node, Table):
            t = ET.SubElement(body, "table")
            hdr = ET.SubElement(t, "header")
            for h in node.headers:
                c = ET.SubElement(hdr, "cell")
                c.text = h
            for row in node.rows:
                r = ET.SubElement(t, "row")
                for cell in row:
                    c = ET.SubElement(r, "cell")
                    c.text = cell

    _indent(root)
    pretty = ET.tostring(root, encoding="unicode")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n' + pretty)
