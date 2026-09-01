import sqlite3
import os
import json
import threading
from typing import List, Optional
from datetime import datetime, timedelta

# 翻译缓存策略：超过 TTL 视为过期；条数或总字节超限时惰性清理最旧条目。
TRANSLATION_CACHE_TTL_SECONDS = 30 * 24 * 3600  # 30 天
TRANSLATION_CACHE_MAX_ENTRIES = 3000
TRANSLATION_CACHE_MAX_BYTES = 30 * 1024 * 1024  # 30MB
TRANSLATION_CACHE_TRIM_RATIO = 0.2  # 超限时删除最旧 20%


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._translation_lock = threading.RLock()
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self._create_tables()

    def _create_tables(self):
        cursor = self.conn.cursor()
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS favorites (
                full_name TEXT PRIMARY KEY,
                html_url TEXT,
                description TEXT,
                description_zh TEXT,
                language TEXT,
                stars INTEGER DEFAULT 0,
                created_at TEXT,
                tags TEXT DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_favorites_stars ON favorites(stars DESC);
            CREATE INDEX IF NOT EXISTS idx_favorites_lang ON favorites(language);

            CREATE TABLE IF NOT EXISTS download_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT,
                html_url TEXT,
                label TEXT,
                url TEXT,
                mode TEXT,
                time TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_history_time ON download_history(time DESC);
            CREATE INDEX IF NOT EXISTS idx_history_name ON download_history(full_name);

            CREATE TABLE IF NOT EXISTS translation_cache (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS api_cache (
                url TEXT PRIMARY KEY,
                response TEXT,
                updated_at TEXT,
                ttl_seconds INTEGER DEFAULT 300
            );

            CREATE TABLE IF NOT EXISTS mirror_cache (
                mirror TEXT PRIMARY KEY,
                latency REAL,
                updated_at TEXT
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS favorites_fts USING fts5(
                full_name, description, description_zh, language,
                content='favorites', content_rowid='rowid'
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS history_fts USING fts5(
                full_name, label, url,
                content='download_history', content_rowid='id'
            );

            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT,
                time TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_search_time ON search_history(time DESC);
        """)
        self.conn.commit()

    def close(self):
        self.conn.close()

    # Search History
    def add_search(self, keyword: str):
        if not keyword.strip():
            return
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO search_history (keyword, time) VALUES (?, ?)", (keyword.strip(), datetime.now().isoformat()))
        cursor.execute("DELETE FROM search_history WHERE id NOT IN (SELECT id FROM search_history ORDER BY time DESC LIMIT 50)")
        self.conn.commit()

    def get_recent_searches(self, limit: int = 10) -> List[str]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT keyword FROM search_history ORDER BY time DESC LIMIT ?", (limit,))
        return [row[0] for row in cursor.fetchall()]

    # Favorites
    def add_favorite(self, repo: dict):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO favorites (full_name, html_url, description, description_zh, language, stars, created_at, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            repo.get("full_name", ""),
            repo.get("html_url", ""),
            repo.get("description", ""),
            repo.get("description_zh", ""),
            repo.get("language", ""),
            repo.get("stars", 0),
            datetime.now().isoformat(),
            repo.get("tags", "")
        ))
        self.conn.commit()
        self._update_favorites_fts(repo)

    def remove_favorite(self, full_name: str):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM favorites WHERE full_name = ?", (full_name,))
        cursor.execute("DELETE FROM favorites_fts WHERE full_name = ?", (full_name,))
        self.conn.commit()

    def update_favorite_tags(self, full_name: str, tags: str):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE favorites SET tags = ? WHERE full_name = ?", (tags, full_name))
        self.conn.commit()

    def get_all_tags(self) -> List[str]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT tags FROM favorites WHERE tags != ''")
        tags = set()
        for row in cursor.fetchall():
            for tag in row[0].split(","):
                tag = tag.strip()
                if tag:
                    tags.add(tag)
        return sorted(tags)

    def is_favorite(self, full_name: str) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM favorites WHERE full_name = ?", (full_name,))
        return cursor.fetchone() is not None

    def get_favorites(self, query: str = "") -> List[dict]:
        cursor = self.conn.cursor()
        if query:
            cursor.execute("""
                SELECT f.* FROM favorites f
                JOIN favorites_fts fts ON f.rowid = fts.rowid
                WHERE favorites_fts MATCH ?
                ORDER BY f.stars DESC
            """, (query + "*",))
        else:
            cursor.execute("SELECT * FROM favorites ORDER BY stars DESC")
        rows = cursor.fetchall()
        return [self._row_to_dict(row, ["full_name", "html_url", "description", "description_zh", "language", "stars", "created_at", "tags"]) for row in rows]

    def _update_favorites_fts(self, repo: dict):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM favorites_fts WHERE full_name = ?", (repo.get("full_name", ""),))
        cursor.execute("""
            INSERT INTO favorites_fts (full_name, description, description_zh, language)
            VALUES (?, ?, ?, ?)
        """, (repo.get("full_name", ""), repo.get("description", ""), repo.get("description_zh", ""), repo.get("language", "")))
        self.conn.commit()

    # Download History
    def add_download(self, record: dict):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO download_history (full_name, html_url, label, url, mode, time)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            record.get("full_name", ""),
            record.get("html_url", ""),
            record.get("label", ""),
            record.get("url", ""),
            record.get("mode", ""),
            record.get("time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        ))
        self.conn.commit()
        # Keep only last 300
        cursor.execute("""
            DELETE FROM download_history WHERE id NOT IN (
                SELECT id FROM download_history ORDER BY time DESC LIMIT 300
            )
        """)
        self.conn.commit()

    def get_downloads(self, query: str = "") -> List[dict]:
        cursor = self.conn.cursor()
        if query:
            cursor.execute("""
                SELECT d.* FROM download_history d
                JOIN history_fts fts ON d.id = fts.rowid
                WHERE history_fts MATCH ?
                ORDER BY d.time DESC
            """, (query + "*",))
        else:
            cursor.execute("SELECT * FROM download_history ORDER BY time DESC LIMIT 300")
        rows = cursor.fetchall()
        return [self._row_to_dict(row, ["id", "full_name", "html_url", "label", "url", "mode", "time"]) for row in rows]

    # 翻译缓存
    def get_translation(self, key: str, ttl_seconds: int = TRANSLATION_CACHE_TTL_SECONDS) -> Optional[str]:
        with self._translation_lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT value FROM translation_cache
                WHERE key = ? AND (updated_at IS NULL OR
                    CAST(strftime('%s', updated_at) AS INTEGER) >=
                    CAST(strftime('%s', 'now') AS INTEGER) - ?)
            """, (key, ttl_seconds))
            row = cursor.fetchone()
            return row[0] if row else None

    def set_translation(self, key: str, value: str):
        with self._translation_lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO translation_cache (key, value, updated_at)
                VALUES (?, ?, ?)
            """, (key, value, datetime.now().isoformat()))
            self.conn.commit()
            self._trim_translation_cache(cursor)

    def _trim_translation_cache(self, cursor) -> None:
        """缓存条数或总字节超限时，删除最旧的 20% 条目，防止无限膨胀。"""
        cursor.execute('SELECT COUNT(*) FROM translation_cache')
        count = cursor.fetchone()[0]
        cursor.execute('SELECT COALESCE(SUM(LENGTH(CAST(value AS BLOB))), 0) FROM translation_cache')
        total_bytes = cursor.fetchone()[0]
        if count <= TRANSLATION_CACHE_MAX_ENTRIES and total_bytes <= TRANSLATION_CACHE_MAX_BYTES:
            return
        trim_count = max(1, int(count * TRANSLATION_CACHE_TRIM_RATIO))
        cursor.execute('''
            DELETE FROM translation_cache WHERE key IN (
                SELECT key FROM translation_cache
                ORDER BY updated_at ASC
                LIMIT ?
            )
        ''', (trim_count,))
        self.conn.commit()

    def clear_translation_cache(self):
        '''清空所有简介和 README 翻译缓存。'''
        with self._translation_lock:
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM translation_cache')
            self.conn.commit()

    def get_translation_cache_stats(self) -> dict:
        '''返回翻译缓存条数和 UTF-8 字节数，供设置页显示。'''
        with self._translation_lock:
            cursor = self.conn.cursor()
            cursor.execute('SELECT value FROM translation_cache')
            values = [row[0] for row in cursor.fetchall()]
        return {
            'count': len(values),
            'bytes': sum(len(str(value or '').encode('utf-8')) for value in values),
        }
    # API Cache
    def get_api_cache(self, url: str) -> Optional[str]:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT response, updated_at, ttl_seconds FROM api_cache
            WHERE url = ? AND datetime(updated_at, '+' || ttl_seconds || ' seconds') > datetime('now')
        """, (url,))
        row = cursor.fetchone()
        return row[0] if row else None

    def get_api_cache_record(self, url: str) -> Optional[dict]:
        """读取完整的接口缓存记录，不判断缓存是否过期。"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT url, response, updated_at, ttl_seconds FROM api_cache WHERE url = ?",
            (url,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "url": row[0],
            "response": row[1],
            "updated_at": row[2],
            "ttl_seconds": int(row[3] or 0),
        }

    def get_recent_api_cache_records(
        self,
        prefix: str = "",
        max_age_seconds: int = 86400,
        limit: int = 100,
    ) -> List[dict]:
        """读取指定前缀下近期的接口缓存，包含近期已过期记录。"""
        try:
            max_age = max(0, int(max_age_seconds))
        except (TypeError, ValueError):
            max_age = 86400
        try:
            max_records = max(1, min(int(limit), 1000))
        except (TypeError, ValueError):
            max_records = 100
        cutoff = (datetime.now() - timedelta(seconds=max_age)).isoformat()
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT url, response, updated_at, ttl_seconds
            FROM api_cache
            WHERE url LIKE ? AND updated_at >= ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (f"{prefix}%", cutoff, max_records),
        )
        return [
            {
                "url": row[0],
                "response": row[1],
                "updated_at": row[2],
                "ttl_seconds": int(row[3] or 0),
            }
            for row in cursor.fetchall()
        ]

    def set_api_cache(self, url: str, response: str, ttl: int = 300):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO api_cache (url, response, updated_at, ttl_seconds)
            VALUES (?, ?, ?, ?)
        """, (url, response, datetime.now().isoformat(), ttl))
        self.conn.commit()

    def clear_expired_cache(self, max_age_seconds: int = 86400):
        """只清理超过保留期限的旧缓存，给首屏回退保留近期过期数据。"""
        try:
            max_age = max(0, int(max_age_seconds))
        except (TypeError, ValueError):
            max_age = 86400
        cutoff = (datetime.now() - timedelta(seconds=max_age)).isoformat()
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM api_cache WHERE updated_at < ?",
            (cutoff,),
        )
        self.conn.commit()

    def clear_api_cache(self):
        """清空接口缓存，供用户手动刷新和配置切换使用。"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM api_cache")
        self.conn.commit()

    # Mirror Cache
    def get_mirror_latency(self, mirror: str) -> Optional[float]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT latency FROM mirror_cache WHERE mirror = ?", (mirror,))
        row = cursor.fetchone()
        return row[0] if row else None

    def set_mirror_latency(self, mirror: str, latency: float):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO mirror_cache (mirror, latency, updated_at)
            VALUES (?, ?, ?)
        """, (mirror, latency, datetime.now().isoformat()))
        self.conn.commit()

    def get_mirror_ranking(self) -> List[tuple]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT mirror, latency FROM mirror_cache ORDER BY latency ASC")
        return cursor.fetchall()

    def _row_to_dict(self, row, columns: List[str]) -> dict:
        return dict(zip(columns, row)) if row else {}
