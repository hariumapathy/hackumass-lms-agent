-- S46 private source access epochs. Stop workers before applying; no imported data is deleted.
alter table public.connection_secrets
    add column revision uuid not null default gen_random_uuid();

create function public.rotate_source_revision() returns trigger
language plpgsql set search_path = public, pg_temp as $$
begin
    -- Even identical explicit replacements are a new grant. Never trust caller-supplied epochs.
    new.revision := gen_random_uuid();
    return new;
end;
$$;
create trigger rotate_source_revision before insert or update on public.connection_secrets
    for each row execute function public.rotate_source_revision();

create function public.invalidate_source_runs() returns trigger
language plpgsql set search_path = public, pg_temp as $$
declare owner_id uuid; source public.platform;
begin
    -- Do not lock the parent here: legacy UPDATE already holds the secret row lock.
    select user_id, platform into owner_id, source from public.connections
        where id = case when tg_op = 'DELETE' then old.connection_id else new.connection_id end;
    if owner_id is not null then
        perform public.procrastinate_cancel_job_v1(id, false, false)
            from public.procrastinate_jobs where task_name='sync_platform' and status='todo'
            and args->'job'->>'user_id'=owner_id::text
            and args->'job'->>'platform'=source::text;
        update public.sync_runs set status='failed', finished_at=now(),
            error='Connection changed. Please update your classes again.'
            where user_id=owner_id and platform=source and status in ('queued','running');
    end if;
    return null;
end;
$$;
create trigger invalidate_source_runs after insert or update or delete on public.connection_secrets
    for each row execute function public.invalidate_source_runs();

-- Pre-epoch queue envelopes cannot safely adopt whatever credential exists at execution time.
select public.procrastinate_cancel_job_v1(id, false, false)
    from public.procrastinate_jobs where task_name='sync_platform' and status='todo';
update public.sync_runs set status='failed', finished_at=now(),
    error='Please update your classes again.' where status in ('queued','running');
