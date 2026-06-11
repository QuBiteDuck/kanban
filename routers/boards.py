from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import Optional
import uuid
from datetime import datetime, timedelta
from database.session import get_db
from database.models import Board, BoardMember, User, Invitation
from schemas.boards import (
    BoardCreate, BoardUpdate, BoardResponse, BoardDetailResponse,
    BoardMemberResponse, InviteCreate, InviteResponse
)
from schemas.common import PaginatedResponse, SuccessResponse
from dependencies import get_current_user, get_pagination_params
from services.permissions import require_board_admin, require_board_member
from config import settings

router = APIRouter(prefix="/api/boards", tags=["boards"])


@router.get("", response_model=PaginatedResponse[BoardResponse])
async def get_boards(
    pagination=Depends(get_pagination_params),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Получить список досок, где пользователь является участником."""
    # Получаем доски, где пользователь является участником
    query = (
        select(Board)
        .join(BoardMember)
        .where(BoardMember.user_id == current_user.id)
        .order_by(Board.created_at.desc())
        .offset((pagination.page - 1) * pagination.limit)
        .limit(pagination.limit)
    )
    
    result = await db.execute(query)
    boards = result.scalars().all()
    
    # Получаем общее количество
    count_query = (
        select(func.count(Board.id))
        .join(BoardMember)
        .where(BoardMember.user_id == current_user.id)
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    pages = (total + pagination.limit - 1) // pagination.limit
    
    return PaginatedResponse(
        items=boards,
        total=total,
        page=pagination.page,
        limit=pagination.limit,
        pages=pages,
    )


@router.post("", response_model=BoardResponse)
async def create_board(
    board_data: BoardCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Создать новую доску. Создатель автоматически становится админом."""
    # Создаем доску
    new_board = Board(
        name=board_data.name,
        description=board_data.description,
        owner_id=current_user.id,
    )
    
    db.add(new_board)
    await db.flush()  # Получаем ID доски
    
    # Добавляем создателя как админа
    creator_membership = BoardMember(
        board_id=new_board.id,
        user_id=current_user.id,
        status="admin",
        role="student",  # По умолчанию студент
        is_creator=True,
    )
    
    db.add(creator_membership)
    await db.commit()
    await db.refresh(new_board)
    
    return new_board


@router.get("/{board_id}", response_model=BoardDetailResponse)
async def get_board(
    board_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Получить детальную информацию о доске."""
    # Проверяем, что пользователь является участником
    membership = await require_board_member(db, current_user.id, board_id)
    
    # Получаем доску с участниками
    result = await db.execute(
        select(Board)
        .options(selectinload(Board.members).selectinload(BoardMember.user))
        .where(Board.id == board_id)
    )
    board = result.scalars().first()
    
    if not board:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Доска не найдена",
        )
    
    # Формируем ответ
    members_data = [
        BoardMemberResponse(
            user_id=member.user_id,
            email=member.user.email,
            name=member.user.name,
            status=member.status,
            role=member.role,
            is_creator=member.is_creator,
            joined_at=member.joined_at,
        )
        for member in board.members
    ]
    
    return BoardDetailResponse(
        id=board.id,
        name=board.name,
        description=board.description,
        owner_id=board.owner_id,
        created_at=board.created_at,
        members=members_data,
        current_user_status=membership.status,
        current_user_role=membership.role,
    )


@router.put("/{board_id}", response_model=BoardResponse)
async def update_board(
    board_id: int,
    board_data: BoardUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Обновить доску. Только для админов."""
    await require_board_admin(db, current_user.id, board_id)
    
    result = await db.execute(select(Board).where(Board.id == board_id))
    board = result.scalars().first()
    
    if not board:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Доска не найдена",
        )
    
    # Обновляем поля
    if board_data.name is not None:
        board.name = board_data.name
    if board_data.description is not None:
        board.description = board_data.description
    
    await db.commit()
    await db.refresh(board)
    
    return board


@router.delete("/{board_id}", response_model=SuccessResponse)
async def delete_board(
    board_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Удалить доску. Только для админов."""
    await require_board_admin(db, current_user.id, board_id)
    
    result = await db.execute(select(Board).where(Board.id == board_id))
    board = result.scalars().first()
    
    if not board:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Доска не найдена",
        )
    
    await db.delete(board)
    await db.commit()
    
    return SuccessResponse(message="Доска успешно удалена")


@router.get("/{board_id}/members", response_model=PaginatedResponse[BoardMemberResponse])
async def get_board_members(
    board_id: int,
    pagination=Depends(get_pagination_params),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Получить список участников доски."""
    await require_board_member(db, current_user.id, board_id)
    
    query = (
        select(BoardMember)
        .options(selectinload(BoardMember.user))
        .where(BoardMember.board_id == board_id)
        .offset((pagination.page - 1) * pagination.limit)
        .limit(pagination.limit)
    )
    
    result = await db.execute(query)
    members = result.scalars().all()
    
    # Общее количество
    count_query = select(func.count(BoardMember.id)).where(BoardMember.board_id == board_id)
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    pages = (total + pagination.limit - 1) // pagination.limit
    
    members_data = [
        BoardMemberResponse(
            user_id=member.user_id,
            email=member.user.email,
            name=member.user.name,
            status=member.status,
            role=member.role,
            is_creator=member.is_creator,
            joined_at=member.joined_at,
        )
        for member in members
    ]
    
    return PaginatedResponse(
        items=members_data,
        total=total,
        page=pagination.page,
        limit=pagination.limit,
        pages=pages,
    )


@router.post("/{board_id}/members/invite", response_model=InviteResponse)
async def invite_member(
    board_id: int,
    invite_data: InviteCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Пригласить участника на доску. Только для админов."""
    await require_board_admin(db, current_user.id, board_id)
    
    # Проверяем, существует ли пользователь с таким email
    result = await db.execute(select(User).where(User.email == invite_data.email))
    invited_user = result.scalars().first()
    
    if not invited_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь с таким email не найден",
        )
    
    # Проверяем, не является ли пользователь уже участником
    membership_check = await db.execute(
        select(BoardMember).where(
            BoardMember.board_id == board_id,
            BoardMember.user_id == invited_user.id,
        )
    )
    if membership_check.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь уже является участником доски",
        )
    
    # Создаем приглашение
    token = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(days=7)
    
    invitation = Invitation(
        token=token,
        board_id=board_id,
        invited_email=invite_data.email,
        status="pending",
        invited_by_id=current_user.id,
        expires_at=expires_at,
    )
    
    db.add(invitation)
    await db.commit()
    
    # Формируем ссылку приглашения
    invitation_link = f"http://localhost:8000/invite/{token}"
    
    return InviteResponse(
        success=True,
        invitation_token=token,
        invitation_link=invitation_link,
    )


@router.put("/{board_id}/members/{user_id}", response_model=SuccessResponse)
async def update_member_role(
    board_id: int,
    user_id: int,
    status_update: Optional[str] = Query(None, pattern="^(admin|member)$"),
    role_update: Optional[str] = Query(None, pattern="^(mentor|student)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Изменить статус/роль участника. Только для админов. Нельзя менять создателя."""
    await require_board_admin(db, current_user.id, board_id)
    
    # Получаем участника
    result = await db.execute(
        select(BoardMember).where(
            BoardMember.board_id == board_id,
            BoardMember.user_id == user_id,
        )
    )
    member = result.scalars().first()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Участник не найден",
        )
    
    # Проверяем, что это не создатель
    if member.is_creator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нельзя изменить статус/роль создателя доски",
        )
    
    # Обновляем поля
    if status_update is not None:
        member.status = status_update
    if role_update is not None:
        member.role = role_update
    
    await db.commit()
    
    return SuccessResponse(message="Роль участника успешно обновлена")


@router.delete("/{board_id}/members/{user_id}", response_model=SuccessResponse)
async def remove_member(
    board_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Удалить участника из доски. Пользователь может удалить сам себя."""
    # Получаем участника
    result = await db.execute(
        select(BoardMember).where(
            BoardMember.board_id == board_id,
            BoardMember.user_id == user_id,
        )
    )
    member = result.scalars().first()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Участник не найден",
        )
    
    # Проверяем, что это не создатель
    if member.is_creator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Создатель не может покинуть доску",
        )
    
    # Проверяем права: либо сам пользователь, либо админ
    if current_user.id != user_id:
        await require_board_admin(db, current_user.id, board_id)
    
    await db.delete(member)
    await db.commit()
    
    return SuccessResponse(message="Участник успешно удален из доски")