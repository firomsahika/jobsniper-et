"""Document Parser Module for JobSniper ET.

Supports PDF (via PyMuPDF) and DOCX (via python-docx) with sanitized text extraction.
"""

import io
import os
from typing import Optional


class DocumentParser:
    """Extracts clean text content from candidate resumes (PDF or DOCX)."""

    @staticmethod
    def extract_from_bytes(file_bytes: bytes, file_name: str) -> Optional[str]:
        """Extracts text based on filename extension."""
        ext = os.path.splitext(file_name)[1].lower()
        if ext == ".pdf":
            return DocumentParser.extract_from_pdf_bytes(file_bytes)
        elif ext in [".docx", ".doc"]:
            return DocumentParser.extract_from_docx_bytes(file_bytes)
        elif ext in [".txt", ".md"]:
            return file_bytes.decode("utf-8", errors="replace")
        return None

    @staticmethod
    def extract_from_pdf_bytes(pdf_bytes: bytes) -> str:
        """Extracts text from PDF bytes using PyMuPDF (fitz)."""
        import fitz  # PyMuPDF

        text_parts = []
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for page in doc:
                text_parts.append(page.get_text("text"))

        full_text = "\n".join(text_parts).strip()
        return DocumentParser._normalize_extracted_text(full_text)

    @staticmethod
    def extract_from_docx_bytes(docx_bytes: bytes) -> str:
        """Extracts text from DOCX bytes using python-docx."""
        import docx

        file_stream = io.BytesIO(docx_bytes)
        doc = docx.Document(file_stream)
        text_parts = []
        for p in doc.paragraphs:
            if p.text:
                text_parts.append(p.text)
        for table in doc.tables:
            for row in table.rows:
                row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_text:
                    text_parts.append(" | ".join(row_text))

        full_text = "\n".join(text_parts).strip()
        return DocumentParser._normalize_extracted_text(full_text)

    @staticmethod
    def _normalize_extracted_text(text: str) -> str:
        """Sanitizes text by collapsing excessive whitespace and weird control chars."""
        lines = [line.strip() for line in text.splitlines()]
        cleaned = "\n".join(l for l in lines if l)
        return cleaned


document_parser = DocumentParser()

