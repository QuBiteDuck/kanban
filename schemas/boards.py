from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from schemas.auth import UserResponse

class BoardCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)

class BoardUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)

class BoardResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    owner_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class BoardMemberResponse(BaseModel):
    user_id: int
    email: str
    name: Optional[str]
    status: str
    role: str
    is_creator: bool
    joined_at: datetime

    class Config:
        from_attributes = True

class BoardDetailResponse(BoardResponse):
    members: List[BoardMemberResponse]
    current_user_status: str
    current_user_role: str

class InviteCreate(BaseModel):
    email: EmailStr
    status: str = Field(..., pattern="^(admin|member)$")
    role: str = Field(..., pattern="^(mentor|student)$")

class InviteResponse(BaseModel):
    success: bool = True
    invitation_token: str
    invitation_link: str

class InviteInfoResponse(BaseModel):
    valid: bool
    board_name: Optional[str] = None
    invited_email: Optional[str] = None
    expires_at: Optional[datetime] = None