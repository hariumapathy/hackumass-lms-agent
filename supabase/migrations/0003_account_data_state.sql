-- S40 internal deletion checkpoint. Never contains course content or credentials.
create table public.account_data_state (
    user_id uuid primary key references auth.users(id) on delete cascade,
    generation bigint not null default 0 check (generation >= 0),
    state text not null check (state in ('pending', 'complete')),
    requested_at timestamptz not null default now(),
    completed_at timestamptz
);
alter table public.account_data_state enable row level security;
-- Only the trusted API/worker database role manages deletion. No client policies.
revoke all on public.account_data_state from anon, authenticated;
