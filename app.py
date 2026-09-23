#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PyPDF Studio — Web GUI server with preview support and auto-cleanup.

Auto-cleanup:
    A background daemon thread wakes every 30 minutes and deletes:
      • files in `output/`   older than 30 minutes
      • files in `uploads/`  older than 30 minutes
    Old preview sessions held in memory are also removed.

Authentication:
    If the PYPDF_USER and PYPDF_PASS environment variables are set, the
    entire app is protected by HTTP Basic Authentication. If they are
    unset, authentication is disabled (convenient for local development,
    dangerous in public hosting — always set them on Render).

Works both locally (Waitress) and in production (Gunicorn on Render).
"""
import io
import os
import time
import uuid
import shutil
import threading
import traceback
from functools import wraps
from pathlib import Path

from flask import (
    Flask, Response, render_template, request, send_file, jsonify,
)

from handlers import TOOLS, HANDLERS, get_tool
from core.utils import OUTPUT_DIR
from core.readers import READERS
from core.writers import WRITERS


# ============================================================
# Configuration
# ============================================================
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

OUTPUT_DIR.mkdir(exist_ok=True)

MAX_MB = 100
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_MB * 1024 * 1024


# ============================================================
# Basic Authentication
# ============================================================
# Values are read from the environment.
# On Render: set PYPDF_USER and PYPDF_PASS in the Environment tab.
# Locally:   export PYPDF_USER=... ; export PYPDF_PASS=...
#
# If either is empty, authentication is DISABLED. That's fine for
# local use but you should always set them on the public server.
AUTH_USER = os.environ.get("PYPDF_USER", "").strip()
AUTH_PASS = os.environ.get("PYPDF_PASS", "").strip()
AUTH_ENABLED = bool(AUTH_USER and AUTH_PASS)


def _check_auth(username: str, password: str) -> bool:
    return username == AUTH_USER and password == AUTH_PASS


def _authenticate() -> Response:
    return Response(
        "Authentication required to use PyPDF Studio.",
        401,
        {"WWW-Authenticate": 'Basic realm="PyPDF Studio"'},
    )


def requires_auth(f):
    """Decorator that enforces Basic Auth when AUTH_ENABLED is True."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not AUTH_ENABLED:
            return f(*args, **kwargs)
        auth = request.authorization
        if not auth or not _check_auth(auth.username, auth.password):
            return _authenticate()
        return f(*args, **kwargs)
    return wrapper


# ============================================================
# Cleanup settings
# ============================================================
CLEANUP_INTERVAL_SECONDS = 30 * 60    # run every 30 minutes
CLEANUP_MAX_AGE_SECONDS  = 30 * 60    # delete files older than 30 minutes
PREVIEW_MAX_AGE_SECONDS  = 60 * 60    # preview sessions expire after 1 hour

# ---- For fast local testing, uncomment the next two lines ----
# CLEANUP_INTERVAL_SECONDS = 30
# CLEANUP_MAX_AGE_SECONDS  = 30

PREVIEW_SESSIONS = {}
PREVIEW_LOCK = threading.Lock()


# ============================================================
# Auto-cleanup thread
# ============================================================
def _delete_old_files(folder: Path, max_age_seconds: int):
    """Delete files (recursively) in `folder` older than max_age_seconds."""
    if not folder.exists():
        return 0, 0

    now = time.time()
    deleted_files = 0
    deleted_dirs  = 0

    for path in folder.rglob("*"):
        try:
            if path.is_file():
                age = now - path.stat().st_mtime
                if age > max_age_seconds:
                    path.unlink()
                    deleted_files += 1
        except Exception:
            continue

    for path in sorted(folder.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        try:
            if path.is_dir() and not any(path.iterdir()):
                path.rmdir()
                deleted_dirs += 1
        except Exception:
            continue

    return deleted_files, deleted_dirs


def _cleanup_preview_sessions():
    """Drop expired in-memory preview sessions and their folders."""
    now = time.time()
    with PREVIEW_LOCK:
        expired = [
            sid for sid, info in PREVIEW_SESSIONS.items()
            if now - info["created"] > PREVIEW_MAX_AGE_SECONDS
        ]
        for sid in expired:
            info = PREVIEW_SESSIONS.pop(sid, None)
            if info:
                shutil.rmtree(info["dir"], ignore_errors=True)
    return len(expired)


def cleanup_loop():
    """Background thread: run cleanup every 30 minutes."""
    time.sleep(5)

    while True:
        try:
            o_files, o_dirs = _delete_old_files(OUTPUT_DIR, CLEANUP_MAX_AGE_SECONDS)
            u_files, u_dirs = _delete_old_files(UPLOAD_DIR, CLEANUP_MAX_AGE_SECONDS)
            previews = _cleanup_preview_sessions()

            if o_files or u_files or previews:
                print(
                    f"[cleanup] removed output={o_files} file(s), "
                    f"uploads={u_files} file(s), "
                    f"preview_sessions={previews}",
                    flush=True,
                )
        except Exception:
            traceback.print_exc()

        time.sleep(CLEANUP_INTERVAL_SECONDS)


def start_cleanup_thread():
    t = threading.Thread(target=cleanup_loop, name="cleanup", daemon=True)
    t.start()
    return t


# Start the cleanup thread at import time so it runs under Gunicorn too.
# Gunicorn does NOT execute the `if __name__ == "__main__":` block,
# so this module-level call is the only way the cleanup thread starts
# in production.
start_cleanup_thread()


# ============================================================
# Diagnostics
# ============================================================
def _check_binaries():
    return {
        "tesseract":   shutil.which("tesseract") is not None,
        "ffmpeg":      shutil.which("ffmpeg") is not None,
        "libreoffice": (shutil.which("soffice") or shutil.which("libreoffice")) is not None,
        "ghostscript": (shutil.which("gs") or shutil.which("gswin64c")) is not None,
    }


def _check_python_modules():
    mods = ["pypdf", "fitz", "docx", "pptx", "openpyxl", "reportlab",
            "weasyprint", "xhtml2pdf", "markdown", "ebooklib", "PIL",
            "bs4", "lxml", "pytesseract", "ezdxf", "dbfread", "dbf",
            "psd_tools", "vsdx", "pdf2docx"]
    out = {}
    for m in mods:
        try:
            __import__(m)
            out[m] = True
        except Exception:
            out[m] = False
    return out


# ============================================================
# Health check — intentionally NOT protected by auth
# ============================================================
@app.route("/health")
def health():
    """Lightweight status endpoint for Render and uptime monitors.

    Kept unauthenticated so Render can verify the app is alive even
    when Basic Auth is enabled.
    """
    return jsonify({"status": "ok", "service": "pypdf-studio"}), 200


# ============================================================
# Pages
# ============================================================
@app.route("/")
@requires_auth
def index():
    categories, seen = [], set()
    for t in TOOLS:
        if t["category"] not in seen:
            categories.append(t["category"])
            seen.add(t["category"])
    return render_template("index.html", tools=TOOLS, categories=categories)


@app.route("/tool/<tool_id>")
@requires_auth
def tool_page(tool_id):
    tool = get_tool(tool_id)
    if not tool:
        return "Tool not found", 404
    return render_template("tool.html", tool=tool)


@app.route("/status")
@requires_auth
def status_page():
    return render_template("status.html",
                           binaries=_check_binaries(),
                           modules=_check_python_modules(),
                           readers=sorted(READERS.keys()),
                           writers=sorted(set(WRITERS.keys())))


# ============================================================
# Preview endpoints
# ============================================================
@app.route("/api/preview/start/<tool_id>", methods=["POST"])
@requires_auth
def api_preview_start(tool_id):
    tool = get_tool(tool_id)
    if not tool or not tool.get("preview"):
        return jsonify({"error": "Preview not available for this tool."}), 400

    files = [f for f in request.files.getlist("files") if f and f.filename]
    if not files:
        return jsonify({"error": "No file provided."}), 400

    pdf_file = None
    second_file = None
    for f in files:
        if pdf_file is None and Path(f.filename).suffix.lower() == ".pdf":
            pdf_file = f
        elif second_file is None:
            second_file = f

    if pdf_file is None:
        return jsonify({"error": "Preview requires a PDF file."}), 400

    _cleanup_preview_sessions()

    session_id = uuid.uuid4().hex[:12]
    work = UPLOAD_DIR / f"preview_{session_id}"
    work.mkdir(parents=True, exist_ok=True)

    src = work / "source.pdf"
    pdf_file.save(src)

    second_path = None
    second_name = None
    if second_file is not None:
        second_path = work / ("secondary" + Path(second_file.filename).suffix.lower())
        second_file.save(second_path)
        second_name = second_file.filename

    try:
        import fitz
        doc = fitz.open(src)
        pages = len(doc)
        if pages == 0:
            doc.close()
            shutil.rmtree(work, ignore_errors=True)
            return jsonify({"error": "PDF has no pages."}), 400
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=50)
            pix.save(work / f"thumb_{i+1}.png")
        doc.close()
    except Exception as e:
        shutil.rmtree(work, ignore_errors=True)
        return jsonify({"error": f"Failed to render preview: {e}"}), 500

    with PREVIEW_LOCK:
        PREVIEW_SESSIONS[session_id] = {
            "dir": work,
            "path": src,
            "pages": pages,
            "filename": pdf_file.filename,
            "second": second_path,
            "second_filename": second_name,
            "created": time.time(),
            "tool": tool_id,
        }

    return jsonify({
        "session_id": session_id,
        "page_count": pages,
        "filename": pdf_file.filename,
        "secondary_filename": second_name,
        "secondary_url": f"/api/preview/secondary/{session_id}" if second_path else None,
    })


@app.route("/api/preview/thumb/<session_id>/<int:page_num>")
@requires_auth
def api_preview_thumb(session_id, page_num):
    info = PREVIEW_SESSIONS.get(session_id)
    if not info:
        return "Not found", 404
    path = Path(info["dir"]) / f"thumb_{page_num}.png"
    if not path.exists():
        return "Not found", 404
    return send_file(path, mimetype="image/png")


@app.route("/api/preview/page/<session_id>/<int:page_num>")
@requires_auth
def api_preview_page(session_id, page_num):
    info = PREVIEW_SESSIONS.get(session_id)
    if not info:
        return "Not found", 404
    if page_num < 1 or page_num > info["pages"]:
        return "Invalid page", 400
    try:
        import fitz
        doc = fitz.open(info["path"])
        pix = doc[page_num - 1].get_pixmap(dpi=140)
        doc.close()
        buf = io.BytesIO(pix.tobytes("png"))
        buf.seek(0)
        return send_file(buf, mimetype="image/png")
    except Exception as e:
        return f"Error: {e}", 500


@app.route("/api/preview/secondary/<session_id>")
@requires_auth
def api_preview_secondary(session_id):
    info = PREVIEW_SESSIONS.get(session_id)
    if not info or not info.get("second"):
        return "Not found", 404
    return send_file(info["second"])


# ============================================================
# Conversion API
# ============================================================
@app.route("/api/run/<tool_id>", methods=["POST"])
@requires_auth
def api_run(tool_id):
    tool = get_tool(tool_id)
    if not tool:
        return jsonify({"error": "Unknown tool."}), 404
    handler = HANDLERS.get(tool_id)
    if not handler:
        return jsonify({"error": "Tool not implemented."}), 500

    uploaded = [f for f in request.files.getlist("files") if f and f.filename]

    preview_id = request.form.get("preview_session")
    preview_info = PREVIEW_SESSIONS.get(preview_id) if preview_id else None

    needs_file = tool.get("accept") is not None
    if needs_file and not uploaded and not preview_info:
        return jsonify({"error": "Please upload at least one file."}), 400

    job = uuid.uuid4().hex[:8]
    work = UPLOAD_DIR / job
    work.mkdir(parents=True, exist_ok=True)

    saved = []
    for f in uploaded:
        safe = Path(f.filename).name
        path = work / safe
        f.save(path)
        saved.append(path)

    if preview_info:
        pdf_copy = work / Path(preview_info["filename"]).name
        shutil.copy2(preview_info["path"], pdf_copy)
        saved.insert(0, pdf_copy)
        if preview_info.get("second"):
            second_name = preview_info["second_filename"] or "secondary.png"
            second_copy = work / Path(second_name).name
            shutil.copy2(preview_info["second"], second_copy)
            saved.append(second_copy)

    options = {}
    for opt in tool.get("options", []):
        options[opt["name"]] = (request.form.get(opt["name"]) or "").strip()

    for k in ("split_points", "rotations", "order", "pages", "angle",
              "signature_x", "signature_y", "signature_w", "signature_pages",
              "rotation", "opacity", "scale"):
        v = request.form.get(k)
        if v is not None and v != "":
            options[k] = v.strip()

    try:
        result = handler(saved, options, work)
        return jsonify({
            "download_url": f"/api/download/{result.name}",
            "filename": result.name,
        })
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ ERROR in tool '{tool_id}':")
        traceback.print_exc()
        print("=" * 60 + "\n")
        err_msg = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
        return jsonify({"error": err_msg}), 500
    finally:
        for p in saved:
            try: p.unlink()
            except Exception: pass
        try: work.rmdir()
        except Exception: pass


@app.route("/api/download/<path:filename>")
@requires_auth
def download(filename):
    safe = Path(filename).name
    p = OUTPUT_DIR / safe
    if not p.exists():
        return "File not found", 404
    return send_file(p, as_attachment=True, download_name=safe)


@app.errorhandler(413)
def too_large(_):
    return jsonify({"error": f"File too large. Max {MAX_MB} MB."}), 413


@app.errorhandler(500)
def internal_error(_):
    return jsonify({"error": "Internal server error. Check the server logs."}), 500


# ============================================================
# Entry point (local development only)
# ============================================================
if __name__ == "__main__":
    from waitress import serve

    port = int(os.environ.get("PORT", 5000))

    print("=" * 60)
    print("  PyPDF Studio — Web GUI")
    print(f"  Open:    http://127.0.0.1:{port}")
    print(f"  Status:  http://127.0.0.1:{port}/status")
    print(f"  Health:  http://127.0.0.1:{port}/health")
    print(f"  Auth:    {'ENABLED' if AUTH_ENABLED else 'disabled (no env vars set)'}")
    print("  Cleanup: every 30 minutes (output/ and uploads/)")
    print("=" * 60)

    # NOTE: the cleanup thread was already started at module level.
    # Do NOT call start_cleanup_thread() here — that would start a
    # second thread and cause duplicate delete operations.
    serve(app, host="0.0.0.0", port=port, threads=8, channel_timeout=300)
