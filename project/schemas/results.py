from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from schemas.auth import UserResponse

class SubmissionTaskResponse(BaseModel):
    id: int
    title: str

    class Config:
        from_attributes = True

class SubmissionUserResponse(BaseModel):
    id: int
    name: Optional[str]
    email: str

    class Config:
        from_attributes = True

class SubmissionResponse(BaseModel):
    id: int
    task_id: int
    task: Optional[SubmissionTaskResponse] = None
    student: Optional[SubmissionUserResponse] = None
    status: str
    submitted_at: datetime
    mentor_comment: Optional[str]
    reviewed_at: Optional[datetime]
    mentor: Optional[SubmissionUserResponse] = None

    class Config:
        from_attributes = True

class SubmissionReview(BaseModel):
    action: str = Field(..., pattern="^(accept|return)$")
    comment: Optional[str] = Field(None, max_length=2000)

class SubmissionsListResponse(BaseModel):
    submissions: List[SubmissionResponse]
    total: int
    page: int
    limit: int
    pages: int