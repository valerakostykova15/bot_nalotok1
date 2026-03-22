import os
import asyncpg

DATABASE_URL = os.getenv("DATABASE_URL")


async def init_db():
    if not DATABASE_URL:
        raise ValueError("Не найден DATABASE_URL")

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                user_name TEXT,
                amount NUMERIC NOT NULL,
                category TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    finally:
        await conn.close()


async def add_expense(user_id: int, user_name: str, amount: float, category: str):
    if not DATABASE_URL:
        raise ValueError("Не найден DATABASE_URL")

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute("""
            INSERT INTO expenses (user_id, user_name, amount, category)
            VALUES ($1, $2, $3, $4)
        """, user_id, user_name, amount, category)
    finally:
        await conn.close()


async def get_stats(user_ids: list[int], days: int):
    if not DATABASE_URL:
        raise ValueError("Не найден DATABASE_URL")

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        rows = await conn.fetch("""
            SELECT category, SUM(amount)::float AS total
            FROM expenses
            WHERE user_id = ANY($1::bigint[])
              AND created_at >= NOW() - make_interval(days => $2)
            GROUP BY category
            ORDER BY category
        """, user_ids, days)
    finally:
        await conn.close()

    stats = {row["category"]: row["total"] for row in rows}
    total = sum(stats.values())
    return total, stats
