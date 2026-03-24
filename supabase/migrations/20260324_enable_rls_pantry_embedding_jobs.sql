-- Enables RLS on queue table exposed in public schema.
-- No client-facing policies are added because jobs are service-managed.

alter table public.pantry_embedding_jobs enable row level security;
