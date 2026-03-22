"""
Transaction categories loaded from categories.json.

To add a new category or keyword, edit categories.json.
Order matters — first matching category wins.
"""

import json
from pathlib import Path

_CATEGORIES_FILE = Path(__file__).parent / "categories.json"

with _CATEGORIES_FILE.open(encoding="utf-8") as _f:
    CATEGORIES: dict[str, list[str]] = json.load(_f)

_MOBILE_KESH = ("unovcavanje", "mobilnog keša")


def categorize(description: str) -> str:
    """Assign spending category based on merchant description. Returns 'Other' if no match."""
    desc_lower = description.lower()
    if all(kw in desc_lower for kw in _MOBILE_KESH):
        return "Mobile kesh"
    for category, keywords in CATEGORIES.items():
        if any(kw in desc_lower for kw in keywords):
            return category
    return "Other"


def categorize_income(description: str) -> str:
    """Assign income category. Returns 'Mobile kesh' for mobile cash withdrawals, else 'Income'."""
    if all(kw in description.lower() for kw in _MOBILE_KESH):
        return "Mobile kesh"
    return "Income"
