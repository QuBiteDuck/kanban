from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from database.session import get_db
from database.models import Invitation, BoardMember, Board, User
from schemas.boards import InviteInfoResponse
from schemas.common import SuccessResponse
from dependencies import get_current_user

router = APIRouter(prefix="/api/invitations", tags=["invitations"])


@router.get("/{token}", response_model=InviteInfoResponse)
async def get_invitation_info(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Получить информацию о приглашении по токену. Публичный эндпоинт."""
    result = await db.execute(
        select(Invitation)
        .options(
            Invitation.board
        )
        .where(Invitation.token == token)
    )
    invitation = result.scalars().first()
    
    if not invitation:
        return InviteInfoResponse(valid=False)
    
    # Проверяем срок действия
    if invitation.status != "pending" or invitation.expires_at < datetime.utcnow():
        return InviteInfoResponse(valid=False)
    
    return InviteInfoResponse(
        valid=True,
        board_name=invitation.board.name,
        invited_email=invitation.invited_email,
        expires_at=invitation.expires_at,
    )


@router.post("/{token}/accept", response_model=SuccessResponse)
async def accept_invitation(
    token: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Принять приглашение. Требует авторизации."""
    # Получаем приглашение
    result = await db.execute(
        select(Invitation)
        .options(Invitation.board)
        .where(Invitation.token == token)
    )
    invitation = result.scalars().first()
    
    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Приглашение не найдено",
        )
    
    # Проверяем срок действия и статус
    if invitation.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Приглашение уже использовано или отменено",
        )
    
    if invitation.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Срок действия приглашения истек",
        )
    
    # Проверяем, что email совпадает
    if invitation.invited_email != current_user.email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Это приглашение предназначено для другого пользователя",
        )
    
    # Проверяем, не является ли пользователь уже участником
    membership_check = await db.execute(
        select(BoardMember).where(
            BoardMember.board_id == invitation.board_id,
            BoardMember.user_id == current_user.id,
        )
    )
    if membership_check.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Вы уже являетесь участником этой доски",
        )
    
    # Получаем статус и роль из приглашения (по умолчанию member/student)
    # В реальной реализации эти поля должны храниться в Invitation
    # Для простоты используем значения по умолчанию
    new_membership = BoardMember(
        board_id=invitation.board_id,
        user_id=current_user.id,
        status="member",
        role="student",
        is_creator=False,
        invited_by=invitation.invited_by_id,
    )
    
    db.add(new_membership)
    
    # Обновляем статус приглашения
    invitation.status = "accepted"
    
    await db.commit()
    
    return SuccessResponse(
        success=True,
        message=f"Вы успешно присоединились к доске '{invitation.board.name}'",
    )