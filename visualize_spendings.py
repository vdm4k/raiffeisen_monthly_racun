#!/usr/bin/env python3
"""
Spending Visualizer - Uses parsed bank statements to create visualizations.
"""

import csv
from pathlib import Path

from pdf_parser import parse_statement, extract_date_range, extract_keyword
from spending_visualizer import generate_html
from index_generator import generate_index_html, get_month_color, MONTH_NAMES


def build_visualization_data(statement) -> dict:
    """Build category_data, income_data, outgoings_data from ParsedStatement."""
    outcomes = [
        {"date": t["date"], "description": t["description"], "amount": t["amount"], "category": cat}
        for cat, txs in statement.outgoings_by_category.items()
        for t in txs
    ]

    category_data: dict[str, dict] = {}
    for t in outcomes:
        cat = t["category"]
        if cat not in category_data:
            category_data[cat] = {
                "total": 0.0,
                "transactions": [],
                "by_keyword": {},
            }
        tx_dict = {"date": t["date"], "description": t["description"], "amount": t["amount"]}
        category_data[cat]["total"] += t["amount"]
        category_data[cat]["transactions"].append(tx_dict)
        kw = extract_keyword(t["description"])
        if kw not in category_data[cat]["by_keyword"]:
            category_data[cat]["by_keyword"][kw] = []
        category_data[cat]["by_keyword"][kw].append(tx_dict)

    for cat in category_data:
        sorted_txs = sorted(
            category_data[cat]["transactions"],
            key=lambda x: x["amount"],
            reverse=True,
        )
        category_data[cat]["top_10"] = sorted_txs[:10]
        by_kw = category_data[cat]["by_keyword"]
        places = [
            {"place": kw, "total": sum(t["amount"] for t in txs), "count": len(txs)}
            for kw, txs in by_kw.items()
        ]
        places.sort(key=lambda p: p["total"], reverse=True)
        category_data[cat]["top_5_places"] = places[:5]

    total_out = statement.total_outcomes
    total_in = statement.total_income

    income_data: dict[str, dict] = {}
    for cat, txs in statement.incomes_by_category.items():
        by_kw: dict[str, list] = {}
        for t in txs:
            tx_dict = {"date": t["date"], "description": t["description"], "amount": t["amount"]}
            kw = extract_keyword(t["description"])
            if kw not in by_kw:
                by_kw[kw] = []
            by_kw[kw].append(tx_dict)
        sorted_txs = sorted(txs, key=lambda x: x["amount"], reverse=True)
        places = [
            {"place": kw, "total": sum(t["amount"] for t in txs), "count": len(txs)}
            for kw, txs in by_kw.items()
        ]
        places.sort(key=lambda p: p["total"], reverse=True)
        income_data[cat] = {
            "total": sum(t["amount"] for t in txs),
            "transactions": txs,
            "by_keyword": by_kw,
            "top_10": [{"date": t["date"], "description": t["description"], "amount": t["amount"]} for t in sorted_txs[:10]],
            "top_5_places": places[:5],
            "is_income": True,
        }

    all_outcome_txs = [
        {"date": t["date"], "description": t["description"], "amount": t["amount"]}
        for cat, txs in statement.outgoings_by_category.items()
        for t in txs
    ]
    outgoings_by_kw: dict[str, list] = {}
    for t in all_outcome_txs:
        tx_dict = {"date": t["date"], "description": t["description"], "amount": t["amount"]}
        kw = extract_keyword(t["description"])
        if kw not in outgoings_by_kw:
            outgoings_by_kw[kw] = []
        outgoings_by_kw[kw].append(tx_dict)
    sorted_outcomes = sorted(all_outcome_txs, key=lambda x: x["amount"], reverse=True)
    places = [
        {"place": kw, "total": sum(t["amount"] for t in txs), "count": len(txs)}
        for kw, txs in outgoings_by_kw.items()
    ]
    places.sort(key=lambda p: p["total"], reverse=True)
    outgoings_data = {
        "Outgoings": {
            "total": total_out,
            "transactions": all_outcome_txs,
            "by_keyword": outgoings_by_kw,
            "top_10": sorted_outcomes[:10],
            "top_5_places": places[:5],
        }
    }

    return {
        "category_data": category_data,
        "income_data": income_data,
        "outgoings_data": outgoings_data,
        "total_income": total_in,
        "total_outcomes": total_out,
        "balance_history": getattr(statement, "balance_history", []),
    }


def run_index():
    """Scan racun folder, parse PDFs, generate index page with month plates."""
    import sys
    import webbrowser

    project_dir = Path(__file__).parent
    racun_dir = project_dir / "racun"
    output_dir = project_dir / "output"

    if not racun_dir.exists():
        racun_dir.mkdir()
        print(f"Created {racun_dir}. Put PDF bank statements there.")
        return

    pdf_files = list(racun_dir.glob("*.pdf")) + list(racun_dir.glob("*.PDF"))
    if not pdf_files:
        print(f"No PDF files in {racun_dir}")
        return

    months_data = []
    seen_keys = set()

    for pdf_path in sorted(pdf_files):
        statement = parse_statement(pdf_path)
        if not statement:
            print(f"Could not parse {pdf_path.name}, skipping")
            continue

        key = statement.month_key
        if key in seen_keys:
            print(f"Duplicate month {key} from {pdf_path.name}, skipping")
            continue
        seen_keys.add(key)

        print(f"Parsing {pdf_path.name} ({key})...")
        analytics = build_visualization_data(statement)
        months_data.append({
            "key": key,
            "year": statement.year,
            "month": statement.month,
            "month_name": MONTH_NAMES.get(statement.month, str(statement.month)),
            "color": get_month_color(statement.month),
            "analytics": analytics,
        })

    if not months_data:
        print("No valid months found.")
        return

    months_data.sort(key=lambda m: (m["year"], m["month"]))

    output_dir.mkdir(exist_ok=True)
    index_path = output_dir / "index.html"
    generate_index_html(months_data, index_path, currency="RSD")
    print(f"Saved: {index_path}")

    open_browser = "--open" in sys.argv or "-o" in sys.argv
    if open_browser:
        webbrowser.open(index_path.as_uri())


def main():
    import sys
    import webbrowser

    if len(sys.argv) < 2 or sys.argv[1].startswith("-"):
        print("Usage: python visualize_spendings.py <path/to/statement.pdf> [--open]")
        return
    pdf_path = Path(sys.argv[1])
    open_browser = "--open" in sys.argv or "-o" in sys.argv

    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}")
        return

    print("Parsing PDF...")
    statement = parse_statement(pdf_path)
    if not statement:
        print("Could not parse PDF")
        return

    print(f"Parsed {len(statement.incomes) + sum(len(t) for t in statement.outgoings_by_category.values())} transactions")

    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    all_txs = []
    for t in statement.incomes:
        cat = t.get("category", "Income")
        all_txs.append((t["date"], t["description"], t["amount"], "Income", cat))
    for cat, txs in statement.outgoings_by_category.items():
        for t in txs:
            all_txs.append((t["date"], t["description"], t["amount"], "Outcome", cat))

    csv_path = output_dir / "transactions.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Date", "Description", "Amount", "Type", "Category"])
        for row in all_txs:
            w.writerow([row[0], row[1], f"{row[2]:.2f}", row[3], row[4]])
    print(f"Saved: {csv_path}")

    viz_data = build_visualization_data(statement)

    html_path = output_dir / "spending_visualization.html"
    generate_html(
        viz_data["category_data"],
        html_path,
        currency="RSD",
        income_data=viz_data["income_data"],
        outgoings_data=viz_data["outgoings_data"],
        total_income=viz_data["total_income"],
        total_outcomes=viz_data["total_outcomes"],
        balance_history=viz_data.get("balance_history", []),
    )
    print(f"Saved: {html_path}")
    if open_browser:
        webbrowser.open(html_path.as_uri())

    print(f"\nSummary:")
    print(f"  Total outcomes: {statement.total_outcomes:,.2f} RSD")
    print(f"  Total incomes:  {statement.total_income:,.2f} RSD")
    print(f"  Incomes by category: {dict((c, sum(t['amount'] for t in txs)) for c, txs in statement.incomes_by_category.items())}")
    print(f"  Outgoings by category: {dict((c, sum(t['amount'] for t in txs)) for c, txs in statement.outgoings_by_category.items())}")


if __name__ == "__main__":
    import sys

    if "--index" in sys.argv or "-i" in sys.argv:
        run_index()
    else:
        main()
