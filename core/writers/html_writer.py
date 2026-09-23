"""AST → HTML writer."""
import html
from core.ast import (
    Document, Heading, Paragraph, BulletList, NumberedList,
    CodeBlock, BlockQuote, HorizontalRule, Table, Image,
)


def write(ast: Document, output_path: str):
    title = ast.metadata.get("title", "Document")
    parts = [
        "<!DOCTYPE html>",
        "<html><head><meta charset='utf-8'>",
        f"<title>{html.escape(title)}</title>",
        "<style>body{font-family:system-ui,sans-serif;max-width:820px;margin:2rem auto;line-height:1.6;padding:0 1rem}"
        "table{border-collapse:collapse}th,td{border:1px solid #ccc;padding:6px 10px}"
        "pre{background:#f4f4f4;padding:12px;border-radius:6px;overflow-x:auto}"
        "blockquote{border-left:4px solid #ccc;margin:1em 0;padding-left:1em;color:#555}</style>",
        "</head><body>",
    ]

    if title and title != "Document":
        parts.append(f"<h1>{html.escape(title)}</h1>")

    for node in ast.children:
        if isinstance(node, Heading):
            parts.append(f"<h{node.level}>{html.escape(node.text)}</h{node.level}>")
        elif isinstance(node, Paragraph):
            parts.append(f"<p>{html.escape(node.text)}</p>")
        elif isinstance(node, BulletList):
            parts.append("<ul>")
            for item in node.items:
                parts.append(f"<li>{html.escape(item)}</li>")
            parts.append("</ul>")
        elif isinstance(node, NumberedList):
            parts.append("<ol>")
            for item in node.items:
                parts.append(f"<li>{html.escape(item)}</li>")
            parts.append("</ol>")
        elif isinstance(node, CodeBlock):
            lang_cls = f" class='language-{node.language}'" if node.language else ""
            parts.append(f"<pre><code{lang_cls}>{html.escape(node.code)}</code></pre>")
        elif isinstance(node, BlockQuote):
            parts.append(f"<blockquote>{html.escape(node.text)}</blockquote>")
        elif isinstance(node, HorizontalRule):
            parts.append("<hr>")
        elif isinstance(node, Table):
            parts.append("<table>")
            parts.append("<thead><tr>" + "".join(f"<th>{html.escape(h)}</th>" for h in node.headers) + "</tr></thead>")
            parts.append("<tbody>")
            for row in node.rows:
                parts.append("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in row) + "</tr>")
            parts.append("</tbody></table>")
        elif isinstance(node, Image):
            parts.append(f"<img src='{html.escape(node.src)}' alt='{html.escape(node.alt)}'>")

    parts.append("</body></html>")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
