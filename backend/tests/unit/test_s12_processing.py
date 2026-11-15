# pyright: reportOptionalMemberAccess=false, reportAttributeAccessIssue=false
"""S12 file processing: unit tests (no database, no network). docs/specs/S12-file-processing.md.

Fixtures (PDF/PPTX/DOCX) are generated in-test with PyMuPDF / python-pptx / zipfile, so no binary
files are committed and no personal data is involved.
"""

import io
import math
import re
import zipfile

import httpx
import pymupdf
import pytest
import respx
from pptx import Presentation

from app.connectors.base import AuthExpired, DownloadRef, PlatformError, TranscriptCue
from app.core.embeddings import FakeEmbeddings, GeminiEmbeddings
from app.sync.processing import (
    MAX_BYTES,
    ExtractError,
    SkipProcessing,
    SupabaseStorage,
    Unit,
    chunk,
    count_tokens,
    extract,
    extract_transcript,
    http_downloader,
    storage_path,
)

PDF = "application/pdf"
PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def make_pdf(pages: list[str]) -> bytes:
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        if text:
            page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def make_pptx(slides: list[tuple[str, str, str]]) -> bytes:
    prs = Presentation()
    for title, body, notes in slides:
        slide = prs.slides.add_slide(prs.slide_layouts[1])  # title + content
        if title:
            slide.shapes.title.text = title
        else:
            slide.shapes.title.element.getparent().remove(slide.shapes.title.element)
        if body:
            slide.placeholders[1].text = body
        else:
            ph = slide.placeholders[1]
            ph.element.getparent().remove(ph.element)
        if notes:
            slide.notes_slide.notes_text_frame.text = notes
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def make_docx(paragraphs: list[tuple[str | None, str]]) -> bytes:
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    body = ""
    for style, text in paragraphs:
        ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
        body += f"<w:p>{ppr}<w:r><w:t>{text}</w:t></w:r></w:p>"
    xml = f'<?xml version="1.0"?><w:document xmlns:w="{ns}"><w:body>{body}</w:body></w:document>'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", xml)
    return buf.getvalue()


def sentences(n: int, start: int = 0) -> str:
    return " ".join(
        f"Sentence number {i} explains dynamic programming and memoization in detail."
        for i in range(start, start + n)
    )


# --- S12-T01: PDF one unit per page ----------------------------------------------------------
def test_s12_t01_pdf_one_unit_per_page_with_page_numbers() -> None:
    out = extract(PDF, make_pdf(["Intro to graphs", "", "Dijkstra shortest paths"]))
    assert out.page_count == 3
    assert [(u.page, u.text) for u in out.units] == [
        (1, "Intro to graphs"),
        (3, "Dijkstra shortest paths"),
    ]


def test_s12_pdf_corrupt_is_extract_error() -> None:
    with pytest.raises(ExtractError):
        extract(PDF, b"%PDF-1.4 this is not really a pdf")


def test_s12_pdf_password_protected_is_extract_error() -> None:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "secret")
    data = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="o", user_pw="u")
    with pytest.raises(ExtractError):
        extract(PDF, data)


def test_s12_pdf_over_500_pages_is_skipped() -> None:
    with pytest.raises(SkipProcessing, match="500"):
        extract(PDF, make_pdf([""] * 501))


def test_s12_file_over_50mb_is_skipped() -> None:
    with pytest.raises(SkipProcessing, match="50 MB"):
        extract("text/plain", b"x" * (MAX_BYTES + 1))


# --- S12-T02: PPTX title + body + notes per slide ---------------------------------------------
def test_s12_t02_pptx_title_body_and_notes_per_slide() -> None:
    data = make_pptx(
        [
            ("Memoization", "Store subproblem answers", "Mention Fibonacci"),
            ("Only a title", "", ""),
            ("", "", ""),  # image-only slide: nothing to keep
            ("Greedy", "Exchange argument", ""),
        ]
    )
    out = extract(PPTX, data)
    assert out.page_count == 4
    assert [u.page for u in out.units] == [1, 2, 4]
    first = out.units[0].text
    assert "Memoization" in first and "Store subproblem answers" in first
    assert "Mention Fibonacci" in first
    assert first.index("Memoization") < first.index("Store") < first.index("Fibonacci")
    assert out.units[1].text == "Only a title"


# --- other formats ----------------------------------------------------------------------------
def test_s12_docx_units_split_on_headings() -> None:
    data = make_docx(
        [
            ("Heading1", "Grading"),
            (None, "Exams are 60 percent."),
            ("Heading1", "Late policy"),
            (None, "Three free late days."),
        ]
    )
    out = extract(DOCX, data)
    assert [u.text for u in out.units] == [
        "Grading\nExams are 60 percent.",
        "Late policy\nThree free late days.",
    ]
    assert all(u.page is None for u in out.units)


def test_s12_html_strips_tags_and_splits_on_headings() -> None:
    html = (
        b"<html><head><style>p{}</style><script>alert(1)</script></head><body>"
        b"<h2>Office hours</h2><p>Monday 2&ndash;4 pm</p><h2>Exams</h2><p>Midterm in week 7</p>"
        b"</body></html>"
    )
    out = extract("text/html", html)
    assert [u.text for u in out.units] == [
        "Office hours\nMonday 2–4 pm",
        "Exams\nMidterm in week 7",
    ]


def test_s12_txt_and_md_are_one_unit_and_unknown_type_skipped() -> None:
    assert [u.text for u in extract("text/plain", b"hello\nworld").units] == ["hello\nworld"]
    assert len(extract("text/markdown", b"# A\ntext\n# B\nmore").units) == 1
    with pytest.raises(SkipProcessing):
        extract("image/png", b"\x89PNG")


# --- S12-T03: never crosses pages -------------------------------------------------------------
def test_s12_t03_chunks_never_span_two_pages() -> None:
    units = [Unit(text=sentences(40, i * 100), page=i + 1) for i in range(3)]
    drafts = chunk(units, context="COMPSCI 311 · Lecture 7")
    assert len(drafts) > 3
    for d in drafts:
        assert d.page in {1, 2, 3}
        numbers = [int(n) for n in re.findall(r"Sentence number (\d+) ", d.text)]
        assert numbers and all((d.page - 1) * 100 <= n < d.page * 100 for n in numbers)


# --- S12-T04: sentence splits with overlap ----------------------------------------------------
def test_s12_t04_long_unit_splits_at_sentences_with_overlap() -> None:
    text = sentences(120)
    drafts = chunk([Unit(text=text, page=1)], max_tokens=200, overlap_tokens=30)
    assert len(drafts) >= 5
    bodies = [d.text.split("\n", 1)[1] if d.text.startswith("[") else d.text for d in drafts]
    for d, body in zip(drafts, bodies, strict=True):
        assert d.token_count <= 200
        assert d.token_count == count_tokens(d.text)
        assert body.endswith(".")  # cut at a sentence boundary
    for prev, nxt in zip(bodies, bodies[1:], strict=False):
        last_sentence = prev.rsplit(". ", 1)[-1]
        assert last_sentence in nxt  # overlap carries the tail sentence forward
        overlap = nxt[: nxt.index(last_sentence) + len(last_sentence)]
        assert count_tokens(overlap) <= 30
    joined = " ".join(bodies)
    for i in range(120):
        assert f"Sentence number {i} " in joined


def test_s12_t04_single_huge_sentence_is_hard_split() -> None:
    text = "word " * 2000
    drafts = chunk([Unit(text=text, page=1)], max_tokens=300, overlap_tokens=20)
    assert len(drafts) > 1 and all(d.token_count <= 300 for d in drafts)


# --- S12-T05: tiny units merge only within the same page --------------------------------------
def test_s12_t05_tiny_units_merge_only_within_same_page() -> None:
    units = [
        Unit(text="Dynamic programming", page=1),
        Unit(text=sentences(8), page=1),
        Unit(text="Tiny page two", page=2),
        Unit(text=sentences(8, 50), page=3),
    ]
    drafts = chunk(units, min_tokens=40)
    assert [d.page for d in drafts] == [1, 2, 3]
    assert drafts[0].text.startswith("Dynamic programming\n")
    assert drafts[1].text == "Tiny page two"


def test_s12_empty_units_produce_no_chunks() -> None:
    assert chunk([Unit(text="   ", page=1), Unit(text="", page=2)]) == []


# --- S12-T06: transcript windows -------------------------------------------------------------
def test_s12_t06_transcript_cues_become_60s_windows() -> None:
    cues = [TranscriptCue(start_s=s, end_s=s + 10, text=f"cue {s}") for s in range(0, 200, 10)]
    out = extract_transcript(cues)
    assert [(u.start_s, u.end_s) for u in out.units] == [(0, 60), (60, 120), (120, 180), (180, 200)]
    assert out.units[0].text.startswith("cue 0 cue 10")
    assert all(u.page is None for u in out.units)
    assert out.duration_s == 200


# --- S12-T07: context header ------------------------------------------------------------------
def test_s12_t07_context_header_prefixed_and_counted() -> None:
    body = "Memoization stores solutions to subproblems so each is solved once."
    [d] = chunk([Unit(text=body, page=12)], context="COMPSCI 311 · Lecture 7 slides")
    assert d.text == f"[COMPSCI 311 · Lecture 7 slides · p.12]\n{body}"
    assert d.token_count == count_tokens(d.text) > count_tokens(body)
    [t] = chunk([Unit(text=body, start_s=754, end_s=800)], context="COMPSCI 311 · Lecture 7")
    assert t.text.startswith("[COMPSCI 311 · Lecture 7 · 12:34]\n")
    assert (t.start_s, t.end_s, t.page) == (754, 800, None)
    [n] = chunk([Unit(text=body)], context="COMPSCI 311 · Syllabus")
    assert n.text.startswith("[COMPSCI 311 · Syllabus]\n")


def test_s12_t07_header_counts_toward_max_tokens() -> None:
    drafts = chunk(
        [Unit(text=sentences(60), page=1)], max_tokens=120, context="COMPSCI 311 · " + "Long " * 20
    )
    assert all(d.token_count <= 120 for d in drafts)


# --- S12-T08: scanned PDF skipped -------------------------------------------------------------
def test_s12_t08_image_only_pdf_is_skipped() -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 20, 20), False)
    pix.clear_with(128)
    page.insert_image(pymupdf.Rect(72, 72, 200, 200), pixmap=pix)
    with pytest.raises(SkipProcessing, match="OCR out of scope"):
        extract(PDF, doc.tobytes())


# --- S12-T10: Gemini retries on 429 -----------------------------------------------------------
@respx.mock
async def test_s12_t10_embedding_provider_retries_on_429(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []

    async def fake_sleep(s: float) -> None:
        sleeps.append(s)

    monkeypatch.setattr("app.core.embeddings.asyncio.sleep", fake_sleep)
    ok = {"data": [{"index": 0, "embedding": [3.0, 4.0] + [0.0] * 1534}]}
    route = respx.post(f"{GeminiEmbeddings.base_url}/embeddings").mock(
        side_effect=[httpx.Response(429), httpx.Response(503), httpx.Response(200, json=ok)]
    )
    [vec] = await GeminiEmbeddings("test-key").embed(["hello"])
    assert route.call_count == 3 and sleeps == [1.0, 2.0]
    assert vec[:2] == pytest.approx([0.6, 0.8])


# --- S12-T11: fake embeddings ----------------------------------------------------------------
async def test_s12_t11_fake_embeddings_deterministic_1536_normalized() -> None:
    fake = FakeEmbeddings()
    a, b, c = await fake.embed(["memoization", "memoization", "greedy"])
    assert a == b and a != c and len(a) == 1536 == fake.dim
    assert math.isclose(math.sqrt(sum(x * x for x in a)), 1.0, rel_tol=1e-9)


# --- download + storage (HTTP mocked) ---------------------------------------------------------
@respx.mock
async def test_s12_downloader_sends_bearer_and_maps_auth_errors() -> None:
    route = respx.get("https://canvas.example/files/1/download").mock(
        return_value=httpx.Response(200, content=b"PDFDATA")
    )
    respx.get("https://canvas.example/files/2/download").mock(return_value=httpx.Response(401))
    respx.get("https://canvas.example/files/3/download").mock(return_value=httpx.Response(502))
    dl = http_downloader("tok123")
    assert await dl(DownloadRef(url="https://canvas.example/files/1/download")) == b"PDFDATA"
    assert route.calls[0].request.headers["Authorization"] == "Bearer tok123"
    with pytest.raises(AuthExpired):
        await dl(DownloadRef(url="https://canvas.example/files/2/download"))
    with pytest.raises(PlatformError):
        await dl(DownloadRef(url="https://canvas.example/files/3/download"))


@respx.mock
async def test_s12_downloader_refuses_files_over_50mb() -> None:
    respx.get("https://canvas.example/big").mock(
        return_value=httpx.Response(200, headers={"content-length": str(MAX_BYTES + 1)})
    )
    with pytest.raises(SkipProcessing, match="50 MB"):
        await http_downloader(None)(DownloadRef(url="https://canvas.example/big"))


def test_s12_storage_path_layout() -> None:
    path = storage_path("u1", "canvas", "12345", "f7", 2, "pdf")
    assert path == "users/u1/canvas/12345/f7/v2.pdf"


@respx.mock
async def test_s12_storage_creates_private_bucket_when_missing() -> None:
    base = "http://storage.test"
    up = respx.post(f"{base}/storage/v1/object/materials/users/u/x.pdf").mock(
        side_effect=[
            httpx.Response(400, json={"statusCode": "404", "error": "Bucket not found"}),
            httpx.Response(200, json={"Key": "materials/users/u/x.pdf"}),
        ]
    )
    bucket = respx.post(f"{base}/storage/v1/bucket").mock(return_value=httpx.Response(200))
    await SupabaseStorage(base, "service-key").upload("users/u/x.pdf", b"data", PDF)
    assert up.call_count == 2 and bucket.call_count == 1
    import json

    assert json.loads(bucket.calls[0].request.content)["public"] is False
    assert up.calls[0].request.headers["apikey"] == "service-key"
