from fastapi import APIRouter, Depends, HTTPException, status, Response, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
from database.session import get_db
from database.models import User, BoardMember
from schemas.auth import UserRegister, UserLogin, UserResponse, UserMeResponse
from dependencies import get_current_user
from config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверка пароля."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Хэширование пароля."""
    return pwd_context.hash(password)


def create_access_token(data: dict) -> str:
    """Создание JWT токена."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.JWT_EXPIRES_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.SECRET_KEY, 
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


@router.post("/register", response_model=UserResponse)
async def register(user_data: UserRegister, db: AsyncSession = Depends(get_db)):
    """Регистрация нового пользователя."""
    # Проверяем, существует ли пользователь с таким email
    result = await db.execute(select(User).where(User.email == user_data.email))
    existing_user = result.scalars().first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким email уже существует",
        )
    
    # Создаем нового пользователя
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        email=user_data.email,
        password_hash=hashed_password,
        name=user_data.name,
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return new_user


@router.post("/login")
async def login(
    user_data: UserLogin,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Вход в систему. Устанавливает JWT в HttpOnly cookie."""
    # Ищем пользователя
    result = await db.execute(select(User).where(User.email == user_data.email))
    user = result.scalars().first()
    
    if not user or not verify_password(user_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Создаем JWT токен
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email}
    )
    
    # Устанавливаем cookie с токеном
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=settings.JWT_EXPIRES_DAYS * 24 * 60 * 60,  # 7 дней в секундах
        samesite="lax",
        secure=False,  # В продакшене должно быть True (HTTPS)
    )
    
    return {"success": True, "message": "Успешный вход"}


@router.post("/logout")
async def logout(response: Response):
    """Выход из системы. Удаляет cookie."""
    response.delete_cookie(key="access_token")
    return {"success": True, "message": "Успешный выход"}


@router.get("/me", response_model=UserMeResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Получение информации о текущем пользователе."""
    # Базовая информация о пользователе
    user_data = UserMeResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        created_at=current_user.created_at,
    )
    
    # Можно добавить информацию о статусе в текущей доске, если передан board_id в query params
    # Но для простоты возвращаем базовую информацию
    
    return user_data