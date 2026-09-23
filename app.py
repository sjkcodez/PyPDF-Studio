#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PyPDF Studio — Web GUI server.

Includes:
  • Auto-cleanup of output/ and uploads/ every 30 minutes.
  • Basic Auth protecting ONLY the /admin/* routes.
  • Anonymous analytics: visits, conversions, downloads, devices.
  • Per-IP rate limiting on conversions.

Environment variables (all optional; sensible defaults apply):
  PYPDF_ADMIN_USER        (default: "admin")
  PYPDF_ADMIN_PASS        (required to enable /admin; unset = /admin disabled)
  PYPDF_RATE_LIMIT        (default: 30)   conversions per hour per IP
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
from collections import deque, defaultdict

from flask import (
    Flask, Response, render_template, request, send_file,
    jsonify, g, make_response,
)

from handlers import TOOLS, HANDLERS, get_tool
from core.utils import OUTPUT_DIR
from core.readers import READERS
from core.writers import WRITERS

import analytics


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
# Admin credentials
# ============================================================
ADMIN_USER = os.environ.get("PYPDF_ADMIN_USER", "admin").strip() or "admin"
ADMIN_PASS = os.environ.get("PYPDF_ADMIN_PASS", "").strip()
ADMIN_ENABLED = bool(ADMIN_PASS)


def requires_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not ADMIN_ENABLED:
            return Response(
                "Admin access is disabled. Set the PYPDF_ADMIN_PASS "
                "environment variable to enable it.",
                503,
            )
        auth = request.authorization
        if not auth or auth.username != ADMIN_USER or auth.password != ADMIN_PASS:
            return Response(
                "Admin authentication required.",
                401,
                {"WWW-Authenticate": 'Basic realm="PyPDF Admin"'},
            )
        return f(*args, **kwargs)
    return wrapper


# ============================================================
# Rate limiting (in-memory, per IP, on /api/run/*)
# ============================================================
RATE_LIMIT_PER_HOUR = int(os.environ.get("PYPDF_RATE_LIMIT", "30"))
_rate_buckets = defaultdict(deque)   # ip -> deque[timestamps]
_rate_lock = threading.Lock()


def _rate_limit_ok(ip: str) -> bool:
    if RATE_LIMIT_PER_HOUR <= 0:
        return True
    now = time.time()
    cutoff = now - 3600
    with _rate_lock:
        bucket = _rate_buckets[ip]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= RATE_LIMIT_PER_HOUR:
            return False
        bucket.append(now)
        return True


# ============================================================
# Cleanup settings
# ============================================================
CLEANUP_INTERVAL_SECONDS = 30 * 60
CLEANUP_MAX_AGE_SECONDS  = 30 * 60
PREVIEW_MAX_AGE_SECONDS  = 60 * 60

PREVIEW_SESSIONS = {}
PREVIEW_LOCK = threading.Lock()


def _delete_old_files(folder: Path, max_age_seconds: int):
    if not folder.exists():
        return 0, 0
    now = time.time()
    df = dd = 0
    for path in folder.rglob("*"):
        try:
            if path.is_file() and (now - path.stat().st_mtime) > max_age_seconds:
                path.unlink(); df += 1
        except Exception:
            continue
    for path in sorted(folder.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        try:
            if path.is_dir() and not any(path.iterdir()):
                path.rmdir(); dd += 1
        except Exception:
            continue
    return df, dd


def _cleanup_preview_sessions():
    now = time.time()
    with PREVIEW_LOCK:
        expired = [s for s, i in PREVIEW_SESSIONS.items()
                   if now - i["created"] > PREVIEW_MAX_AGE_SECONDS]
        for sid in expired:
            info = PREVIEW_SESSIONS.pop(sid, None)
            if info:
                shutil.rmtree(info["dir"], ignore_errors=True)
    return len(expired)


def cleanup_loop():
    time.sleep(5)
    while True:
        try:
            of, _ = _delete_old_files(OUTPUT_DIR, CLEANUP_MAX_AGE_SECONDS)
            uf, _ = _delete_old_files(UPLOAD_DIR, CLEANUP_MAX_AGE_SECONDS)
            pv = _cleanup_preview_sessions()
            if of or uf or pv:
                print(f"[cleanup] output={of} uploads={uf} previews={pv}", flush=True)
        except Exception:
            traceback.print_exc()
        time.sleep(CLEANUP_INTERVAL_SECONDS)


def start_cleanup_thread():
    t = threading.Thread(target=cleanup_loop, name="cleanup", daemon=True)
    t.start()
    return t


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
            "psd_tools", "vsdx", "pdf2docx", "xmltodict"]
    out = {}
    for m in mods:
        try:
            __import__(m); out[m] = True
        except Exception:
            out[m] = False
    return out


def _client_ip() -> str:
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote_addr or "unknown"


# ============================================================
# Analytics hooks
# ============================================================
@app.before_request
def _analytics_before():
    # Don't track static files, admin, health checks, or internal API responses
    skip_prefixes = ("/static/", "/admin", "/health")
    if request.path.startswith(skip_prefixes):
        return

    # Assign / reuse a session ID
    sid = request.cookies.get("pypdf_sid", "")
    is_new = not sid
    if is_new:
        sid = uuid.uuid4().hex[:16]
    g.session_id = sid
    g.is_new_session = is_new

    # Only count page views, not API calls
    if not request.path.startswith("/api/"):
        try:
            analytics.record_visit(
                ip=_client_ip(),
                ua=request.user_agent.string or "",
                path=request.path,
                referrer=request.referrer or "",
                session_id=sid,
            )
        except Exception:
            pass


@app.after_request
def _analytics_after(response):
    if getattr(g, "is_new_session", False):
        response.set_cookie(
            "pypdf_sid", g.session_id,
            max_age=60 * 60 * 24 * 30,
            httponly=True,
            samesite="Lax",
        )
    return response


# ============================================================
# Health check
# ============================================================
@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "pypdf-studio"}), 200


# ============================================================
# Pages
# ============================================================
@app.route("/")
def index():
    categories, seen = [], set()
    for t in TOOLS:
        if t["category"] not in seen:
            categories.append(t["category"])
            seen.add(t["category"])
    return render_template("index.html", tools=TOOLS, categories=categories)


@app.route("/tool/<tool_id>")
def tool_page(tool_id):
    tool = get_tool(tool_id)
    if not tool:
        return "Tool not found", 404
    return render_template("tool.html", tool=tool)


@app.route("/status")
def status_page():
    return render_template("status.html",
                           binaries=_check_binaries(),
                           modules=_check_python_modules(),
                           readers=sorted(READERS.keys()),
                           writers=sorted(set(WRITERS.keys())))


# ============================================================
# Admin dashboard (password-protected)
# ============================================================
@app.route("/admin")
@requires_admin
def admin_dashboard():
    try:
        days = float(request.args.get("days", "7"))
    except Exception:
        days = 7.0
    if days not in (1.0, 7.0, 30.0, 0.0):
        days = 7.0
    stats = analytics.get_stats(days=days)
    return render_template("admin.html", stats=stats)


@app.route("/admin/api/stats")
@requires_admin
def admin_api_stats():
    try:
        days = float(request.args.get("days", "7"))
    except Exception:
        days = 7.0
    return jsonify(analytics.get_stats(days=days))


@app.route("/admin/export.csv")
@requires_admin
def admin_export_csv():
    csv_text = analytics.export_csv()
    return Response(
        csv_text,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=analytics.csv"},
    )


# ============================================================
# Preview endpoints
# ============================================================
@app.route("/api/preview/start/<tool_id>", methods=["POST"])
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

    second_path = second_name = None
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
            "dir": work, "path": src, "pages": pages,
            "filename": pdf_file.filename,
            "second": second_path, "second_filename": second_name,
            "created": time.time(), "tool": tool_id,
        }

    return jsonify({
        "session_id": session_id,
        "page_count": pages,
        "filename": pdf_file.filename,
        "secondary_filename": second_name,
        "secondary_url": f"/api/preview/secondary/{session_id}" if second_path else None,
    })


@app.route("/api/preview/thumb/<session_id>/<int:page_num>")
def api_preview_thumb(session_id, page_num):
    info = PREVIEW_SESSIONS.get(session_id)
    if not info: return "Not found", 404
    path = Path(info["dir"]) / f"thumb_{page_num}.png"
    if not path.exists(): return "Not found", 404
    return send_file(path, mimetype="image/png")


@app.route("/api/preview/page/<session_id>/<int:page_num>")
def api_preview_page(session_id, page_num):
    info = PREVIEW_SESSIONS.get(session_id)
    if not info: return "Not found", 404
    if page_num < 1 or page_num > info["pages"]: return "Invalid page", 400
    try:
        import fitz
        doc = fitz.open(info["path"])
        pix = doc[page_num - 1].get_pixmap(dpi=140)
        doc.close()
        buf = io.BytesIO(pix.tobytes("png")); buf.seek(0)
        return send_file(buf, mimetype="image/png")
    except Exception as e:
        return f"Error: {e}", 500


@app.route("/api/preview/secondary/<session_id>")
def api_preview_secondary(session_id):
    info = PREVIEW_SESSIONS.get(session_id)
    if not info or not info.get("second"): return "Not found", 404
    return send_file(info["second"])


# ============================================================
# Conversion API
# ============================================================
@app.route("/api/run/<tool_id>", methods=["POST"])
def api_run(tool_id):
    tool = get_tool(tool_id)
    if not tool:
        return jsonify({"error": "Unknown tool."}), 404
    handler = HANDLERS.get(tool_id)
    if not handler:
        return jsonify({"error": "Tool not implemented."}), 500

    ip = _client_ip()

    # ---- Rate limit ----
    if not _rate_limit_ok(ip):
        return jsonify({
            "error": (
                f"Rate limit reached. You can do at most "
                f"{RATE_LIMIT_PER_HOUR} conversions per hour. "
                f"Please try again later."
            )
        }), 429

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
    total_input_size = 0
    for f in uploaded:
        safe = Path(f.filename).name
        path = work / safe
        f.save(path)
        saved.append(path)
        try:
            total_input_size += path.stat().st_size
        except Exception:
            pass

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

    # Infer input/output extensions for analytics
    input_ext = ""
    if saved:
        input_ext = saved[0].suffix.lower()
    output_ext = "." + (options.get("format") or "").lower().lstrip(".")

    t0 = time.time()
    try:
        result = handler(saved, options, work)
        elapsed_ms = int((time.time() - t0) * 1000)

        try:
            out_size = result.stat().st_size
        except Exception:
            out_size = 0

        analytics.record_conversion(
            tool_id=tool_id,
            input_ext=input_ext,
            output_ext=result.suffix.lower() if result.suffix else output_ext,
            input_size=total_input_size,
            output_size=out_size,
            duration_ms=elapsed_ms,
            ip=ip,
            session_id=getattr(g, "session_id", ""),
            success=True,
        )

        return jsonify({
            "download_url": f"/api/download/{result.name}",
            "filename": result.name,
        })
    except Exception as e:
        elapsed_ms = int((time.time() - t0) * 1000)
        print("\n" + "=" * 60)
        print(f"❌ ERROR in tool '{tool_id}':")
        traceback.print_exc()
        print("=" * 60 + "\n")
        err_msg = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__

        analytics.record_conversion(
            tool_id=tool_id,
            input_ext=input_ext,
            output_ext=output_ext,
            input_size=total_input_size,
            output_size=0,
            duration_ms=elapsed_ms,
            ip=ip,
            session_id=getattr(g, "session_id", ""),
            success=False,
            error=err_msg,
        )

        return jsonify({"error": err_msg}), 500
    finally:
        for p in saved:
            try: p.unlink()
            except Exception: pass
        try: work.rmdir()
        except Exception: pass


@app.route("/api/download/<path:filename>")
def download(filename):
    safe = Path(filename).name
    p = OUTPUT_DIR / safe
    if not p.exists():
        return "File not found", 404

    try:
        analytics.record_download(
            filename=safe,
            ip=_client_ip(),
            session_id=getattr(g, "session_id", ""),
        )
    except Exception:
        pass

    return send_file(p, as_attachment=True, download_name=safe)


@app.errorhandler(413)
def too_large(_):
    return jsonify({"error": f"File too large. Max {MAX_MB} MB."}), 413


@app.errorhandler(500)
def internal_error(_):
    return jsonify({"error": "Internal server error. Check the server logs."}), 500


# ============================================================
# Entry point
# ============================================================
if __name__ == "__main__":
    from waitress import serve
    port = int(os.environ.get("PORT", 5000))

    print("=" * 60)
    print("  PyPDF Studio — Web GUI")
    print(f"  Open:     http://127.0.0.1:{port}")
    print(f"  Admin:    http://127.0.0.1:{port}/admin")
    print(f"  Status:   http://127.0.0.1:{port}/status")
    print(f"  Health:   http://127.0.0.1:{port}/health")
    print(f"  Admin pw: {'set' if ADMIN_ENABLED else 'NOT SET (admin disabled)'}")
    print(f"  Rate cap: {RATE_LIMIT_PER_HOUR} / hour / IP")
    print("=" * 60)

    serve(app, host="0.0.0.0", port=port, threads=8, channel_timeout=300)
