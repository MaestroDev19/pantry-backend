import asyncio
import os
import uuid
import random
import string
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

def random_string(length=10):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))

async def check():
    url = os.getenv("SUPABASE_URL")
    # We use publishable key for client-side authenticated requests
    key = os.getenv("SUPABASE_PUBLISHABLE_KEY")
    if not url or not key:
        print("Missing SUPABASE_URL or SUPABASE_PUBLISHABLE_KEY in env")
        return

    # Initialize client
    client = create_client(url, key)
    
    email = f"test_{random_string()}@example.com"
    password = f"Password_{random_string()}"
    
    print(f"Creating test user: {email}")
    try:
        # Sign up
        auth_res = client.auth.sign_up({"email": email, "password": password})
        user = auth_res.user
        if not user:
            print("Failed to sign up test user (no user returned)")
            return
        
        user_id = user.id
        print(f"Signed up successfully. User ID: {user_id}")
        
        # Test inserting into remembered_recipes
        recipe_id = str(uuid.uuid4())
        recipe_data = {
            "id": recipe_id,
            "title": "RLS Test Recipe",
            "ingredients": ["test"],
            "instructions": ["test"],
            "source": "generated"
        }
        
        print(f"Attempting to insert remembered recipe as user {user_id}...")
        try:
            # Set the user's JWT token on the client headers for authenticated request
            # (sign_up usually logs in the user automatically, but let's make sure the session is active)
            session = auth_res.session
            if session:
                client.postgrest.auth(session.access_token)
                
            res = client.table("remembered_recipes").upsert({
                "user_id": user_id,
                "recipe_id": recipe_id,
                "recipe_data": recipe_data
            }).execute()
            print("SUCCESS! Inserted recipe successfully.")
            print("Response:", res.data)
        except Exception as insert_err:
            print("INSERT FAILED WITH ERROR:")
            print(insert_err)
            
    except Exception as e:
        print("Auth or unexpected error:", e)

if __name__ == "__main__":
    asyncio.run(check())
