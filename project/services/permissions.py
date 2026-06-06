from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import BoardMember, Task
from typing import Optional


async def get_user_board_membership(
    db: AsyncSession, user_id: int, board_id: int
) -> Optional[BoardMember]:
    """Получить членство пользователя в доске (или None, если не участник)."""
    result = await db.execute(
        select(BoardMember).where(
            BoardMember.user_id == user_id,
            BoardMember.board_id == board_id,
        )
    )
    return result.scalars().first()


async def require_board_member(
    db: AsyncSession, user_id: int, board_id: int
) -> BoardMember:
    """Проверить, что пользователь является участником доски."""
    membership = await get_user_board_membership(db, user_id, board_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Вы не являетесь участником этой доски",
        )
    return membership


async def require_board_admin(
    db: AsyncSession, user_id: int, board_id: int
) -> BoardMember:
    """Проверить, что пользователь является админом доски."""
    membership = await require_board_member(db, user_id, board_id)
    if membership.status != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуются права администратора доски",
        )
    return membership


async def require_student(
    db: AsyncSession, user_id: int, board_id: int
) -> BoardMember:
    """Проверить, что пользователь является студентом на доске."""
    membership = await require_board_member(db, user_id, board_id)
    if membership.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуются права студента",
        )
    return membership


async def require_mentor(
    db: AsyncSession, user_id: int, board_id: int
) -> BoardMember:
    """Проверить, что пользователь является наставником на доске."""
    membership = await require_board_member(db, user_id, board_id)
    if membership.role != "mentor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуются права наставника",
        )
    return membership


async def can_delete_task(
    db: AsyncSession, user_id: int, task_id: int
) -> bool:
    """
    Проверка права на удаление задачи.
    
    ВАЖНО: право определяется через принадлежность пользователя к board_id данной задачи,
    а НЕ через поле assignee_id. Любой участник доски (студент или админ) может удалить задачу.
    """
    # Получаем задачу
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalars().first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Задача не найдена",
        )
    
    # Проверяем, что пользователь является участником доски этой задачи
    membership = await get_user_board_membership(db, user_id, task.board_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Вы не являетесь участником доски этой задачи и не можете её удалить",
        )
    
    return True


async def check_task_move_permissions(
    db: AsyncSession, user_id: int, task_id: int, target_column: str, target_substatus: Optional[str]
) -> bool:
    """
    Проверка прав на перемещение задачи согласно матрице.
    
    Студент: может менять статус (in_progress → done), отправлять на проверку.
    Наставник: может проверять задачи (accept/return), менять substatus.
    """
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalars().first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена")
    
    membership = await require_board_member(db, user_id, task.board_id)
    
    # Студент может двигать задачи в колонку done (отправка на проверку)
    if membership.role == "student":
        if target_column == "done" and target_substatus == "in_review":
            return True
        if target_column == "in_progress" and task.column == "done":
            # Студент может отзывать задачу с проверки
            return True
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Студент может только отправлять задачу на проверку или отзывать её",
        )
    
    # Наставник может проверять задачи (accept/return)
    if membership.role == "mentor":
        if target_substatus in ("accepted", "returned"):
            return True
        if target_column == "in_progress" and target_substatus == "returned":
            return True
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Наставник может только проверять задачи (accept/return)",
        )
    
    return True