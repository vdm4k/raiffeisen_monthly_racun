"""
Index page generator - month plates with seasonal colors, multi-select, Show analytics.
"""

from pathlib import Path
import json
from typing import Any

# Seasonal colors: Winter (Dec, Jan, Feb) = blue shades
MONTH_COLORS = {
    12: "#0d47a1",   # December - strong blue
    1: "#64b5f6",    # January - light blue
    2: "#1976d2",    # February - medium blue
    3: "#43a047",    # March - spring green
    4: "#66bb6a",    # April - light green
    5: "#2e7d32",    # May - dark green
    6: "#ffa726",    # June - summer orange
    7: "#ff9800",    # July - orange
    8: "#f57c00",    # August - dark orange
    9: "#8d6e63",    # September - fall brown
    10: "#a1887f",   # October - light brown
    11: "#5d4037",   # November - dark brown
}

MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
    7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December",
}


def get_month_color(month: int) -> str:
    return MONTH_COLORS.get(month, "#607d8b")


def generate_index_html(
    months_data: list[dict[str, Any]],
    output_path: str | Path,
    currency: str = "RSD",
) -> None:
    """
    Generate index page with month plates and embedded analytics data.

    months_data: [
        {"key": "2026-01", "year": 2026, "month": 1, "month_name": "January", "color": "#64b5f6",
         "analytics": {category_data, income_data, outgoings_data, total_income, total_outcomes},
        ...
    ]
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    plates = [
        {
            "key": m["key"],
            "year": m["year"],
            "month": m["month"],
            "month_name": m["month_name"],
            "color": m["color"],
        }
        for m in months_data
    ]

    analytics_by_month = {m["key"]: m.get("analytics", {}) for m in months_data}

    template_path = Path(__file__).parent / "index_template.html"
    if template_path.exists():
        html = template_path.read_text(encoding="utf-8")
    else:
        raise FileNotFoundError(f"Template not found: {template_path}")

    html = html.replace("__PLATES_JSON__", json.dumps(plates, ensure_ascii=False))
    html = html.replace("__ANALYTICS_JSON__", json.dumps(analytics_by_month, ensure_ascii=False))
    html = html.replace("__CURRENCY__", json.dumps(currency))

    output_path.write_text(html, encoding="utf-8")
