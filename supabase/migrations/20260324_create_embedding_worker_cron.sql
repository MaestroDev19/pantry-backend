-- Runs pantry embedding worker on a fixed schedule.
-- Update the endpoint URL if your API base URL changes.

create extension if not exists pg_cron;
create extension if not exists pg_net;

-- Store this once in Supabase SQL editor (or via migration in secure environment):
-- select vault.create_secret('YOUR_WORKER_SECRET', 'embedding_worker_secret');

create or replace function public.run_pantry_embedding_worker()
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  worker_secret text;
begin
  select decrypted_secret
  into worker_secret
  from vault.decrypted_secrets
  where name = 'embedding_worker_secret'
  limit 1;

  if worker_secret is null or length(worker_secret) = 0 then
    raise exception 'Missing vault secret: embedding_worker_secret';
  end if;

  perform net.http_post(
    url := 'https://YOUR_API_HOST/api/pantry-items/internal/embedding-jobs/run?max_jobs=20',
    headers := jsonb_build_object(
      'content-type', 'application/json',
      'x-worker-secret', worker_secret
    ),
    body := '{}'::jsonb
  );
end;
$$;

-- Replace existing schedule if it exists.
select cron.unschedule('pantry-embedding-worker')
where exists (
  select 1
  from cron.job
  where jobname = 'pantry-embedding-worker'
);

-- Every minute (free-tier friendly).
select cron.schedule(
  'pantry-embedding-worker',
  '* * * * *',
  $$select public.run_pantry_embedding_worker();$$
);
