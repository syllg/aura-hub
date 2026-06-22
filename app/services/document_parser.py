from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from app.domain.chunking import ParsedDocument, ParsedPage, detect_version


class DocumentParseError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class DocumentParser:
    def extract(self, path: Path, *, filename: str, content_type: str) -> ParsedDocument:
        suffix = Path(filename).suffix.lower()
        if suffix == ".pdf":
            return self._extract_pdf(path, filename, content_type)
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise DocumentParseError(
                "DOCUMENT_TEXT_NOT_EXTRACTABLE",
                "Dokumen text harus menggunakan encoding UTF-8.",
            ) from exc
        if not text.strip():
            raise DocumentParseError("EMPTY_DOCUMENT", "Dokumen tidak berisi teks.")
        return ParsedDocument(
            filename=filename,
            content_type=content_type,
            pages=[ParsedPage(page_number=None, text=text)],
            detected_version=detect_version(text),
        )

    def _extract_pdf(self, path: Path, filename: str, content_type: str) -> ParsedDocument:
        try:
            reader = PdfReader(str(path))
            pages = [
                ParsedPage(page_number=index + 1, text=page.extract_text() or "")
                for index, page in enumerate(reader.pages)
            ]
        except Exception as exc:
            raise DocumentParseError(
                "DOCUMENT_TEXT_NOT_EXTRACTABLE", "PDF tidak dapat diekstrak."
            ) from exc
        joined = "\n".join(page.text for page in pages)
        if not joined.strip():
            raise DocumentParseError(
                "DOCUMENT_TEXT_NOT_EXTRACTABLE",
                "PDF tidak memiliki text layer yang dapat diekstrak.",
            )
        return ParsedDocument(
            filename=filename,
            content_type=content_type,
            pages=pages,
            detected_version=detect_version(joined),
        )
