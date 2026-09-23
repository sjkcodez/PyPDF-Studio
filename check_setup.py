"""Quick check for all PyPDF Studio dependencies + fix hints."""
import sys, shutil, importlib

MODULES = [
    "pypdf", "fitz", "docx", "pptx", "openpyxl",
    "reportlab", "weasyprint", "xhtml2pdf", "markdown",
    "ebooklib", "PIL", "bs4", "lxml",
    "pytesseract", "ezdxf", "dbfread", "dbf",
    "psd_tools", "vsdx", "pdf2docx",
    "flask", "werkzeug", "requests",
]

BINARIES = {
    "tesseract":   "sudo apt install -y tesseract-ocr tesseract-ocr-swa",
    "soffice":     "sudo apt install -y libreoffice",
    "libreoffice": "sudo apt install -y libreoffice",
    "gs":          "sudo apt install -y ghostscript",
}

print("=" * 62)
print("PyPDF Studio — Setup check")
print("=" * 62)

print("\n📦 Python modules:")
missing_modules = []
for m in MODULES:
    try:
        importlib.import_module(m)
        print(f"  ✅ {m}")
    except Exception as e:
        print(f"  ❌ {m}  ({e.__class__.__name__})")
        missing_modules.append(m)

print("\n🔧 External binaries:")
missing_binaries = []
for b, fix in BINARIES.items():
    path = shutil.which(b)
    if path:
        print(f"  ✅ {b:<12} → {path}")
    else:
        # Avoid duplicate hints for soffice/libreoffice
        if b == "libreoffice" and shutil.which("soffice"):
            continue
        print(f"  ❌ {b:<12} (install: {fix})")
        missing_binaries.append((b, fix))

print("\n" + "=" * 62)
if missing_modules:
    print("Install missing Python packages with:")
    print(f"  pip install {' '.join(missing_modules)}")
else:
    print("✅ All Python modules are installed.")

if missing_binaries:
    print("\nInstall missing system binaries with:")
    seen = set()
    for b, fix in missing_binaries:
        if fix not in seen:
            print(f"  {fix}")
            seen.add(fix)
else:
    print("✅ All required system binaries are installed.")

print("=" * 62)
