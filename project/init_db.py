# для ручноо создания таблицы без uvicorn
import asyncio
from database.create_tables import init_db

async def main():
    print("Создание таблиц базы данных...")
    await init_db()
    print("Таблицы успешно созданы!")

if __name__ == "__main__":
    asyncio.run(main())