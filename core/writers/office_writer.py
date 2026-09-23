"""AST → legacy Office / RTF / ODF formats via LibreOffice.

Strategy: write AST to a modern format (docx / xlsx / pptx), then ask
LibreOffice headless to convert it to the final target extension.
"""
import tempfile
from pathlib import Path

from core import libreoffice
from core.ast import Document


DOC_TARGETS = {".doc", ".rtf", ".odt", ".ott", ".fodt", ".pub"}
XLS_TARGETS = {".xls", ".ods", ".ots", ".fods"}
PPT_TARGETS = {".ppt", ".odp", ".otp", ".fodp"}


def write(ast: Document, output_path: str):
    ext = Path(output_path).suffix.lower()

    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)

        if ext in DOC_TARGETS:
            from core.writers import docx_writer
            inter = tdp / "out.docx"
            docx_writer.write(ast, str(inter))
            target = ext.lstrip(".")
            converted = libreoffice.convert(inter, target, tdp)
            Path(converted).replace(output_path)
            return

        if ext in XLS_TARGETS:
            from core.writers import xlsx_writer
            inter = tdp / "out.xlsx"
            xlsx_writer.write(ast, str(inter))
            target = ext.lstrip(".")
            converted = libreoffice.convert(inter, target, tdp)
            Path(converted).replace(output_path)
            return

        if ext in PPT_TARGETS:
            from core.writers import pptx_writer
            inter = tdp / "out.pptx"
            pptx_writer.write(ast, str(inter))
            target = ext.lstrip(".")
            converted = libreoffice.convert(inter, target, tdp)
            Path(converted).replace(output_path)
            return

    raise ValueError(f"LibreOffice writer: unsupported extension '{ext}'")
