"""
数据库模块
负责消息数据的持久化存储
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from src.models import MessageData


class DatabaseManager:
    """
    数据库管理器

    负责SQLite数据库的连接管理、迁移和操作

    Attributes:
        db_connections: 连接池字典
        batch_size: 批量插入大小
    """

    def __init__(self, batch_size: int = 100):
        """
        初始化数据库管理器

        Args:
            batch_size: 批量插入的记录数
        """
        self.db_connections: Dict[str, sqlite3.Connection] = {}
        self.batch_size = batch_size

    def get_connection(self, channel: str) -> sqlite3.Connection:
        """
        获取指定频道的数据库连接

        Args:
            channel: 频道标识符

        Returns:
            SQLite数据库连接
        """
        if channel not in self.db_connections:
            self.db_connections[channel] = self._create_connection(channel)

        return self.db_connections[channel]

    def _create_connection(self, channel: str) -> sqlite3.Connection:
        """
        创建新的数据库连接

        Args:
            channel: 频道标识符

        Returns:
            SQLite数据库连接
        """
        channel_dir = Path(channel)
        channel_dir.mkdir(exist_ok=True)

        db_file = channel_dir / f"{channel}.db"
        conn = sqlite3.connect(str(db_file), check_same_thread=False)

        # 优化数据库性能
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")

        # 创建消息表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY,
                message_id INTEGER UNIQUE,
                date TEXT,
                sender_id INTEGER,
                first_name TEXT,
                last_name TEXT,
                username TEXT,
                message TEXT,
                media_type TEXT,
                media_path TEXT,
                reply_to INTEGER,
                post_author TEXT,
                views INTEGER,
                forwards INTEGER,
                reactions TEXT
            )
        """)

        # 创建索引
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_message_id ON messages(message_id)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_date ON messages(date)")

        conn.commit()

        # 执行数据库迁移
        self._migrate_database(conn)

        return conn

    def _migrate_database(self, conn: sqlite3.Connection) -> None:
        """
        执行数据库迁移，添加新字段

        Args:
            conn: 数据库连接
        """
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(messages)")
        columns = {row[1] for row in cursor.fetchall()}

        migrations = []
        if "post_author" not in columns:
            migrations.append("ALTER TABLE messages ADD COLUMN post_author TEXT")
        if "views" not in columns:
            migrations.append("ALTER TABLE messages ADD COLUMN views INTEGER")
        if "forwards" not in columns:
            migrations.append("ALTER TABLE messages ADD COLUMN forwards INTEGER")
        if "reactions" not in columns:
            migrations.append("ALTER TABLE messages ADD COLUMN reactions TEXT")

        for migration in migrations:
            try:
                conn.execute(migration)
            except sqlite3.OperationalError:
                pass

        if migrations:
            conn.commit()

    def close_all_connections(self) -> None:
        """
        关闭所有数据库连接
        """
        for conn in self.db_connections.values():
            conn.close()
        self.db_connections.clear()

    @contextmanager
    def get_connection_context(
        self, channel: str
    ) -> Generator[sqlite3.Connection, None, None]:
        """
        获取数据库连接的上下文管理器

        Args:
            channel: 频道标识符

        Yields:
            SQLite数据库连接
        """
        conn = self.get_connection(channel)
        try:
            yield conn
        finally:
            pass  # 连接由管理器统一管理

    def batch_insert_messages(self, channel: str, messages: List[MessageData]) -> None:
        """
        批量插入消息数据

        Args:
            channel: 频道标识符
            messages: 消息数据列表
        """
        if not messages:
            return

        conn = self.get_connection(channel)

        data = [
            (
                msg.message_id,
                msg.date,
                msg.sender_id,
                msg.first_name,
                msg.last_name,
                msg.username,
                msg.message,
                msg.media_type,
                msg.media_path,
                msg.reply_to,
                msg.post_author,
                msg.views,
                msg.forwards,
                msg.reactions,
            )
            for msg in messages
        ]

        conn.executemany(
            """
            INSERT OR IGNORE INTO messages
            (message_id, date, sender_id, first_name, last_name, username,
             message, media_type, media_path, reply_to, post_author, views,
             forwards, reactions)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            data,
        )
        conn.commit()

    def update_media_path(self, channel: str, message_id: int, media_path: str) -> None:
        """
        更新消息的媒体路径

        Args:
            channel: 频道标识符
            message_id: 消息ID
            media_path: 媒体文件路径
        """
        conn = self.get_connection(channel)
        conn.execute(
            "UPDATE messages SET media_path = ? WHERE message_id = ?",
            (media_path, message_id),
        )
        conn.commit()

    def get_message_count(self, channel: str) -> int:
        """
        获取频道消息总数

        Args:
            channel: 频道标识符

        Returns:
            消息数量
        """
        conn = self.get_connection(channel)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM messages")
        return cursor.fetchone()[0]

    def get_missing_media_messages(self, channel: str) -> List[tuple]:
        """
        获取缺少媒体文件的消息

        Args:
            channel: 频道标识符

        Returns:
            缺少媒体的消息列表 (message_id, media_type)
        """
        conn = self.get_connection(channel)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT message_id, media_type
            FROM messages
            WHERE media_type IS NOT NULL
            AND media_type != "MessageMediaWebPage"
            AND (media_path IS NULL OR media_path = "")
        """)

        return cursor.fetchall()

    def get_media_statistics(self, channel: str) -> Dict[str, int]:
        """
        获取媒体下载统计

        Args:
            channel: 频道标识符

        Returns:
            统计信息字典
        """
        conn = self.get_connection(channel)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*)
            FROM messages
            WHERE media_type IS NOT NULL
            AND media_type != "MessageMediaWebPage"
        """)
        total_with_media = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*)
            FROM messages
            WHERE media_type IS NOT NULL
            AND media_type != "MessageMediaWebPage"
            AND media_path IS NOT NULL
        """)
        total_with_files = cursor.fetchone()[0]

        return {
            "total_with_media": total_with_media,
            "total_with_files": total_with_files,
            "missing": total_with_media - total_with_files,
        }
