"""AST → plain text writer."""
from core.ast import (
    Document, Heading, Paragraph, BulletList, NumberedList,
    CodeBlock, BlockQuote, HorizontalRule, Table,
)


def write(ast: Document, output_path: str):
    out = []
    if ast.metadata.get("title"):
        out.append(ast.metadata["title"])
        out.append("=" * len(ast.metadata["title"]))
        out.append("")

    for node in ast.children:
        if isinstance(node, Heading):
            out.append(node.text.upper() if node.level <= 2 else node.text)
            out.append("-" * len(node.text))
        elif isinstance(node, Paragraph):
            out.append(node.text)
            out.append("")
        elif isinstance(node, BulletList):
            out.extend(f"  • {item}" for item in node.items)
            out.append("")
        elif isinstance(node, NumberedList):
            out.extend(f"  {i}. {item}" for i, item in enumerate(node.items, 1))
            out.append("")
        elif isinstance(node, CodeBlock):
            out.append("    " + node.code.replace("\n", "\n    "))
            out.append("")
        elif isinstance(node, BlockQuote):
            out.append(f"  > {node.text}")
            out.append("")
        elif isinstance(node, HorizontalRule):
            out.append("-" * 40)
            out.append("")
        elif isinstance(node, Table):
            out.append(" | ".join(node.headers))
            out.append("-" * 40)
            for row in node.rows:
                out.append(" | ".join(row))
            out.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
