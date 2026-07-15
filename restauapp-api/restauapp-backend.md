# RestauApp — Backend Developer Guide

**Stack:** Python · FastAPI · MongoDB Atlas · Render.com

---

## Folder Structure

```
restauapp-api/
├── main.py
├── db.py
├── .env
├── requirements.txt
├── models/
│   ├── user.py
│   ├── product.py
│   └── order.py
└── routes/
    ├── auth.py
    ├── products.py
    ├── orders.py
    └── payments.py
```

---

## Setup

```bash
mkdir restauapp-api
cd restauapp-api
python -m venv venv
venv\Scripts\activate
pip install fastapi uvicorn motor python-dotenv passlib httpx python-jose
```

`requirements.txt` banao:

```
fastapi
uvicorn
motor
python-dotenv
passlib
httpx
python-jose
```

---

## .env

```env
MONGO_URI=mongodb+srv://user:password@cluster0.xxxxx.mongodb.net/restauapp
SECRET_KEY=koi_bhi_random_string
SAFEPAY_SECRET=sec_xxxxxxxxxxxx
```

---

## db.py

```python
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

load_dotenv()

client = AsyncIOMotorClient(os.getenv("MONGO_URI"))
db = client["restauapp"]

users_col    = db["users"]
products_col = db["products"]
orders_col   = db["orders"]
payments_col = db["payments"]
```

---

## models/user.py

```python
from pydantic import BaseModel, EmailStr

class UserRegister(BaseModel):
    name: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str
```

---

## models/product.py

```python
from pydantic import BaseModel
from typing import Optional

class Product(BaseModel):
    name: str
    description: str
    price: float
    category: str
    image_url: Optional[str] = None
    is_available: bool = True
```

---

## models/order.py

```python
from pydantic import BaseModel
from typing import List

class OrderItem(BaseModel):
    product_id: str
    quantity: int
    price: float

class Order(BaseModel):
    user_id: str
    items: List[OrderItem]
    total_amount: float
    status: str = "pending"
```

---

## routes/auth.py

```python
from fastapi import APIRouter, HTTPException
from models.user import UserRegister, UserLogin
from db import users_col
from passlib.hash import bcrypt

router = APIRouter()

@router.post("/register")
async def register(user: UserRegister):
    exists = await users_col.find_one({"email": user.email})
    if exists:
        raise HTTPException(status_code=400, detail="Email pehle se registered hai")

    await users_col.insert_one({
        "name":     user.name,
        "email":    user.email,
        "password": bcrypt.hash(user.password),
        "role":     "customer"
    })
    return {"message": "Account ban gaya!"}


@router.post("/login")
async def login(creds: UserLogin):
    user = await users_col.find_one({"email": creds.email})
    if not user or not bcrypt.verify(creds.password, user["password"]):
        raise HTTPException(status_code=401, detail="Email ya password galat hai")

    return {
        "message": "Login ho gaya!",
        "name":    user["name"],
        "user_id": str(user["_id"])
    }
```

---

## routes/products.py

```python
from fastapi import APIRouter
from models.product import Product
from db import products_col
from bson import ObjectId

router = APIRouter()

@router.get("/")
async def get_products():
    products = []
    async for p in products_col.find({"is_available": True}):
        p["_id"] = str(p["_id"])
        products.append(p)
    return products


@router.get("/category/{cat}")
async def get_by_category(cat: str):
    products = []
    async for p in products_col.find({"category": cat}):
        p["_id"] = str(p["_id"])
        products.append(p)
    return products


@router.post("/")
async def add_product(product: Product):
    result = await products_col.insert_one(product.dict())
    return {"message": "Product add ho gaya!", "id": str(result.inserted_id)}


@router.delete("/{product_id}")
async def delete_product(product_id: str):
    await products_col.delete_one({"_id": ObjectId(product_id)})
    return {"message": "Product delete ho gaya!"}
```

---

## routes/orders.py

```python
from fastapi import APIRouter
from models.order import Order
from db import orders_col
from bson import ObjectId

router = APIRouter()

@router.post("/")
async def create_order(order: Order):
    result = await orders_col.insert_one(order.dict())
    return {"message": "Order place ho gaya!", "order_id": str(result.inserted_id)}


@router.get("/user/{user_id}")
async def get_user_orders(user_id: str):
    orders = []
    async for o in orders_col.find({"user_id": user_id}):
        o["_id"] = str(o["_id"])
        orders.append(o)
    return orders


@router.put("/{order_id}/status")
async def update_status(order_id: str, status: str):
    await orders_col.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": {"status": status}}
    )
    return {"message": f"Status update: {status}"}
```

---

## routes/payments.py

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db import orders_col, payments_col
from bson import ObjectId
import httpx
import os

router = APIRouter()

SAFEPAY_BASE   = "https://sandbox.api.getsafepay.com"
SAFEPAY_SECRET = os.getenv("SAFEPAY_SECRET")

class PaymentRequest(BaseModel):
    order_id: str
    amount: float
    user_id: str


@router.post("/create")
async def create_payment(data: PaymentRequest):
    amount_paisa = int(data.amount * 100)

    async with httpx.AsyncClient() as client:
        res = await client.post(f"{SAFEPAY_BASE}/order/v1/init", json={
            "client":      SAFEPAY_SECRET,
            "amount":      amount_paisa,
            "currency":    "PKR",
            "environment": "sandbox"
        })

    if res.status_code != 200:
        raise HTTPException(status_code=400, detail="Safepay error")

    tracker = res.json()["data"]["tracker"]["token"]

    await payments_col.insert_one({
        "order_id": data.order_id,
        "user_id":  data.user_id,
        "amount":   data.amount,
        "tracker":  tracker,
        "status":   "pending"
    })

    checkout_url = (
        f"https://sandbox.api.getsafepay.com/components"
        f"?env=sandbox&beacon={tracker}"
        f"&redirect_url=http://localhost:3000/payment/success"
        f"&cancel_url=http://localhost:3000/payment/cancel"
    )

    return {"checkout_url": checkout_url, "tracker": tracker}


@router.get("/success")
async def payment_success(order_id: str):
    await orders_col.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": {"status": "paid"}}
    )
    await payments_col.update_one(
        {"order_id": order_id},
        {"$set": {"status": "completed"}}
    )
    return {"message": "Payment ho gaya!"}


@router.get("/cancel")
async def payment_cancel(order_id: str):
    await orders_col.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": {"status": "cancelled"}}
    )
    return {"message": "Payment cancel ho gaya"}
```

---

## main.py

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import auth, products, orders, payments

app = FastAPI(title="RestauApp API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,     prefix="/api/auth",     tags=["Auth"])
app.include_router(products.router, prefix="/api/products", tags=["Products"])
app.include_router(orders.router,   prefix="/api/orders",   tags=["Orders"])
app.include_router(payments.router, prefix="/api/payments", tags=["Payments"])

@app.get("/")
async def home():
    return {"message": "RestauApp API chal rahi hai!"}
```

---

## App Chalao

```bash
uvicorn main:app --reload
```

- API: `http://localhost:8000`
- Docs: `http://localhost:8000/docs`

---

## All Endpoints

| Method | URL | Kaam |
|--------|-----|------|
| POST | `/api/auth/register` | Naya account |
| POST | `/api/auth/login` | Login |
| GET | `/api/products` | Sab products |
| GET | `/api/products/category/{cat}` | Category filter |
| POST | `/api/products` | Product add |
| DELETE | `/api/products/{id}` | Product delete |
| POST | `/api/orders` | Order place |
| GET | `/api/orders/user/{id}` | User ki orders |
| PUT | `/api/orders/{id}/status` | Status update |
| POST | `/api/payments/create` | Payment shuru |
| GET | `/api/payments/success` | Payment success |
| GET | `/api/payments/cancel` | Payment cancel |

---

## MongoDB Atlas Setup

1. `https://cloud.mongodb.com` pe free account banao
2. M0 Free cluster banao — AWS Mumbai choose karo
3. Database user banao — username/password note karo
4. Network Access — `0.0.0.0/0` allow karo
5. Connection string copy karo — `.env` mein daalo

---

## Render.com Deploy

```bash
# GitHub pe push karo pehle
git init
git add .
git commit -m "first commit"
git push origin main
```

Render pe:
1. New Web Service banao
2. GitHub repo connect karo
3. Start command: `uvicorn main:app --host 0.0.0.0 --port 8000`
4. Environment variables mein `.env` ki values daalo
5. Deploy!

URL milegi: `https://restauapp.onrender.com`

---

## C# App Connection

```csharp
// Testing
private static string BASE_URL = "http://localhost:8000/api";

// Production (Render deploy ke baad)
private static string BASE_URL = "https://restauapp.onrender.com/api";
```
