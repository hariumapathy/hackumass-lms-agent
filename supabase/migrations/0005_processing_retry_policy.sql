-- S45 bounded retry policy; private outbox only, no application response fields.
alter table public.processing_intents
    add column attempts integer not null default 0 check (attempts >= 0 and attempts <= 4),
    add column next_attempt_at timestamptz not null default now(),
    add column last_started_at timestamptz,
    add column blocked_reason text check (blocked_reason in
        ('configuration','source_auth','permanent','exhausted','source_refresh')),
    add column last_error_code text;
