from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class FileResponse(BaseModel):
    id: int
    task_id: int
    filename: str
    original_filename: str
    mime_type: str
    size: int
    is_mentor_file: bool
    uploaded_by: Optional[str] = None
    uploaded_at: datetime

    class Config:
        from_attributes = True