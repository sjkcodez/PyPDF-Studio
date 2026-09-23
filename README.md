# PyPDF Studio v5.0

A universal PDF toolkit with **25+ tools**, available as both a **terminal CLI** and a **modern web GUI**. Built in Python with a Pandoc-style `Reader → AST → Writer` architecture that enables any-to-any document conversion.

---

## 🚀 Features

### 🖥️ Two Interfaces, One Engine
- **CLI** — a menu-driven terminal app for power users
- **Web GUI** — a local Flask app with drag & drop, search, category filters, and progress indicators

### 📂 Organize
- Merge PDFs
- Split PDF (into single pages, ZIP output)
- Extract Pages
- Remove Pages
- Rearrange Pages

### ⚡ Optimize
- Compress PDF
- Flatten PDF (bake annotations into the page)

### 🔄 Convert TO PDF
- Images → PDF (JPG, PNG, WebP, BMP, TIFF)
- Webpage (URL) → PDF
- Word, PowerPoint, Excel, ODT, RTF → PDF (via LibreOffice)

### 🔄 Convert FROM PDF
- PDF → Word (.docx)
- PDF → Images (PNG / JPG, ZIP output)
- PDF → Text (.txt)
- Extract embedded images

### ✏️ Edit
- Rotate Pages (90° / 180° / 270°)
- Crop PDF (trim margins in points)
- Overlay two PDFs
- Add Page Numbers

### 🔐 Security
- Protect PDF (add password)
- Unlock PDF (remove password)
- Sign PDF (image signature)
- Flatten PDF

### 💧 Watermark
- Text Watermark
- Image Watermark

### 🔎 OCR
- Searchable PDFs via **Tesseract**

### 📊 Compare
- Compare two PDFs and report differences

### 🌐 Universal Converter *(Pandoc-style)*
Any-to-any conversion between:
`.md` · `.html` · `.docx` · `.pdf` · `.txt` · `.xml` · `.dbf` · `.dxf`

Plus **read-only extraction** from:
`.ai` · `.psd` · `.vsdx` · `.xps`

> Formats like `.indd`, `.dwg`, and `.mpp` are **not supported** — they are proprietary and require the original commercial applications. PyPDF Studio will explain exactly why and suggest an alternative when you try.

---

## 🏗️ Architecture

PyPDF Studio uses a **hub-and-spoke** conversion model:

```
Input file → [READER] → Universal AST → [WRITER] → Output file
```

- Every **reader** converts its input format into a common **AST** (Abstract Syntax Tree) of nodes: `Heading`, `Paragraph`, `List`, `Table`, `CodeBlock`, etc.
- Every **writer** renders the AST into its target format.
- This means **M readers + N writers** produce **M × N conversions** — no pairwise code needed.

Adding a new format requires only **one new reader or writer**, and it instantly interoperates with all existing formats.

---

## 📁 Project Structure

```
PyPDF-Studio/
│
├── pypdf_studio.py              # CLI launcher
├── app.py                       # Web GUI (Flask) launcher
├── handlers.py                  # Non-interactive handlers for the web GUI
├── check_setup.py               # Dependency diagnostic tool
├── requirements.txt
├── README.md
├── LICENSE
│
├── core/
│   ├── __init__.py
│   ├── utils.py
│   ├── ast.py                   # Universal Document AST
│   ├── converter.py             # Reader → AST → Writer engine
│   ├── convert_to_pdf.py
│   ├── convert_from_pdf.py
│   ├── merge_split.py
│   ├── security.py
│   ├── edit.py
│   ├── ocr.py
│   ├── watermark.py
│   ├── compare.py
│   ├── utilities.py
│   │
│   ├── readers/                 # Format → AST
│   │   ├── __init__.py
│   │   ├── markdown_reader.py
│   │   ├── html_reader.py
│   │   ├── docx_reader.py
│   │   ├── txt_reader.py
│   │   ├── xml_reader.py
│   │   ├── dbf_reader.py
│   │   ├── dxf_reader.py
│   │   ├── pdf_reader.py
│   │   ├── ai_reader.py
│   │   ├── psd_reader.py
│   │   ├── vsdx_reader.py
│   │   ├── xps_reader.py
│   │   └── unsupported_reader.py
│   │
│   └── writers/                 # AST → Format
│       ├── __init__.py
│       ├── markdown_writer.py
│       ├── html_writer.py
│       ├── docx_writer.py
│       ├── pdf_writer.py
│       ├── txt_writer.py
│       ├── xml_writer.py
│       ├── dbf_writer.py
│       └── dxf_writer.py
│
├── templates/                   # Web GUI pages
│   ├── index.html               # Dashboard
│   ├── tool.html                # Individual tool page
│   └── status.html              # System health check
│
├── static/                      # Web GUI assets
│   ├── style.css
│   ├── dashboard.js
│   └── tool.js
│
├── uploads/                     # Temporary uploads (auto-cleaned)
├── output/                      # All generated files
├── temp/                        # Working directory
├── assets/
└── logs/
    └── pypdf_studio.log
```

---

## 🛠️ Installation

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Install system binaries (one-time)

These are **NOT** pip packages — they are system tools that must be installed separately.

#### Ubuntu / Debian / Kali

```bash
sudo apt update
sudo apt install -y \
    tesseract-ocr tesseract-ocr-swa \
    libreoffice \
    ghostscript
```

#### Fedora

```bash
sudo dnf install -y \
    tesseract tesseract-langpack-swa \
    libreoffice \
    ghostscript
```

#### macOS

```bash
brew install tesseract tesseract-lang ghostscript
brew install --cask libreoffice
```

#### Windows

| Tool | Source |
|------|--------|
| Tesseract | https://github.com/UB-Mannheim/tesseract/wiki |
| LibreOffice | https://www.libreoffice.org/download/ |
| Ghostscript | https://www.ghostscript.com/download/gsdnld.html |

> **Optional:** `ffmpeg` is **not required** by any tool in this project. You can skip it.

### 3. Verify your setup

```bash
python check_setup.py
```

This prints a clean report of installed Python modules, external binaries, and any missing pieces with copy-paste fix commands.

---

## ▶️ Run

### Option 1 — Web GUI (recommended for most users)

```bash
python app.py
```

Then open:

| URL | Purpose |
|-----|---------|
| `http://127.0.0.1:5000` | **Dashboard** — all tools in a searchable, filterable grid |
| `http://127.0.0.1:5000/status` | **Health check** — shows what's installed |

The GUI runs **entirely on your machine** — no file ever leaves your computer.

### Option 2 — CLI (classic terminal interface)

```bash
python pypdf_studio.py
```

You'll see:

```
 Main Menu
--------------------------------------------------------------
  1. Convert TO PDF       (Word, Excel, PPT, Images, ...)
  2. Convert FROM PDF     (Word, Excel, PPT, Images, ...)
  3. Merge & Split        (Merge, Split, Extract, ...)
  4. Edit PDF             (Rotate, Crop, Overlay, ...)
  5. Watermark            (Text, Image)
  6. Security             (Protect, Unlock, Sign, Flatten)
  7. OCR                  (Searchable PDF)
  8. Compare PDFs
  9. Utilities            (Compress, Job Application)
 10. Universal Converter  (Any → Any: MD, HTML, DOCX, PDF, TXT)
  0. Exit
--------------------------------------------------------------
```

---

## 🌐 Web GUI in Detail

### Dashboard

- **Sticky dark-navy header** with a pill-shaped **search box**
- **Category filter chips** — All / Organize / Optimize / Convert / Edit / Security / Watermark / OCR / Compare / Universal
- **Tool cards** with colored category icons, name, description, and category tag
- Hover lift and soft shadow for a clean, office-friendly feel

### Tool Page (4-stage flow)

1. **Upload** — drag & drop or browse. Multi-file tools (Merge, Overlay, Sign) tell you exactly what to upload.
2. **Options** — only shown for tools that need them (password, page range, angle, URL, etc.).
3. **Progress** — animated bar.
4. **Result** — download button + "Convert another" to reset.

### Health Check (`/status`)

Shows a live report of:

- All external binaries (Tesseract, LibreOffice, Ghostscript)
- Every Python module
- All registered readers and writers

Use this page whenever a tool misbehaves — it tells you exactly what's missing.

---

## 📥 Usage Examples

### Convert a Word file to PDF (Web)

1. Open `http://127.0.0.1:5000`
2. Click **Convert TO PDF → Word to PDF** *(coming soon via GUI; use CLI for now)*
3. Or simply use the **Universal Converter** card

### Convert Markdown → DOCX (Web)

1. Open `http://127.0.0.1:5000/tool/universal`
2. Drag your `.md` file into the dropzone
3. Choose **DOCX** as the output format
4. Click **Continue → Convert now**
5. Download the result

### Merge 3 PDFs (CLI)

```
Choice: 3 → 1
PDF: file1.pdf
PDF: file2.pdf
PDF: file3.pdf
PDF: (blank line)
Saved: output/merged_YYYYMMDD.pdf
```

### OCR a scanned PDF (Web)

1. Ensure `tesseract-ocr` is installed (`python check_setup.py` will confirm)
2. Open `http://127.0.0.1:5000/tool/ocr`
3. Upload the scanned PDF
4. Choose language (eng / swa / fra / deu / spa / ita)
5. Convert → download searchable PDF

---

## 📂 Output Location

All generated files are saved to `output/`:

```
output/
├── a1b2c3d4_merged.pdf
├── e5f6g7h8_converted.docx
├── i9j0k1l2_ocr.pdf
└── ...
```

Logs are written to `logs/pypdf_studio.log`.

---

## 📋 Supported Formats

### Readable (input)

| Category | Extensions |
|----------|-----------|
| Fully supported | `.md` `.markdown` `.html` `.htm` `.docx` `.txt` `.xml` `.dbf` `.dxf` |
| Read-only (text extraction) | `.pdf` `.ai` `.psd` `.vsdx` `.xps` |
| Not supported | `.indd` `.dwg` `.mpp` |

### Writable (output)

`.md` `.html` `.docx` `.pdf` `.txt` `.xml` `.dbf` `.dxf`

---

## 🧰 Technology Stack

| Category | Library |
|----------|---------|
| PDF core | `pypdf`, `PyMuPDF (fitz)` |
| PDF → DOCX | `pdf2docx` |
| Image handling | `Pillow` |
| Office | `python-docx`, `openpyxl`, `python-pptx` |
| PDF generation | `reportlab` |
| HTML → PDF | `weasyprint`, `xhtml2pdf` (fallback) |
| EPUB | `ebooklib`, `markdown` |
| OCR | `pytesseract` |
| Web parsing | `requests`, `beautifulsoup4`, `lxml` |
| CAD | `ezdxf` |
| Database | `dbfread`, `dbf` |
| Photoshop | `psd-tools` |
| Visio | `vsdx` |
| Web framework | `Flask` |

---

## ❗ Troubleshooting

### `tesseract` not found

Install it:

```bash
sudo apt install -y tesseract-ocr tesseract-ocr-swa    # Linux
brew install tesseract                                  # macOS
```

### Warning: `The 'fitz' API is deprecated`

This is a **deprecation warning**, not an error — but easy to silence. In every file that starts with `import fitz`, replace it with:

```python
try:
    import pymupdf as fitz
except ImportError:
    import fitz
```

One-liner for Linux / macOS:

```bash
grep -rl "^import fitz$" --include="*.py" . | while read f; do
  sed -i 's/^import fitz$/try:\n    import pymupdf as fitz\nexcept ImportError:\n    import fitz/' "$f"
done
```

### LibreOffice not found (Office → PDF fails)

Install LibreOffice. PyPDF Studio uses it as a headless conversion engine for `.docx`, `.xlsx`, `.pptx`, `.odt`, `.rtf`.

### WeasyPrint fails on Windows

WeasyPrint needs GTK libraries. PyPDF Studio automatically **falls back** to `xhtml2pdf` if WeasyPrint fails, so webpage → PDF still works.

### "No reader for '.xyz'" in the Universal Converter

Open `http://127.0.0.1:5000/status` and check the **Readers** list. If the extension isn't there, that format isn't supported yet. `.indd`, `.dwg`, and `.mpp` fall into this category permanently — they require proprietary software.

### Port 5000 already in use

Edit `app.py` and change the port at the bottom:

```python
app.run(host="127.0.0.1", port=5001)   # or any free port
```

---

## 🔒 Privacy

- The web GUI listens only on **`127.0.0.1`** — it is not reachable from other machines.
- No telemetry, no analytics, no external calls (except when you explicitly use the **Webpage → PDF** tool, which fetches the URL you provide).
- Uploaded files are **deleted** immediately after each conversion — only the output stays in `output/`.

---

## 🗺️ Roadmap

- PDF → PowerPoint, PDF → Excel
- Job Application PDF builder in the web GUI
- Batch mode (upload multiple files, convert all at once)
- Conversion history with re-download
- Light / dark theme toggle
- Playlist / multi-URL downloading for Webpage → PDF
- Additional writers: PPTX, XLSX, EPUB, LaTeX

---

## 🤝 Contributing

1. Fork the repository
2. Create a branch: `git checkout -b feature/new-tool`
3. Commit your changes: `git commit -m "Add new tool"`
4. Push: `git push origin feature/new-tool`
5. Open a Pull Request

---

## 📜 License

MIT License. See `LICENSE`.

---

## 👨‍💻 Built With

- Python 3.10+
- Flask
- PyMuPDF, pypdf, reportlab, WeasyPrint
- Tesseract OCR, LibreOffice, Ghostscript

---

*PyPDF Studio runs locally. Your documents never leave your computer.*
