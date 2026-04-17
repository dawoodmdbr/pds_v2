# PDS — Plagiarism Detection System

A web-based plagiarism detection tool for programming assignments. Upload student submissions as PDF or DOCX files, run similarity analysis, and get colour-coded Excel reports — all from a clean browser interface running locally.

Built with Python + Flask. No internet required at runtime.

---

## 📸 Screenshots

---

### Web UI
<p align="center">
  <img src="https://github.com/user-attachments/assets/25e5a0df-9025-49bd-922c-943f115911dd" width="700"/>
</p>

---

### Results
<p align="center">
  <img src="https://github.com/user-attachments/assets/4d9ba582-fd03-41ac-ae74-a0984be4e0d2" width="700"/>
</p>


> Run `python app.py`, open `http://localhost:5000`, upload files, click **Run Analysis**.

---

## Features

- **Drag & drop upload** — PDF and DOCX files, up to 100 submissions per run
- **Smart roll number extraction** — handles inconsistent filename formats automatically
- **Duplicate detection** — keeps the latest resubmission, skips older versions
- **Language-aware preprocessing** — strips comments for C++, Python, and Java
- **Two-metric similarity engine** — difflib SequenceMatcher + thefuzz token_set_ratio
- **In-browser results table** — view flagged pairs and all pairs without leaving the page
- **Two Excel reports** — similarity matrix and flagged pairs with code snippets
- **Timestamped output** — every run saved separately, nothing overwritten

---

## Supported Roll Number Formats

All of the following are recognised and normalised to `24F-3053`:

| Format | Example |
|---|---|
| Standard | `24F-3053` |
| Underscore | `24F_3053` |
| Spaces around dash | `24F - 3053` |
| Space before digits | `24F- 3053` |
| Compact letter-first | `f243053` |
| Compact year-first | `24f3053` |
| Letter before year | `F24-3053` |
| Numeric only | `243053` |

If a roll number cannot be extracted, the raw filename is used as the student identifier and flagged with a warning.

---

## How It Works

```
Upload files
     │
     ▼
Extract roll numbers + resolve duplicates
     │
     ▼
Parse PDF / DOCX → extract text
     │
     ▼
Detect language (C++ / Python / Java)
Strip comments + normalize whitespace
     │
     ▼
Pairwise similarity for every student pair
  • difflib SequenceMatcher   (40% weight)
  • thefuzz token_set_ratio   (60% weight)
     │
     ▼
Results table in browser  +  two Excel files
```

**Why this algorithm?** `token_set_ratio` tokenizes both submissions, sorts the tokens, then compares — making it naturally robust to variable renaming, reordered lines, and added comments without needing explicit variable normalization. `SequenceMatcher` adds sensitivity to structural ordering. Together they catch copy-paste plagiarism, light obfuscation, and renamed-variable submissions reliably.

---

## Output

Each run creates a timestamped folder inside `uploads/`:

```
uploads/
└── <session-id>/
    └── output/
        └── 2026-04-12_14-30-00/
            ├── similarity_matrix_2026-04-12_14-30-00.xlsx
            └── flagged_pairs_2026-04-12_14-30-00.xlsx
```

### similarity_matrix.xlsx

N × N grid of all student pairs with similarity percentages. Colour coded:

| Colour | Range | Meaning |
|---|---|---|
| 🔴 Red | ≥ 90% | Very high — likely plagiarism |
| 🟠 Orange | ≥ 70% | High — flagged for review |
| 🟡 Yellow | ≥ 50% | Moderate — worth inspecting |
| ⬜ White | < 50% | Low |

### flagged_pairs.xlsx

One row per pair above your threshold, sorted **descending** (highest similarity first). Columns:

| Column | Description |
|---|---|
| Rank | 1 = most suspicious |
| Student A / B | Roll numbers |
| Similarity % | Weighted final score |
| SequenceMatcher % | Raw difflib score |
| FuzzyToken % | Raw thefuzz score |
| Student A / B Code | First 1,500 chars of extracted text |

---

## Setup

**Requirements:** Python 3.11+

```bash
# 1. Clone the repo
git clone https://github.com/yourusername/pds.git
cd pds

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
python app.py

# 4. Open in browser
# http://localhost:5000
```

### Dependencies

| Package | Purpose |
|---|---|
| `flask` | Web server |
| `pdfplumber` | PDF text extraction |
| `python-docx` | DOCX text extraction |
| `openpyxl` | Excel report generation |
| `thefuzz` | Token-set fuzzy similarity |
| `python-Levenshtein` | Speeds up thefuzz |
| `scikit-learn` | (Reserved for future use) |

---

## Project Structure

```
pds/
├── app.py                  ← Flask server + all routes
├── requirements.txt
├── README.md
├── core/
│   ├── file_handler.py     ← Roll number extraction, duplicate resolution
│   ├── parser.py           ← PDF + DOCX text extraction
│   ├── preprocessor.py     ← Language detection, comment stripping
│   ├── comparator.py       ← Pairwise similarity computation
│   └── reporter.py         ← Excel report generation
├── templates/
│   └── index.html          ← Single-page frontend
├── static/
│   ├── style.css
│   └── app.js
└── uploads/                ← Created at runtime (gitignored)
```

---

## Usage Notes

- **Scanned PDFs** (image-based) are not supported — files must be text-based
- **One file per student** — if a student resubmits, name the new file with a `(1)` suffix (e.g. `24F-3053(1).docx`) and the system will keep it automatically
- **Threshold** — default is 70%. Lower it to catch more pairs; raise it to reduce noise
- The similarity score is a tool to assist human judgment — always review flagged pairs before drawing conclusions

---

## Limitations

- No support for ZIP archives — upload files individually
- No cross-language comparison (C++ vs Python)
- Does not detect plagiarism from external sources (GitHub, Stack Overflow, etc.)
- Scanned or image-based PDFs return no text and are excluded from comparison

---

## Tech Stack

Python · Flask · pdfplumber · python-docx · thefuzz · openpyxl · Vanilla HTML/CSS/JS
