"""
core/file_handler.py
Responsibilities:
  1. Accept a list of uploaded file paths.
  2. Extract and normalise roll numbers from filenames.
  3. Resolve duplicates — keep latest by (suffix_number, mtime).

Canonical roll number format: 24F-3053

Supported variants:
  24F-3053   24F_3053   24F - 3053   24F- 3053
  f243053    24f3053    F24-3053     243053
"""

import re
from pathlib import Path


_PATTERNS = [
    # 24F-3053 | 24F_3053 | 24F - 3053 | 24F- 3053 | 24F3053
    re.compile(r"(\d{2})([A-Za-z])\s*[-_]?\s*(\d{4})"),
    # f243053 | F243053
    re.compile(r"[fF](\d{2})(\d{4})"),
    # 24f3053
    re.compile(r"(\d{2})[fF](\d{4})"),
    # F24-3053 | F24_3053
    re.compile(r"([A-Za-z])(\d{2})\s*[-_]?\s*(\d{4})"),
    # 243053 (numeric only — type assumed F)
    re.compile(r"(\d{2})(\d{4})"),
]


def _extract_roll(filename: str) -> str | None:
    stem = Path(filename).stem

    m = _PATTERNS[0].search(stem)
    if m:
        return f"{m.group(1).upper()}{m.group(2).upper()}-{m.group(3)}"

    m = _PATTERNS[1].search(stem)
    if m:
        return f"{m.group(1).upper()}F-{m.group(2)}"

    m = _PATTERNS[2].search(stem)
    if m:
        return f"{m.group(1).upper()}F-{m.group(2)}"

    m = _PATTERNS[3].search(stem)
    if m:
        return f"{m.group(2).upper()}{m.group(1).upper()}-{m.group(3)}"

    m = _PATTERNS[4].search(stem)
    if m:
        return f"{m.group(1).upper()}F-{m.group(2)}"

    return None


def _suffix_number(filepath: Path) -> int:
    """Return trailing (N) suffix number, 0 if none."""
    m = re.search(r"\((\d+)\)$", filepath.stem)
    return int(m.group(1)) if m else 0


def resolve(file_paths: list[Path]) -> list[dict]:
    """
    Given a list of Path objects, extract roll numbers and resolve duplicates.

    Returns list of dicts:
    {
        path:     Path,
        filename: str,
        roll:     str,
        status:   'ok' | 'duplicate' | 'warning',
        note:     str,
    }
    """
    # Group by roll number
    roll_map: dict[str, list[Path]] = {}
    for p in file_paths:
        roll = _extract_roll(p.name) or p.stem
        roll_map.setdefault(roll, []).append(p)

    results = []
    for roll, paths in roll_map.items():
        roll_real = _extract_roll(paths[0].name)
        if len(paths) == 1:
            results.append({
                "path":     paths[0],
                "filename": paths[0].name,
                "roll":     roll,
                "status":   "ok" if roll_real else "warning",
                "note":     "" if roll_real else "Roll number not detected — using filename.",
            })
        else:
            # Keep the one with highest suffix, then latest mtime
            best = max(paths, key=lambda p: (_suffix_number(p), p.stat().st_mtime))
            skipped = [p for p in paths if p != best]
            results.append({
                "path":     best,
                "filename": best.name,
                "roll":     roll,
                "status":   "ok",
                "note":     f"Latest kept (supersedes {', '.join(p.name for p in skipped)})",
            })
            for s in skipped:
                results.append({
                    "path":     s,
                    "filename": s.name,
                    "roll":     roll,
                    "status":   "duplicate",
                    "note":     f"Skipped — superseded by {best.name}",
                })

    # OK first, warnings second, duplicates last
    order = {"ok": 0, "warning": 1, "duplicate": 2}
    results.sort(key=lambda r: order[r["status"]])
    return results
