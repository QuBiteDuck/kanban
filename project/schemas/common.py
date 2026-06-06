from pydantic import BaseModel, Field
from typing import Generic, TypeVar, List, Optional

T = TypeVar("T")

class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1, description="Номер страницы")
    limit: int = Field(default=50, ge=1, le=100, description="Количество элементов на странице")

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    limit: int
    pages: int

class SuccessResponse(BaseModel):
    success: bool = True
    message: Optional[str] = None