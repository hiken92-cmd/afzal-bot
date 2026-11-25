import os
import aiosqlite
from typing import Dict, Any, List, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "nutrition.db")
DB_TIMEOUT = 15.0


async def _ensure_user_in_tx(db: aiosqlite.Connection, user_id: int, username: str = ""):
    """Гарантирует наличие пользователя внутри уже открытого соединения (без вложенных коннектов)."""
    if username:
        await db.execute("""
            INSERT INTO users (user_id, username, mode) VALUES (?, ?, 'nutrition')
            ON CONFLICT(user_id) DO UPDATE SET username = excluded.username
        """, (user_id, username))
    else:
        await db.execute("""
            INSERT OR IGNORE INTO users (user_id, mode) VALUES (?, 'nutrition')
        """, (user_id,))


async def init_db():
    """Инициализация базы данных SQLite с оптимизацией WAL и индексами."""
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        await db.execute("PRAGMA journal_mode = WAL;")
        await db.execute("PRAGMA synchronous = NORMAL;")

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
                nutrition_precision TEXT DEFAULT 'expert',
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

        await db.execute("CREATE INDEX IF NOT EXISTS idx_meals_user_created ON meals (user_id, created_at);")

        # Миграция для существующих БД
        try:
            await db.execute("ALTER TABLE users ADD COLUMN nutrition_precision TEXT DEFAULT 'expert';")
        except Exception:
            pass

        await db.commit()


async def get_or_create_user(user_id: int, username: str = "") -> Dict[str, Any]:
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        db.row_factory = aiosqlite.Row
        await _ensure_user_in_tx(db, user_id, username)
        await db.commit()
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row)


async def get_user_mode(user_id: int) -> str:
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        async with db.execute("SELECT mode FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0] or "nutrition"

        await _ensure_user_in_tx(db, user_id)
        await db.commit()
        return "nutrition"


async def set_user_mode(user_id: int, mode: str):
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        await db.execute("""
            INSERT INTO users (user_id, mode) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET mode = excluded.mode
        """, (user_id, mode))
        await db.commit()


async def get_nutrition_precision(user_id: int) -> str:
    """Возвращает режим точности нутрициолога ('expert' или 'fast')."""
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        async with db.execute("SELECT nutrition_precision FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0] in ("expert", "fast"):
                return row[0]
        return "expert"


async def set_nutrition_precision(user_id: int, precision: str):
    """Устанавливает режим точности нутрициолога ('expert' или 'fast')."""
    if precision not in ("expert", "fast"):
        precision = "expert"
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        await db.execute("""
            INSERT INTO users (user_id, nutrition_precision) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET nutrition_precision = excluded.nutrition_precision
        """, (user_id, precision))
        await db.commit()


async def toggle_nutrition_precision(user_id: int) -> str:
    """Переключает режим точности между 'expert' и 'fast'."""
    current = await get_nutrition_precision(user_id)
    new_prec = "fast" if current == "expert" else "expert"
    await set_nutrition_precision(user_id, new_prec)
    return new_prec


async def set_translator_settings(user_id: int, target_lang: Optional[str] = None, style: Optional[str] = None):
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        await _ensure_user_in_tx(db, user_id)
        if target_lang and style:
            await db.execute("UPDATE users SET target_lang = ?, translation_style = ? WHERE user_id = ?", (target_lang, style, user_id))
        elif target_lang:
            await db.execute("UPDATE users SET target_lang = ? WHERE user_id = ?", (target_lang, user_id))
        elif style:
            await db.execute("UPDATE users SET translation_style = ? WHERE user_id = ?", (style, user_id))
        await db.commit()


async def get_translator_settings(user_id: int) -> Dict[str, str]:
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        async with db.execute("SELECT target_lang, translation_style FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"target_lang": row[0] or "ru", "style": row[1] or "general"}
            return {"target_lang": "ru", "style": "general"}


async def set_user_goals(user_id: int, calories: float, proteins: float, fats: float, carbs: float,
                         weight: float, height: float, age: int, gender: str, activity: str, goal: str):
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        await _ensure_user_in_tx(db, user_id)
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
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        await _ensure_user_in_tx(db, user_id)
        cursor = await db.execute("""
            INSERT INTO meals (user_id, meal_name, calories, proteins, fats, carbs, weight_g, confidence, advice)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, meal_name, calories, proteins, fats, carbs, weight_g, confidence, advice))
        await db.commit()
        return cursor.lastrowid


async def get_today_meals(user_id: int) -> List[Dict[str, Any]]:
    """Возвращает приемы пищи за текущие сутки с учетом часового пояса Узбекистана (UTC+5)."""
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT *, strftime('%H:%M', created_at, '+5 hours') AS time_local
            FROM meals 
            WHERE user_id = ? AND date(created_at, '+5 hours') = date('now', '+5 hours')
            ORDER BY created_at DESC, id DESC
        """, (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_today_stats(user_id: int) -> Dict[str, float]:
    """Возвращает суммарную статистику КБЖУ за текущие сутки (UTC+5)."""
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        async with db.execute("""
            SELECT 
                COALESCE(SUM(calories), 0),
                COALESCE(SUM(proteins), 0),
                COALESCE(SUM(fats), 0),
                COALESCE(SUM(carbs), 0),
                COUNT(id)
            FROM meals 
            WHERE user_id = ? AND date(created_at, '+5 hours') = date('now', '+5 hours')
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
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        async with db.execute("""
            SELECT id FROM meals 
            WHERE user_id = ? AND date(created_at, '+5 hours') = date('now', '+5 hours')
            ORDER BY created_at DESC, id DESC LIMIT 1
        """, (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return False
            meal_id = row[0]

        await db.execute("DELETE FROM meals WHERE id = ?", (meal_id,))
        await db.commit()
        return True


async def clear_today_meals(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        cursor = await db.execute("""
            DELETE FROM meals 
            WHERE user_id = ? AND date(created_at, '+5 hours') = date('now', '+5 hours')
        """, (user_id,))
        await db.commit()
        return cursor.rowcount
