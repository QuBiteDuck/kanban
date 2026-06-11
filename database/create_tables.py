from sqlalchemy.ext.asyncio import create_async_engine
from database.models import Base
from config import settings

async def init_db():
    """Создаёт все таблицы в базе данных при старте приложения."""
    engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
    async with engine.begin() as conn:
        # Запускаем синхронное создание таблиц внутри асинхронной транзакции
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()