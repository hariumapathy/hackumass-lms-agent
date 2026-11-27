-- S48 private source generations. Drain all writers/workers before compatible rollout.
alter table public.materials add column source_revision uuid not null default gen_random_uuid();
alter table public.posts add column source_revision uuid not null default gen_random_uuid();

create function public.rotate_processing_source_revision() returns trigger
language plpgsql set search_path = public, pg_temp as $$
declare outputs text[] := array['source_revision','processing_status','processing_error',
    'version','storage_path','page_count','duration_s','last_synced_at','created_at'];
begin
    if tg_op = 'INSERT' then
        new.source_revision := gen_random_uuid();
    elsif (to_jsonb(new) - outputs) is distinct from (to_jsonb(old) - outputs)
        or new.source_revision is distinct from old.source_revision then
        new.source_revision := gen_random_uuid();
    end if;
    return new;
end;
$$;
create trigger material_source_revision before insert or update on public.materials
    for each row execute function public.rotate_processing_source_revision();
create trigger post_source_revision before insert or update on public.posts
    for each row execute function public.rotate_processing_source_revision();

-- Persist payload origin; never derive an old payload's authorization from a current join.
alter table public.processing_intents add column parent_source_revision uuid;
update public.processing_intents i set parent_source_revision=m.source_revision
    from public.materials m where i.user_id=m.user_id and i.material_id=m.id;
update public.processing_intents i set parent_source_revision=p.source_revision
    from public.posts p where i.user_id=p.user_id and i.post_id=p.id;
-- Pending material payloads have no recorded origin. Reobserve without resetting stop policy.
update public.processing_intents set parent_source_revision=gen_random_uuid(),
    payload_ciphertext=null, revision=gen_random_uuid(), dispatched_at=null,
    dispatch_token=null,dispatch_started_at=null,last_started_at=null,
    blocked_reason=case when blocked_reason in ('configuration','permanent','exhausted','source_auth')
        then blocked_reason when attempts>=4 then 'exhausted' else 'source_refresh' end,
    last_error_code=case when blocked_reason in ('configuration','permanent','exhausted','source_auth')
        then last_error_code when attempts>=4 then 'worker_interrupted' else 'missing_source' end
    where material_id is not null and completed_at is null;
-- Posts read current owned DB text; invalidate old deliveries, preserving budget/stop policy.
update public.processing_intents i set source_hash=p.content_hash,
    parent_source_revision=p.source_revision,revision=gen_random_uuid(),dispatched_at=null,
    blocked_reason=case when i.blocked_reason is null and i.attempts>=4
        then 'exhausted' else i.blocked_reason end,
    last_error_code=case when i.blocked_reason is null and i.attempts>=4
        then 'worker_interrupted' else i.last_error_code end,
    dispatch_token=null,dispatch_started_at=null,last_started_at=null
    from public.posts p where i.post_id=p.id and i.user_id=p.user_id and i.completed_at is null;
alter table public.processing_intents alter column parent_source_revision set not null;

create function public.bind_initial_processing_source() returns trigger
language plpgsql set search_path = public, pg_temp as $$
begin
    if new.parent_source_revision is null then
        if new.material_id is not null then
            select source_revision into new.parent_source_revision from public.materials
                where id=new.material_id and user_id=new.user_id;
        else
            select source_revision into new.parent_source_revision from public.posts
                where id=new.post_id and user_id=new.user_id;
        end if;
    end if;
    return new;
end;
$$;
create trigger initial_processing_source before insert on public.processing_intents
    for each row execute function public.bind_initial_processing_source();
