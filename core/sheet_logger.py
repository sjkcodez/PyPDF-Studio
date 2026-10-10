"""Async, batched writer to Google Sheets + startup hydration.

Credentials:
  • Preferred: set GOOGLE_CREDS_FILE to a path containing a service-account
    JSON file (e.g. /app/secrets/gcp-sa.json inside the container).
  • Fallback: set GOOGLE_CREDS to the entire JSON as a single-line string.

Also requires SHEET_ID = the Google Sheets spreadsheet ID.

Timestamps:
  • All timestamps written to Sheets use CONTAINER LOCAL TIME
    (datetime.now()), not UTC. Set TZ=Africa/Dar_es_Salaam in
    docker-compose.yml / Render env vars to control what "local" means.

On startup, the worker hydrates SQLite from Sheets so the admin dashboard
shows history after a Render cold start (ephemeral disk).
"""
from __future__ import annotations

import json
import os
import queue
import threading
import time
from datetime import datetime

try:
    import gspread
    from google.oauth2.service_account import Credentials
    _GSPREAD_AVAILABLE = True
except ImportError:
    _GSPREAD_AVAILABLE = False


# ---------- Tunables ----------
FLUSH_INTERVAL = 10
BATCH_SIZE = 50
MAX_QUEUE_SIZE = 5000
HYDRATE_ROWS = 500

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ---------- Module state ----------
_queue: "queue.Queue[tuple[str, list]]" = queue.Queue()
_client = None
_sheet = None
_started = False
_lock = threading.Lock()


def _log(msg: str) -> None:
    print(f"[sheet_logger] {msg}", flush=True)


# ============================================================
# Credentials loading
# ============================================================
def _load_creds_dict():
    """Return the service-account dict, or None if unavailable."""
    # 1) Preferred: read from file path
    creds_file = os.environ.get("GOOGLE_CREDS_FILE", "").strip()
    if creds_file:
        try:
            with open(creds_file, "r", encoding="utf-8") as fh:
                creds_dict = json.load(fh)
            _log(f"loaded credentials from file: {creds_file}")
            return creds_dict
        except Exception as e:
            _log(f"could not read credentials file '{creds_file}': {e}")
            return None

    # 2) Fallback: inline JSON in env var
    creds_json = os.environ.get("GOOGLE_CREDS", "").strip()
    if creds_json:
        try:
            creds_dict = json.loads(creds_json)
            _log("loaded credentials from GOOGLE_CREDS env var")
            return creds_dict
        except Exception as e:
            _log(f"GOOGLE_CREDS is not valid JSON: {e}")
            return None

    _log("no credentials available (set GOOGLE_CREDS_FILE or GOOGLE_CREDS)")
    return None


def _init_client() -> bool:
    global _client, _sheet

    if _sheet is not None:
        return True
    if not _GSPREAD_AVAILABLE:
        _log("gspread/google-auth not installed — disabled")
        return False

    sheet_id = os.environ.get("SHEET_ID", "").strip()
    if not sheet_id:
        _log("SHEET_ID not set — disabled")
        return False

    creds_dict = _load_creds_dict()
    if creds_dict is None:
        return False

    try:
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        _client = gspread.authorize(creds)
        _sheet = _client.open_by_key(sheet_id)
        _log(f"connected to sheet: {_sheet.title}")
        return True
    except Exception as e:
        _log(f"auth failed: {e}")
        return False


# ============================================================
# Timestamp helpers — all use container LOCAL time
# ============================================================
def _now() -> str:
    """Current container-local time as 'YYYY-MM-DD HH:MM:SS'."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _parse_ts(s: str):
    """Parse 'YYYY-MM-DD HH:MM:SS' (container local time) into epoch seconds."""
    try:
        dt = datetime.strptime(str(s).strip(), "%Y-%m-%d %H:%M:%S")
        return dt.astimezone().timestamp()
    except Exception:
        return None


# ============================================================
# Flush
# ============================================================
def _flush_batch(events: list[tuple[str, list]]) -> bool:
    if not _init_client():
        return False

    by_tab: dict[str, list[list]] = {}
    for tab, row in events:
        by_tab.setdefault(tab, []).append(row)

    try:
        for tab, rows in by_tab.items():
            try:
                ws = _sheet.worksheet(tab)
            except gspread.WorksheetNotFound:
                _log(f"tab '{tab}' not found — skipping {len(rows)}")
                continue
            ws.append_rows(rows, value_input_option="USER_ENTERED")
            _log(f"flushed {len(rows)} rows to '{tab}'")
        return True
    except Exception as e:
        _log(f"flush failed: {e}")
        return False


# ============================================================
# Hydration — pull recent rows from Sheets back into SQLite
# ============================================================
def _hydrate_from_sheets() -> None:
    if not _init_client():
        return

    try:
        import analytics as A
    except Exception as e:
        _log(f"could not import analytics for hydration: {e}")
        return

    conn = A._connect()
    try:
        # ---------------- Visits ----------------
        try:
            ws = _sheet.worksheet("Visits")
            data = ws.get_all_values()
            if len(data) > 1:
                rows = data[1:][-HYDRATE_ROWS:]
                max_ts = conn.execute(
                    "SELECT COALESCE(MAX(ts), 0) FROM visits"
                ).fetchone()[0]
                inserted = 0
                for r in rows:
                    if len(r) < 7:
                        continue
                    ts_str, ip, path, referrer, device, browser, sid = r[:7]
                    ts = _parse_ts(ts_str)
                    if ts is None or ts <= max_ts:
                        continue
                    conn.execute(
                        """INSERT INTO visits
                           (ts, ip, user_agent, device, os, browser,
                            path, referrer, session_id)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (ts, ip, "", device, "unknown", browser,
                         path, referrer, sid),
                    )
                    inserted += 1
                if inserted:
                    conn.commit()
                _log(f"hydrated {inserted} new visits")
        except Exception as e:
            _log(f"hydrate visits failed: {e}")

        # ---------------- Conversions ----------------
        try:
            ws = _sheet.worksheet("Conversions")
            data = ws.get_all_values()
            if len(data) > 1:
                rows = data[1:][-HYDRATE_ROWS:]
                max_ts = conn.execute(
                    "SELECT COALESCE(MAX(ts), 0) FROM conversions"
                ).fetchone()[0]
                inserted = 0
                for r in rows:
                    if len(r) < 10:
                        continue
                    (ts_str, tool_id, in_ext, out_ext, in_kb, out_kb,
                     dur, success, error, sid) = r[:10]
                    ts = _parse_ts(ts_str)
                    if ts is None or ts <= max_ts:
                        continue

                    def _num(v):
                        try:
                            return float(v)
                        except Exception:
                            return 0.0

                    input_size = int(_num(in_kb) * 1024)
                    output_size = int(_num(out_kb) * 1024)
                    duration = int(_num(dur))
                    ok = 1 if str(success).strip().upper() in (
                        "TRUE", "1", "YES", "OK"
                    ) else 0
                    conn.execute(
                        """INSERT INTO conversions
                           (ts, tool_id, input_ext, output_ext, input_size,
                            output_size, duration_ms, ip, session_id,
                            success, error)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (ts, tool_id, in_ext, out_ext, input_size,
                         output_size, duration, "", sid, ok, error or ""),
                    )
                    inserted += 1
                if inserted:
                    conn.commit()
                _log(f"hydrated {inserted} new conversions")
        except Exception as e:
            _log(f"hydrate conversions failed: {e}")

        # ---------------- Downloads ----------------
        try:
            ws = _sheet.worksheet("Downloads")
            data = ws.get_all_values()
            if len(data) > 1:
                rows = data[1:][-HYDRATE_ROWS:]
                max_ts = conn.execute(
                    "SELECT COALESCE(MAX(ts), 0) FROM downloads"
                ).fetchone()[0]
                inserted = 0
                for r in rows:
                    if len(r) < 4:
                        continue
                    ts_str, filename, ip, sid = r[:4]
                    ts = _parse_ts(ts_str)
                    if ts is None or ts <= max_ts:
                        continue
                    conn.execute(
                        "INSERT INTO downloads (ts, filename, ip, session_id) "
                        "VALUES (?, ?, ?, ?)",
                        (ts, filename, ip, sid),
                    )
                    inserted += 1
                if inserted:
                    conn.commit()
                _log(f"hydrated {inserted} new downloads")
        except Exception as e:
            _log(f"hydrate downloads failed: {e}")

    finally:
        try:
            conn.close()
        except Exception:
            pass


# ============================================================
# Worker
# ============================================================
def _worker():
    _log("worker started")
    _init_client()

    try:
        _hydrate_from_sheets()
    except Exception as e:
        _log(f"hydration top-level failed: {e}")

    buffer: list[tuple[str, list]] = []
    last_flush = time.time()

    while True:
        try:
            timeout = max(0.5, FLUSH_INTERVAL - (time.time() - last_flush))
            try:
                item = _queue.get(timeout=timeout)
                buffer.append(item)
            except queue.Empty:
                pass

            if len(buffer) >= BATCH_SIZE or (
                buffer and time.time() - last_flush >= FLUSH_INTERVAL
            ):
                if _flush_batch(buffer):
                    buffer.clear()
                    last_flush = time.time()
                else:
                    if len(buffer) > MAX_QUEUE_SIZE:
                        buffer = buffer[-MAX_QUEUE_SIZE:]
                    time.sleep(5)
        except Exception as e:
            _log(f"worker error: {e}")
            time.sleep(5)


def _enqueue(tab: str, row: list):
    if _queue.qsize() >= MAX_QUEUE_SIZE:
        _log(f"queue full, dropping event for {tab}")
        return
    _queue.put((tab, row))
    _log(f"enqueued {tab}: queue size = {_queue.qsize()}")


# ============================================================
# Public API
# ============================================================
def start():
    """Start the background worker + hydration thread. Idempotent."""
    global _started
    with _lock:
        if _started:
            return
        if not _GSPREAD_AVAILABLE:
            _log("disabled (library missing)")
            return

        has_creds = bool(
            os.environ.get("GOOGLE_CREDS_FILE")
            or os.environ.get("GOOGLE_CREDS")
        )
        has_sheet = bool(os.environ.get("SHEET_ID"))
        if not has_creds or not has_sheet:
            _log(f"disabled (credentials={has_creds}, sheet_id={has_sheet})")
            return

        t = threading.Thread(target=_worker, name="sheet_logger", daemon=True)
        t.start()
        _started = True


# ---------- Event writers ----------

def log_visit(ip: str, path: str, referrer: str,
              device: str, browser: str, session_id: str):
    _enqueue("Visits", [_now(), ip, path, referrer,
                        device, browser, session_id])


def log_conversion(tool_id: str, input_ext: str, output_ext: str,
                   input_size: int, output_size: int, duration_ms: int,
                   success: bool, error: str, session_id: str):
    _enqueue("Conversions", [
        _now(),
        tool_id,
        input_ext,
        output_ext,
        round(input_size / 1024, 1) if input_size else "",
        round(output_size / 1024, 1) if output_size else "",
        duration_ms,
        bool(success),
        (error or "")[:200],
        session_id,
    ])


def log_download(filename: str, ip: str, session_id: str):
    _enqueue("Downloads", [_now(), filename, ip, session_id])
