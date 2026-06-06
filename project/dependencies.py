from fastapi import Depends, HTTPException, status, Cookie, Query
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError, jwt
from typing import Optional
from config import settings
from database.session import get_db
from database.models import User
from schemas.common import PaginationParams


async def get_current_user(
    access_token: Optional[str] = Cookie(None, alias="access_token"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Извлечение текущего пользователя из JWT в HttpOnly cookie.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Недействительные учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not access_token:
        raise credentials_exception
    
    try:
        payload = jwt.decode(
            access_token, 
            settings.SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        user_id: int = payload.get("sub")
        email: str = payload.get("email")
        
        if user_id is None or email is None:
            raise credentials_exception
        
    except JWTError:
        raise credentials_exception
    
    # Получаем пользователя из БД
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    
    if not user:
        raise credentials_exception
    
    return user


async def get_optional_user(
    access_token: Optional[str] = Cookie(None, alias="access_token"),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Получить пользователя, если он авторизован (или None)."""
    try:
        return await get_current_user(access_token, db)
    except HTTPException:
        return None


def get_pagination_params(
    page: int = Query(default=1, ge=1, description="Номер страницы"),
    limit: int = Query(default=50, ge=1, le=100, description="Количество элементов на странице"),
) -> PaginationParams:
    """Параметры пагинации."""
    return PaginationParams(page=page, limit=limit)