"""
Transaction categories loaded from categories.json.

To add a new category or keyword, edit categories.json.
Order matters — first matching category wins.

Keyword formats supported:
- Plain text:  "lidl"     → substring match (literal)
- Glob:        "mp*"      → * matches anything  (mp480, mp420, ...)
- Regex:       "mp\d+"    → full regex syntax   (mp followed by digits)
               "mp.*"     → regex dot-star
"""

import json
import re
from pathlib import Path

_CATEGORIES_FILE = Path(__file__).parent / "categories.json"

# Regex metacharacters that signal a keyword is already a regex pattern
_REGEX_CHARS = re.compile(r'[.+?^${}()\[\]\\]')


def _compile_keyword(kw: str) -> re.Pattern:
    """Compile a keyword string to a regex pattern."""
    if '*' in kw and '.*' not in kw:
        # Glob: escape everything, then restore * as .*
        pattern = re.escape(kw).replace(r'\*', '.*')
    elif _REGEX_CHARS.search(kw):
        # Already a regex — use as-is
        pattern = kw
    else:
        # Plain literal — escape so special chars are treated literally
        pattern = re.escape(kw)
    return re.compile(pattern)


with _CATEGORIES_FILE.open(encoding="utf-8") as _f:
    _raw: dict[str, list[str]] = json.load(_f)

CATEGORIES: dict[str, list[re.Pattern]] = {
    cat: [_compile_keyword(kw) for kw in keywords]
    for cat, keywords in _raw.items()
}

_MOBILE_KESH = ("unovcavanje", "mobilnog keša")


def categorize(description: str) -> str:
    """Assign spending category based on merchant description. Returns 'Other' if no match."""
    desc_lower = description.lower()
    if all(kw in desc_lower for kw in _MOBILE_KESH):
        return "Mobile kesh"
    for category, patterns in CATEGORIES.items():
        if any(p.search(desc_lower) for p in patterns):
            return category
    return "Other"


def categorize_income(description: str) -> str:
    """Assign income category. Returns 'Mobile kesh' for mobile cash withdrawals, else 'Income'."""
    if all(kw in description.lower() for kw in _MOBILE_KESH):
        return "Mobile kesh"
    return "Income"
