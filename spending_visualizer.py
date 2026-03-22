"""
Interactive HTML Spending Visualizer.

Receives a map: category -> {total, transactions, by_keyword, top_3}
Generates a clickable HTML page. Click a chart segment to see a detail page with:
- Grouped by keyword
- Top 3 spendings
- Back button to return
"""

from pathlib import Path
import json
from typing import Any


def generate_html(
    category_data: dict[str, dict[str, Any]],
    output_path: str | Path,
    currency: str = "RSD",
    income_data: dict[str, Any] | None = None,
    outgoings_data: dict[str, Any] | None = None,
    total_income: float = 0,
    total_outcomes: float = 0,
    balance_history: list[dict] | None = None,
) -> None:
    """
    Generate interactive HTML spending visualization.

    Args:
        category_data: Spending categories (Grocery, Health, etc.) - Incomes excluded
        income_data: {"Incomes": {total, transactions, by_keyword, top_3}} for clickable Incomes
        total_income: Total income amount
        total_outcomes: Total spending amount
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    spending_labels = list(category_data.keys())
    spending_totals = [category_data[cat]["total"] for cat in spending_labels]
    spending_colors = ["#2ecc71", "#3498db", "#e74c3c", "#9b59b6", "#95a5a6", "#f39c12"]

    # Build details: spending categories + Incomes (if any)
    details_by_category = {}
    for cat in spending_labels:
        data = category_data[cat]
        details_by_category[cat] = {
            "total": data["total"],
            "transactions": data.get("transactions", []),
            "by_keyword": data.get("by_keyword", {}),
            "top_10": data.get("top_10", []),
            "top_5_places": data.get("top_5_places", []),
            "is_income": False,
        }
    if income_data:
        all_inc_txs = []
        by_kw_agg: dict = {}
        for inc_data in income_data.values():
            all_inc_txs.extend(inc_data.get("transactions", []))
            for kw, txs in inc_data.get("by_keyword", {}).items():
                by_kw_agg.setdefault(kw, []).extend(txs)
        sorted_inc = sorted(all_inc_txs, key=lambda x: x["amount"], reverse=True)
        inc_places = [
            {"place": kw, "total": sum(t["amount"] for t in txs), "count": len(txs)}
            for kw, txs in by_kw_agg.items()
        ]
        inc_places.sort(key=lambda p: p["total"], reverse=True)
        details_by_category["Incomes"] = {
            "total": total_income,
            "transactions": all_inc_txs,
            "by_keyword": by_kw_agg,
            "top_10": sorted_inc[:10],
            "top_5_places": inc_places[:5],
            "is_income": True,
        }
        for inc_cat, inc_data in income_data.items():
            details_by_category[inc_cat] = {
                **inc_data,
                "is_income": True,
            }
    if outgoings_data and "Outgoings" in outgoings_data:
        details_by_category["Outgoings"] = {
            **outgoings_data["Outgoings"],
            "is_income": False,
        }

    savings = total_income - total_outcomes

    html = _build_html(
        spending_labels=spending_labels,
        spending_totals=spending_totals,
        spending_colors=spending_colors[: len(spending_labels)],
        details_by_category=details_by_category,
        currency=currency,
        total_income=total_income,
        total_outcomes=total_outcomes,
        savings=savings,
        balance_history=balance_history or [],
    )

    output_path.write_text(html, encoding="utf-8")


def get_analytics_embedded_html(currency: str = "RSD") -> str:
    """
    Return the analytics view HTML for embedding in index page.
    Expects window.analyticsData to be set with {category_data, income_data, outgoings_data, total_income, total_outcomes}.
    Call initAnalyticsCharts() after injecting to initialize.
    """
    # This is a minimal template - the actual init is in the index's initCharts which builds from combined data
    return """<div id="analyticsRoot">
    <h1>Spending Overview</h1>
    <div class="savings-summary"><span class="savings-label">Savings:</span><span class="savings-value" id="savingsValue">0</span><span class="savings-currency">""" + currency + """</span></div>
    <div class="charts">
        <div class="chart-container"><h3>Incomes vs Outgoings</h3><div class="chart-wrapper"><canvas id="ioPieChart"></canvas></div></div>
        <div class="chart-container"><h3>Spending by Category</h3><div class="chart-wrapper"><canvas id="pieChart"></canvas></div></div>
        <div class="chart-container"><h3>Spending Totals</h3><div class="chart-wrapper"><canvas id="barChart"></canvas></div></div>
    </div>
    <div class="category-buttons"><p class="category-hint">Or click a category:</p><div class="category-btn-wrap" id="catButtonsWrap"></div></div>
</div>
<div id="detailView" class="detail-view">
    <button class="back-btn" onclick="analyticsGoBack()">← Back</button>
    <div class="detail-header"><h2 id="detailTitle">Category</h2><div class="total" id="detailTotal"></div></div>
    <div class="section"><h3 id="top3Title">Top 3 Spendings</h3><ul class="top3-list" id="top3List"></ul></div>
    <div class="section"><h3>Grouped by Keyword</h3><div id="byKeywordContent"></div></div>
</div>"""


def _category_buttons(
    labels: list[str], colors: list[str], income_categories: list[str] | None = None
) -> str:
    """Generate clickable category buttons HTML."""
    parts = []
    if income_categories:
        inc_colors = ["#27ae60", "#1abc9c", "#16a085"]
        for i, inc_cat in enumerate(income_categories):
            color = inc_colors[i % len(inc_colors)]
            parts.append(
                f'<button class="cat-btn" data-category="{inc_cat}" '
                f'style="--cat-color: {color}">{inc_cat}</button>'
            )
    for i, label in enumerate(labels):
        color = colors[i] if i < len(colors) else "#95a5a6"
        parts.append(
            f'<button class="cat-btn" data-category="{label}" '
            f'style="--cat-color: {color}">{label}</button>'
        )
    return "\n".join(parts)


def _build_html(
    spending_labels: list[str],
    spending_totals: list[float],
    spending_colors: list[str],
    details_by_category: dict[str, dict],
    currency: str,
    total_income: float = 0,
    total_outcomes: float = 0,
    savings: float = 0,
    balance_history: list[dict] | None = None,
) -> str:
    details_json = json.dumps(details_by_category, ensure_ascii=False)
    balance_history = balance_history or []
    balance_json = json.dumps(balance_history)
    income_cats = [
        c for c in details_by_category
        if details_by_category.get(c, {}).get("is_income") and c != "Incomes"
    ]
    category_buttons_html = _category_buttons(
        spending_labels, spending_colors[: len(spending_labels)], income_categories=income_cats
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Spending Visualizer</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js"></script>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', system-ui, sans-serif;
            margin: 0;
            padding: 2rem;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            color: #e8e8e8;
        }}
        h1 {{
            text-align: center;
            margin-bottom: 1rem;
            font-weight: 300;
            letter-spacing: 0.05em;
        }}
        .savings-summary {{
            text-align: center;
            margin-bottom: 1.5rem;
            padding: 0.75rem 1.5rem;
            background: rgba(255,255,255,0.06);
            border-radius: 10px;
            display: inline-block;
            margin-left: 50%;
            transform: translateX(-50%);
        }}
        .savings-label {{
            margin-right: 0.5rem;
            opacity: 0.9;
        }}
        .savings-value {{
            font-size: 1.25rem;
            font-weight: 600;
        }}
        .savings-value.positive {{ color: #2ecc71; }}
        .savings-value.negative {{ color: #e74c3c; }}
        .savings-currency {{
            margin-left: 0.25rem;
            opacity: 0.8;
        }}
        .charts {{
            display: flex;
            flex-wrap: wrap;
            gap: 2rem;
            justify-content: center;
            margin-bottom: 2rem;
        }}
        .chart-container {{
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 1.5rem;
            max-width: 450px;
            cursor: pointer;
        }}
        .chart-container.balance-chart {{
            max-width: 100%;
            width: 100%;
            cursor: default;
        }}
        .chart-container.balance-chart .chart-wrapper {{
            height: 220px;
        }}
        .chart-container:hover {{
            transform: scale(1.02);
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }}
        .chart-container h3 {{
            margin: 0 0 1rem 0;
            font-size: 1rem;
            font-weight: 500;
            opacity: 0.9;
        }}
        .chart-wrapper {{
            position: relative;
            height: 280px;
        }}
        #mainView {{ display: block; }}
        #detailView {{ display: none; }}
        #detailView.visible {{ display: block; }}
        #mainView.hidden {{ display: none; }}
        .back-btn {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.6rem 1.2rem;
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 8px;
            color: #e8e8e8;
            font-size: 0.95rem;
            cursor: pointer;
            margin-bottom: 1.5rem;
            transition: background 0.2s;
        }}
        .back-btn:hover {{
            background: rgba(255,255,255,0.15);
        }}
        .detail-header {{
            margin-bottom: 2rem;
        }}
        .detail-header h2 {{
            margin: 0;
            font-size: 1.5rem;
            font-weight: 400;
        }}
        .detail-header .total {{
            margin-top: 0.25rem;
            opacity: 0.8;
            font-size: 1rem;
        }}
        .section {{
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 1.25rem 1.5rem;
            margin-bottom: 1.5rem;
        }}
        .section h3 {{
            margin: 0 0 1rem 0;
            font-size: 1rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            opacity: 0.7;
        }}
        .keyword-group {{
            margin-bottom: 1rem;
        }}
        .keyword-group:last-child {{ margin-bottom: 0; }}
        .keyword-name {{
            font-weight: 500;
            margin-bottom: 0.5rem;
            padding-bottom: 0.25rem;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        .keyword-total {{
            font-size: 0.85rem;
            opacity: 0.7;
            margin-bottom: 0.5rem;
        }}
        .tx-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
        }}
        .tx-table th {{
            text-align: left;
            padding: 0.5rem 0.5rem 0.25rem;
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            opacity: 0.6;
        }}
        .tx-table td {{
            padding: 0.4rem 0.5rem;
            border-top: 1px solid rgba(255,255,255,0.06);
        }}
        .tx-table tr:hover td {{
            background: rgba(255,255,255,0.03);
        }}
        .tx-amount {{
            text-align: right;
            font-variant-numeric: tabular-nums;
        }}
        .top3-list {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}
        .top3-list li {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.75rem 0;
            border-bottom: 1px solid rgba(255,255,255,0.06);
        }}
        .top3-list li:last-child {{
            border-bottom: none;
        }}
        .top3-desc {{
            flex: 1;
            margin-right: 1rem;
        }}
        .top3-amount {{
            font-variant-numeric: tabular-nums;
            font-weight: 500;
        }}
        .top3-badge {{
            display: inline-block;
            width: 1.5rem;
            height: 1.5rem;
            line-height: 1.5rem;
            text-align: center;
            background: rgba(46, 204, 113, 0.3);
            border-radius: 4px;
            font-size: 0.75rem;
            margin-right: 0.5rem;
        }}
        .top5-places-list {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}
        .top5-places-list li {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.6rem 0;
            border-bottom: 1px solid rgba(255,255,255,0.06);
        }}
        .top5-places-list li:last-child {{ border-bottom: none; }}
        .pct-badge {{
            display: inline-block;
            margin-left: 0.5rem;
            padding: 0.15rem 0.4rem;
            background: rgba(255,255,255,0.1);
            border-radius: 4px;
            font-size: 0.8rem;
            opacity: 0.9;
        }}
        .place-details-list details {{
            margin-bottom: 0.5rem;
            background: rgba(255,255,255,0.05);
            border-radius: 8px;
            overflow: hidden;
        }}
        .place-details-list details summary {{
            padding: 0.6rem 1rem;
            cursor: pointer;
            font-weight: 500;
            list-style: none;
        }}
        .place-details-list details summary::-webkit-details-marker {{ display: none; }}
        .place-details-list details summary::before {{
            content: '▶';
            display: inline-block;
            margin-right: 0.5rem;
            font-size: 0.7rem;
            transition: transform 0.2s;
        }}
        .place-details-list details[open] summary::before {{ transform: rotate(90deg); }}
        .place-details-list details ul {{
            list-style: none;
            padding: 0 1rem 1rem;
            margin: 0;
            border-top: 1px solid rgba(255,255,255,0.06);
        }}
        .place-details-list details li {{
            display: flex;
            justify-content: space-between;
            padding: 0.4rem 0;
            border-bottom: 1px solid rgba(255,255,255,0.04);
            font-size: 0.9rem;
        }}
        .category-buttons {{
            margin-top: 2rem;
            text-align: center;
        }}
        .category-hint {{
            margin: 0 0 0.75rem 0;
            font-size: 0.9rem;
            opacity: 0.8;
        }}
        .category-btn-wrap {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem;
            justify-content: center;
        }}
        .cat-btn {{
            padding: 0.6rem 1.25rem;
            background: rgba(255,255,255,0.08);
            border: 1px solid var(--cat-color, rgba(255,255,255,0.3));
            border-radius: 8px;
            color: #e8e8e8;
            font-size: 0.95rem;
            cursor: pointer;
            transition: background 0.2s, transform 0.2s;
        }}
        .cat-btn:hover {{
            background: rgba(255,255,255,0.15);
            transform: scale(1.05);
        }}
    </style>
</head>
<body>
    <div id="mainView">
        <h1>Spending Overview</h1>
        <div class="savings-summary">
            <span class="savings-label">Savings:</span>
            <span class="savings-value" id="savingsValue">0</span>
            <span class="savings-currency">{currency}</span>
        </div>
        <div class="charts">
            <div class="chart-container" id="io-pie-container">
                <h3>Incomes vs Outgoings (click segment)</h3>
                <div class="chart-wrapper">
                    <canvas id="ioPieChart"></canvas>
                </div>
            </div>
            <div class="chart-container" id="pie-container">
                <h3>Spending by Category (click segment)</h3>
                <div class="chart-wrapper">
                    <canvas id="pieChart"></canvas>
                </div>
            </div>
            <div class="chart-container" id="bar-container">
                <h3>Spending Totals (click bar)</h3>
                <div class="chart-wrapper">
                    <canvas id="barChart"></canvas>
                </div>
            </div>
            <div class="chart-container balance-chart">
                <h3>Account Balance Over Time</h3>
                <div class="chart-wrapper">
                    <canvas id="balanceLineChart"></canvas>
                </div>
            </div>
        </div>
        <div class="category-buttons">
            <p class="category-hint">Or click a category:</p>
            <div class="category-btn-wrap">
                {category_buttons_html}
            </div>
        </div>
    </div>

    <div id="detailView">
        <button class="back-btn" onclick="goBack()">← Back</button>
        <div class="detail-header">
            <h2 id="detailTitle">Category</h2>
            <div class="total" id="detailTotal"></div>
        </div>
        <div class="section">
            <h3 id="top5Title">Top 5 Places</h3>
            <ul class="top5-places-list" id="top5PlacesList"></ul>
        </div>
        <div class="section">
            <h3 id="top10Title">Top 10 Spendings</h3>
            <ul class="top5-places-list" id="top10List"></ul>
        </div>
        <div class="section">
            <h3>Browse by Place</h3>
            <div id="placeDetailsList" class="place-details-list"></div>
        </div>
    </div>

    <script>
        const detailsByCategory = {details_json};
        const currency = "{currency}";
        const totalIncome = {total_income};
        const totalOutcomes = {total_outcomes};
        const savings = {savings};
        const spendingLabels = {json.dumps(spending_labels)};
        const spendingTotals = {json.dumps(spending_totals)};
        const spendingColors = {json.dumps(spending_colors[: len(spending_labels)])};
        const balanceHistory = {balance_json};

        const savingsEl = document.getElementById('savingsValue');
        savingsEl.textContent = savings.toLocaleString();
        savingsEl.classList.add(savings >= 0 ? 'positive' : 'negative');

        const ioPieCtx = document.getElementById('ioPieChart').getContext('2d');
        const ioTotal = totalIncome + totalOutcomes;
        const ioData = ioTotal > 0
            ? [Math.max(0, totalIncome), Math.max(0, totalOutcomes)]
            : [1, 1];
        const ioPieChart = new Chart(ioPieCtx, {{
            type: 'doughnut',
            data: {{
                labels: ['Incomes', 'Outgoings'],
                datasets: [{{
                    data: ioData,
                    backgroundColor: ['#27ae60', '#e74c3c'],
                    borderWidth: 2,
                    borderColor: '#1a1a2e',
                    hoverBorderWidth: 3
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                interaction: {{ mode: 'point', intersect: true }},
                plugins: {{
                    legend: {{ position: 'bottom' }},
                    tooltip: {{
                        callbacks: {{
                            label: (ctx) => {{
                                const total = ioTotal || 1;
                                const val = ctx.raw;
                                const pct = total > 0 ? ((val / total) * 100).toFixed(1) : 0;
                                const amt = ctx.index === 0 ? totalIncome : totalOutcomes;
                                return `${{ctx.label}}: ${{amt.toLocaleString()}} ${{currency}} (${{pct}}%)`;
                            }}
                        }}
                    }}
                }},
                onClick: (evt, elements) => {{
                    if (elements.length) {{
                        const cat = elements[0].index === 0 ? 'Incomes' : 'Outgoings';
                        if (detailsByCategory[cat]) showDetails(cat);
                    }}
                }}
            }}
        }});

        const pieCtx = document.getElementById('pieChart').getContext('2d');
        const pieChart = new Chart(pieCtx, {{
            type: 'doughnut',
            data: {{
                labels: spendingLabels,
                datasets: [{{
                    data: spendingTotals,
                    backgroundColor: spendingColors,
                    borderWidth: 2,
                    borderColor: '#1a1a2e',
                    hoverBorderWidth: 3
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                interaction: {{ mode: 'point', intersect: true }},
                plugins: {{
                    legend: {{ position: 'bottom' }},
                    tooltip: {{
                        callbacks: {{
                            label: (ctx) => {{
                                const total = ctx.dataset.data.reduce((a,b) => a+b, 0);
                                const pct = ((ctx.raw / total) * 100).toFixed(1);
                                return `${{ctx.label}}: ${{ctx.raw.toLocaleString()}} ${{currency}} (${{pct}}%)`;
                            }}
                        }}
                    }}
                }},
                onClick: (evt, elements) => {{
                    if (elements.length) showDetails(spendingLabels[elements[0].index]);
                }}
            }}
        }});

        const barCtx = document.getElementById('barChart').getContext('2d');
        const barChart = new Chart(barCtx, {{
            type: 'bar',
            data: {{
                labels: spendingLabels,
                datasets: [{{
                    data: spendingTotals,
                    backgroundColor: spendingColors,
                    borderWidth: 0
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                interaction: {{ mode: 'point', intersect: true }},
                plugins: {{
                    legend: {{ display: false }},
                    tooltip: {{
                        callbacks: {{
                            label: (ctx) => `${{ctx.raw.toLocaleString()}} ${{currency}}`
                        }}
                    }}
                }},
                scales: {{
                    x: {{
                        ticks: {{ color: '#aaa' }},
                        grid: {{ color: 'rgba(255,255,255,0.05)' }}
                    }},
                    y: {{
                        ticks: {{ color: '#aaa' }},
                        grid: {{ display: false }}
                    }}
                }},
                onClick: (evt, elements) => {{
                    if (elements.length) showDetails(spendingLabels[elements[0].index]);
                }}
            }}
        }});

        const balanceChartContainer = document.querySelector('.chart-container.balance-chart');
        if (balanceHistory.length === 0 && balanceChartContainer) {{
            balanceChartContainer.style.display = 'none';
        }}
        const balanceCtx = document.getElementById('balanceLineChart');
        if (balanceCtx && balanceHistory.length > 0) {{
            const balLabels = balanceHistory.map(p => p.date);
            const balData = balanceHistory.map(p => p.balance);
            new Chart(balanceCtx.getContext('2d'), {{
                type: 'line',
                data: {{
                    labels: balLabels,
                    datasets: [{{
                        label: 'Balance (' + currency + ')',
                        data: balData,
                        borderColor: '#3498db',
                        backgroundColor: 'rgba(52, 152, 219, 0.1)',
                        fill: true,
                        tension: 0.2
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ display: false }},
                        tooltip: {{
                            callbacks: {{
                                label: (ctx) => ctx.raw.toLocaleString() + ' ' + currency
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{
                            ticks: {{ color: '#aaa', maxRotation: 45 }},
                            grid: {{ color: 'rgba(255,255,255,0.05)' }}
                        }},
                        y: {{
                            ticks: {{ color: '#aaa' }},
                            grid: {{ color: 'rgba(255,255,255,0.05)' }}
                        }}
                    }}
                }}
            }});
        }}

        function showDetails(category) {{
            const data = detailsByCategory[category] || {{}};
            const total = data.total || 0;
            const top10 = data.top_10 || [];
            const top5Places = data.top_5_places || [];
            const byKeyword = data.by_keyword || {{}};
            const isIncome = data.is_income || false;

            document.getElementById('detailTitle').textContent = category;
            document.getElementById('top5Title').textContent = isIncome ? 'Top 5 Income Sources' : 'Top 5 Places';
            document.getElementById('top10Title').textContent = isIncome ? 'Top 10 Incomes' : 'Top 10 Spendings';
            document.getElementById('detailTotal').textContent =
                `Total: ${{total.toLocaleString()}} ${{currency}}`;

            const top5List = document.getElementById('top5PlacesList');
            if (top5Places.length) {{
                const pctBase = total || 1;
                top5List.innerHTML = top5Places.map((p, i) => {{
                    const pct = ((p.total / pctBase) * 100).toFixed(1);
                    return `
                    <li>
                        <span><span class="top3-badge">${{i+1}}</span>${{escapeHtml(p.place)}}</span>
                        <span class="top3-amount">${{p.total.toLocaleString()}} ${{currency}} <span class="pct-badge">${{pct}}%</span></span>
                    </li>
                `;
                }}).join('');
            }} else {{
                top5List.innerHTML = '<li>No data</li>';
            }}

            const top10List = document.getElementById('top10List');
            if (top10.length) {{
                const pctBase = total || 1;
                top10List.innerHTML = top10.map((t, i) => {{
                    const pct = ((t.amount / pctBase) * 100).toFixed(1);
                    return `
                    <li>
                        <span><span class="top3-badge">${{i+1}}</span>${{escapeHtml(t.description)}}</span>
                        <span class="top3-amount">${{t.amount.toLocaleString()}} ${{currency}} <span class="pct-badge">${{pct}}%</span></span>
                    </li>
                `;
                }}).join('');
            }} else {{
                top10List.innerHTML = '<li>No transactions</li>';
            }}

            const placeList = document.getElementById('placeDetailsList');
            const kwEntries = Object.entries(byKeyword).sort((a, b) => {{
                const sumA = a[1].reduce((s, t) => s + t.amount, 0);
                const sumB = b[1].reduce((s, t) => s + t.amount, 0);
                return sumB - sumA;
            }});
            placeList.innerHTML = kwEntries.map(([kw, txs]) => {{
                const kwTotal = txs.reduce((s, t) => s + t.amount, 0);
                const sorted = txs.slice().sort((a, b) => b.amount - a.amount);
                return `
                    <details>
                        <summary>${{escapeHtml(kw)}} - ${{kwTotal.toLocaleString()}} ${{currency}} (${{txs.length}} times)</summary>
                        <ul>${{sorted.map(t => `
                            <li><span>${{t.date}} ${{escapeHtml(t.description)}}</span><span class="tx-amount">${{t.amount.toLocaleString()}} ${{currency}}</span></li>
                        `).join('')}}</ul>
                    </details>
                `;
            }}).join('');

            document.getElementById('mainView').classList.add('hidden');
            document.getElementById('detailView').classList.add('visible');
            history.pushState({{ category }}, '', '#${{category}}');
        }}

        function goBack() {{
            document.getElementById('detailView').classList.remove('visible');
            document.getElementById('mainView').classList.remove('hidden');
            history.back();
        }}

        function escapeHtml(s) {{
            const div = document.createElement('div');
            div.textContent = s;
            return div.innerHTML;
        }}

        window.addEventListener('popstate', (e) => {{
            if (!e.state || !e.state.category) {{
                document.getElementById('detailView').classList.remove('visible');
                document.getElementById('mainView').classList.remove('hidden');
            }}
        }});

        document.querySelectorAll('.cat-btn').forEach(btn => {{
            btn.addEventListener('click', () => showDetails(btn.dataset.category));
        }});
    </script>
</body>
</html>"""
