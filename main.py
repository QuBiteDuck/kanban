import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from database.create_tables import init_db
from routers import (
    auth_router,
    boards_router,
    invitations_router,
    tasks_router,
    results_router,
    files_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Инициализация базы данных...")
    await init_db()
    
    print("Создание директории для файлов...")
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    
    yield
    
    # Shutdown
    print("Завершение работы приложения...")


app = FastAPI(
    title="Kanban Board API",
    description="API для управления канбан-досками с поддержкой ролей, файлов и проверок",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware (ВАЖНО: allow_credentials=True для HttpOnly cookies)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутеров
app.include_router(auth_router)
app.include_router(boards_router)
app.include_router(invitations_router)
app.include_router(tasks_router)
app.include_router(results_router)
app.include_router(files_router)

# Монтирование статических файлов (если есть frontend в папке static)
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    return {"message": "Kanban Board API is running", "docs": "/docs"}