"""
core/preprocessor.py

Preprocessing pipeline (from proven v1 CLI approach):
  1. Detect language (C++, Python, Java)
  2. Strip comments (language-aware)
  3. Normalize line endings
  4. Strip blank lines + collapse whitespace per line
  5. Lowercase

No variable renaming — fuzzy similarity handles obfuscation naturally.
"""

import re

_LANG_HINTS = {
    "cpp":    [("#include", 3), ("cout",  2), ("cin",   2), ("int main", 3),
               ("namespace", 1), ("nullptr", 2), ("::", 1)],
    "python": [("def ",    3), ("import ", 2), ("print(", 2),
               ("elif ",   2), ("self.",   2), ("__init__", 3)],
    "java":   [("public class", 4), ("System.out", 3), ("void main", 3),
               ("extends ", 2), ("implements ", 2), ("ArrayList", 2)],
}


def detect_language(text: str) -> str:
    scores = {}
    for lang, hints in _LANG_HINTS.items():
        scores[lang] = sum(w for kw, w in hints if kw in text)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "unknown"


def preprocess(text: str, language: str) -> str:
    """
    Returns a cleaned string (not token list).
    Suitable for difflib SequenceMatcher and thefuzz token_set_ratio.
    """
    # Strip comments
    if language in ("cpp", "java"):
        text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
        text = re.sub(r"//[^\n]*", " ", text)
    elif language == "python":
        text = re.sub(r'""".*?"""', " ", text, flags=re.DOTALL)
        text = re.sub(r"'''.*?'''", " ", text, flags=re.DOTALL)
        text = re.sub(r"#[^\n]*", " ", text)

    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Clean each line
    lines = []
    for line in text.split("\n"):
        line = line.strip()
        line = re.sub(r"[ \t]+", " ", line)
        if line:
            lines.append(line)

    return "\n".join(lines).lower()
