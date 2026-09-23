"""Writers: AST → format."""
from . import markdown_writer
from . import html_writer
from . import docx_writer
from . import pdf_writer
from . import txt_writer
from . import xml_writer
from . import dbf_writer
from . import dxf_writer
from . import xlsx_writer
from . import pptx_writer
from . import csv_writer
from . import office_writer


WRITERS = {
    # ---------- Direct writers ----------
    "md":       markdown_writer.write,
    "markdown": markdown_writer.write,
    "html":     html_writer.write,
    "htm":      html_writer.write,
    "docx":     docx_writer.write,
    "pdf":      pdf_writer.write,
    "txt":      txt_writer.write,
    "text":     txt_writer.write,
    "xml":      xml_writer.write,
    "dbf":      dbf_writer.write,
    "dxf":      dxf_writer.write,
    "xlsx":     xlsx_writer.write,
    "xlsm":     xlsx_writer.write,
    "pptx":     pptx_writer.write,
    "csv":      csv_writer.write,
    "tsv":      csv_writer.write,

    # ---------- Via LibreOffice ----------
    "doc":      office_writer.write,
    "rtf":      office_writer.write,
    "odt":      office_writer.write,
    "ott":      office_writer.write,
    "fodt":     office_writer.write,
    "pub":      office_writer.write,
    "xls":      office_writer.write,
    "ods":      office_writer.write,
    "ots":      office_writer.write,
    "fods":     office_writer.write,
    "ppt":      office_writer.write,
    "odp":      office_writer.write,
    "otp":      office_writer.write,
    "fodp":     office_writer.write,
}


def get_writer(fmt: str):
    return WRITERS.get(fmt.lower())
