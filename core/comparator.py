"""
core/comparator.py

Similarity algorithm (from proven v1 CLI approach):
  - difflib SequenceMatcher  (40%) — character-level structure
  - thefuzz token_set_ratio  (60%) — token overlap, order-independent

Returns pairs sorted DESCENDING by similarity (highest risk first).
"""

import difflib
from itertools import combinations
from thefuzz import fuzz


def _similarity(text_a: str, text_b: str) -> tuple[float, float, float]:
    """
    Returns (final_score, seq_score, fuzzy_score) all as percentages.
    """
    if not text_a or not text_b:
        return 0.0, 0.0, 0.0

    seq   = difflib.SequenceMatcher(None, text_a, text_b).ratio() * 100
    fuzzy = float(fuzz.token_set_ratio(text_a, text_b))
    final = round(seq * 0.4 + fuzzy * 0.6, 1)
    return final, round(seq, 1), round(fuzzy, 1)


class CancelledError(Exception):
    """Raised when the caller asks the comparison to stop."""


def compare(submissions: dict[str, str],
            progress_cb=None,
            should_cancel=None) -> list[dict]:
    """
    Args:
        submissions: { roll_number: preprocessed_text_string }

    Returns list of dicts sorted DESCENDING by similarity:
    [
        {
            roll_a:      str,
            roll_b:      str,
            similarity:  float,   ← weighted final score %
            seq_score:   float,   ← difflib %
            fuzzy_score: float,   ← thefuzz %
        },
        ...
    ]
    """
    rolls   = list(submissions.keys())
    results = []
    total   = len(rolls) * (len(rolls) - 1) // 2

    for done, (roll_a, roll_b) in enumerate(combinations(rolls, 2)):
        if should_cancel and should_cancel():
            raise CancelledError()
        if progress_cb:
            progress_cb(done, total)
        text_a = submissions[roll_a]
        text_b = submissions[roll_b]
        final, seq, fuzzy = _similarity(text_a, text_b)
        results.append({
            "roll_a":      roll_a,
            "roll_b":      roll_b,
            "similarity":  final,
            "seq_score":   seq,
            "fuzzy_score": fuzzy,
        })

    if progress_cb:
        progress_cb(total, total)

    # Descending — highest similarity first
    results.sort(key=lambda r: r["similarity"], reverse=True)
    return results
