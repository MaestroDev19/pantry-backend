import asyncio
import os
import sys
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

# Set standard output to UTF-8
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

async def check():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in env")
        return

    supabase = create_client(url, key)

    try:
        res = supabase.table("remembered_recipes").select("*").eq("recipe_id", "53129").execute()
        if len(res.data) > 0:
            record = res.data[0]
            print("ID:", record.get("recipe_id"))
            recipe_data = record.get("recipe_data", {})
            print("Title:", recipe_data.get("title"))
            print("Instructions:")
            for idx, inst in enumerate(recipe_data.get("instructions", [])):
                print(f"  {idx + 1}: {repr(inst)}")
        else:
            print("Recipe not found")
    except Exception as e:
        print("Error reading remembered_recipes table:", e)

if __name__ == "__main__":
    asyncio.run(check())
