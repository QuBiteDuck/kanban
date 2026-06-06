from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from datetime import datetime
from database.session import get_db
from database.models import Submission, Task, User, ActivityLog, BoardMember
from schemas.results import SubmissionResponse, SubmissionReview, SubmissionsListResponse
from schemas.common import PaginatedResponse, SuccessResponse
from dependencies import get_current_user, get_pagination_params
from services.permissions import require_student, require_mentor, require_board_member

router = APIRouter(prefix="/api", tags=["results"])


@router.get("/boards/{board_id}/submissions", response_model=SubmissionsListResponse)
async def get_submissions(
    board_id: int,
    status_filter: str = Query(None, alias="status", pattern="^(pending|accepted|returned)$"),
    student_id: int = Query(None),
    pagination=Depends(get_pagination_params),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Получить список сабмишенов доски. Только для наставников/админов."""
    await require_mentor(db, current_user.id, board_id)
    
    query = (
        select(Submission)
        .options(
            selectinload(Submission.task),
            selectinload(Submission.reviewer)
        )
        .join(Task, Submission.task_id == Task.id)
        .join(User, Task.assignee_id == User.id) # Студент
        .where(Task.board_id == board_id)
    )
    
    if status_filter:
        query = query.where(Submission.status == status_filter)
    if student_id:
        query = query.where(Task.assignee_id == student_id)
        
    query = query.order_by(Submission.submitted_at.desc())
    
    # Подсчет
    count_query = select(func.count(Submission.id)).join(Task, Submission.task_id == Task.id).where(Task.board_id == board_id)
    if status_filter:
        count_query = count_query.where(Submission.status == status_filter)
    if student_id:
        count_query = count_query.where(Task.assignee_id == student_id)
        
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    pages = (total + pagination.limit - 1) // pagination.limit if total > 0 else 1
    
    query = query.offset((pagination.page - 1) * pagination.limit).limit(pagination.limit)
    result = await db.execute(query)
    submissions = result.scalars().all()
    
    items = []
    for sub in submissions:
        items.append(SubmissionResponse(
            id=sub.id,
            task_id=sub.task_id,
            task={"id": sub.task.id, "title": sub.task.title} if sub.task else None,
            student={"id": sub.task.assignee.id, "name": sub.task.assignee.name, "email": sub.task.assignee.email} if sub.task and sub.task.assignee else None,
            status=sub.status,
            submitted_at=sub.submitted_at,
            mentor_comment=sub.mentor_comment,
            reviewed_at=sub.reviewed_at,
            mentor={"id": sub.reviewer.id, "name": sub.reviewer.name, "email": sub.reviewer.email} if sub.reviewer else None
        ))
        
    return SubmissionsListResponse(
        submissions=items, total=total, page=pagination.page, limit=pagination.limit, pages=pages
    )


@router.post("/tasks/{task_id}/submissions", response_model=SubmissionResponse)
async def submit_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Студент отправляет задачу на проверку.
    Транзакция: обновление задачи + создание записи в submissions + лог.
    """
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalars().first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена")
        
    await require_student(db, current_user.id, task.board_id)
    
    # Проверяем, нет ли уже активной pending-попытки
    active_sub = await db.execute(
        select(Submission).where(Submission.task_id == task_id, Submission.status == "pending")
    )
    if active_sub.scalars().first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Задача уже отправлена на проверку")
        
    # Атомарная транзакция
    async with db.begin():
        # 1. Обновляем задачу
        task.column = "done"
        task.substatus = "in_review"
        
        # 2. Создаем сабмишен
        new_submission = Submission(
            task_id=task_id,
            status="pending"
        )
        db.add(new_submission)
        await db.flush() # Получаем ID
        
        # 3. Логируем
        log = ActivityLog(
            task_id=task_id, user_id=current_user.id, action="submit",
            new_value="Отправлено на проверку (in_review)"
        )
        db.add(log)
        
    await db.refresh(new_submission)
    
    return SubmissionResponse(
        id=new_submission.id, task_id=new_submission.task_id, status=new_submission.status,
        submitted_at=new_submission.submitted_at, mentor_comment=new_submission.mentor_comment,
        reviewed_at=new_submission.reviewed_at
    )


@router.delete("/tasks/{task_id}/submissions/{submission_id}", response_model=SuccessResponse)
async def revoke_submission(
    task_id: int,
    submission_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Студент отзывает задачу с проверки.
    Транзакция: удаление записи + возврат задачи в in_progress.
    """
    result = await db.execute(
        select(Submission).where(Submission.id == submission_id, Submission.task_id == task_id)
    )
    submission = result.scalars().first()
    if not submission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сабмишен не найден")
        
    if submission.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Можно отозвать только ожидающие проверки задачи")
        
    task_result = await db.execute(select(Task).where(Task.id == task_id))
    task = task_result.scalars().first()
    
    await require_student(db, current_user.id, task.board_id)
    
    # Атомарная транзакция
    async with db.begin():
        await db.delete(submission)
        task.column = "in_progress"
        task.substatus = None
        
        log = ActivityLog(
            task_id=task_id, user_id=current_user.id, action="revoke",
            new_value="Отозвано с проверки (in_progress)"
        )
        db.add(log)
        
    return SuccessResponse(message="Задача отозвана с проверки")


@router.post("/submissions/{submission_id}/review", response_model=SubmissionResponse)
async def review_submission(
    submission_id: int,
    review_data: SubmissionReview,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Наставник проверяет задачу (accept / return).
    Транзакция: обновление submission + обновление task + лог.
    """
    result = await db.execute(
        select(Submission).options(selectinload(Submission.task)).where(Submission.id == submission_id)
    )
    submission = result.scalars().first()
    if not submission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сабмишен не найден")
        
    if submission.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Этот сабмишен уже был проверен")
        
    task = submission.task
    await require_mentor(db, current_user.id, task.board_id)
    
    # Атомарная транзакция
    async with db.begin():
        submission.status = review_data.action # 'accepted' or 'returned'
        submission.mentor_comment = review_data.comment
        submission.reviewed_at = datetime.utcnow()
        submission.reviewed_by_id = current_user.id
        
        if review_data.action == "accept":
            task.substatus = "accepted"
            action_desc = "Принято наставником"
        else: # return
            task.substatus = "returned"
            task.column = "in_progress" # Возвращаем в работу
            action_desc = "Возвращено на доработку"
            
        log = ActivityLog(
            task_id=task.id, user_id=current_user.id, action="review",
            old_value="in_review", new_value=action_desc
        )
        db.add(log)
        
    await db.refresh(submission)
    
    return SubmissionResponse(
        id=submission.id, task_id=submission.task_id, status=submission.status,
        submitted_at=submission.submitted_at, mentor_comment=submission.mentor_comment,
        reviewed_at=submission.reviewed_at,
        mentor={"id": current_user.id, "name": current_user.name, "email": current_user.email}
    )