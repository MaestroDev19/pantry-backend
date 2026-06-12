import asyncio
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

async def main():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
        return
    
    supabase = create_client(url, key)
    try:
        print("Calling RPC run_pantry_embedding_worker...")
        res = supabase.rpc("run_pantry_embedding_worker").execute()
        print("RPC executed successfully!")
        print("Response:", res.data)
    except Exception as e:
        print("RPC execution failed:", e)

if __name__ == "__main__":
    asyncio.run(main())
