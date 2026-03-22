"""
Tests for pdf_parser module.
"""

import sys
import unittest
from pathlib import Path

# Allow imports from the project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from pdf_parser import parse_pdf, PdfDescription, TransactionRecord


_RACUN_DIR = Path(__file__).parent.parent / "racun"
_PDF_FILES = sorted(_RACUN_DIR.glob("*.PDF")) + sorted(_RACUN_DIR.glob("*.pdf"))
PDF_PATH = _PDF_FILES[0] if _PDF_FILES else None


class TestPdfParser(unittest.TestCase):
    """Tests for parse_pdf and PdfDescription."""

    def setUp(self):
        if PDF_PATH is None:
            self.skipTest("No PDF files found in racun/")

    def test_parse_pdf_returns_filled_structure(self):
        """parse_pdf should return a PdfDescription, not None."""
        result = parse_pdf(PDF_PATH)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, PdfDescription)

    def test_pdf_description_has_required_fields(self):
        """PdfDescription must have valuta, date range, account number, incomes, outgoings."""
        result = parse_pdf(PDF_PATH)
        self.assertIsNotNone(result)
        self.assertIn(result.valuta, ("RSD", "EUR", "USD"))
        self.assertRegex(result.date, r"\d{2}\.\d{2}\.\d{4}")
        self.assertRegex(result.racun_number, r"^\d{15,}$")
        self.assertIsInstance(result.incomes, set)
        self.assertIsInstance(result.outgoings, set)

    def test_each_record_has_date_description_money(self):
        """Every income and outgoing record must have date, description, and a numeric amount."""
        result = parse_pdf(PDF_PATH)
        self.assertIsNotNone(result)
        for rec in result.incomes | result.outgoings:
            self.assertIsInstance(rec, TransactionRecord)
            self.assertRegex(rec.date, r"\d{2}\.\d{2}\.\d{4}")
            self.assertIsNotNone(rec.description)
            self.assertIsInstance(rec.money, (int, float))
            self.assertGreater(rec.money, 0)

    def test_has_transactions(self):
        """At least some transactions (incomes or outgoings) must be parsed."""
        result = parse_pdf(PDF_PATH)
        self.assertIsNotNone(result)
        self.assertGreater(len(result.incomes) + len(result.outgoings), 0)

    def test_has_outgoings(self):
        """At least several outgoing transactions must be parsed."""
        result = parse_pdf(PDF_PATH)
        self.assertIsNotNone(result)
        self.assertGreaterEqual(len(result.outgoings), 5)

    def test_mobile_kesh_classified_as_outgoing(self):
        """Unovcavanje Mobilnog keša transactions must be outgoings, not incomes."""
        result = parse_pdf(PDF_PATH)
        self.assertIsNotNone(result)
        mobile_kesh_in_income = [
            r for r in result.incomes
            if "Unovcavanje" in r.description and "Mobilnog" in r.description
        ]
        self.assertEqual(len(mobile_kesh_in_income), 0, "Mobile kesh should not appear in incomes")


if __name__ == "__main__":
    unittest.main()
