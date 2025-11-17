import os
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import db, create_document, get_documents
from schemas import User as UserSchema, Reflection as ReflectionSchema

app = FastAPI(title="Joybait API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------
# Utility / seed content
# ----------------------

SEED_CHALLENGES = [
    {
        "_id": "c1",
        "title": "Give someone a genuine compliment",
        "description": "Keep it specific and sincere.",
        "mood": "social",
        "environment": "public",
        "confidence": 2,
    },
    {
        "_id": "c2",
        "title": "Ask a stranger about their favorite food",
        "description": "If you're shy, try a barista or cashier.",
        "mood": "social",
        "environment": "public",
        "confidence": 3,
    },
    {
        "_id": "c3",
        "title": "Sit alone at a café and smile at someone nearby",
        "description": "A gentle moment of openness.",
        "mood": "solo",
        "environment": "public",
        "confidence": 1,
    },
    {
        "_id": "c4",
        "title": "Send a kind message to a friend you haven't talked to in a while",
        "description": "Low-pressure, high-warmth.",
        "mood": "uplifting",
        "environment": "home",
        "confidence": 1,
    },
]

# Simple badge logic for MVP
BADGES = [
    {"id": "first", "name": "First Step", "requirement": 1},
    {"id": "week1", "name": "Week One", "requirement": 7},
    {"id": "streak5", "name": "On a Roll", "requirement": 5},
]


# ----------------------
# Models (requests)
# ----------------------

class SignupRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    mode: Optional[str] = None  # "casual" | "challenge"

class ModeRequest(BaseModel):
    mode: str

class ChallengeFilter(BaseModel):
    mood: Optional[str] = None
    environment: Optional[str] = None
    confidence_min: Optional[int] = None
    confidence_max: Optional[int] = None

class ReflectionRequest(BaseModel):
    user_id: str
    challenge_id: str
    mood_before: int
    mood_after: int
    note: Optional[str] = None
    is_public: bool = False


# ----------------------
# Health
# ----------------------

@app.get("/")
def read_root():
    return {"message": "Joybait backend running"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "❌ Not Set",
        "database_name": "❌ Not Set",
        "connection_status": "Not Connected",
        "collections": [],
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
            try:
                response["collections"] = db.list_collection_names()
                response["database"] = "✅ Connected & Working"
                response["connection_status"] = "Connected"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response


# ----------------------
# Auth (MVP pseudo-auth)
# ----------------------

@app.post("/auth/signup")
def signup(payload: SignupRequest):
    # For MVP, create anonymous-ish user document and return its id
    user = UserSchema(
        name=payload.name,
        email=payload.email,
        mode=payload.mode,
        xp=0,
        streak=0,
        preferences={},
    )
    user_id = create_document("user", user)
    return {"user_id": user_id}

@app.post("/user/{user_id}/mode")
def set_mode(user_id: str, payload: ModeRequest):
    # Save as preference document for simplicity
    if db is None:
        raise HTTPException(500, "Database not configured")
    db["user"].update_one({"_id": {"$eq": db.get_default_codec_options().document_class().get("_id", user_id)}}, {"$set": {"mode": payload.mode}})
    return {"ok": True, "mode": payload.mode}


# ----------------------
# Challenges
# ----------------------

@app.post("/challenge/next")
def get_next_challenge(filters: ChallengeFilter):
    # Filter from seed list for MVP
    candidates = SEED_CHALLENGES
    if filters.mood:
        candidates = [c for c in candidates if c["mood"] == filters.mood]
    if filters.environment:
        candidates = [c for c in candidates if c["environment"] == filters.environment]
    if filters.confidence_min is not None:
        candidates = [c for c in candidates if c["confidence"] >= filters.confidence_min]
    if filters.confidence_max is not None:
        candidates = [c for c in candidates if c["confidence"] <= filters.confidence_max]

    if not candidates:
        raise HTTPException(404, "No challenges match those filters yet")

    # Simple rotation: pick by day index
    idx = datetime.now(timezone.utc).toordinal() % len(candidates)
    return candidates[idx]

@app.get("/challenges")
def list_challenges():
    return SEED_CHALLENGES


# ----------------------
# Reflections & XP
# ----------------------

@app.post("/reflect")
def submit_reflection(payload: ReflectionRequest):
    # Save reflection
    ref = ReflectionSchema(**payload.model_dump())
    reflection_id = create_document("reflection", ref)

    # Update XP and streak
    if db is None:
        raise HTTPException(500, "Database not configured")

    user_doc = db["user"].find_one({"_id": {"$exists": True}})  # naive, will update by id next
    # Better: use the provided id
    user_doc = db["user"].find_one({"_id": payload.user_id}) if db else None

    today = datetime.now(timezone.utc).date()

    if user_doc:
        last = user_doc.get("last_completed_at")
        last_date = last.date() if isinstance(last, datetime) else None
        streak = user_doc.get("streak", 0)
        if last_date == today:
            # already completed today: small xp
            xp_gain = 5
        else:
            xp_gain = 10
            if last_date and (today - last_date).days == 1:
                streak += 1
            else:
                streak = 1
        db["user"].update_one(
            {"_id": payload.user_id},
            {"$set": {"last_completed_at": datetime.now(timezone.utc), "streak": streak},
             "$inc": {"xp": xp_gain}},
        )
    else:
        # If somehow user not found, ignore for MVP
        pass

    return {"reflection_id": reflection_id}


@app.get("/user/{user_id}/profile")
def get_profile(user_id: str):
    if db is None:
        raise HTTPException(500, "Database not configured")
    user = db["user"].find_one({"_id": user_id})
    if not user:
        raise HTTPException(404, "User not found")

    # Compute badges
    xp = user.get("xp", 0)
    streak = user.get("streak", 0)
    badges = [b for b in BADGES if xp >= b["requirement"] or streak >= b["requirement"]]

    # Last 5 reflections
    refs = list(db["reflection"].find({"user_id": user_id}).sort("created_at", -1).limit(5))

    return {
        "user": {
            "_id": user_id,
            "name": user.get("name"),
            "mode": user.get("mode"),
            "xp": xp,
            "streak": streak,
        },
        "badges": badges,
        "recent_reflections": [
            {
                "id": str(r.get("_id")),
                "challenge_id": r.get("challenge_id"),
                "mood_before": r.get("mood_before"),
                "mood_after": r.get("mood_after"),
                "note": r.get("note"),
                "created_at": r.get("created_at"),
            }
            for r in refs
        ],
    }


# ----------------------
# Joy Gallery (public feed)
# ----------------------

@app.get("/gallery")
def gallery(limit: int = 20):
    if db is None:
        raise HTTPException(500, "Database not configured")
    docs = list(
        db["reflection"].find({"is_public": True}).sort("created_at", -1).limit(min(limit, 50))
    )
    return [
        {
            "id": str(d.get("_id")),
            "challenge_id": d.get("challenge_id"),
            "note": d.get("note"),
            "mood_after": d.get("mood_after"),
            "created_at": d.get("created_at"),
        }
        for d in docs
    ]


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
