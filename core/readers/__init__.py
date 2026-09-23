"""Readers: format → AST."""
from . import markdown_reader
from . import html_reader
from . import docx_reader
from . import txt_reader
from . import xml_reader
from . import json_reader
from . import dbf_reader
from . import dxf_reader
from . import ai_reader
from . import psd_reader
from . import vsdx_reader
from . import xps_reader
from . import pdf_reader
from . import xlsx_reader
from . import pptx_reader
from . import csv_reader
from . import office_reader
from .unsupported_reader import indd_read, dwg_read, mpp_read


READERS = {
    # ---------- Direct (full content round-trip) ----------
    ".md":       markdown_reader.read,
    ".markdown": markdown_reader.read,
    ".html":     html_reader.read,
    ".htm":      html_reader.read,
    ".docx":     docx_reader.read,
    ".txt":      txt_reader.read,
    ".xml":      xml_reader.read,
    ".json":     json_reader.read,
    ".dbf":      dbf_reader.read,
    ".dxf":      dxf_reader.read,
    ".xlsx":     xlsx_reader.read,
    ".xlsm":     xlsx_reader.read,
    ".pptx":     pptx_reader.read,
    ".csv":      csv_reader.read,
    ".tsv":      csv_reader.read,

    # ---------- Read-only (extraction) ----------
    ".pdf":      pdf_reader.read,
    ".ai":       ai_reader.read,
    ".psd":      psd_reader.read,
    ".vsdx":     vsdx_reader.read,
    ".xps":      xps_reader.read,

    # ---------- Via LibreOffice (legacy Office, RTF, ODF, Publisher) ----------
    ".doc":      office_reader.read,
    ".dot":      office_reader.read,
    ".rtf":      office_reader.read,
    ".odt":      office_reader.read,
    ".ott":      office_reader.read,
    ".fodt":     office_reader.read,
    ".pub":      office_reader.read,
    ".xls":      office_reader.read,
    ".xlt":      office_reader.read,
    ".ods":      office_reader.read,
    ".ots":      office_reader.read,
    ".fods":     office_reader.read,
    ".ppt":      office_reader.read,
    ".pot":      office_reader.read,
    ".odp":      office_reader.read,
    ".otp":      office_reader.read,
    ".fodp":     office_reader.read,

    # ---------- Explicitly unsupported ----------
    ".indd":     indd_read,
    ".dwg":      dwg_read,
    ".mpp":      mpp_read,
}


def get_reader(extension: str):
    return READERS.get(extension.lower())
