import sqlite3
import os
import json
import re
import threading
from typing import List, Optional
from datetime import datetime

from github_open_source_browser.translator import (
    GLOSSARY_TERMS,
    LEARN_STOPWORDS,
    LOCAL_TRANSLATION_DICT,
)

# 翻译缓存策略：超过 TTL 视为过期；条数或总字节超限时惰性清理最旧条目。
TRANSLATION_CACHE_TTL_SECONDS = 30 * 24 * 3600  # 30 天
TRANSLATION_CACHE_MAX_ENTRIES = 3000
TRANSLATION_CACHE_MAX_BYTES = 30 * 1024 * 1024  # 30MB
TRANSLATION_CACHE_TRIM_RATIO = 0.2  # 超限时删除最旧 20%

# 翻译记忆库：条数超限时惰性删除最旧 20%（记忆库无 TTL，靠条数限制防止无限膨胀）
TRANSLATION_MEMORY_MAX_ENTRIES = 2000
TRANSLATION_MEMORY_TRIM_RATIO = 0.2

# 自动学习时忽略的已知词（本地词典 + 术语表 + 停用词），避免重复收录
_KNOWN_TERM_LOOKUP = (
    frozenset(LOCAL_TRANSLATION_DICT.keys())
    | frozenset(t.lower() for t in GLOSSARY_TERMS)
    | frozenset(LEARN_STOPWORDS)
)
_LEARN_WORD_PATTERN = re.compile(r"[a-zA-Z]{3,}")


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._translation_lock = threading.RLock()
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self._create_tables()
        self._existing_learned = self._load_learned_terms()

    def _load_learned_terms(self) -> set:
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT term FROM learned_terms")
            return {row[0] for row in cursor.fetchall()}
        except Exception:
            return set()

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

            CREATE TABLE IF NOT EXISTS translation_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                translated TEXT,
                hits INTEGER DEFAULT 1,
                updated_at TEXT,
                UNIQUE(source, target)
            );
            CREATE INDEX IF NOT EXISTS idx_memory_source ON translation_memory(source);

            CREATE TABLE IF NOT EXISTS learned_terms (
                term TEXT PRIMARY KEY,
                sample_source TEXT,
                sample_translated TEXT,
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

            CREATE TABLE IF NOT EXISTS ranking_history (
                since TEXT PRIMARY KEY,
                data TEXT,
                updated_at TEXT
            );
        """)
        self.conn.commit()

    def close(self):
        self.conn.close()

    # 排名历史（趋势页涨跌标记：daily/weekly/monthly 的上一期排名快照）
    def get_ranking_history(self, since: str) -> dict[str, int]:
        with self._translation_lock:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT data FROM ranking_history WHERE since = ?",
                (since,),
            )
            row = cursor.fetchone()
            if not row:
                return {}
            try:
                data = json.loads(row[0])
                return data if isinstance(data, dict) else {}
            except Exception:
                return {}

    def save_ranking_history(self, since: str, rankings: dict[str, int]) -> None:
        if not isinstance(rankings, dict):
            return
        with self._translation_lock:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO ranking_history (since, data, updated_at)
                VALUES (?, ?, ?)
                """,
                (since, json.dumps(rankings, ensure_ascii=False), datetime.now().isoformat()),
            )
            self.conn.commit()

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
            """, (key, value, datetime.utcnow().isoformat()))
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
            cursor.execute('''
                SELECT COUNT(*), COALESCE(SUM(LENGTH(CAST(value AS BLOB))), 0)
                FROM translation_cache
            ''')
            count, total_bytes = cursor.fetchone()
        return {
            'count': count,
            'bytes': total_bytes,
        }

    def list_translation_cache(self, limit: int = 200, offset: int = 0) -> List[dict]:
        """列出翻译缓存条目（最新优先），供缓存管理界面查看。"""
        limit = max(1, min(int(limit), 500))
        offset = max(0, int(offset))
        with self._translation_lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT key, value, updated_at
                FROM translation_cache
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
            ''', (limit, offset))
            rows = cursor.fetchall()
        return [
            {
                'key': row[0],
                'value': row[1],
                'size': len(row[1].encode('utf-8')) if row[1] else 0,
                'updated_at': row[2],
            }
            for row in rows
        ]

    def delete_translation_cache(self, keys: List[str]) -> int:
        """按 key 列表删除指定翻译缓存条目，返回删除条数。"""
        keys = [k for k in (keys or []) if k]
        if not keys:
            return 0
        with self._translation_lock:
            cursor = self.conn.cursor()
            placeholders = ','.join('?' * len(keys))
            cursor.execute(f'DELETE FROM translation_cache WHERE key IN ({placeholders})', keys)
            self.conn.commit()
            return cursor.rowcount

    # 翻译记忆库（代理翻译结果永久沉淀，无需代理即可复用）
    def get_translation_memory(self, source: str, target: str) -> Optional[str]:
        """命中翻译记忆库时返回译文并累加命中次数。"""
        with self._translation_lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT translated FROM translation_memory
                WHERE source = ? AND target = ?
            ''', (source, target))
            row = cursor.fetchone()
            if row and row[0]:
                cursor.execute('''
                    UPDATE translation_memory SET hits = hits + 1, updated_at = ?
                    WHERE source = ? AND target = ?
                ''', (datetime.now().isoformat(), source, target))
                self.conn.commit()
                return row[0]
            return None

    def set_translation_memory(self, source: str, target: str, translated: str) -> None:
        """保存代理翻译结果到记忆库（source+target 唯一，重复保存时刷新译文与时间）。"""
        if not source or not translated or source == translated:
            return
        with self._translation_lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO translation_memory (source, target, translated, hits, updated_at)
                VALUES (?, ?, ?, 1, ?)
                ON CONFLICT(source, target) DO UPDATE SET
                    translated = excluded.translated,
                    hits = hits + 1,
                    updated_at = excluded.updated_at
            ''', (source, target, translated, datetime.now().isoformat()))
            self.conn.commit()
            self._trim_translation_memory(cursor)

    def _trim_translation_memory(self, cursor) -> None:
        """记忆库条数超限时，删除最旧的 20% 条目，防止无限膨胀。"""
        cursor.execute('SELECT COUNT(*) FROM translation_memory')
        count = cursor.fetchone()[0]
        if count <= TRANSLATION_MEMORY_MAX_ENTRIES:
            return
        trim_count = max(1, int(count * TRANSLATION_MEMORY_TRIM_RATIO))
        cursor.execute('''
            DELETE FROM translation_memory WHERE id IN (
                SELECT id FROM translation_memory
                ORDER BY updated_at ASC
                LIMIT ?
            )
        ''', (trim_count,))
        self.conn.commit()

    def list_translation_memory(self, limit: int = 200, offset: int = 0) -> List[dict]:
        """列出翻译记忆条目（按最近使用排序）。"""
        limit = max(1, min(int(limit), 500))
        offset = max(0, int(offset))
        with self._translation_lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT id, source, target, translated, hits, updated_at
                FROM translation_memory
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
            ''', (limit, offset))
            rows = cursor.fetchall()
        return [
            {
                'id': row[0],
                'source': row[1],
                'target': row[2],
                'translated': row[3],
                'hits': row[4],
                'updated_at': row[5],
            }
            for row in rows
        ]

    def delete_translation_memory(self, ids: List[int]) -> int:
        """按 id 列表删除翻译记忆条目。"""
        ids = [int(i) for i in (ids or [])]
        if not ids:
            return 0
        with self._translation_lock:
            cursor = self.conn.cursor()
            placeholders = ','.join('?' * len(ids))
            cursor.execute(f'DELETE FROM translation_memory WHERE id IN ({placeholders})', ids)
            self.conn.commit()
            return cursor.rowcount

    def clear_translation_memory(self) -> None:
        with self._translation_lock:
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM translation_memory')
            self.conn.commit()

    def get_translation_memory_stats(self) -> dict:
        with self._translation_lock:
            cursor = self.conn.cursor()
            cursor.execute('SELECT COUNT(*), COALESCE(SUM(hits), 0) FROM translation_memory')
            count, hits = cursor.fetchone()
        return {'count': count, 'hits': hits}

    # 学习词表（代理翻译后自动收录的新词）
    def record_learned_terms(self, source: str, translated: str) -> int:
        """从代理翻译的源文本中提取不在本地词典/术语表/停用词中的新词并收录。
        返回本次新增词条数。"""
        if not source or not translated:
            return 0
        sample_source = source[:200]
        sample_translated = translated[:200]
        now = datetime.now().isoformat()
        added = 0
        with self._translation_lock:
            cursor = self.conn.cursor()
            for word in _LEARN_WORD_PATTERN.findall(source):
                key = word.lower()
                if key in _KNOWN_TERM_LOOKUP or key in self._existing_learned:
                    continue
                cursor.execute('''
                    INSERT OR IGNORE INTO learned_terms (term, sample_source, sample_translated, updated_at)
                    VALUES (?, ?, ?, ?)
                ''', (key, sample_source, sample_translated, now))
                if cursor.rowcount > 0:
                    self._existing_learned.add(key)
                    added += 1
            self.conn.commit()
        return added

    def get_learned_terms_count(self) -> int:
        with self._translation_lock:
            cursor = self.conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM learned_terms')
            return cursor.fetchone()[0]

    def list_learned_terms(self, limit: int = 200, offset: int = 0) -> List[dict]:
        limit = max(1, min(int(limit), 500))
        offset = max(0, int(offset))
        with self._translation_lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT term, sample_source, sample_translated, updated_at
                FROM learned_terms
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
            ''', (limit, offset))
            rows = cursor.fetchall()
        return [
            {
                'term': row[0],
                'sample_source': row[1],
                'sample_translated': row[2],
                'updated_at': row[3],
            }
            for row in rows
        ]

    def delete_learned_terms(self, terms: List[str]) -> int:
        """按词汇名删除指定学习词条。"""
        terms = [t for t in (terms or []) if t]
        if not terms:
            return 0
        with self._translation_lock:
            cursor = self.conn.cursor()
            placeholders = ','.join('?' * len(terms))
            cursor.execute(f'DELETE FROM learned_terms WHERE term IN ({placeholders})', terms)
            self.conn.commit()
            for t in terms:
                self._existing_learned.discard(t)
            return cursor.rowcount

    def clear_learned_terms(self) -> None:
        with self._translation_lock:
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM learned_terms')
            self.conn.commit()
            self._existing_learned.clear()
