# PDS v2 — Plagiarism Detection System

Web-based plagiarism detection for programming assignments (PDF/DOCX).  
Runs locally on `localhost:5000`. No internet required.

## Setup

```bash
pip install -r requirements.txt
python app.py
```

Then open **http://localhost:5000** in your browser.

## Usage

1. Drag & drop or browse to select student assignment files (PDF/DOCX)
2. Set similarity threshold (default 70%) and language
3. Click **Run Analysis**
4. View results in browser and download both Excel reports

## Features

- Extracts roll numbers from inconsistent filenames (`24F-3053`, `f243071`, `24F_3053`, `24F - 3053`, etc.)
- Handles duplicate submissions — keeps latest by filename suffix `(1)`, `(2)`
- Parses PDF and DOCX files
- Detects C++, Python, Java — strips comments, normalizes identifiers → `var0, var1, var2`
- Full-file Jaccard + Cosine similarity on token trigrams
- Browser results table + two downloadable Excel reports

## Output

Each run saves to: `uploads/<session>/output/YYYY-MM-DD_HH-MM-SS/`

| File | Contents |
|---|---|
| `similarity_matrix_TIMESTAMP.xlsx` | N×N matrix, colour coded |
| `flagged_pairs_TIMESTAMP.xlsx` | Flagged pairs with code snippets, ascending sort |

## Colour Key

| Colour | Range | Meaning |
|---|---|---|
| Red | ≥ 90% | Very High |
| Orange | ≥ 70% | High (flagged) |
| Yellow | ≥ 50% | Moderate |

## Run Tests

```bash
pip install pytest
pytest tests/ -v
```
