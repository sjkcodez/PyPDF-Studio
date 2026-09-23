"""AST → Markdown writer."""
from core.ast import (
    Document, Heading, Paragraph, BulletList, NumberedList,
    CodeBlock, BlockQuote, HorizontalRule, Table, Image,
)


def write(ast: Document, output_path: str):
    lines = []
    if ast.metadata.get("title"):
        lines.append(f"# {ast.metadata['title']}\n")

    for node in ast.children:
        if isinstance(node, Heading):
            lines.append(f"{'#' * node.level} {node.text}\n")
        elif isinstance(node, Paragraph):
            lines.append(f"{node.text}\n")
        elif isinstance(node, BulletList):
            for item in node.items:
                lines.append(f"- {item}")
            lines.append("")
        elif isinstance(node, NumberedList):
            for i, item in enumerate(node.items, 1):
                lines.append(f"{i}. {item}")
            lines.append("")
        elif isinstance(node, CodeBlock):
            lines.append(f"```{node.language}")
            lines.append(node.code)
            lines.append("```\n")
        elif isinstance(node, BlockQuote):
            lines.append(f"> {node.text}\n")
        elif isinstance(node, HorizontalRule):
            lines.append("---\n")
        elif isinstance(node, Table):
            lines.append("| " + " | ".join(node.headers) + " |")
            lines.append("|" + "|".join([" --- "] * len(node.headers)) + "|")
            for row in node.rows:
                lines.append("| " + " | ".join(row) + " |")
            lines.append("")
        elif isinstance(node, Image):
            lines.append(f"![{node.alt}]({node.src})\n")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
