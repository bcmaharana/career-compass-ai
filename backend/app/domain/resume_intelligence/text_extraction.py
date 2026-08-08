"""Text extraction abstraction for uploaded resume files.

Application services depend only on this Protocol — the concrete
implementation (pdfplumber/python-docx, see
app/adapters/parsing/resume_text_extractor.py) is swappable without any
calling code changing, same pattern as ObjectStorageRepository.
"""

from __future__ import annotations

from typing import Protocol


class ResumeTextExtractor(Protocol):
    def extract_text(self, *, content: bytes, content_type: str) -> str:
        """Extract plain text from a PDF or DOCX file's raw bytes.

        This is CPU-bound sync work — callers must run it via
        asyncio.to_thread rather than awaiting it directly, matching the
        boto3 sync-wrapped-in-thread convention used elsewhere in this
        codebase.

        Raises app.core.exceptions.CareerCompassError (or a subclass) on
        an unsupported content_type or a library-level parse failure.
        """
        ...
