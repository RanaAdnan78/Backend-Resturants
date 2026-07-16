import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URI = "mongodb+srv://restauapp:restauapp123@cluster0.8tskltx.mongodb.net/restauapp?appName=Cluster0"

async def test():
    print("Connecting...")
    client = AsyncIOMotorClient(MONGO_URI)
    db = client["restauapp"]
    result = await db["test"].insert_one({"hello": "RestauApp!"})
    print("Connected! ID:", result.inserted_id)
    client.close()

asyncio.run(test())