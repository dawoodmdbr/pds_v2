"""
app.py
Flask backend for PDS v2.

Routes:
  GET  /                    → index page
  POST /upload              → receive files, return file manifest JSON
  POST /analyze             → run pipeline, return results JSON
  GET  /download/<filename> → stream Excel file to browser
  POST /clear               → delete session uploads
"""

import os
import time
import uuid
import shutil
import threading
import traceback
from datetime import datetime
from pathlib import Path

from flask import (Flask, render_template, request,
                   jsonify, send_file, session)

from core.file_handler import resolve
from core.parser import parse
from core.preprocessor import detect_language, preprocess
from core.comparator import compare, CancelledError
from core.reporter import generate

app = Flask(__name__)
app.secret_key = os.urandom(24)

UPLOAD_ROOT = Path("uploads")
UPLOAD_ROOT.mkdir(exist_ok=True)
ALLOWED_EXT = {".pdf", ".docx"}


def _session_dir() -> Path:
    sid = session.setdefault("id", str(uuid.uuid4()))
    d = UPLOAD_ROOT / sid
    d.mkdir(exist_ok=True)
    return d


# ── Index ─────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


# ── Upload ────────────────────────────────────────────────────────────────────
@app.route("/upload", methods=["POST"])
def upload():
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files received."}), 400

    upload_dir = _session_dir()

    # Clear previous uploads for this session
    for f in upload_dir.glob("*"):
        if f.is_file():
            f.unlink()

    saved = []
    for f in files:
        if Path(f.filename).suffix.lower() not in ALLOWED_EXT:
            continue
        dest = upload_dir / f.filename
        f.save(str(dest))
        saved.append(dest)

    if not saved:
        return jsonify({"error": "No valid PDF or DOCX files found."}), 400

    # Resolve roll numbers and duplicates
    records = resolve(saved)

    manifest = [
        {
            "filename": r["filename"],
            "roll":     r["roll"],
            "status":   r["status"],
            "note":     r["note"],
        }
        for r in records
    ]
    return jsonify({"files": manifest, "total": len(saved)})


# ── Analyze (background job) ──────────────────────────────────────────────────
MAX_RUNTIME_SECONDS = 15 * 60          # overall safety timeout per analysis
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _set(job, **kw):
    with _jobs_lock:
        job.update(kw)


def _run_job(job, upload_dir: Path, threshold: float, lang_over: str):
    """Runs the full pipeline in a worker thread, reporting progress."""
    started = job["started"]

    def cancelled():
        if job["cancel"]:
            return True
        if time.time() - started > MAX_RUNTIME_SECONDS:
            job["timed_out"] = True
            return True
        return False

    try:
        all_files = list(upload_dir.glob("*.pdf")) + list(upload_dir.glob("*.docx"))
        if len(all_files) < 2:
            raise ValueError("Need at least 2 valid files to compare.")

        records = resolve(all_files)
        valid   = [r for r in records if r["status"] in ("ok", "warning")]
        if len(valid) < 2:
            raise ValueError("Not enough valid files after duplicate removal.")

        # ── Parse ──
        raw_texts: dict[str, str] = {}
        unreadable = []
        for i, rec in enumerate(valid):
            if cancelled():
                raise CancelledError()
            _set(job, stage="Reading files", done=i, total=len(valid),
                 detail=rec["filename"])
            text = parse(rec["path"])
            if text:
                raw_texts[rec["roll"]] = text
            else:
                unreadable.append(rec["filename"])

        if len(raw_texts) < 2:
            raise ValueError("Too many unreadable files. Check they are "
                             "text-based PDFs or valid DOCX.")

        # ── Language + preprocess ──
        _set(job, stage="Preprocessing", done=0, total=1, detail="")
        if lang_over == "auto":
            language = detect_language(next(iter(raw_texts.values())))
            if language == "unknown":
                language = "cpp"
        else:
            language = lang_over

        submissions = {roll: preprocess(t, language)
                       for roll, t in raw_texts.items()}

        # ── Compare ──
        def on_progress(done, total):
            _set(job, stage="Comparing pairs", done=done, total=total, detail="")

        pair_results = compare(submissions,
                               progress_cb=on_progress,
                               should_cancel=cancelled)

        # ── Report ──
        _set(job, stage="Generating Excel reports", done=0, total=1, detail="")
        timestamp  = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_dir = upload_dir / "output" / timestamp
        rolls      = list(raw_texts.keys())

        matrix_path, flagged_path = generate(
            output_dir=output_dir, timestamp=timestamp, rolls=rolls,
            pair_results=pair_results, raw_texts=raw_texts,
            threshold=threshold,
        )

        def row(r):
            return {"roll_a": r["roll_a"], "roll_b": r["roll_b"],
                    "similarity": r["similarity"],
                    "seq_score": r["seq_score"],
                    "fuzzy_score": r["fuzzy_score"]}

        flagged_rows = [row(r) for r in pair_results if r["similarity"] >= threshold]
        result = {
            "language":       language,
            "total_students": len(rolls),
            "total_pairs":    len(pair_results),
            "flagged_count":  len(flagged_rows),
            "unreadable":     unreadable,
            "all_pairs":      [row(r) for r in pair_results],
            "flagged_pairs":  flagged_rows,
            "timestamp":      timestamp,
        }
        _set(job, status="done", result=result,
             matrix=str(matrix_path), flagged=str(flagged_path))

    except CancelledError:
        if job.get("timed_out"):
            _set(job, status="error",
                 error=f"Analysis stopped after {MAX_RUNTIME_SECONDS // 60} minutes "
                       "(timeout). Try fewer or shorter files.")
        else:
            _set(job, status="cancelled")
    except Exception as e:            # never fail silently
        traceback.print_exc()
        _set(job, status="error", error=f"{type(e).__name__}: {e}")


@app.route("/analyze", methods=["POST"])
def analyze():
    data      = request.get_json() or {}
    threshold = float(data.get("threshold", 70))
    lang_over = data.get("language", "auto")

    upload_dir = _session_dir()
    job_id = str(uuid.uuid4())
    job = {"status": "running", "stage": "Starting", "done": 0, "total": 1,
           "detail": "", "started": time.time(), "cancel": False,
           "timed_out": False, "sid": session["id"]}
    with _jobs_lock:
        _jobs[job_id] = job

    threading.Thread(target=_run_job,
                     args=(job, upload_dir, threshold, lang_over),
                     daemon=True).start()
    return jsonify({"job_id": job_id})


@app.route("/progress/<job_id>")
def progress(job_id):
    job = _jobs.get(job_id)
    if not job or job["sid"] != session.get("id"):
        return jsonify({"status": "error", "error": "Job not found."}), 404

    out = {"status": job["status"], "stage": job["stage"],
           "done": job["done"], "total": job["total"],
           "detail": job["detail"],
           "elapsed": round(time.time() - job["started"], 1)}

    if job["status"] == "done":
        session["matrix"]  = job["matrix"]
        session["flagged"] = job["flagged"]
        out["result"] = job["result"]
    elif job["status"] == "error":
        out["error"] = job["error"]
    return jsonify(out)


@app.route("/cancel/<job_id>", methods=["POST"])
def cancel(job_id):
    job = _jobs.get(job_id)
    if job and job["sid"] == session.get("id"):
        job["cancel"] = True
    return jsonify({"ok": True})


# ── Download ──────────────────────────────────────────────────────────────────
@app.route("/download/<which>")
def download(which):
    key = "matrix" if which == "matrix" else "flagged"
    path = session.get(key)
    if not path or not Path(path).exists():
        return "File not found.", 404
    return send_file(path, as_attachment=True,
                     download_name=Path(path).name)


# ── Clear session ─────────────────────────────────────────────────────────────
@app.route("/clear", methods=["POST"])
def clear():
    upload_dir = _session_dir()
    if upload_dir.exists():
        shutil.rmtree(upload_dir)
    session.clear()
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
