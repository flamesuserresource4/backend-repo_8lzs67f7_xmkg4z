"""
Database Schemas for Joybait MVP

Each Pydantic model corresponds to a MongoDB collection. The collection
name is the lowercase class name by convention in this environment.

Collections defined:
- User -> "user"
- Challenge -> "challenge" (for future dynamic packs; static list used for now)
- Reflection -> "reflection"
- Group -> "group"
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime

Mode = Literal["casual", "challenge"]
MoodTag = Literal["social", "solo", "uplifting"]
EnvironmentTag = Literal["home", "public", "school", "work"]

class User(BaseModel):
    name: Optional[str] = Field(None, description="Display name")
    email: Optional[str] = Field(None, description="User email (optional for MVP)")
    mode: Optional[Mode] = Field(None, description="User-selected play mode")
    xp: int = Field(0, ge=0, description="Total experience points")
    streak: int = Field(0, ge=0, description="Consecutive completion streak")
    last_completed_at: Optional[datetime] = Field(None, description="UTC timestamp of last completion")
    preferences: Optional[dict] = Field(default_factory=dict, description="Filter preferences")

class Challenge(BaseModel):
    title: str
    description: Optional[str] = None
    mood: MoodTag
    environment: EnvironmentTag
    confidence: int = Field(..., ge=1, le=5)

class Reflection(BaseModel):
    user_id: str
    challenge_id: str
    mood_before: int = Field(..., ge=1, le=5)
    mood_after: int = Field(..., ge=1, le=5)
    note: Optional[str] = None
    is_public: bool = Field(False, description="Eligible for Joy Gallery")

class Group(BaseModel):
    name: str
    code: str
    owner_id: str
    member_ids: List[str] = Field(default_factory=list)
    current_challenge_id: Optional[str] = None
