-- Legacy trigger called sync_pantry_embedding(), which referenced public.pantry_embeddings.
-- That table is not part of this project; embeddings live on pantry_items and jobs are
-- enqueued by the pantry microservice into pantry_embedding_jobs.

drop trigger if exists trigger_sync_pantry_embedding on public.pantry_items;
drop function if exists public.sync_pantry_embedding();
