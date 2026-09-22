"""Document processor — extracts structured text from multiple document formats."""

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ProcessedDocument:
    """Result of document processing — structured text with metadata."""

    source_file: str
    file_name: str
    document_type: str
    content_markdown: str
    page_count: int = 1
    metadata: dict | None = None


class DocumentProcessor:
    """Extract structured text from PDF, Word, Excel, Image, and Text files.

    Uses free, open-source libraries for all processing. Designed so this
    class can be swapped with an Azure Document Intelligence implementation.
    """

    def process(self, file_path: str | Path) -> ProcessedDocument:
        """Process a document file and return structured Markdown content."""
        path = Path(file_path)
        ext = path.suffix.lower()

        if not path.exists():
            raise FileNotFoundError(f"Document not found: {path}")

        logger.info(f"Processing {path.name} ({ext})")

        match ext:
            case ".pdf":
                return self._process_pdf(path)
            case ".docx":
                return self._process_docx(path)
            case ".xlsx":
                return self._process_xlsx(path)
            case ".png" | ".jpg" | ".jpeg":
                return self._process_image(path)
            case ".txt" | ".md":
                return self._process_text(path)
            case _:
                raise ValueError(f"Unsupported file format: {ext}")

    def _process_pdf(self, path: Path) -> ProcessedDocument:
        """Extract content from PDF using Docling (primary) or pypdf (fallback)."""
        content = ""
        page_count = 0

        # Try Docling first for layout-aware extraction
        try:
            from docling.document_converter import DocumentConverter

            converter = DocumentConverter()
            result = converter.convert(str(path))
            content = result.document.export_to_markdown()
            # Estimate page count from the docling result
            page_count = max(1, content.count("\n---\n") + 1)
            logger.info(f"PDF processed with Docling: {path.name}")
        except Exception as e:
            logger.warning(f"Docling failed for {path.name}: {e}. Falling back to pypdf.")
            content, page_count = self._process_pdf_fallback(path)

        return ProcessedDocument(
            source_file=str(path),
            file_name=path.name,
            document_type="pdf",
            content_markdown=content.strip(),
            page_count=page_count,
        )

    def _process_pdf_fallback(self, path: Path) -> tuple[str, int]:
        """Fallback PDF processing using pypdf."""
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        pages = []
        for i, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(f"## Page {i}\n\n{text.strip()}")

        return "\n\n".join(pages), len(reader.pages)

    def _process_docx(self, path: Path) -> ProcessedDocument:
        """Extract content from Word documents using python-docx."""
        from docx import Document as DocxDocument
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        doc = DocxDocument(str(path))
        sections: list[str] = []

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue

            style_name = (para.style.name or "").lower()

            # Convert heading styles to Markdown headings
            if "heading 1" in style_name:
                sections.append(f"# {text}")
            elif "heading 2" in style_name:
                sections.append(f"## {text}")
            elif "heading 3" in style_name:
                sections.append(f"### {text}")
            elif "heading" in style_name:
                sections.append(f"#### {text}")
            elif "list" in style_name:
                sections.append(f"- {text}")
            else:
                sections.append(text)

        # Extract tables
        for table in doc.tables:
            table_md = self._table_to_markdown(
                [[cell.text.strip() for cell in row.cells] for row in table.rows]
            )
            sections.append(table_md)

        content = "\n\n".join(sections)
        logger.info(f"DOCX processed: {path.name} ({len(sections)} sections)")

        return ProcessedDocument(
            source_file=str(path),
            file_name=path.name,
            document_type="docx",
            content_markdown=content.strip(),
        )

    def _process_xlsx(self, path: Path) -> ProcessedDocument:
        """Extract content from Excel files using openpyxl (sheet by sheet)."""
        from openpyxl import load_workbook

        wb = load_workbook(str(path), read_only=True, data_only=True)
        sheets: list[str] = []

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows = []
            for row in ws.iter_rows(values_only=True):
                row_data = [str(cell) if cell is not None else "" for cell in row]
                if any(cell.strip() for cell in row_data):
                    rows.append(row_data)

            if rows:
                table_md = self._table_to_markdown(rows)
                sheets.append(f"## Sheet: {sheet_name}\n\n{table_md}")

        wb.close()
        content = "\n\n".join(sheets)
        logger.info(f"XLSX processed: {path.name} ({len(sheets)} sheets)")

        return ProcessedDocument(
            source_file=str(path),
            file_name=path.name,
            document_type="xlsx",
            content_markdown=content.strip(),
        )

    def _process_image(self, path: Path) -> ProcessedDocument:
        """Extract text from images using Tesseract OCR."""
        try:
            from PIL import Image
            import pytesseract

            image = Image.open(str(path))
            text = pytesseract.image_to_string(image)
        except ImportError:
            logger.error("pytesseract or Pillow not installed. Cannot process images.")
            text = f"[Image: {path.name} — OCR not available]"
        except Exception as e:
            logger.error(f"OCR failed for {path.name}: {e}")
            text = f"[Image: {path.name} — OCR failed: {e}]"

        content = f"## Image: {path.name}\n\n{text.strip()}"
        logger.info(f"Image processed: {path.name}")

        return ProcessedDocument(
            source_file=str(path),
            file_name=path.name,
            document_type="image",
            content_markdown=content.strip(),
        )

    def _process_text(self, path: Path) -> ProcessedDocument:
        """Read plain text or Markdown files directly."""
        content = path.read_text(encoding="utf-8", errors="replace")
        logger.info(f"Text file read: {path.name}")

        return ProcessedDocument(
            source_file=str(path),
            file_name=path.name,
            document_type="text",
            content_markdown=content.strip(),
        )

    @staticmethod
    def _table_to_markdown(rows: list[list[str]]) -> str:
        """Convert a 2D list of strings to a Markdown table."""
        if not rows:
            return ""

        # Use first row as header
        header = rows[0]
        separator = ["---"] * len(header)
        lines = [
            "| " + " | ".join(header) + " |",
            "| " + " | ".join(separator) + " |",
        ]
        for row in rows[1:]:
            # Pad or trim row to match header width
            padded = row + [""] * (len(header) - len(row))
            lines.append("| " + " | ".join(padded[: len(header)]) + " |")

        return "\n".join(lines)
