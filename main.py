import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import User, Challenge, Submission, WalletTransaction

app = FastAPI(title="EcoHero+ API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Helpers
class ObjectIdStr(BaseModel):
    id: str


def to_str_id(doc):
    if doc is None:
        return None
    d = {**doc}
    if d.get("_id") is not None:
        d["id"] = str(d.pop("_id"))
    return d


@app.get("/")
def read_root():
    return {"message": "EcoHero+ Backend Ready"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": [],
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, "name") else "Unknown"
            response["connection_status"] = "Connected"
            try:
                response["collections"] = db.list_collection_names()
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# Seed a few default challenges if none exist
@app.post("/seed")
def seed_challenges():
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    existing = db["challenge"].count_documents({})
    if existing > 0:
        return {"status": "ok", "seeded": False, "count": existing}

    defaults = [
        {
            "title": "Draw a poster about saving trees",
            "description": "Create a colorful poster that shows how trees help the planet.",
            "audience": "kid",
            "points": 100,
            "is_active": True,
        },
        {
            "title": "Water a plant",
            "description": "Water a plant at home or school and take a photo.",
            "audience": "kid",
            "points": 100,
            "is_active": True,
        },
        {
            "title": "Switch off lights before bed",
            "description": "Make it a habit to switch off unnecessary lights.",
            "audience": "kid",
            "points": 50,
            "is_active": True,
        },
        {
            "title": "Plant a tree",
            "description": "Plant a tree in your community or backyard.",
            "audience": "adult",
            "points": 1000,
            "is_active": True,
        },
        {
            "title": "Recycle bottles",
            "description": "Recycle at least 10 plastic or glass bottles.",
            "audience": "adult",
            "points": 500,
            "is_active": True,
        },
        {
            "title": "Use bicycle/public transport",
            "description": "Choose a bike or public transport instead of a car for a trip.",
            "audience": "adult",
            "points": 300,
            "is_active": True,
        },
    ]

    for item in defaults:
        create_document("challenge", Challenge(**item))

    return {"status": "ok", "seeded": True, "count": len(defaults)}


# Public endpoints
@app.get("/challenges")
def list_challenges(audience: Optional[str] = None):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    query = {"is_active": True}
    if audience in {"kid", "adult"}:
        query["audience"] = audience
    docs = get_documents("challenge", query, limit=100)
    return [to_str_id(d) for d in docs]


class CreateUserRequest(User):
    pass


@app.post("/users")
def create_user(payload: CreateUserRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    # Simple parental approval rule: under 18 requires parent_email
    if payload.age < 18 and not payload.parent_email:
        raise HTTPException(status_code=400, detail="Parent email required for under-18 users")

    new_id = create_document("user", payload)
    return {"id": new_id}


class SubmitRequest(BaseModel):
    user_id: str
    challenge_id: str
    notes: Optional[str] = None


@app.post("/submit")
def submit_challenge(payload: SubmitRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    # Basic existence checks
    try:
        user = db["user"].find_one({"_id": ObjectId(payload.user_id)})
        challenge = db["challenge"].find_one({"_id": ObjectId(payload.challenge_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ids provided")

    if not user or not challenge:
        raise HTTPException(status_code=404, detail="User or challenge not found")

    # Award points per challenge definition
    points = challenge.get("points", 0)

    sub = Submission(
        user_id=payload.user_id,
        challenge_id=payload.challenge_id,
        proof_url=None,
        notes=payload.notes,
        points_awarded=points,
        status="approved",
    )
    sub_id = create_document("submission", sub)

    return {"id": sub_id, "points_awarded": points}


@app.get("/wallet/{user_id}")
def get_wallet(user_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    try:
        _ = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user id")

    # Sum approved submissions minus redemptions
    earned = sum(
        d.get("points_awarded", 0)
        for d in db["submission"].find({"user_id": user_id, "status": "approved"})
    )
    redeemed = sum(
        d.get("points", 0)
        for d in db["wallettransaction"].find({"user_id": user_id, "type": "redeem"})
    )
    balance = max(0, earned - redeemed)

    dollars = balance / 1000.0  # 1000 points = $1

    return {
        "user_id": user_id,
        "points": balance,
        "dollars": round(dollars, 2),
        "can_withdraw": dollars >= 10.0,
        "min_withdrawal_dollars": 10.0,
    }


class RedeemRequest(BaseModel):
    user_id: str
    points: int
    for_under18: Optional[bool] = False


@app.post("/redeem")
def redeem_points(payload: RedeemRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    # Get wallet
    wallet = get_wallet(payload.user_id)
    if payload.points <= 0 or payload.points > wallet["points"]:
        raise HTTPException(status_code=400, detail="Invalid points amount")

    # Enforce min withdrawal $10
    dollars = payload.points / 1000.0
    if dollars < 10.0:
        raise HTTPException(status_code=400, detail="Minimum withdrawal is $10")

    # Record redemption
    txn = WalletTransaction(
        user_id=payload.user_id,
        type="redeem",
        points=payload.points,
        note=("Parent-approved withdrawal" if payload.for_under18 else "Withdrawal"),
    )
    txn_id = create_document("wallettransaction", txn)

    return {"id": txn_id, "status": "pending_payout"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
