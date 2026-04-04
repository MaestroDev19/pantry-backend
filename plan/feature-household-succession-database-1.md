---
goal: Postgres-enforced household owner succession and household delete when last member leaves
version: 1.0
date_created: 2026-04-03
last_updated: 2026-04-03
owner: pantry-microservice
status: 'Planned'
tags: ['feature', 'migration', 'supabase', 'households', 'postgres']
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

Automate promotion of `households.owner_id` to the longest-tenured remaining member (`household_members.joined_at`, tie-break `user_id`) whenever a member row is deleted and the owner is no longer a member; delete the `households` row when the last `household_members` row for that household is removed. Enforcement is exclusively via one `AFTER DELETE` trigger on `public.household_members` so `DELETE` and `auth.users` `ON DELETE CASCADE` paths behave identically.

## 1. Requirements & Constraints

| ID | Statement |
|----|-----------|
| REQ-001 | On `AFTER DELETE` on `household_members`, if no rows remain for `OLD.household_id`, `DELETE` the `households` row with that `id`. |
| REQ-002 | If one or more members remain and `households.owner_id` is `NULL` or not found in remaining `household_members` for that household, set `owner_id` to the successor row: `ORDER BY joined_at ASC NULLS LAST, user_id ASC LIMIT 1`. |
| REQ-003 | If `owner_id` still references a remaining member, do not change `owner_id`. |
| REQ-004 | Implementation is one PL/pgSQL function + one trigger; function is `SECURITY DEFINER` with safe `search_path`. |
| REQ-005 | No client-facing `GRANT EXECUTE` on the function; only trigger invokes it. |
| CON-001 | `household_members.user_id` is globally unique (one household per user); successor selection is per `household_id`. |
| CON-002 | Child tables must use `ON DELETE CASCADE` from `households` where “no orphans” is required. |
| SEC-001 | `search_path` must be pinned to avoid hijacking in `SECURITY DEFINER`. |

## 2. Implementation Steps

### Implementation Phase 1 — Database objects

- GOAL-001: Add succession function and `AFTER DELETE` trigger on `public.household_members`.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Author migration SQL with `household_members_after_delete_succession()` exactly as specified in `docs/superpowers/plans/2026-04-03-household-succession-postgres.md`. |  |  |
| TASK-002 | Create trigger `household_members_succession` `AFTER DELETE` `FOR EACH ROW`. |  |  |
| TASK-003 | `REVOKE ALL` on function from `PUBLIC`. |  |  |
| TASK-004 | Audit FKs from `households` / `household_members`; add or fix `ON DELETE CASCADE` on dependents that must not orphan. |  |  |

### Implementation Phase 2 — Integration & verification

- GOAL-002: Align `leave_household_rpc` and verify cascade from user deletion.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | Verify `leave_household_rpc` removes the member row (trigger fires). Remove duplicate owner updates from RPC if any. |  |  |
| TASK-006 | Reconcile with existing triggers on `households` / `household_members` (`sync_household_owner_membership`, etc.). |  |  |
| TASK-007 | Run manual SQL scenario script (multi-member, tie-break, last-member household delete). |  |  |
| TASK-008 | Optional: add Supabase/local integration coverage or document that SQL script is the authority. |  |  |

## 3. Alternatives

- **ALT-001:** `BEFORE DELETE` trigger — rejected; row still visible in `AFTER DELETE` for counting remaining without off-by-one.
- **ALT-002:** App-only succession in FastAPI — rejected; user requirement is bypass-proof including raw SQL and future routes.

## 4. Dependencies

- **DEP-001:** Supabase project with `households`, `household_members`, and existing RPCs.
- **DEP-002:** Knowledge of all FKs referencing `households(id)`.

## 5. Files

- **FILE-001:** `supabase/migrations/<timestamp>_household_members_succession.sql` — function, trigger, revokes.
- **FILE-002:** `docs/superpowers/plans/2026-04-03-household-succession-postgres.md` — human implementation plan.
- **FILE-003:** `.agents/prompts/household-succession-implementation.md` — agent prompts.
- **FILE-004:** Supabase SQL definitions for `leave_household_rpc` / related triggers (modify if needed).

## 6. Testing

- **TEST-001:** Three members, delete owner → `owner_id` equals oldest remaining by `joined_at`.
- **TEST-002:** Same `joined_at`, two users → deterministic `user_id` order.
- **TEST-003:** Delete last member → `households` row removed.
- **TEST-004:** Delete non-owner member → `owner_id` unchanged.
- **TEST-005:** Simulate `auth.users` delete with CASCADE on `household_members` → same outcomes.

## 7. Risks & Assumptions

- **RISK-001:** Missing `ON DELETE CASCADE` on a child table leaves orphans when household is deleted — mitigated by FK audit (TASK-004).
- **RISK-001b:** Concurrent last-two-members leaving — rare; both paths should converge to empty household + delete; if failures occur, consider `SELECT ... FOR UPDATE` on `households` inside the function (short lock).
- **ASSUMPTION-001:** `leave_household_rpc` deletes the membership row for the leaving user in the shared household context.

## 8. Related Specifications / Further Reading

- `docs/superpowers/plans/2026-04-03-household-succession-postgres.md`
- `.agents/skills/postgres-concurrency-and-locking-safety/SKILL.md`
