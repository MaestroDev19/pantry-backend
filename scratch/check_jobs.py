import asyncio
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

async def check():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in env")
        return

    supabase = create_client(url, key)

    # Check pantry items count and status
    res = supabase.table("pantry_items").select("embedding_status", count="exact").execute()
    print(f"Total pantry items: {res.count if hasattr(res, 'count') else len(res.data)}")
    
    # Group by embedding status
    res_status = supabase.table("pantry_items").select("id, embedding_status").execute()
    status_counts = {}
    for row in res_status.data:
        status_counts[row["embedding_status"]] = status_counts.get(row["embedding_status"], 0) + 1
    print("Pantry items by status:", status_counts)

    # Check jobs table
    res_jobs = supabase.table("pantry_embedding_jobs").select("*").execute()
    print(f"Total embedding jobs: {len(res_jobs.data)}")
    for job in res_jobs.data[:10]:
        print(f"Job ID: {job['id']}, Item ID: {job['pantry_item_id']}, Status: {job['status']}, Attempts: {job['attempts']}, Last Error: {job['last_error']}")

    # Let's run a query to check pg_net/pg_cron details using RPC or another way if possible,
    # or just query pg_cron using sql/rpc. Since we don't have SQL endpoint, we can do it via a custom query or pg_cron functions if exposed, or we might need to look at our schema.
    try:
        # Check if we can execute raw sql or helper rpc
        # Let's see if we can read job runs
        pass
    except Exception as e:
        print("Failed to fetch cron details:", e)

if __name__ == "__main__":
    asyncio.run(check())
