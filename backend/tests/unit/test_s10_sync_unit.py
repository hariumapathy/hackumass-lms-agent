"""S10 sync framework: unit tests (no DB). docs/specs/S10-sync-framework.md."""

from datetime import UTC, datetime

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr, ValidationError

from app.connectors.base import NItem, NPost, SyncScope
from app.core.crypto import CryptoError, decrypt, encrypt, get_fernet
from app.core.settings import Settings
from app.sync.diff import changed_fields, classify, meaningful_fields, record_hash


def _item(**kw) -> NItem:  # noqa: ANN003
    base = dict(
        platform_id="99812",
        course_platform_id="12345",
        type="exam",
        title="Midterm 1",
        due_at=datetime(2026, 11, 21, tzinfo=UTC),
        points=100,
        source_url="https://example.instructure.com/courses/12345/assignments/99812",
    )
    return NItem(**{**base, **kw})


def test_s10_t01_hash_ignores_sync_timestamps_and_raw() -> None:
    a = _item(source_updated_at=datetime(2026, 11, 1, tzinfo=UTC), raw={"x": 1})
    b = _item(source_updated_at=datetime(2026, 11, 9, tzinfo=UTC), raw={"y": 2})
    assert record_hash(a) == record_hash(b)
    assert record_hash(a) != record_hash(_item(points=90))


def test_s10_t02_classify_new_changed_unchanged() -> None:
    h = record_hash(_item())
    assert classify(None, h) == "new"
    assert classify(h, h) == "unchanged"
    assert classify(record_hash(_item(title="Midterm One")), h) == "changed"


def test_s10_t02_changed_fields_lists_only_meaningful_differences() -> None:
    old = meaningful_fields(_item())
    new = meaningful_fields(_item(due_at=datetime(2026, 11, 23, tzinfo=UTC)))
    changes = changed_fields(
        {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in old.items()}, new
    )
    assert [(c.field, c.old, c.new) for c in changes] == [
        ("due_at", "2026-11-21T00:00:00+00:00", "2026-11-23T00:00:00+00:00")
    ]
    post_old = meaningful_fields(
        NPost(
            platform_id="1",
            course_platform_id="c",
            kind="announcement",
            title="T",
            body="a",
            posted_at=datetime(2026, 11, 1, tzinfo=UTC),
            source_url="u",
        )
    )
    assert [c.field for c in changed_fields(post_old, {**post_old, "body": "b"})] == ["body"]


def test_s10_scope_validation_and_key() -> None:
    assert SyncScope().key() == "full::"
    assert SyncScope(kind="course", course_platform_id="12").key() == "course:12:"
    with pytest.raises(ValidationError):
        SyncScope(kind="course")
    with pytest.raises(ValidationError):
        SyncScope(kind="item", course_platform_id="12")


def test_s10_t10_fernet_round_trip_and_wrong_key() -> None:
    key = Fernet.generate_key().decode()
    f = get_fernet(Settings(encryption_key=SecretStr(key)))
    token = "7~canvas-token-abc"
    ct = encrypt(token, f)
    assert ct != token.encode() and token.encode() not in ct
    assert decrypt(ct, f) == token
    other = get_fernet(Settings(encryption_key=SecretStr(Fernet.generate_key().decode())))
    with pytest.raises(CryptoError):
        decrypt(ct, other)


def test_s10_missing_encryption_key_refuses() -> None:
    with pytest.raises(CryptoError, match="ENCRYPTION_KEY"):
        get_fernet(Settings(encryption_key=None))
    with pytest.raises(CryptoError):
        get_fernet(Settings(encryption_key=SecretStr("not-a-key")))
