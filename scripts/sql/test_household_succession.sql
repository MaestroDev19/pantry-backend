-- Manual regression checks for public.household_members_after_delete_succession.
--
-- Prerequisites (disposable local / staging only):
--   1. Edit u1, u2, u3 in the DO block below to real auth.users ids.
--   2. Migration 20260403194755_household_members_succession.sql applied.
--
-- Expected:
--   After deleting u1: owner becomes u2 (oldest joined_at).
--   After deleting u2: owner becomes u3.
--   After deleting u3: household row removed.
--   Tie-break: same joined_at -> lower user_id (uuid sort) becomes owner after owner leaves.
--
-- Run: psql $DATABASE_URL -v ON_ERROR_STOP=1 -f scripts/sql/test_household_succession.sql

BEGIN;

DO $$
DECLARE
  u1 uuid := '11111111-1111-1111-1111-111111111111'::uuid;
  u2 uuid := '22222222-2222-2222-2222-222222222222'::uuid;
  u3 uuid := '33333333-3333-3333-3333-333333333333'::uuid;
  hid uuid;
  owner uuid;
  ua uuid := 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'::uuid;
  ub uuid := 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'::uuid;
  htie uuid;
BEGIN
  INSERT INTO public.households (name, invite_code, is_personal, owner_id)
  VALUES ('Succession test', 'SUCC01', false, u1)
  RETURNING id INTO hid;

  INSERT INTO public.household_members (household_id, user_id, joined_at)
  VALUES
    (hid, u1, timestamptz '2026-01-01 10:00:00+00'),
    (hid, u2, timestamptz '2026-01-02 10:00:00+00'),
    (hid, u3, timestamptz '2026-01-03 10:00:00+00');

  DELETE FROM public.household_members WHERE user_id = u1 AND household_id = hid;
  SELECT h.owner_id INTO owner FROM public.households h WHERE h.id = hid;
  IF owner IS DISTINCT FROM u2 THEN
    RAISE EXCEPTION 'step1: expected owner %, got %', u2, owner;
  END IF;

  DELETE FROM public.household_members WHERE user_id = u2 AND household_id = hid;
  SELECT h.owner_id INTO owner FROM public.households h WHERE h.id = hid;
  IF owner IS DISTINCT FROM u3 THEN
    RAISE EXCEPTION 'step2: expected owner %, got %', u3, owner;
  END IF;

  DELETE FROM public.household_members WHERE user_id = u3 AND household_id = hid;
  IF EXISTS (SELECT 1 FROM public.households h WHERE h.id = hid) THEN
    RAISE EXCEPTION 'step3: household should be deleted';
  END IF;

  -- Tie-break: ua < ub as text; both same joined_at; owner ua leaves -> ub wins.
  INSERT INTO public.households (name, invite_code, is_personal, owner_id)
  VALUES ('Tie test', 'SUCC02', false, ua)
  RETURNING id INTO htie;

  INSERT INTO public.household_members (household_id, user_id, joined_at)
  VALUES
    (htie, ua, timestamptz '2026-06-01 12:00:00+00'),
    (htie, ub, timestamptz '2026-06-01 12:00:00+00');

  DELETE FROM public.household_members WHERE user_id = ua AND household_id = htie;
  SELECT h.owner_id INTO owner FROM public.households h WHERE h.id = htie;
  IF owner IS DISTINCT FROM ub THEN
    RAISE EXCEPTION 'tie: expected owner %, got %', ub, owner;
  END IF;

  DELETE FROM public.household_members WHERE user_id = ub AND household_id = htie;
END $$;

ROLLBACK;
