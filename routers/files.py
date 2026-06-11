import os
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File as FastAPIFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from database.session import get_db
from database.models import File, Task, User, BoardMember
from schemas.files import FileResponse
from schemas.common import PaginatedResponse, SuccessResponse
from dependencies import get_current_user, get_pagination_params
from services.permissions import require_mentor, require_board_admin, require_board_member, get_user_board_membership
from services.file_service import FileService
from config import settings

router = APIRouter(prefix="/api", tags=["files"])


@router.post("/tasks/{task_id}/files", response_model=FileResponse)
async def upload_file(
    task_id: int,
    file: UploadFile = FastAPIFile(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Загрузить файл к задаче. 
    ВАЖНО: Только наставник может загружать файлы к любой задаче.
    """
    # Проверяем существование задачи и получаем board_id
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalars().first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена")
    
    # Проверка прав: только наставник
    await require_mentor(db, current_user.id, task.board_id)
    
    # Сохраняем файл через сервис
    file_info = await FileService.save_file(file, is_mentor_file=True)
    
    # Создаем запись в БД
    new_file = File(
        task_id=task_id,
        user_id=current_user.id,
        filename=file_info["filename"],
        original_filename=file_info["original_filename"],
        file_path=file_info["file_path"],
        mime_type=file_info["mime_type"],
        size=file_info["size"],
        is_mentor_file=file_info["is_mentor_file"],
    )
    
    db.add(new_file)
    await db.commit()
    await db.refresh(new_file)
    
    return FileResponse(
        id=new_file.id,
        task_id=new_file.task_id,
        filename=new_file.filename,
        original_filename=new_file.original_filename,
        mime_type=new_file.mime_type,
        size=new_file.size,
        is_mentor_file=new_file.is_mentor_file,
        uploaded_by=current_user.name or current_user.email,
        uploaded_at=new_file.uploaded_at,
    )


@router.get("/tasks/{task_id}/files", response_model=PaginatedResponse[FileResponse])
async def get_task_files(
    task_id: int,
    pagination=Depends(get_pagination_params),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Получить список файлов задачи."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalars().first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена")
        
    await require_board_member(db, current_user.id, task.board_id)
    
    query = (
        select(File)
        .where(File.task_id == task_id)
        .order_by(File.uploaded_at.desc())
        .offset((pagination.page - 1) * pagination.limit)
        .limit(pagination.limit)
    )
    
    result = await db.execute(query)
    files = result.scalars().all()
    
    count_query = select(func.count(File.id)).where(File.task_id == task_id)
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    pages = (total + pagination.limit - 1) // pagination.limit if total > 0 else 1
    
    items = [
        FileResponse(
            id=f.id, task_id=f.task_id, filename=f.filename, original_filename=f.original_filename,
            mime_type=f.mime_type, size=f.size, is_mentor_file=f.is_mentor_file, uploaded_at=f.uploaded_at
        ) for f in files
    ]
    
    return PaginatedResponse(items=items, total=total, page=pagination.page, limit=pagination.limit, pages=pages)


@router.get("/files/{file_id}/download")
async def download_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Скачать файл. Проверяет доступ к задаче и валидирует путь."""
    result = await db.execute(
        select(File).options(selectinload(File.task)).where(File.id == file_id)
    )
    file_obj = result.scalars().first()
    if not file_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Файл не найден")
        
    # Проверяем доступ к доске этой задачи
    await require_board_member(db, current_user.id, file_obj.task.board_id)
    
    # Валидация пути (защита от path traversal)
    try:
        target_path = FileService.validate_path(file_obj.file_path)
    except HTTPException as e:
        raise e
        
    return FileResponse(
        path=str(target_path),
        filename=file_obj.original_filename,
        media_type=file_obj.mime_type,
        headers={"Content-Disposition": f'attachment; filename="{file_obj.original_filename}"'}
    )


@router.delete("/files/{file_id}", response_model=SuccessResponse)
async def delete_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Удалить файл. 
    ВАЖНО: Только загрузивший пользователь или админ доски может удалить файл.
    Удаляет запись из БД и файл с диска.
    """
    result = await db.execute(
        select(File).options(selectinload(File.task)).where(File.id == file_id)
    )
    file_obj = result.scalars().first()
    if not file_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Файл не найден")
        
    # Проверка прав: загрузивший ИЛИ админ доски
    is_owner = file_obj.user_id == current_user.id
    is_admin = False
    
    if not is_owner:
        membership = await get_user_board_membership(db, current_user.id, file_obj.task.board_id)
        if membership and membership.status == "admin":
            is_admin = True
            
    if not is_owner and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только загрузивший пользователь или администратор доски может удалить этот файл"
        )
        
    file_path_to_delete = file_obj.file_path
    
    # Атомарное удаление из БД
    async with db.begin():
        await db.delete(file_obj)
        
    # Физическое удаление с диска (после успешного коммита БД)
    FileService.delete_file(file_path_to_delete)
    
    return SuccessResponse(message="Файл успешно удален")