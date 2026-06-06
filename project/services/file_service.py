import os
import uuid
import mimetypes
from datetime import datetime
from pathlib import Path
from fastapi import UploadFile, HTTPException, status
from PIL import Image
from config import settings


class FileService:
    """Сервис для работы с файлами: сохранение, удаление, валидация."""

    @staticmethod
    def validate_file_size(size: int) -> None:
        """Проверка размера файла."""
        if size > settings.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Размер файла превышает максимальный ({settings.MAX_FILE_SIZE} байт)",
            )

    @staticmethod
    def validate_mime_type(mime_type: str) -> None:
        """Проверка MIME-типа файла."""
        allowed = settings.allowed_mime_types_list
        if mime_type not in allowed:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Недопустимый тип файла. Разрешены: {', '.join(allowed)}",
            )

    @staticmethod
    def validate_path(file_path: str) -> Path:
        """
        Валидация пути к файлу. Защита от path traversal (../).
        Путь должен находиться внутри UPLOAD_DIR.
        """
        upload_dir = Path(settings.UPLOAD_DIR).resolve()
        target_path = (upload_dir / file_path).resolve()
        
        # Проверяем, что итоговый путь находится внутри директории загрузок
        if not str(target_path).startswith(str(upload_dir)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Недопустимый путь к файлу",
            )
        
        if not target_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Файл не найден",
            )
        
        return target_path

    @staticmethod
    def get_file_extension(filename: str) -> str:
        """Получить расширение файла."""
        return Path(filename).suffix.lower()

    @staticmethod
    def generate_unique_filename(original_filename: str) -> str:
        """Генерация уникального имени файла."""
        ext = FileService.get_file_extension(original_filename)
        return f"{uuid.uuid4().hex}{ext}"

    @staticmethod
    def get_upload_subdir() -> str:
        """Получить поддиректорию для загрузки (YYYY/MM/DD)."""
        now = datetime.now()
        return f"{now.year}/{now.month:02d}/{now.day:02d}"

    @staticmethod
    def compress_image(file_path: Path, mime_type: str) -> None:
        """Сжатие изображений через Pillow (JPEG, quality=85)."""
        image_types = {"image/jpeg", "image/png", "image/gif", "image/webp"}
        if mime_type not in image_types:
            return
        
        try:
            with Image.open(file_path) as img:
                # Конвертируем в RGB для JPEG (если нужно)
                if mime_type == "image/jpeg" and img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                
                # Сохраняем с сжатием
                if mime_type == "image/jpeg":
                    img.save(file_path, "JPEG", quality=85, optimize=True)
                elif mime_type == "image/png":
                    img.save(file_path, "PNG", optimize=True)
                elif mime_type == "image/webp":
                    img.save(file_path, "WEBP", quality=85, optimize=True)
                # GIF не сжимаем
        except Exception as e:
            # Если не удалось сжать — просто пропускаем (файл уже сохранен)
            print(f"Warning: Failed to compress image {file_path}: {e}")

    @staticmethod
    async def save_file(upload_file: UploadFile, is_mentor_file: bool = False) -> dict:
        """
        Сохранение файла на диск.
        
        Возвращает словарь с информацией о файле:
        - filename: уникальное имя на диске
        - original_filename: оригинальное имя
        - file_path: относительный путь (YYYY/MM/DD/uuid.ext)
        - mime_type: MIME-тип
        - size: размер в байтах
        """
        # Читаем содержимое файла
        content = await upload_file.read()
        size = len(content)
        
        # Валидация
        FileService.validate_file_size(size)
        
        # Определяем MIME-тип
        mime_type = upload_file.content_type or mimetypes.guess_type(upload_file.filename)[0]
        if not mime_type:
            mime_type = "application/octet-stream"
        FileService.validate_mime_type(mime_type)
        
        # Генерируем уникальное имя и путь
        unique_filename = FileService.generate_unique_filename(upload_file.filename)
        subdir = FileService.get_upload_subdir()
        relative_path = f"{subdir}/{unique_filename}"
        
        # Создаем директорию
        full_dir = Path(settings.UPLOAD_DIR) / subdir
        full_dir.mkdir(parents=True, exist_ok=True)
        
        # Сохраняем файл
        full_path = full_dir / unique_filename
        with open(full_path, "wb") as f:
            f.write(content)
        
        # Сжимаем изображение (если нужно)
        FileService.compress_image(full_path, mime_type)
        
        return {
            "filename": unique_filename,
            "original_filename": upload_file.filename,
            "file_path": relative_path,
            "mime_type": mime_type,
            "size": size,
            "is_mentor_file": is_mentor_file,
        }

    @staticmethod
    def delete_file(file_path: str) -> bool:
        """Удаление файла с диска. Возвращает True, если файл удален."""
        try:
            target_path = FileService.validate_path(file_path)
            target_path.unlink()
            return True
        except HTTPException:
            return False
        except Exception as e:
            print(f"Error deleting file {file_path}: {e}")
            return False