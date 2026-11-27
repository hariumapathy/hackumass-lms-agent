-- S44 transactional processing outbox; private source payload is encrypted, worker-only.
create table public.processing_intents (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    material_id uuid unique references public.materials(id) on delete cascade,
    post_id uuid unique references public.posts(id) on delete cascade,
    source_hash text not null,
    revision uuid not null default gen_random_uuid(),
    payload_ciphertext bytea,
    dispatch_token uuid,
    dispatch_started_at timestamptz,
    dispatched_at timestamptz,
    completed_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint processing_intent_one_parent check ((material_id is null) <> (post_id is null)),
    constraint processing_intent_lease_pair check ((dispatch_token is null) = (dispatch_started_at is null))
);
create index processing_intents_owner on public.processing_intents(user_id);
create index processing_intents_pending on public.processing_intents(created_at,id)
    where dispatched_at is null and completed_at is null;
alter table public.processing_intents enable row level security;
revoke all on public.processing_intents from anon, authenticated;
