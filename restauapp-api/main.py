from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI(title="RestauApp API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def home():
    return {"message": "RestauApp API chal rahi hai!"}