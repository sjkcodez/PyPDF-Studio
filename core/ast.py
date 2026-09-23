"""
Universal Document AST for PyPDF Studio.

Every reader converts its input format into this AST.
Every writer renders this AST into its output format.
This is what enables M×N (any-to-any) conversions with only M readers + N writers.
"""
from dataclasses import dataclass, field
from typing import List, Optional


# ------------------------------------------------------------------
# Base
# ------------------------------------------------------------------
class Node:
    """Base class for all AST nodes."""
    pass


# ------------------------------------------------------------------
# Block-level nodes
# ------------------------------------------------------------------
@dataclass
class Document(Node):
    """Root node. Holds metadata + ordered list of children."""
    metadata: dict = field(default_factory=dict)
    children: List[Node] = field(default_factory=list)


@dataclass
class Heading(Node):
    level: int
    text: str


@dataclass
class Paragraph(Node):
    text: str


@dataclass
class BulletList(Node):
    items: List[str]


@dataclass
class NumberedList(Node):
    items: List[str]


@dataclass
class CodeBlock(Node):
    code: str
    language: str = ""


@dataclass
class BlockQuote(Node):
    text: str


@dataclass
class HorizontalRule(Node):
    pass


@dataclass
class Table(Node):
    headers: List[str]
    rows: List[List[str]]


@dataclass
class Image(Node):
    src: str
    alt: str = ""


@dataclass
class Link(Node):
    text: str
    url: str


# ------------------------------------------------------------------
# Helper: title from metadata
# ------------------------------------------------------------------
def get_title(ast: Document, fallback: str = "Untitled") -> str:
    return ast.metadata.get("title") or fallback
