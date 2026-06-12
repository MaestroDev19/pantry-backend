import httpx
import asyncio

async def main():
    url = "https://pantry-backend-livid.vercel.app/api/pantry-items/internal/embedding-jobs/run?max_jobs=20"
    headers = {
        "x-worker-secret": "PantryEmbeddingWorkerSecret"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers)
            print("Status code:", response.status_code)
            print("Response:", response.text)
    except Exception as e:
        print("Error calling endpoint:", e)

if __name__ == "__main__":
    asyncio.run(main())
