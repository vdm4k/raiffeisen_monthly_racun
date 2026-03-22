# Raiffeisen Monthly Statement Parser

A Python tool that parses Raiffeisen bank statement PDFs and generates interactive HTML spending dashboards.

## Features

- Parses Raiffeisen bank statement PDFs (Serbian RSD accounts)
- Auto-categorizes transactions (Grocery, Health, Clothes, Restaurants, Travel, etc.)
- Generates interactive HTML dashboards with Chart.js charts
- Multi-month index view with seasonal color coding
- Exports transactions to CSV
- Balance history visualization
- Merchant/place frequency analysis

## Usage

### 1. Put your statements in the `racun` folder

```
raiffeisen_monthly_racun_parser/
└── racun/
    ├── statement-january.PDF
    ├── statement-february.PDF
    └── ...
```

### 2. Run

**Linux:**
```bash
./run.sh
```

**macOS:** double-click `run.command` in Finder, or from terminal:
```bash
./run.command
```

**Windows:** double-click `run.bat`, or from command prompt:
```bat
run.bat
```

The script will automatically create a virtual environment, install dependencies, and open the result in your browser.

This generates `output/index.html` — a month grid where you can select one or more months and explore spending by category and merchant.

---

### Single PDF (quick mode)

```bash
python visualize_spendings.py racun/statement.PDF --open
```

Output: `output/spending_visualization.html` and `output/transactions.csv`.

### Run Tests

```bash
python -m unittest tests/test_pdf_parser.py -v
```

## Project Structure

```
raiffeisen_monthly_racun_parser/
├── racun/                   # Put your PDF bank statements here (gitignored)
├── output/                  # Generated files — HTML, CSV (gitignored)
├── categories.json          # Spending categories and keywords — edit to add new ones
├── categories.py            # Loads categories.json, exposes categorize()
├── pdf_parser.py            # PDF extraction and transaction parsing
├── spending_visualizer.py   # Single-month HTML dashboard generator
├── index_generator.py       # Multi-month index page generator
├── index_template.html      # Base HTML template for index page
├── visualize_spendings.py   # Entry point / orchestration
├── tests/
│   └── test_pdf_parser.py
└── requirements.txt
```

## Adding or Editing Categories

Edit `categories.json` — no code changes needed. Order matters: first matching category wins.

```json
{
  "Entertainment": ["bioskop", "cineplexx", "netflix"],
  "Grocery": ["lidl", "maxi", "..."]
}
```

## Transaction Categories

| Category    | Examples                                  |
|-------------|-------------------------------------------|
| Grocery     | Lidl, Maxi, Univerexport, DM, Vero        |
| Health      | Apoteka, Lilly, DrMax, Osiguranje         |
| Clothes     | H&M, Nike, Zara, Calvin Klein, Decathlon  |
| Gadgets     | iStyle, Gigatron                          |
| Phone       | Yettel, SBB                               |
| Utilities   | Gas, EPS, Informatika                     |
| Restaurants | Tramontana, Tokio Sushi                   |
| Travel      | Hotel, Rent a Car, Resort                 |
| Mobile kesh | Mobile cash withdrawals                   |
| Other       | Everything else                           |

## Output

- **output/index.html** — Multi-month overview grid with seasonal colors; select months to view combined analytics
- **output/spending_visualization.html** — Single-month interactive dashboard (pie, doughnut, bar, line charts; click to drill down by category and merchant)
- **output/transactions.csv** — Flat export with columns: Date, Description, Amount, Type, Category
