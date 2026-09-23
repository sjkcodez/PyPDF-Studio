"""Graceful handlers for formats that cannot be read in pure Python."""
from pathlib import Path


class UnsupportedFormatError(RuntimeError):
    pass


def _make_handler(ext, reason, alternative):
    def handler(path: str):
        raise UnsupportedFormatError(
            f"\n⚠ Cannot read '{ext}' files in pure Python.\n"
            f"   Reason: {reason}\n"
            f"   Suggested alternative: {alternative}\n"
        )
    return handler


indd_read = _make_handler(
    ".indd",
    "Adobe InDesign uses a closed, undocumented binary format.",
    "Export your document to IDML, PDF, or DOCX from InDesign first, then convert that file.",
)

dwg_read = _make_handler(
    ".dwg",
    "AutoCAD DWG is a proprietary binary format; no pure-Python library exists.",
    "Export to DXF from AutoCAD, or use the ODA File Converter, then convert the .dxf.",
)

mpp_read = _make_handler(
    ".mpp",
    "Microsoft Project MPP is proprietary and requires Java + the MPXJ library.",
    "Export to XML or CSV from Microsoft Project, then convert that file.",
)
