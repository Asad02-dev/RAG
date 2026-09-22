"""Generate sample .docx and .xlsx documents for testing the RAG pipeline."""

from pathlib import Path
import openpyxl
from docx import Document

DOCS_DIR = Path(__file__).resolve().parent.parent / "data" / "documents"
DOCS_DIR.mkdir(parents=True, exist_ok=True)


def create_sample_docx():
    doc_path = DOCS_DIR / "employee_handbook.docx"
    doc = Document()
    doc.add_heading("Acme Corporation — Employee Handbook", level=1)

    doc.add_heading("Remote Work Policy", level=2)
    doc.add_paragraph(
        "All full-time engineers are eligible for 100% remote work. "
        "Employees receive a $1,000 home office stipend upon joining."
    )

    doc.add_heading("Paid Time Off (PTO)", level=2)
    doc.add_paragraph(
        "Employees receive 25 days of paid annual leave plus 10 public holidays. "
        "Up to 5 unused PTO days may roll over to the following calendar year."
    )

    doc.add_heading("Health and Wellness Benefits", level=2)
    doc.add_paragraph(
        "Comprehensive dental, vision, and mental health coverage begins on day one of employment. "
        "Gym memberships are reimbursed up to $75 per month."
    )

    doc.save(str(doc_path))
    print(f"Created: {doc_path}")


def create_sample_xlsx():
    xlsx_path = DOCS_DIR / "quarterly_financials.xlsx"
    wb = openpyxl.Workbook()

    ws = wb.active
    ws.title = "Q4 Financial Summary"

    ws.append(["Department", "Q3 Actual ($)", "Q4 Projected ($)", "Growth (%)"])
    ws.append(["Research & Development", "1,200,000", "1,450,000", "+20.8%"])
    ws.append(["Sales & Marketing", "850,000", "920,000", "+8.2%"])
    ws.append(["Cloud Infrastructure", "410,000", "390,000", "-4.8%"])
    ws.append(["Customer Operations", "280,000", "310,000", "+10.7%"])

    wb.save(str(xlsx_path))
    print(f"Created: {xlsx_path}")


if __name__ == "__main__":
    create_sample_docx()
    create_sample_xlsx()
