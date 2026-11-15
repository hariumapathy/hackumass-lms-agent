-- S01: database schema (contract). Source of truth for all stored data.
-- Spec: docs/specs/S01-database-schema.md. Change only with whole-team agreement (AGENTS.md).
--
-- Rules implemented here:
--   * Every table has user_id (except connection_secrets, which cascades from connections).
--   * RLS on every table. `authenticated` may only SELECT its own rows; no client writes at all.
--     The backend writes with the service role / direct DB connection, and every repository
--     function filters by user_id (S01 rule 3).
--   * connection_secrets: RLS on, no policies, no grants -> no client role can ever read it.
--   * All timestamps are UTC timestamptz.

create extension if not exists vector with schema extensions;
create extension if not exists pgcrypto with schema extensions;

-- ---------------------------------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------------------------------
create type public.platform as enum ('canvas', 'gradescope', 'echo360', 'piazza');
create type public.record_status as enum ('active', 'changed', 'removed');
create type public.connection_status as enum ('active', 'needs_reconnect', 'error', 'disconnected');
create type public.item_type as enum ('assignment', 'exam', 'quiz', 'lab', 'project', 'other');
create type public.material_kind as enum ('file', 'page', 'syllabus', 'transcript');
create type public.post_kind as enum ('announcement', 'piazza', 'email');
create type public.processing_status as enum ('pending', 'processing', 'done', 'failed', 'skipped');
create type public.sync_trigger as enum ('schedule', 'connect', 'manual', 'agent');
create type public.sync_status as enum ('queued', 'running', 'succeeded', 'failed', 'needs_reconnect');
create type public.study_set_type as enum ('plan', 'quiz', 'flashcards');
create type public.study_block_status as enum ('proposed', 'approved', 'declined');

-- ---------------------------------------------------------------------------------------------
-- Identity and connections
-- ---------------------------------------------------------------------------------------------
create table public.profiles (
  user_id uuid primary key references auth.users on delete cascade,
  display_name text,
  timezone text not null default 'America/New_York',
  model_choice text,
  created_at timestamptz not null default now()
);

create table public.connections (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users on delete cascade,
  platform public.platform not null,
  status public.connection_status not null default 'active',
  expires_at timestamptz,
  last_sync_at timestamptz,
  last_error text,
  account_label text,
  created_at timestamptz not null default now(),
  unique (user_id, platform)
);

create table public.connection_secrets (
  connection_id uuid primary key references public.connections on delete cascade,
  ciphertext bytea not null,
  kind text not null check (kind in ('canvas_token', 'storage_state')),
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------------------------
-- Courses and course content
-- ---------------------------------------------------------------------------------------------
create table public.courses (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users on delete cascade,
  name text not null,
  code text,
  term text,
  color text,
  created_at timestamptz not null default now()
);

-- Common source columns (S01): platform, platform_id, source_url, content_hash,
-- source_updated_at, last_synced_at, status, unique (user_id, platform, platform_id).
create table public.course_links (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users on delete cascade,
  course_id uuid not null references public.courses on delete cascade,
  platform public.platform not null,
  platform_id text not null,
  source_url text not null,
  content_hash text not null,
  source_updated_at timestamptz,
  last_synced_at timestamptz not null default now(),
  status public.record_status not null default 'active',
  created_at timestamptz not null default now(),
  unique (user_id, platform, platform_id)
);

create table public.items (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users on delete cascade,
  course_id uuid not null references public.courses on delete cascade,
  type public.item_type not null default 'other',
  title text not null,
  description text,
  due_at timestamptz,
  points numeric,
  status public.record_status not null default 'active',
  updated_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create table public.item_sources (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users on delete cascade,
  item_id uuid references public.items on delete set null,
  course_id uuid not null references public.courses on delete cascade,
  raw_title text not null,
  raw_due_at timestamptz,
  raw jsonb not null default '{}'::jsonb,
  platform public.platform not null,
  platform_id text not null,
  source_url text not null,
  content_hash text not null,
  source_updated_at timestamptz,
  last_synced_at timestamptz not null default now(),
  status public.record_status not null default 'active',
  created_at timestamptz not null default now(),
  unique (user_id, platform, platform_id)
);

create table public.materials (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users on delete cascade,
  course_id uuid not null references public.courses on delete cascade,
  kind public.material_kind not null,
  title text not null,
  mime_type text,
  storage_path text,
  page_count int,
  duration_s int,
  recorded_at timestamptz,
  version int not null default 1,
  processing_status public.processing_status not null default 'pending',
  processing_error text,
  platform public.platform not null,
  platform_id text not null,
  source_url text not null,
  content_hash text not null,
  source_updated_at timestamptz,
  last_synced_at timestamptz not null default now(),
  status public.record_status not null default 'active',
  created_at timestamptz not null default now(),
  unique (user_id, platform, platform_id)
);

create table public.posts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users on delete cascade,
  course_id uuid not null references public.courses on delete cascade,
  kind public.post_kind not null,
  title text not null,
  body text not null default '',
  author text,
  posted_at timestamptz not null,
  platform public.platform not null,
  platform_id text not null,
  source_url text not null,
  content_hash text not null,
  source_updated_at timestamptz,
  last_synced_at timestamptz not null default now(),
  status public.record_status not null default 'active',
  created_at timestamptz not null default now(),
  unique (user_id, platform, platform_id)
);

create table public.chunks (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users on delete cascade,
  course_id uuid not null references public.courses on delete cascade,
  material_id uuid references public.materials on delete cascade,
  post_id uuid references public.posts on delete cascade,
  material_version int,
  is_current boolean not null default true,
  text text not null,
  page int,
  start_s int,
  end_s int,
  token_count int not null,
  embedding extensions.vector(1536) not null,
  tsv tsvector generated always as (to_tsvector('english', text)) stored,
  created_at timestamptz not null default now(),
  constraint chunks_one_parent check ((material_id is null) <> (post_id is null))
);

create table public.changes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users on delete cascade,
  entity_type text not null check (entity_type in ('item', 'post', 'material')),
  entity_id uuid not null,
  course_id uuid references public.courses on delete cascade,
  field text not null,
  old_value jsonb,
  new_value jsonb,
  detected_at timestamptz not null default now(),
  seen_at timestamptz,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------------------------
-- Agent, study and calendar
-- ---------------------------------------------------------------------------------------------
create table public.conversations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users on delete cascade,
  title text not null default 'New chat',
  updated_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create table public.messages (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users on delete cascade,
  conversation_id uuid not null references public.conversations on delete cascade,
  role text not null check (role in ('user', 'assistant')),
  content jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table public.agent_runs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users on delete cascade,
  conversation_id uuid references public.conversations on delete cascade,
  model text not null,
  status text not null default 'running' check (status in ('running', 'done', 'error')),
  turns int not null default 0,
  tool_calls jsonb not null default '[]'::jsonb,
  allowed_chunk_ids bigint[] not null default '{}',
  error text,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  created_at timestamptz not null default now()
);

create table public.study_sets (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users on delete cascade,
  course_id uuid references public.courses on delete set null,
  conversation_id uuid references public.conversations on delete set null,
  type public.study_set_type not null,
  title text not null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table public.study_blocks (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users on delete cascade,
  run_id uuid references public.agent_runs on delete set null,
  course_id uuid references public.courses on delete set null,
  item_id uuid references public.items on delete set null,
  title text not null,
  start_at timestamptz not null,
  end_at timestamptz not null,
  status public.study_block_status not null default 'proposed',
  decided_at timestamptz,
  created_at timestamptz not null default now(),
  constraint study_blocks_time_order check (end_at > start_at)
);

create table public.calendar_feeds (
  user_id uuid primary key references auth.users on delete cascade,
  secret_token text not null unique,
  rotated_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create table public.sync_runs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users on delete cascade,
  platform public.platform not null,
  scope jsonb not null default '{"kind": "full"}'::jsonb,
  trigger public.sync_trigger not null,
  status public.sync_status not null default 'queued',
  stats jsonb not null default '{"new": 0, "changed": 0, "unchanged": 0, "removed": 0}'::jsonb,
  error text,
  queued_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz not null default now()
);

create table public.misses (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users on delete cascade,
  tool text not null,
  query text not null,
  course_id uuid references public.courses on delete set null,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------------------------
create index items_user_due_idx on public.items (user_id, due_at);
create index items_course_idx on public.items (course_id);
create index item_sources_item_idx on public.item_sources (item_id);
create index course_links_course_idx on public.course_links (course_id);
create index materials_course_idx on public.materials (user_id, course_id);
create index chunks_embedding_hnsw_idx on public.chunks
  using hnsw (embedding extensions.vector_cosine_ops);
create index chunks_tsv_idx on public.chunks using gin (tsv);
create index chunks_user_course_current_idx on public.chunks (user_id, course_id, is_current);
create index chunks_material_idx on public.chunks (material_id);
create index chunks_post_idx on public.chunks (post_id);
create index changes_user_detected_idx on public.changes (user_id, detected_at desc);
create index posts_user_course_posted_idx on public.posts (user_id, course_id, posted_at desc);
create index sync_runs_user_platform_finished_idx on public.sync_runs
  (user_id, platform, finished_at desc);
create index messages_conversation_idx on public.messages (conversation_id, created_at);
create index study_blocks_user_start_idx on public.study_blocks (user_id, start_at);

-- ---------------------------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------------------------
do $$
declare
  t text;
  user_tables text[] := array[
    'profiles', 'connections', 'courses', 'course_links', 'items', 'item_sources', 'materials',
    'posts', 'chunks', 'changes', 'conversations', 'messages', 'agent_runs', 'study_sets',
    'study_blocks', 'calendar_feeds', 'sync_runs', 'misses'
  ];
begin
  foreach t in array user_tables loop
    execute format('alter table public.%I enable row level security', t);
    -- Clients read only; every write goes through the backend.
    execute format('revoke all on public.%I from anon, authenticated', t);
    execute format('grant select on public.%I to authenticated', t);
    execute format(
      'create policy %I on public.%I for select to authenticated using (user_id = (select auth.uid()))',
      t || '_select_own', t
    );
  end loop;
end
$$;

-- Secrets: RLS on with no policies and no grants. Only the service role / backend reads them.
alter table public.connection_secrets enable row level security;
revoke all on public.connection_secrets from anon, authenticated;

-- New tables added later must repeat the pattern above; don't let Supabase's default
-- privileges hand clients write access.
alter default privileges in schema public revoke insert, update, delete, truncate
  on tables from anon, authenticated;
