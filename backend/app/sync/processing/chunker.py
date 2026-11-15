"""Chunking (S12 rules 2-4): never crosses a page/slide/window, sentence splits with overlap,
context header `[COURSE · Title · p.N]` included in the text and the token count."""

import re
from functools import lru_cache

import tiktoken
from pydantic import BaseModel

from app.sync.processing.extract import Unit


class ChunkDraft(BaseModel):
    text: str
    page: int | None = None
    start_s: int | None = None
    end_s: int | None = None
    token_count: int


@lru_cache
def _encoding() -> tiktoken.Encoding:
    return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_encoding().encode(text, disallowed_special=()))


def mmss(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


def header(context: str | None, unit: Unit) -> str:
    """Same format as the S03 seed: `[COMPSCI 311 · Lecture 7 slides · p.12]\\n`."""
    if not context:
        return ""
    if unit.page is not None:
        anchor = f"p.{unit.page}"
    elif unit.start_s is not None:
        anchor = mmss(unit.start_s)
    else:
        anchor = None
    return f"[{context}{f' · {anchor}' if anchor else ''}]\n"


def _same_anchor(a: Unit, b: Unit) -> bool:
    return a.page == b.page and a.start_s is None and b.start_s is None


def _merge_small(units: list[Unit], min_tokens: int) -> list[Unit]:
    """A unit under `min_tokens` is merged into the next unit on the same page only."""
    out: list[Unit] = []
    carry: Unit | None = None
    for u in units:
        if carry is not None:
            if _same_anchor(carry, u):
                u = u.model_copy(update={"text": f"{carry.text}\n{u.text}"})
            else:
                out.append(carry)
            carry = None
        if count_tokens(u.text) < min_tokens:
            carry = u
        else:
            out.append(u)
    if carry is not None:
        out.append(carry)
    return out


_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")


def _hard_split(text: str, budget: int) -> list[str]:
    tokens = _encoding().encode(text, disallowed_special=())
    parts = [
        _encoding().decode(tokens[i : i + budget]).strip() for i in range(0, len(tokens), budget)
    ]
    return [p for p in parts if p]


def _split(text: str, budget: int, overlap: int) -> list[str]:
    if count_tokens(text) <= budget:
        return [text]
    pieces: list[str] = []
    for s in (s.strip() for s in _SENTENCE.split(text)):
        if not s:
            continue
        pieces.extend(_hard_split(s, budget) if count_tokens(s) > budget else [s])
    chunks: list[str] = []
    cur: list[str] = []
    for p in pieces:
        if cur and count_tokens(" ".join([*cur, p])) > budget:
            chunks.append(" ".join(cur))
            tail: list[str] = []
            for q in reversed(cur):
                if count_tokens(" ".join([q, *tail])) > overlap:
                    break
                tail.insert(0, q)
            cur = tail if count_tokens(" ".join([*tail, p])) <= budget else []
        cur.append(p)
    if cur:
        chunks.append(" ".join(cur))
    return chunks


def chunk(
    units: list[Unit],
    max_tokens: int = 500,
    overlap_tokens: int = 60,
    min_tokens: int = 40,
    context: str | None = None,
) -> list[ChunkDraft]:
    """`context` is "COURSE · Title"; the anchor (p.N / m:ss) is added per unit."""
    clean = [u.model_copy(update={"text": u.text.strip()}) for u in units if u.text.strip()]
    drafts: list[ChunkDraft] = []
    for u in _merge_small(clean, min_tokens):
        head = header(context, u)
        budget = max(20, max_tokens - count_tokens(head) - 1)  # -1: BPE join slack
        for body in _split(u.text, budget, overlap_tokens):
            text = head + body
            drafts.append(
                ChunkDraft(
                    text=text,
                    page=u.page,
                    start_s=u.start_s,
                    end_s=u.end_s,
                    token_count=count_tokens(text),
                )
            )
    return drafts
