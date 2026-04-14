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
import uuid
import shutil
from datetime import datetime
from pathlib import Path

from flask import (Flask, render_template, request,
                   jsonify, send_file, session)

from core.file_handler import resolve
from core.parser import parse
from core.preprocessor import detect_language, preprocess
from core.comparator import compare
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


# ── Analyze ───────────────────────────────────────────────────────────────────
@app.route("/analyze", methods=["POST"])
def analyze():
    data      = request.get_json()
    threshold = float(data.get("threshold", 70))
    lang_over = data.get("language", "auto")

    upload_dir = _session_dir()
    all_files  = list(upload_dir.glob("*.pdf")) + list(upload_dir.glob("*.docx"))

    if len(all_files) < 2:
        return jsonify({"error": "Need at least 2 valid files to compare."}), 400

    records = resolve(all_files)
    valid   = [r for r in records if r["status"] in ("ok", "warning")]

    if len(valid) < 2:
        return jsonify({"error": "Not enough valid files after duplicate removal."}), 400

    # ── Parse ──────────────────────────────────────────────────────────────
    raw_texts: dict[str, str] = {}
    unreadable = []

    for rec in valid:
        text = parse(rec["path"])
        if text:
            raw_texts[rec["roll"]] = text
        else:
            unreadable.append(rec["filename"])

    if len(raw_texts) < 2:
        return jsonify({"error": "Too many unreadable files. Check they are text-based PDFs or valid DOCX."}), 400

    # ── Language ───────────────────────────────────────────────────────────
    if lang_over == "auto":
        language = detect_language(next(iter(raw_texts.values())))
        if language == "unknown":
            language = "cpp"   # safe default
    else:
        language = lang_over

    # ── Preprocess ─────────────────────────────────────────────────────────
    submissions: dict[str, str] = {
        roll: preprocess(text, language)
        for roll, text in raw_texts.items()
    }

    # ── Compare ────────────────────────────────────────────────────────────
    pair_results = compare(submissions)

    # ── Report ─────────────────────────────────────────────────────────────
    timestamp  = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_dir = upload_dir / "output" / timestamp
    rolls      = list(raw_texts.keys())

    matrix_path, flagged_path = generate(
        output_dir=output_dir,
        timestamp=timestamp,
        rolls=rolls,
        pair_results=pair_results,
        raw_texts=raw_texts,
        threshold=threshold,
    )

    # Store output paths in session for download
    session["matrix"]  = str(matrix_path)
    session["flagged"] = str(flagged_path)

    # Build table data for browser display
    flagged_rows = [
        {
            "roll_a":      r["roll_a"],
            "roll_b":      r["roll_b"],
            "similarity":  r["similarity"],
            "seq_score":   r["seq_score"],
            "fuzzy_score": r["fuzzy_score"],
        }
        for r in pair_results
        if r["similarity"] >= threshold
    ]

    all_rows = [
        {
            "roll_a":      r["roll_a"],
            "roll_b":      r["roll_b"],
            "similarity":  r["similarity"],
            "seq_score":   r["seq_score"],
            "fuzzy_score": r["fuzzy_score"],
        }
        for r in pair_results
    ]

    return jsonify({
        "language":      language,
        "total_students": len(rolls),
        "total_pairs":   len(pair_results),
        "flagged_count": len(flagged_rows),
        "unreadable":    unreadable,
        "all_pairs":     all_rows,
        "flagged_pairs": flagged_rows,
        "timestamp":     timestamp,
    })


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
