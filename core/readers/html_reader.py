"""HTML → AST reader."""
from pathlib import Path
from bs4 import BeautifulSoup
from core.ast import (
    Document, Heading, Paragraph, BulletList,
    NumberedList, CodeBlock, BlockQuote, HorizontalRule, Table, Image,
)


def read(path: str) -> Document:
    html = Path(path).read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    ast = Document()

    if soup.title and soup.title.string:
        ast.metadata["title"] = soup.title.string.strip()

    body = soup.body or soup

    for el in body.find_all(recursive=False):
        name = el.name.lower()

        if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            ast.children.append(Heading(level=int(name[1]), text=el.get_text(strip=True)))

        elif name == "p":
            text = el.get_text(" ", strip=True)
            if text:
                ast.children.append(Paragraph(text=text))

        elif name == "ul":
            items = [li.get_text(" ", strip=True) for li in el.find_all("li", recursive=False)]
            ast.children.append(BulletList(items=items))

        elif name == "ol":
            items = [li.get_text(" ", strip=True) for li in el.find_all("li", recursive=False)]
            ast.children.append(NumberedList(items=items))

        elif name == "pre":
            code_el = el.find("code")
            code = code_el.get_text() if code_el else el.get_text()
            lang = ""
            if code_el and code_el.get("class"):
                for c in code_el["class"]:
                    if c.startswith("language-"):
                        lang = c.replace("language-", "")
            ast.children.append(CodeBlock(code=code.rstrip("\n"), language=lang))

        elif name == "blockquote":
            ast.children.append(BlockQuote(text=el.get_text(" ", strip=True)))

        elif name == "hr":
            ast.children.append(HorizontalRule())

        elif name == "table":
            headers = []
            thead = el.find("thead")
            if thead:
                headers = [th.get_text(strip=True) for th in thead.find_all("th")]
            rows = []
            for tr in el.find_all("tr"):
                cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
                if cells and cells != headers:
                    rows.append(cells)
            if not headers and rows:
                headers = rows.pop(0)
            ast.children.append(Table(headers=headers, rows=rows))

        elif name == "img":
            ast.children.append(Image(src=el.get("src", ""), alt=el.get("alt", "")))

    return ast
