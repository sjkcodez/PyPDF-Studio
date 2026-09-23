"""JSON → AST reader.

JSON is exposed as a single CodeBlock so it flows through the same AST
pipeline as XML. This lets JSON → PDF, JSON → HTML, JSON → TXT, etc. work.
"""
import json
from pathlib import Path
from core.ast import Document, CodeBlock


def read(path: str) -> Document:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    pretty = json.dumps(data, indent=2, ensure_ascii=False)

    ast = Document()
    ast.metadata["title"] = Path(path).stem
    ast.children.append(CodeBlock(code=pretty, language="json"))
    return ast
