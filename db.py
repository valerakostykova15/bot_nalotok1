import aiosqlite

DB_NAME = "budget.db"


async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                user_name TEXT,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


async def add_expense(user_id: int, user_name: str, amount: float, category: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO expenses (user_id, user_name, amount, category)
            VALUES (?, ?, ?, ?)
        """, (user_id, user_name, amount, category))
        await db.commit()


async def get_stats(user_ids: list[int], days: int):
    async with aiosqlite.connect(DB_NAME) as db:
        if days == 1:
            query = """
                SELECT category, SUM(amount)
                FROM expenses
                WHERE user_id IN ({})
                  AND date(created_at) = date('now', 'localtime')
                GROUP BY category
            """
        else:
            query = """
                SELECT category, SUM(amount)
                FROM expenses
                WHERE user_id IN ({})
                  AND datetime(created_at) >= datetime('now', ?, 'localtime')
                GROUP BY category
            """

        placeholders = ",".join("?" for _ in user_ids)

        if days == 1:
            cursor = await db.execute(query.format(placeholders), user_ids)
        else:
            cursor = await db.execute(
                query.format(placeholders),
                user_ids + [f"-{days} days"]
            )

        rows = await cursor.fetchall()

    category_stats = {category: amount for category, amount in rows}
    total = sum(category_stats.values())

    return total, category_stats
