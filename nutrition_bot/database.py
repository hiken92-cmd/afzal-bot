import os
import aiosqlite
from datetime import datetime
from typing import Dict, Any, List, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "nutrition.db")

async def init_db():
    """Инициализация таблиц базы данных SQLite."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                mode TEXT DEFAULT 'nutrition',
                target_lang TEXT DEFAULT 'ru',
                translation_style TEXT DEFAULT 'general',
                daily_calories REAL DEFAULT 2000.0,
                daily_proteins REAL DEFAULT 100.0,
                daily_fats REAL DEFAULT 70.0,
                daily_carbs REAL DEFAULT 250.0,
                weight REAL DEFAULT 70.0,
                height REAL DEFAULT 175.0,
                age INTEGER DEFAULT 25,
                gender TEXT DEFAULT 'male',
                activity_level TEXT DEFAULT 'moderate',
                goal TEXT DEFAULT 'maintain',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS meals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                meal_name TEXT,
                calories REAL,
                proteins REAL,
                fats REAL,
                carbs REAL,
                weight_g REAL,
                confidence INTEGER DEFAULT 90,
                advice TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
        await db.commit()

async def get_or_create_user(user_id: int, username: str = "") -> Dict[str, Any]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
        
        # Создаем нового пользователя с режимом nutrition по умолчанию
        await db.execute("""
            INSERT INTO users (user_id, username, mode) VALUES (?, ?, 'nutrition')
            ON CONFLICT(user_id) DO UPDATE SET username = excluded.username
        """, (user_id, username or ""))
        await db.commit()
        
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row)

async def get_user_mode(user_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT mode FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0] or "nutrition"
        
        # Если пользователя нет в базе — автоматически регистрируем его в режиме nutrition
        await db.execute("""
            INSERT INTO users (user_id, mode) VALUES (?, 'nutrition')
            ON CONFLICT(user_id) DO NOTHING
        """, (user_id,))
        await db.commit()
        return "nutrition"

async def set_user_mode(user_id: int, mode: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, mode) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET mode = excluded.mode
        """, (user_id, mode))
        await db.commit()

async def set_translator_settings(user_id: int, target_lang: Optional[str] = None, style: Optional[str] = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await get_or_create_user(user_id)
        if target_lang and style:
            await db.execute("UPDATE users SET target_lang = ?, translation_style = ? WHERE user_id = ?", (target_lang, style, user_id))
        elif target_lang:
            await db.execute("UPDATE users SET target_lang = ? WHERE user_id = ?", (target_lang, user_id))
        elif style:
            await db.execute("UPDATE users SET translation_style = ? WHERE user_id = ?", (style, user_id))
        await db.commit()

async def get_translator_settings(user_id: int) -> Dict[str, str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT target_lang, translation_style FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"target_lang": row[0] or "ru", "style": row[1] or "general"}
            return {"target_lang": "ru", "style": "general"}

async def set_user_goals(user_id: int, calories: float, proteins: float, fats: float, carbs: float,
                         weight: float, height: float, age: int, gender: str, activity: str, goal: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await get_or_create_user(user_id)
        await db.execute("""
            UPDATE users SET 
                daily_calories = ?, daily_proteins = ?, daily_fats = ?, daily_carbs = ?,
                weight = ?, height = ?, age = ?, gender = ?, activity_level = ?, goal = ?
            WHERE user_id = ?
        """, (calories, proteins, fats, carbs, weight, height, age, gender, activity, goal, user_id))
        await db.commit()

async def get_user_profile(user_id: int) -> Dict[str, Any]:
    return await get_or_create_user(user_id)

async def add_meal(user_id: int, meal_name: str, calories: float, proteins: float, fats: float, carbs: float,
                   weight_g: float = 0.0, confidence: int = 90, advice: str = "") -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await get_or_create_user(user_id)
        cursor = await db.execute("""
            INSERT INTO meals (user_id, meal_name, calories, proteins, fats, carbs, weight_g, confidence, advice)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, meal_name, calories, proteins, fats, carbs, weight_g, confidence, advice))
        await db.commit()
        return cursor.lastrowid

async def get_today_meals(user_id: int) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM meals 
            WHERE user_id = ? AND date(created_at) = date('now', 'localtime')
            ORDER BY created_at DESC
        """, (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def get_today_stats(user_id: int) -> Dict[str, float]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT 
                COALESCE(SUM(calories), 0),
                COALESCE(SUM(proteins), 0),
                COALESCE(SUM(fats), 0),
                COALESCE(SUM(carbs), 0),
                COUNT(id)
            FROM meals 
            WHERE user_id = ? AND date(created_at) = date('now', 'localtime')
        """, (user_id,)) as cursor:
            row = await cursor.fetchone()
            return {
                "calories": float(row[0]),
                "proteins": float(row[1]),
                "fats": float(row[2]),
                "carbs": float(row[3]),
                "count": int(row[4])
            }

async def delete_last_meal(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT id FROM meals 
            WHERE user_id = ? AND date(created_at) = date('now', 'localtime')
            ORDER BY created_at DESC LIMIT 1
        """, (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return False
            meal_id = row[0]
        
        await db.execute("DELETE FROM meals WHERE id = ?", (meal_id,))
        await db.commit()
        return True

async def clear_today_meals(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            DELETE FROM meals 
            WHERE user_id = ? AND date(created_at) = date('now', 'localtime')
        """, (user_id,))
        await db.commit()
        return cursor.rowcount
