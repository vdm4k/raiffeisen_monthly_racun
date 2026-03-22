"""
PDF Parser for Raiffeisen bank statements.

Receives path to a PDF file and returns ParsedStatement or PdfDescription with:
- Month (year, month)
- Incomes
- Outgoings by category
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pdfplumber

from categories import categorize, categorize_income


@dataclass(frozen=True)
class TransactionRecord:
    """Single transaction: date, description, money (amount)."""

    date: str
    description: str
    money: float


@dataclass
class PdfDescription:
    """Parsed bank statement with core fields."""

    valuta: str  # RSD or EUR
    date: str  # Statement date range e.g. "01.11.2025 - 30.11.2025"
    racun_number: str  # 15+ digit account number
    incomes: set[TransactionRecord] = field(default_factory=set)
    outgoings: set[TransactionRecord] = field(default_factory=set)


@dataclass
class ParsedStatement:
    """Result of parsing a bank statement PDF."""

    year: int
    month: int
    month_key: str  # e.g. "2026-01"
    incomes: list[dict]  # [{"date", "description", "amount"}, ...]
    incomes_by_category: dict[str, list[dict]]  # {"Income": [...], "Mobile kesh": [...], ...}
    outgoings_by_category: dict[str, list[dict]]  # {"Grocery": [...], "Health": [...], ...}
    balance_history: list[dict]  # [{"date", "balance"}, ...] - account balance over time

    @property
    def total_income(self) -> float:
        return sum(t["amount"] for t in self.incomes)

    @property
    def total_outcomes(self) -> float:
        return sum(
            t["amount"]
            for txs in self.outgoings_by_category.values()
            for t in txs
        )


def parse_amount(text: str) -> Optional[float]:
    if not text:
        return None
    cleaned = re.sub(r"[^\d.,]", "", text).replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _read_pdf_text(pdf_path: str) -> str:
    """Read all PDF pages and return as a single normalized whitespace-separated string."""
    with pdfplumber.open(pdf_path) as pdf:
        lines = []
        for page in pdf.pages:
            lines.extend((page.extract_text() or "").split("\n"))
    return re.sub(r" {2,}", " ", " ".join(lines)).strip()


def _extract_zaduzhenje_payee(text_after: str) -> str | None:
    """
    Extract payee from 'na Rn: ACCOUNT-PAYEE' in normalized single-line text.
    Example: 'na Rn: 200342595010100162-Novi Sad - Gas d.o.o. Kurs: ...'
             -> 'Novi Sad - Gas'
    """
    m = re.search(
        r"na Rn:\s*\d+-(.{3,60}?)(?:\s+d\.o\.o|\s+Kurs:|\s+Za |\s+\d{2}\.\d{2}\.\d{4})",
        text_after,
    )
    if not m:
        return None
    payee = m.group(1).strip(" -")
    return payee[:60] if payee else None


def extract_keyword(description: str) -> str:
    """Extract merchant/keyword from transaction description for grouping."""
    skip = {"srb", "novi", "sad", "rs", "rn:", "na", "doo", "ad", "beograd"}
    parts = re.sub(r"[,.]", " ", description).split()
    for p in parts:
        p_clean = p.strip(".-")
        if not p_clean or p_clean.lower() in skip or p_clean.isdigit():
            continue
        if len(p_clean) >= 2 and p_clean[0].isalpha():
            return p_clean
    if parts:
        return parts[0][:20] if parts[0] else "Other"
    return "Other"


def _extract_header(pdf_path: str) -> tuple[str, str, str] | None:
    """Extract (valuta, date_range, racun_number) from PDF first page."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = (pdf.pages[0].extract_text() or "")[:800]
        valuta = "RSD"
        if m := re.search(r"Valuta:\s*(\w+)", text, re.IGNORECASE):
            valuta = m.group(1).upper()
        date_range = ""
        if m := re.search(r"[Oo]d\s+(\d{2}\.\d{2}\.\d{4})\s+do\s+(\d{2}\.\d{2}\.\d{4})", text):
            date_range = f"{m.group(1)} - {m.group(2)}"
        racun = ""
        if m := re.search(r"(?:Izvod po tekućem računu broj|Izvod po deviznom računu broj)[^\d]*\n(?:Izvod broj:[^\n]+\n)?(\d{15,})", text, re.IGNORECASE | re.DOTALL):
            racun = m.group(1).strip()
        if not racun and (m := re.search(r"\n(\d{15,})\s*\n", text)):
            racun = m.group(1).strip()
        if racun and valuta:
            return (valuta, date_range, racun)
    except Exception:
        pass
    return None


def extract_date_range(pdf_path: str) -> tuple[int, int] | None:
    """Extract (year, month) from PDF. Looks for 'Od DD.MM.YYYY do DD.MM.YYYY'."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = (pdf.pages[0].extract_text() or "")[:500]
        m = re.search(
            r"[Oo]d\s+(\d{2})\.(\d{2})\.(\d{4})\s+do\s+\d{2}\.\d{2}\.\d{4}",
            text,
            re.IGNORECASE,
        )
        if m:
            day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return (year, month)
    except Exception:
        pass
    return None


def _parse_pdf_simple(full_text: str) -> tuple[list[dict], list[dict]]:
    """
    Parse Raiffeisen statement from normalized single-line text.
    Returns (incomes, outcomes).

    full_text must come from _read_pdf_text() — all newlines collapsed to spaces.
    Patterns work without re.DOTALL since there are no newlines to span.
    """
    incomes: list[dict] = []
    outcomes: list[dict] = []
    seen: set[tuple] = set()

    def _clean_desc(raw: str) -> str:
        s = re.sub(r"\s+", " ", raw.strip())
        s = re.sub(r"\s+0\.00\s+[\d,]+\.\d{2}$", "", s)
        return s[:80]

    def _valid_desc(desc: str) -> bool:
        if not desc or len(desc) < 2:
            return False
        if "Datum" in desc or "izvršenja" in desc or "Opis" in desc:
            return False
        if "Kurs" in desc or re.search(r"\d{1,3},\d{3}\.\d{2}", desc):
            return False
        return True

    def add_outcome(exec_date: str, desc: str, amt: float):
        key = (exec_date, desc[:40], round(amt, 2))
        if key in seen:
            return
        seen.add(key)
        outcomes.append({"date": exec_date, "description": desc, "amount": amt, "category": categorize(desc)})

    def add_income(exec_date: str, desc: str, amt: float):
        key = (exec_date, desc[:40], round(amt, 2))
        if key in seen:
            return
        seen.add(key)
        incomes.append({"date": exec_date, "description": desc, "amount": amt, "category": categorize_income(desc)})

    # Card transactions: date date 9374 desc ... RSD isplata uplata balance
    card_pattern = re.compile(
        r"(\d{2}\.\d{2}\.\d{4})\s+(\d{2}\.\d{2}\.\d{4})\s+9374\s+(.+?)\s+(?:RSD|USD|EUR)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+[\d,]+\.\d{2}"
    )

    # Devizni / non-card: date date desc 0.00 0.00 isplata uplata balance
    devizni_pattern = re.compile(
        r"(\d{2}\.\d{2}\.\d{4})\s+(\d{2}\.\d{2}\.\d{4})\s+(.+?)\s+0\.00\s+0\.00\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+[\d,]+\.\d{2}"
    )

    for pattern, max_card, max_devizni in (
        (card_pattern, 400_000, None),
        (devizni_pattern, None, 500_000),
    ):
        for m in pattern.finditer(full_text):
            exec_date, desc_raw, isplata_str, uplata_str = m.group(2), m.group(3), m.group(4), m.group(5)
            desc = _clean_desc(desc_raw)
            if not _valid_desc(desc):
                continue
            isplata = parse_amount(isplata_str)
            uplata = parse_amount(uplata_str)
            limit = max_card if pattern is card_pattern else max_devizni
            if uplata and uplata > 0:
                if uplata <= 50_000_000:
                    add_income(exec_date, desc, uplata)
            elif isplata and isplata > 0:
                if limit is None or isplata <= limit:
                    add_outcome(exec_date, desc, isplata)

    # Zaduženje / Unovcavanje: date date desc 0.00 amount 0.00 balance
    transfer_pattern = re.compile(
        r"(\d{2}\.\d{2}\.\d{4})\s+(\d{2}\.\d{2}\.\d{4})\s+(Zaduženje[^0-9]+?|Unovcavanje[^0-9]+?)\s+0\.00\s+([\d,]+\.\d{2})\s+0\.00\s+([\d,]+\.\d{2})"
    )
    for m in transfer_pattern.finditer(full_text):
        exec_date, desc_raw, amt_str = m.group(2), m.group(3), m.group(4)
        amt = parse_amount(amt_str)
        if not amt or amt <= 0 or amt > 500_000:
            continue
        if "Zaduženje" in desc_raw:
            payee = _extract_zaduzhenje_payee(full_text[m.end(): m.end() + 400])
            desc = payee if payee else _clean_desc(desc_raw)
        else:
            desc = _clean_desc(desc_raw)
        add_outcome(exec_date, desc, amt)

    # Odobrenje (IPP) — income: date date desc 0.00 0.00 uplata balance
    odobrenje_pattern = re.compile(
        r"(\d{2}\.\d{2}\.\d{4})\s+(\d{2}\.\d{2}\.\d{4})\s+(Odobrenje[^0-9]+?)0\.00\s+0\.00\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})"
    )
    for m in odobrenje_pattern.finditer(full_text):
        exec_date, desc_raw, amt_str = m.group(2), m.group(3), m.group(4)
        desc = _clean_desc(desc_raw)
        amt = parse_amount(amt_str)
        if not amt or amt <= 0 or amt > 50_000_000:
            continue
        add_income(exec_date, desc, amt)

    return incomes, outcomes


def _parse_balance_history(full_text: str) -> list[dict]:
    """Extract (date, balance) points from normalized PDF text for balance-over-time chart."""
    points: list[dict] = []
    seen: set[tuple] = set()

    patterns = [
        # Card: date date 9374 desc ... RSD isplata uplata balance
        re.compile(
            r"(\d{2}\.\d{2}\.\d{4})\s+(\d{2}\.\d{2}\.\d{4})\s+9374\s+.+?(?:RSD|USD|EUR)\s+[\d,]+\.\d{2}\s+[\d,]+\.\d{2}\s+([\d,]+\.\d{2})"
        ),
        # Transfers (Zaduženje/Unovcavanje): date date desc 0.00 amount 0.00 balance
        re.compile(
            r"(\d{2}\.\d{2}\.\d{4})\s+(\d{2}\.\d{2}\.\d{4})\s+(?:Zaduženje|Unovcavanje|Odobrenje)[^0-9]+?0\.00\s+[\d,]+\.\d{2}\s+0\.00\s+([\d,]+\.\d{2})"
        ),
        # Odobrenje: date date desc 0.00 0.00 amount balance
        re.compile(
            r"(\d{2}\.\d{2}\.\d{4})\s+(\d{2}\.\d{2}\.\d{4})\s+Odobrenje[^0-9]+?0\.00\s+0\.00\s+[\d,]+\.\d{2}\s+([\d,]+\.\d{2})"
        ),
    ]

    for pattern in patterns:
        for m in pattern.finditer(full_text):
            exec_date, bal_str = m.group(2), m.group(3)
            bal = parse_amount(bal_str)
            if bal and 0 < bal < 100_000_000:
                key = (exec_date, round(bal, 2))
                if key not in seen:
                    seen.add(key)
                    points.append({"date": exec_date, "balance": bal})

    def _date_sort_key(date_str: str) -> tuple:
        parts = date_str.split(".")
        return (int(parts[2]), int(parts[1]), int(parts[0])) if len(parts) == 3 else (0, 0, 0)

    points.sort(key=lambda p: _date_sort_key(p["date"]))
    return points


def parse_statement(pdf_path: str | Path) -> ParsedStatement | None:
    """
    Parse a Raiffeisen bank statement PDF.

    Returns ParsedStatement with month, incomes, and outgoings_by_category,
    or None if the PDF could not be parsed.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        return None

    date_range = extract_date_range(str(pdf_path))
    if not date_range:
        return None

    year, month = date_range
    month_key = f"{year}-{month:02d}"

    full_text = _read_pdf_text(str(pdf_path))
    incomes, outcomes = _parse_pdf_simple(full_text)
    if len(incomes) + len(outcomes) < 5:
        return None

    incomes_by_category: dict[str, list[dict]] = {}
    for t in incomes:
        cat = t.get("category", "Income")
        incomes_by_category.setdefault(cat, []).append(
            {"date": t["date"], "description": t["description"], "amount": t["amount"]}
        )

    outgoings_by_category: dict[str, list[dict]] = {}
    for t in outcomes:
        cat = t.get("category", "Other")
        outgoings_by_category.setdefault(cat, []).append(
            {"date": t["date"], "description": t["description"], "amount": t["amount"]}
        )

    return ParsedStatement(
        year=year,
        month=month,
        month_key=month_key,
        incomes=incomes,
        incomes_by_category=incomes_by_category,
        outgoings_by_category=outgoings_by_category,
        balance_history=_parse_balance_history(full_text),
    )


def parse_pdf(pdf_path: str | Path) -> PdfDescription | None:
    """
    Parse a Raiffeisen bank statement PDF.

    Returns PdfDescription with valuta, date, racun_number, incomes, outgoings.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        return None

    header = _extract_header(str(pdf_path))
    if not header:
        return None

    valuta, date_range, racun_number = header
    full_text = _read_pdf_text(str(pdf_path))
    incomes_raw, outcomes_raw = _parse_pdf_simple(full_text)

    return PdfDescription(
        valuta=valuta,
        date=date_range,
        racun_number=racun_number,
        incomes={TransactionRecord(date=t["date"], description=t["description"], money=t["amount"]) for t in incomes_raw},
        outgoings={TransactionRecord(date=t["date"], description=t["description"], money=t["amount"]) for t in outcomes_raw},
    )
