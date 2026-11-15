import logging

from app.core.logging import CalendarAccessFilter


def test_S25_calendar_feed_secrets_are_redacted_from_access_logs():
    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        "",
        0,
        '%s - "%s %s HTTP/%s" %d',
        ("client", "GET", "/calendar/very-private-token.ics?x=1", "1.1", 200),
        None,
    )
    CalendarAccessFilter().filter(record)
    assert "very-private-token" not in record.getMessage()
    assert "/calendar/[private].ics" in record.getMessage()
