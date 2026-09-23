"""Legacy Office / RTF / ODF / Publisher → AST.

Strategy: convert the input to a modern format (.docx / .xlsx / .pptx)
using LibreOffice headless, then delegate to our direct reader.
"""
import tempfile
from pathlib import Path

from core import libreoffice
from core.ast import Document


DOC_EXTS = {".doc", ".dot", ".rtf", ".odt", ".ott", ".fodt", ".pub"}
XLS_EXTS = {".xls", ".xlt", ".ods", ".ots", ".fods"}
PPT_EXTS = {".ppt", ".pot", ".odp", ".otp", ".fodp"}


def read(path: str) -> Document:
    ext = Path(path).suffix.lower()

    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)

        if ext in DOC_EXTS:
            converted = libreoffice.convert(path, "docx", tdp)
            from core.readers import docx_reader
            return docx_reader.read(str(converted))

        if ext in XLS_EXTS:
            converted = libreoffice.convert(path, "xlsx", tdp)
            from core.readers import xlsx_reader
            return xlsx_reader.read(str(converted))

        if ext in PPT_EXTS:
            converted = libreoffice.convert(path, "pptx", tdp)
            from core.readers import pptx_reader
            return pptx_reader.read(str(converted))

    raise ValueError(f"LibreOffice reader: unsupported extension '{ext}'")
