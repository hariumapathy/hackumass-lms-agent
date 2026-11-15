"""Text extraction (S12 rule 1): one `Unit` per page / slide / heading section / transcript window.

PDF -> PyMuPDF, PPTX -> python-pptx, DOCX -> stdlib zip+XML, HTML -> stdlib HTMLParser,
TXT/MD -> one unit. No OCR: image-only documents raise `SkipProcessing`.
"""

import io
import re
import zipfile
from html.parser import HTMLParser
from xml.etree import ElementTree

from pydantic import BaseModel

from app.connectors.base import TranscriptCue

MAX_BYTES = 50 * 1024 * 1024  # S12 rule 5
MAX_PAGES = 500
WINDOW_S = 60
NO_TEXT = "no text; OCR out of scope"

PDF = "application/pdf"
PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
HTML = {"text/html", "application/xhtml+xml"}
TEXT = {"text/plain", "text/markdown", "text/x-markdown", "text/csv"}
EXTENSIONS = {PDF: "pdf", PPTX: "pptx", DOCX: "docx", "text/html": "html", "text/plain": "txt"}
EXTENSIONS |= {"text/markdown": "md", "text/x-markdown": "md", "text/csv": "csv"}


class SkipProcessing(Exception):  # noqa: N818 (an outcome, not an error)
    """Material can't be processed by design (too big, unsupported, no text) -> `skipped`."""


class ExtractError(Exception):
    """Corrupt / password-protected file -> `failed`."""


class Unit(BaseModel):
    text: str
    page: int | None = None
    start_s: int | None = None
    end_s: int | None = None


class Extracted(BaseModel):
    units: list[Unit]
    page_count: int | None = None
    duration_s: int | None = None


def _clean(text: str) -> str:
    lines = [re.sub(r"[ \t ]+", " ", ln).strip() for ln in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _base_mime(mime_type: str | None) -> str:
    return (mime_type or "").split(";")[0].strip().lower()


def extract(mime_type: str | None, data: bytes) -> Extracted:
    if len(data) > MAX_BYTES:
        raise SkipProcessing("file is over 50 MB")
    mime = _base_mime(mime_type)
    if mime == PDF:
        out = _pdf(data)
    elif mime == PPTX:
        out = _pptx(data)
    elif mime == DOCX:
        out = _docx(data)
    elif mime in HTML:
        out = Extracted(units=_html_units(data.decode("utf-8", errors="replace")))
    elif mime in TEXT or mime.startswith("text/"):
        text = _clean(data.decode("utf-8", errors="replace"))
        out = Extracted(units=[Unit(text=text)] if text else [])
    else:
        raise SkipProcessing(f"unsupported file type ({mime or 'unknown'})")
    if not out.units:
        raise SkipProcessing(NO_TEXT)
    return out


def _pdf(data: bytes) -> Extracted:
    import pymupdf

    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:  # noqa: BLE001 (any parser error = corrupt file)
        raise ExtractError("PDF could not be opened (corrupt file)") from exc
    with doc:
        if doc.needs_pass:
            raise ExtractError("PDF is password-protected")
        if doc.page_count > MAX_PAGES:
            raise SkipProcessing(f"PDF has over {MAX_PAGES} pages")
        units = []
        for i in range(doc.page_count):
            text = _clean(str(doc[i].get_text("text")))
            if text:
                units.append(Unit(text=text, page=i + 1))
        return Extracted(units=units, page_count=doc.page_count)


def _pptx(data: bytes) -> Extracted:
    from pptx import Presentation

    try:
        prs = Presentation(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001
        raise ExtractError("slides could not be opened (corrupt file)") from exc
    slides = list(prs.slides)
    if len(slides) > MAX_PAGES:
        raise SkipProcessing(f"deck has over {MAX_PAGES} slides")
    units = []
    for i, slide in enumerate(slides, start=1):
        title_shape = slide.shapes.title
        parts = [title_shape.text_frame.text] if title_shape is not None else []
        for shape in slide.shapes:
            if title_shape is not None and shape.shape_id == title_shape.shape_id:
                continue
            if shape.has_text_frame:
                parts.append(shape.text_frame.text)  # type: ignore[attr-defined]
            elif getattr(shape, "has_table", False):
                for row in shape.table.rows:  # type: ignore[attr-defined]
                    parts.append(" | ".join(c.text for c in row.cells))
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame
            if notes is not None and notes.text.strip():
                parts.append(notes.text)
        text = _clean("\n".join(p for p in parts if p and p.strip()))
        if text:
            units.append(Unit(text=text, page=i))
    return Extracted(units=units, page_count=len(slides))


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _docx(data: bytes) -> Extracted:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            root = ElementTree.fromstring(z.read("word/document.xml"))
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as exc:
        raise ExtractError("document could not be opened (corrupt file)") from exc
    sections: list[list[str]] = [[]]
    for p in root.iter(f"{_W}p"):
        style = p.find(f"{_W}pPr/{_W}pStyle")
        is_heading = style is not None and (
            (style.get(f"{_W}val") or "").lower().startswith(("heading", "title"))
        )
        text = "".join(t.text or "" for t in p.iter(f"{_W}t")).strip()
        if not text:
            continue
        if is_heading and sections[-1]:
            sections.append([])
        sections[-1].append(text)
    return Extracted(units=_section_units(sections))


def _section_units(sections: list[list[str]]) -> list[Unit]:
    out = []
    for s in sections:
        text = _clean("\n".join(s))
        if text:
            out.append(Unit(text=text))
    return out


class _HTMLText(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "tr", "section", "article", "table", "ul", "ol", "pre"}
    HEADINGS = {"h1", "h2", "h3"}
    SKIP = {"script", "style", "head", "noscript", "template"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.sections: list[list[str]] = [[]]
        self._buf: list[str] = []
        self._skip = 0

    def _flush(self) -> None:
        text = " ".join("".join(self._buf).split())
        if text:
            self.sections[-1].append(text)
        self._buf = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP:
            self._skip += 1
        elif tag in self.HEADINGS:
            self._flush()
            if self.sections[-1]:
                self.sections.append([])
        elif tag in self.BLOCK:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP:
            self._skip = max(0, self._skip - 1)
        elif tag in self.HEADINGS or tag in self.BLOCK:
            self._flush()

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._buf.append(data)


def _html_units(html: str) -> list[Unit]:
    parser = _HTMLText()
    parser.feed(html)
    parser.close()
    parser._flush()
    return _section_units(parser.sections)


def html_to_text(html: str) -> str:
    """Plain text of an HTML fragment (posts / Canvas page bodies)."""
    return "\n".join(u.text for u in _html_units(html))


def looks_like_html(text: str) -> bool:
    return bool(re.search(r"<(p|div|br|span|a|h[1-6]|ul|li|strong|em|table)\b", text, re.I))


def extract_transcript(cues: list[TranscriptCue], window_s: int = WINDOW_S) -> Extracted:
    """Group cues into ~`window_s` windows; each window keeps its start/end seconds."""
    units: list[Unit] = []
    cur: list[TranscriptCue] = []
    for cue in sorted(cues, key=lambda c: c.start_s):
        if cur and cue.start_s - cur[0].start_s >= window_s:
            units.append(_window(cur))
            cur = []
        cur.append(cue)
    if cur:
        units.append(_window(cur))
    units = [u for u in units if u.text]
    if not units:
        raise SkipProcessing("transcript is empty")
    return Extracted(units=units, duration_s=max(c.end_s for c in cues))


def _window(cues: list[TranscriptCue]) -> Unit:
    text = " ".join(" ".join(c.text.split()) for c in cues if c.text.strip())
    return Unit(text=text, start_s=cues[0].start_s, end_s=max(c.end_s for c in cues))
