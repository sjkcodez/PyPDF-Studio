"""AST → Markdown writer.

Emits:
  • Headings with #, ##, ###, …
  • Bold with **text**
  • Italic with _text_
  • Bold + italic with _**text**_
  • Lists, tables, code blocks, quotes, images
"""
from core.ast import (
    Document, Heading, Paragraph, BulletList, NumberedList,
    CodeBlock, BlockQuote, HorizontalRule, Table, Image, Run,
)


# ============================================================
# Inline formatting
# ============================================================
def _format_run(run: Run) -> str:
    """Wrap a single Run's text in the right Markdown emphasis markers."""
    text = run.text or ""
    if not text:
        return ""
    if run.bold and run.italic:
        return f"_**{text}**_"
    if run.bold:
        return f"**{text}**"
    if run.italic:
        return f"_{text}_"
    return text


def _format_inline(node, heading_mode: bool = False) -> str:
    """Return Markdown text for a Heading or Paragraph.

    If `heading_mode` is True and every run is bold (or every run is italic),
    the marker is dropped — the heading style already conveys emphasis, so
    "# **MAUNIDESK**" would be redundant.
    """
    runs = list(getattr(node, "runs", None) or [])
    if not runs:
        return getattr(node, "text", "") or ""

    if heading_mode:
        if all(r.bold for r in runs) and not any(r.italic for r in runs):
            runs = [Run(text=r.text, bold=False, italic=False) for r in runs]
        elif all(r.italic for r in runs) and not any(r.bold for r in runs):
            runs = [Run(text=r.text, bold=False, italic=False) for r in runs]

    # Merge adjacent runs with identical styling so we don't emit
    # "**hello****world**" for a single bold span.
    merged: list = []
    for r in runs:
        if merged and merged[-1].bold == r.bold and merged[-1].italic == r.italic:
            merged[-1] = Run(
                text=(merged[-1].text or "") + (r.text or ""),
                bold=r.bold,
                italic=r.italic,
            )
        else:
            merged.append(Run(text=r.text, bold=r.bold, italic=r.italic))

    return "".join(_format_run(r) for r in merged).strip()


# ============================================================
# Writer
# ============================================================
def write(ast: Document, output_path: str):
    lines = []

    for node in ast.children:

        if isinstance(node, Heading):
            body = _format_inline(node, heading_mode=True)
            if body:
                lines.append(f"{'#' * node.level} {body}\n")

        elif isinstance(node, Paragraph):
            body = _format_inline(node)
            if body:
                lines.append(f"{body}\n")

        elif isinstance(node, BulletList):
            for item in node.items:
                lines.append(f"- {item}")
            lines.append("")

        elif isinstance(node, NumberedList):
            for i, item in enumerate(node.items, 1):
                lines.append(f"{i}. {item}")
            lines.append("")

        elif isinstance(node, CodeBlock):
            lang = node.language or ""
            lines.append(f"```{lang}")
            lines.append(node.code)
            lines.append("```\n")

        elif isinstance(node, BlockQuote):
            lines.append(f"> {node.text}\n")

        elif isinstance(node, HorizontalRule):
            lines.append("---\n")

        elif isinstance(node, Table):
            if node.headers:
                lines.append("| " + " | ".join(node.headers) + " |")
                lines.append("|" + "|".join([" --- "] * len(node.headers)) + "|")
                for row in node.rows:
                    lines.append("| " + " | ".join(row) + " |")
                lines.append("")

        elif isinstance(node, Image):
            lines.append(f"![{node.alt}]({node.src})\n")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
