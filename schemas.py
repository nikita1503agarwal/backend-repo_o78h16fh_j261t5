"""
Database Schemas for EcoHero+

Each Pydantic model represents a MongoDB collection. The collection name is the
lowercased class name. For example: User -> "user" collection.

These schemas are used for validating data before inserting into the database.
"""
from typing import Optional, Literal, List
from pydantic import BaseModel, Field, EmailStr


class User(BaseModel):
    """
    Users collection schema
    Collection: "user"
    """
    name: str = Field(..., description="Full name")
    age: int = Field(..., ge=0, le=120, description="Age in years")
    email: Optional[EmailStr] = Field(None, description="User email (optional for kids)")
    parent_email: Optional[EmailStr] = Field(
        None, description="Parent/guardian email for under-18 accounts"
    )
    is_parent_approved: bool = Field(
        False, description="Whether a parent has approved the account"
    )


class Challenge(BaseModel):
    """
    Eco challenges users can complete
    Collection: "challenge"
    """
    title: str = Field(..., description="Challenge title")
    description: str = Field(..., description="What to do")
    audience: Literal["kid", "adult", "all"] = Field(
        "all", description="Primary audience"
    )
    points: int = Field(..., ge=10, le=5000, description="Points awarded on completion")
    is_active: bool = Field(True, description="Whether challenge is available")


class Submission(BaseModel):
    """
    Proof submissions for completed challenges
    Collection: "submission"
    """
    user_id: str = Field(..., description="User id (string)")
    challenge_id: str = Field(..., description="Challenge id (string)")
    proof_url: Optional[str] = Field(
        None, description="URL to photo/video proof (optional for MVP)"
    )
    notes: Optional[str] = Field(None, description="Short note from the user")
    points_awarded: int = Field(..., ge=0, description="Points awarded for this submission")
    status: Literal["approved", "pending", "rejected"] = Field(
        "approved", description="Moderation status"
    )


class WalletTransaction(BaseModel):
    """
    Wallet transactions for redemptions and adjustments
    Collection: "wallettransaction"
    """
    user_id: str = Field(..., description="User id (string)")
    type: Literal["redeem", "adjustment"] = Field(..., description="Transaction type")
    points: int = Field(..., ge=1, description="Points deducted (positive number)")
    note: Optional[str] = Field(None, description="Optional description")


# Optional helper for badges (future):
class Badge(BaseModel):
    """
    Earned badges
    Collection: "badge"
    """
    user_id: str
    name: str
    icon: Optional[str] = None
    description: Optional[str] = None
