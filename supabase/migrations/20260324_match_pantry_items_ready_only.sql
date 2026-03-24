-- Ensures vector retrieval only returns rows with ready embeddings.
-- Assumes pantry_items.embedding is a pgvector column.

create extension if not exists vector;

drop function if exists public.match_pantry_items(vector, integer, jsonb);

create or replace function public.match_pantry_items(
  query_embedding vector(768),
  match_count int default 10,
  filter jsonb default '{}'::jsonb
)
returns table (
  id uuid,
  owner_id uuid,
  household_id uuid,
  name text,
  category text,
  quantity double precision,
  unit text,
  expiry_date date,
  embedding_status text,
  similarity double precision
)
language sql
stable
set search_path = public, extensions
as $$
  select
    p.id,
    p.owner_id,
    p.household_id,
    p.name,
    p.category,
    p.quantity,
    p.unit,
    p.expiry_date,
    p.embedding_status,
    1 - (p.embedding <=> query_embedding) as similarity
  from public.pantry_items p
  where p.embedding is not null
    and p.embedding_status = 'ready'
    and (
      filter = '{}'::jsonb
      or (
        (not (filter ? 'household_id') or p.household_id = (filter->>'household_id')::uuid)
        and (not (filter ? 'owner_id') or p.owner_id = (filter->>'owner_id')::uuid)
        and (not (filter ? 'category') or p.category = filter->>'category')
      )
    )
  order by p.embedding <=> query_embedding
  limit greatest(match_count, 1);
$$;
