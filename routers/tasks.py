from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete
from sqlalchemy.orm import selectinload
from typing import Optional, List
from datetime import datetime
from database.session import get_db
from database.models import (
    Task, Subtask, Comment, File, ActivityLog, 
    BoardMember, User, Submission
)
from schemas.tasks import (
    TaskCreate, TaskUpdate, TaskResponse, TaskMove, TaskDetailResponse,
    SubtaskCreate, SubtaskUpdate, SubtaskResponse,
    CommentCreate, CommentUpdate, CommentResponse, ActivityResponse, CommentAuthorResponse
)
from schemas.common import PaginatedResponse, SuccessResponse
from dependencies import get_current_user, get_pagination_params
from services.permissions import (
    require_board_member, require_student, require_mentor, 
    can_delete_task, check_task_move_permissions, get_user_board_membership
)
from services.file_service import FileService

router = APIRouter(prefix="/api", tags=["tasks"])


# ==========================================
# ЗАДАЧИ (TASKS)
# ==========================================

@router.get("/boards/{board_id}/tasks", response_model=PaginatedResponse[TaskResponse])
async def get_tasks(
    board_id: int,
    q: Optional[str] = Query(None, description="Поиск по названию"),
    column: Optional[str] = Query(None, pattern="^(not_started|in_progress|done)$"),
    priority: Optional[str] = Query(None, pattern="^(high|med|low)$"),
    assignee_id: Optional[int] = Query(None),
    pagination=Depends(get_pagination_params),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Получить список задач доски с фильтрацией и пагинацией."""
    await require_board_member(db, current_user.id, board_id)
    
    # Подзапросы для подсчета количества связанных элементов
    subtasks_count_q = select(func.count(Subtask.id)).where(Subtask.task_id == Task.id).scalar_subquery()
    comments_count_q = select(func.count(Comment.id)).where(Comment.task_id == Task.id).scalar_subquery()
    files_count_q = select(func.count(File.id)).where(File.task_id == Task.id).scalar_subquery()
    
    query = select(
        Task, subtasks_count_q, comments_count_q, files_count_q
    ).where(Task.board_id == board_id)
    
    if q:
        query = query.where(Task.title.ilike(f"%{q}%"))
    if column:
        query = query.where(Task.column == column)
    if priority:
        query = query.where(Task.priority == priority)
    if assignee_id:
        query = query.where(Task.assignee_id == assignee_id)
        
    query = query.order_by(Task.created_at.desc())
    
    # Подсчет общего количества для пагинации
    count_query = select(func.count(Task.id)).where(Task.board_id == board_id)
    if q:
        count_query = count_query.where(Task.title.ilike(f"%{q}%"))
    if column:
        count_query = count_query.where(Task.column == column)
    if priority:
        count_query = count_query.where(Task.priority == priority)
    if assignee_id:
        count_query = count_query.where(Task.assignee_id == assignee_id)
        
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    pages = (total + pagination.limit - 1) // pagination.limit if total > 0 else 1
    
    # Применяем пагинацию к основному запросу
    query = query.offset((pagination.page - 1) * pagination.limit).limit(pagination.limit)
    result = await db.execute(query)
    
    tasks_data = []
    for row in result.all():
        task = row[0]
        assignee_data = None
        if task.assignee:
            assignee_data = {
                "id": task.assignee.id,
                "name": task.assignee.name,
                "email": task.assignee.email
            }
            
        tasks_data.append(TaskResponse(
            id=task.id,
            board_id=task.board_id,
            title=task.title,
            description=task.description,
            column=task.column,
            substatus=task.substatus,
            priority=task.priority,
            due_date=task.due_date,
            assignee=assignee_data,
            tags=task.tags or [],
            subtasks_count=row[1] or 0,
            comments_count=row[2] or 0,
            files_count=row[3] or 0,
            created_at=task.created_at,
            updated_at=task.updated_at,
        ))
        
    return PaginatedResponse(
        items=tasks_data,
        total=total,
        page=pagination.page,
        limit=pagination.limit,
        pages=pages,
    )


@router.post("/boards/{board_id}/tasks", response_model=TaskResponse)
async def create_task(
    board_id: int,
    task_data: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Создать задачу. Только для студентов (или админов)."""
    # Проверяем, что пользователь студент или админ (по матрице прав)
    membership = await require_board_member(db, current_user.id, board_id)
    if membership.role not in ("student", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только студенты или администраторы могут создавать задачи",
        )
    
    new_task = Task(
        board_id=board_id,
        title=task_data.title,
        description=task_data.description,
        priority=task_data.priority,
        due_date=task_data.due_date,
        assignee_id=task_data.assignee_id,
        tags=task_data.tags or [],
        column="not_started",
    )
    
    db.add(new_task)
    await db.commit()
    await db.refresh(new_task)
    
    # Возвращаем с базовой информацией
    return TaskResponse(
        id=new_task.id,
        board_id=new_task.board_id,
        title=new_task.title,
        description=new_task.description,
        column=new_task.column,
        substatus=new_task.substatus,
        priority=new_task.priority,
        due_date=new_task.due_date,
        assignee=None, # Можно доработать через selectinload
        tags=new_task.tags or [],
        subtasks_count=0,
        comments_count=0,
        files_count=0,
        created_at=new_task.created_at,
        updated_at=new_task.updated_at,
    )


@router.get("/tasks/{task_id}", response_model=TaskDetailResponse)
async def get_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Получить детальную информацию о задаче."""
    # Сначала получаем задачу, чтобы узнать board_id
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalars().first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена")
    
    await require_board_member(db, current_user.id, task.board_id)
    
    # Загружаем все связанные данные
    result = await db.execute(
        select(Task)
        .options(
            selectinload(Task.subtasks),
            selectinload(Task.comments).selectinload(Comment.user),
            selectinload(Task.activity_logs).selectinload(ActivityLog.user),
            selectinload(Task.files)
        )
        .where(Task.id == task_id)
    )
    task = result.scalars().first()
    
    assignee_data = None
    if task.assignee:
        assignee_data = {"id": task.assignee.id, "name": task.assignee.name, "email": task.assignee.email}
        
    comments_data = [
        CommentResponse(
            id=c.id, task_id=c.task_id, user_id=c.user_id, text=c.text,
            author={"id": c.user.id, "name": c.user.name, "email": c.user.email} if c.user else None,
            created_at=c.created_at, updated_at=c.updated_at
        ) for c in task.comments
    ]
    
    activity_data = [
        ActivityResponse(
            id=a.id, task_id=a.task_id, user_id=a.user_id, action=a.action,
            old_value=a.old_value, new_value=a.new_value,
            user_name=a.user.name if a.user else "Система",
            created_at=a.created_at
        ) for a in task.activity_logs
    ]
    
    files_data = [
        {
            "id": f.id, "filename": f.filename, "original_filename": f.original_filename,
            "size": f.size, "is_mentor_file": f.is_mentor_file, "uploaded_at": f.uploaded_at
        } for f in task.files
    ]
    
    return TaskDetailResponse(
        id=task.id, board_id=task.board_id, title=task.title, description=task.description,
        column=task.column, substatus=task.substatus, priority=task.priority, due_date=task.due_date,
        assignee=assignee_data, tags=task.tags or [],
        subtasks_count=len(task.subtasks), comments_count=len(task.comments), files_count=len(task.files),
        created_at=task.created_at, updated_at=task.updated_at,
        subtasks=[SubtaskResponse(id=s.id, task_id=s.task_id, text=s.text, is_completed=s.is_completed, order=s.order) for s in task.subtasks],
        comments=comments_data,
        activity=activity_data,
        files=files_data
    )


@router.put("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    task_data: TaskUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Обновить задачу."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalars().first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена")
        
    await require_board_member(db, current_user.id, task.board_id)
    
    # Логирование изменений
    changes = []
    if task_data.title is not None and task_data.title != task.title:
        changes.append(f"Название: '{task.title}' -> '{task_data.title}'")
        task.title = task_data.title
    if task_data.description is not None and task_data.description != task.description:
        changes.append("Описание обновлено")
        task.description = task_data.description
    if task_data.priority is not None and task_data.priority != task.priority:
        changes.append(f"Приоритет: '{task.priority}' -> '{task_data.priority}'")
        task.priority = task_data.priority
    if task_data.due_date is not None and task_data.due_date != task.due_date:
        changes.append(f"Срок: '{task.due_date}' -> '{task_data.due_date}'")
        task.due_date = task_data.due_date
    if task_data.assignee_id is not None and task_data.assignee_id != task.assignee_id:
        changes.append("Исполнитель изменен")
        task.assignee_id = task_data.assignee_id
    if task_data.tags is not None and task_data.tags != task.tags:
        changes.append("Теги обновлены")
        task.tags = task_data.tags
        
    if changes:
        log = ActivityLog(
            task_id=task.id, user_id=current_user.id, action="update",
            new_value="; ".join(changes)
        )
        db.add(log)
        
    await db.commit()
    await db.refresh(task)
    
    # Упрощенный возврат (в реальном проекте лучше вынести в общую функцию маппинга)
    return TaskResponse(
        id=task.id, board_id=task.board_id, title=task.title, description=task.description,
        column=task.column, substatus=task.substatus, priority=task.priority, due_date=task.due_date,
        assignee=None, tags=task.tags or [], subtasks_count=0, comments_count=0, files_count=0,
        created_at=task.created_at, updated_at=task.updated_at
    )


@router.delete("/tasks/{task_id}", response_model=SuccessResponse)
async def delete_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Удалить задачу.
    ВАЖНО: Любой участник доски (студент или админ) может удалить задачу.
    Проверка прав осуществляется через принадлежность пользователя к board_id данной задачи.
    """
    # 1. Проверка прав (используем специальную функцию из services/permissions.py)
    await can_delete_task(db, current_user.id, task_id)
    
    # 2. Получаем файлы задачи для последующего удаления с диска
    files_result = await db.execute(select(File).where(File.task_id == task_id))
    files_to_delete = files_result.scalars().all()
    file_paths = [f.file_path for f in files_to_delete]
    
    # 3. Удаляем задачу из БД (CASCADE удалит subtasks, comments, files, submissions, activity_log)
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalars().first()
    await db.delete(task)
    await db.commit()
    
    # 4. Физическое удаление файлов с диска
    for file_path in file_paths:
        FileService.delete_file(file_path)
        
    return SuccessResponse(message="Задача и связанные файлы успешно удалены")


@router.patch("/tasks/{task_id}/move", response_model=TaskResponse)
async def move_task(
    task_id: int,
    move_data: TaskMove,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Переместить задачу (drag-and-drop). Атомарная операция + лог."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalars().first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена")
        
    # Проверка прав на перемещение согласно матрице
    await check_task_move_permissions(db, current_user.id, task_id, move_data.target_column, move_data.target_substatus)
    
    old_column = task.column
    old_substatus = task.substatus
    
    task.column = move_data.target_column
    task.substatus = move_data.target_substatus
    
    # Логируем действие
    action_desc = f"Перемещение: {old_column}({old_substatus}) -> {move_data.target_column}({move_data.target_substatus})"
    log = ActivityLog(
        task_id=task.id, user_id=current_user.id, action="move",
        old_value=f"{old_column}/{old_substatus}",
        new_value=f"{move_data.target_column}/{move_data.target_substatus}"
    )
    db.add(log)
    
    await db.commit()
    await db.refresh(task)
    
    return TaskResponse(
        id=task.id, board_id=task.board_id, title=task.title, description=task.description,
        column=task.column, substatus=task.substatus, priority=task.priority, due_date=task.due_date,
        assignee=None, tags=task.tags or [], subtasks_count=0, comments_count=0, files_count=0,
        created_at=task.created_at, updated_at=task.updated_at
    )


# ==========================================
# ПОДЗАДАЧИ (SUBTASKS)
# ==========================================

@router.post("/tasks/{task_id}/subtasks", response_model=SubtaskResponse)
async def create_subtask(
    task_id: int,
    subtask_data: SubtaskCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Создать подзадачу. Только студент."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalars().first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена")
        
    await require_student(db, current_user.id, task.board_id)
    
    # Определяем order
    if subtask_data.order is None:
        count_result = await db.execute(select(func.count(Subtask.id)).where(Subtask.task_id == task_id))
        order = count_result.scalar()
    else:
        order = subtask_data.order
        
    new_subtask = Subtask(
        task_id=task_id, text=subtask_data.text, order=order, is_completed=False
    )
    db.add(new_subtask)
    
    log = ActivityLog(task_id=task_id, user_id=current_user.id, action="add_subtask", new_value=subtask_data.text)
    db.add(log)
    
    await db.commit()
    await db.refresh(new_subtask)
    return new_subtask


@router.put("/subtasks/{subtask_id}", response_model=SubtaskResponse)
async def update_subtask(
    subtask_id: int,
    subtask_data: SubtaskUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Обновить подзадачу. Только студент."""
    result = await db.execute(
        select(Subtask).options(selectinload(Subtask.task)).where(Subtask.id == subtask_id)
    )
    subtask = result.scalars().first()
    if not subtask:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Подзадача не найдена")
        
    await require_student(db, current_user.id, subtask.task.board_id)
    
    if subtask_data.text is not None:
        subtask.text = subtask_data.text
    if subtask_data.is_completed is not None:
        subtask.is_completed = subtask_data.is_completed
    if subtask_data.order is not None:
        subtask.order = subtask_data.order
        
    await db.commit()
    await db.refresh(subtask)
    return subtask


@router.delete("/subtasks/{subtask_id}", response_model=SuccessResponse)
async def delete_subtask(
    subtask_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Удалить подзадачу. Только студент."""
    result = await db.execute(
        select(Subtask).options(selectinload(Subtask.task)).where(Subtask.id == subtask_id)
    )
    subtask = result.scalars().first()
    if not subtask:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Подзадача не найдена")
        
    await require_student(db, current_user.id, subtask.task.board_id)
    
    await db.delete(subtask)
    await db.commit()
    return SuccessResponse(message="Подзадача удалена")


# ==========================================
# КОММЕНТАРИИ (COMMENTS)
# ==========================================

@router.post("/tasks/{task_id}/comments", response_model=CommentResponse)
async def create_comment(
    task_id: int,
    comment_data: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Оставить комментарий. Только наставник."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalars().first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена")
        
    await require_mentor(db, current_user.id, task.board_id)
    
    new_comment = Comment(
        task_id=task_id, user_id=current_user.id, text=comment_data.text
    )
    db.add(new_comment)
    
    log = ActivityLog(task_id=task_id, user_id=current_user.id, action="add_comment", new_value="Комментарий добавлен")
    db.add(log)
    
    await db.commit()
    await db.refresh(new_comment)
    
    return CommentResponse(
        id=new_comment.id, task_id=new_comment.task_id, user_id=new_comment.user_id,
        text=new_comment.text, author={"id": current_user.id, "name": current_user.name, "email": current_user.email},
        created_at=new_comment.created_at, updated_at=new_comment.updated_at
    )


@router.put("/comments/{comment_id}", response_model=CommentResponse)
async def update_comment(
    comment_id: int,
    comment_data: CommentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Обновить комментарий. Только автор (наставник)."""
    result = await db.execute(
        select(Comment).options(selectinload(Comment.task)).where(Comment.id == comment_id)
    )
    comment = result.scalars().first()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Комментарий не найден")
        
    if comment.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Вы не автор этого комментария")
        
    await require_mentor(db, current_user.id, comment.task.board_id)
    
    comment.text = comment_data.text
    await db.commit()
    await db.refresh(comment)
    
    return CommentResponse(
        id=comment.id, task_id=comment.task_id, user_id=comment.user_id,
        text=comment.text, author={"id": current_user.id, "name": current_user.name, "email": current_user.email},
        created_at=comment.created_at, updated_at=comment.updated_at
    )


@router.delete("/comments/{comment_id}", response_model=SuccessResponse)
async def delete_comment(
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Удалить комментарий. Только автор (наставник)."""
    result = await db.execute(
        select(Comment).options(selectinload(Comment.task)).where(Comment.id == comment_id)
    )
    comment = result.scalars().first()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Комментарий не найден")
        
    if comment.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Вы не автор этого комментария")
        
    await require_mentor(db, current_user.id, comment.task.board_id)
    
    await db.delete(comment)
    await db.commit()
    return SuccessResponse(message="Комментарий удален")