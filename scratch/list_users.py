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

    try:
        res = supabase.table("profiles").select("*").execute()
        print("Profiles:")
        for profile in res.data:
            print(profile)
    except Exception as e:
        print("Error listing profiles:", e)

if __name__ == "__main__":
    asyncio.run(check())
