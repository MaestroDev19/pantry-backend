-- Core tables for pantry CRUD and embedding worker queue.
-- Must run before 20260324_* migrations that reference these tables.
-- If POST /rest/v1/pantry_items returns 404, apply this migration (or run the same SQL in the SQL Editor).

create extension if not exists vector;

create table if not exists public.pantry_items (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users (id) on delete cascade,
  household_id uuid not null,
  name text not null,
  category text not null,
  quantity double precision not null,
  unit text not null,
  expiry_date date,
  embedding vector(768),
  embedding_status text not null default 'pending',
  embedding_updated_at timestamptz,
  embedding_error text,
  created_at timestamptz not null default (now() at time zone 'utc'),
  updated_at timestamptz not null default (now() at time zone 'utc')
);

create index if not exists pantry_items_owner_id_idx on public.pantry_items (owner_id);
create index if not exists pantry_items_household_id_idx on public.pantry_items (household_id);

create table if not exists public.pantry_embedding_jobs (
  id bigint generated always as identity primary key,
  pantry_item_id uuid not null references public.pantry_items (id) on delete cascade,
  status text not null,
  attempts integer not null default 0,
  next_attempt_at timestamptz not null default (now() at time zone 'utc'),
  last_error text,
  updated_at timestamptz not null default (now() at time zone 'utc'),
  unique (pantry_item_id)
);

create index if not exists pantry_embedding_jobs_status_next_attempt_idx
  on public.pantry_embedding_jobs (status, next_attempt_at);
