-- Household membership and user profiles (for pantry owner display).
-- Safe to run if tables already exist (e.g. Supabase starter templates).

create table if not exists public.households (
  id uuid primary key default gen_random_uuid(),
  created_at timestamp with time zone null default (now() at time zone 'utc')
);

create table if not exists public.profiles (
  id uuid not null,
  updated_at timestamp with time zone null,
  full_name text null,
  avatar_url text null,
  email text null,
  constraint profiles_pkey primary key (id),
  constraint profiles_id_fkey foreign key (id) references auth.users (id) on delete cascade
);

create table if not exists public.household_members (
  id uuid not null default gen_random_uuid (),
  household_id uuid null,
  user_id uuid null,
  joined_at timestamp with time zone null default now(),
  constraint household_members_pkey primary key (id),
  constraint household_members_user_id_key unique (user_id),
  constraint household_members_household_id_fkey foreign key (household_id) references public.households (id) on delete cascade,
  constraint household_members_user_id_fkey foreign key (user_id) references auth.users (id) on delete cascade
);

create index if not exists idx_household_members_user on public.household_members using btree (user_id);

create index if not exists idx_household_members_household on public.household_members using btree (household_id);

create index if not exists idx_household_members_household_user on public.household_members using btree (household_id, user_id);
