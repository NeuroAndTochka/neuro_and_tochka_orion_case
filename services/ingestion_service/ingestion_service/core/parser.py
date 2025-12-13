from __future__ import annotations

from pathlib import Path
from typing import List, Tuple


class DocumentParser:
    def __init__(self, max_pages: int, max_file_mb: int) -> None:
        self.max_pages = max_pages
        self.max_file_mb = max_file_mb

    @staticmethod
    def _clean_text(text: str) -> str:
        # Убираем нулевые байты и приводим строку к безопасному виду для БД.
        return text.replace("\x00", "").strip()

    def parse(self, file_path: Path) -> Tuple[List[str], dict]:
        size_mb = file_path.stat().st_size / (1024 * 1024)
        if size_mb > self.max_file_mb:
            raise ValueError(f"file too large: {size_mb:.1f} MB > {self.max_file_mb} MB")

        ext = file_path.suffix.lower()
        if ext == ".pdf":
            return self._parse_pdf(file_path)
        if ext in {".docx", ".doc"}:
            return self._parse_docx(file_path)
        # fallback: treat as text
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        return [self._clean_text(text)], {"pages": 1, "title": file_path.name}

    def _parse_pdf(self, file_path: Path) -> Tuple[List[str], dict]:
        try:
            import PyPDF2  # type: ignore
        except ImportError:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            return [text], {"pages": 1, "title": file_path.name}

        pages: List[str] = []
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            if len(reader.pages) > self.max_pages:
                raise ValueError(f"too many pages: {len(reader.pages)} > {self.max_pages}")
            for page in reader.pages:
                try:
                    pages.append(self._clean_text(page.extract_text() or ""))
                except Exception:
                    pages.append("")
        return pages, {"pages": len(pages), "title": file_path.name}

    def _parse_docx(self, file_path: Path) -> Tuple[List[str], dict]:
        try:
            import docx  # type: ignore
        except ImportError:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            return [text], {"pages": 1, "title": file_path.name}

        document = docx.Document(file_path)
        paragraphs = [p.text for p in document.paragraphs]
        text = "\n".join(paragraphs)
        approx_pages = max(1, len(text.split()) // 800)
        if approx_pages > self.max_pages:
            raise ValueError(f"too many pages (approx): {approx_pages} > {self.max_pages}")
        return [self._clean_text(text)], {"pages": approx_pages, "title": file_path.name}
