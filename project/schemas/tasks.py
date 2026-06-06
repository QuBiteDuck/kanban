from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date
from schemas.auth import UserResponse

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    description: Optional[str] = Field(None, max_length=5000)
    priority: str = Field(default="med", pattern="^(high|med|low)$")
    due_date: Optional[date] = None
    assignee_id: Optional[int] = None
    tags: Optional[List[str]] = Field(default_factory=list)

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=300)
    description: Optional[str] = Field(None, max_length=5000)
    priority: Optional[str] = Field(None, pattern="^(high|med|low)$")
    due_date: Optional[date] = None
    assignee_id: Optional[int] = None
    tags: Optional[List[str]] = None

class TaskMove(BaseModel):
    target_column: str = Field(..., pattern="^(not_started|in_progress|done)$")
    target_substatus: Optional[str] = Field(None, pattern="^(in_review|accepted|returned)$")

class TaskAssigneeResponse(BaseModel):
    id: int
    name: Optional[str]
    email: str

    class Config:
        from_attributes = True

class TaskResponse(BaseModel):
    id: int
    board_id: int
    title: str
    description: Optional[str]
    column: str
    substatus: Optional[str]
    priority: str
    due_date: Optional[date]
    assignee: Optional[TaskAssigneeResponse] = None
    tags: List[str]
    subtasks_count: int = 0
    comments_count: int = 0
    files_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class SubtaskCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)
    order: Optional[int] = None

class SubtaskUpdate(BaseModel):
    text: Optional[str] = Field(None, min_length=1, max_length=500)
    is_completed: Optional[bool] = None
    order: Optional[int] = None

class SubtaskResponse(BaseModel):
    id: int
    task_id: int
    text: str
    is_completed: bool
    order: int

    class Config:
        from_attributes = True

class CommentCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)

class CommentUpdate(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)

class CommentAuthorResponse(BaseModel):
    id: int
    name: Optional[str]
    email: str

    class Config:
        from_attributes = True

class CommentResponse(BaseModel):
    id: int
    task_id: int
    user_id: int
    text: str
    author: Optional[CommentAuthorResponse] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ActivityResponse(BaseModel):
    id: int
    task_id: int
    user_id: int
    action: str
    old_value: Optional[str]
    new_value: Optional[str]
    user_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class TaskDetailResponse(TaskResponse):
    subtasks: List[SubtaskResponse]
    comments: List[CommentResponse]
    activity: List[ActivityResponse]
    files: List[dict]