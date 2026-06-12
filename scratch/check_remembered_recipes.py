import asyncio
import os
import uuid
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

    # Check remembered_recipes table structure and records
    try:
        res = supabase.table("remembered_recipes").select("*").execute()
        print(f"Total remembered recipes: {len(res.data)}")
        if len(res.data) > 0:
            print("Sample record:")
            print(res.data[0])
    except Exception as e:
        print("Error reading remembered_recipes table:", e)

    # Let's try to query information_schema or pg_policies to see if there is any policy on remembered_recipes
    # Since we have service_role, we might be able to query pg_policies? Wait, supabase-py table() only accesses exposed tables/views in public. pg_policies is in pg_catalog. Let's see if we can query it or if it is blocked.
    try:
        # Check if pg_policies is queryable
        res = supabase.table("pg_policies").select("*").execute()
        print("pg_policies queryable!")
    except Exception as e:
        print("Could not query pg_policies directly via table():", e)

if __name__ == "__main__":
    asyncio.run(check())
