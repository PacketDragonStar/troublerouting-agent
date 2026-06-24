"""StateStore——外部状态存储 + 上下文管理（SQLite / MySQL 双后端）

Agent 不从对话历史传递数据，统一从数据库读取。
对话历史仅存推理链，大日志数据写入 DB 避免上下文溢出。

Phase 1：SQLite（零配置 Demo）
Phase 2：MySQL（生产级并发）
"""

import json
import os
from typing import Any, Optional


class StateStore:
    """外部状态存储

    三张表：
    - fault_sessions: 故障摘要
    - collected_data: 设备数据（含大日志）
    - diagnosis: 诊断结论

    backend: "sqlite" (默认) 或 "mysql"
    """

    def __init__(self, backend: str = "", db_path: str = "data/troublerouting.db"):
        """初始化 StateStore，自动从 STATE_BACKEND 环境变量选择后端"""
        if not backend:
            backend = os.getenv("STATE_BACKEND", "sqlite")
        self.backend = backend
        self.db_path = db_path
        self._conn = None

    def initialize(self) -> None:
        """初始化数据库连接和建表"""
        if self.backend == "mysql":
            self._init_mysql()
        else:
            self._init_sqlite()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ---- SQLite 实现 ----

    def _init_sqlite(self) -> None:
        import sqlite3
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._conn:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS fault_sessions (
                    session_id TEXT PRIMARY KEY,
                    fault_description TEXT,
                    path TEXT,
                    raw_text TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS collected_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    device_ip TEXT NOT NULL,
                    data_json TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS diagnosis (
                    session_id TEXT PRIMARY KEY,
                    root_cause TEXT,
                    confidence REAL,
                    evidence_json TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)

    # ---- MySQL 实现 ----

    def _init_mysql(self) -> None:
        import pymysql
        self._conn = pymysql.connect(
            host=os.getenv("MYSQL_HOST", "localhost"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASS", ""),
            database=os.getenv("MYSQL_DB", "troublerouting"),
            charset="utf8mb4",
            autocommit=True,
        )
        with self._conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS fault_sessions (
                    session_id VARCHAR(64) PRIMARY KEY,
                    fault_description TEXT,
                    path VARCHAR(16),
                    raw_text TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS collected_data (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    session_id VARCHAR(64) NOT NULL,
                    device_ip VARCHAR(45) NOT NULL,
                    data_json JSON,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_session (session_id),
                    INDEX idx_device (session_id, device_ip)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS diagnosis (
                    session_id VARCHAR(64) PRIMARY KEY,
                    root_cause TEXT,
                    confidence DOUBLE,
                    evidence_json JSON,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

    # ---- 通用方法 ----

    def list_tables(self) -> list[str]:
        if self._conn is None:
            self.initialize()
        if self.backend == "mysql":
            with self._conn.cursor() as cur:
                cur.execute("SHOW TABLES")
                return [r[0] for r in cur.fetchall()]
        else:
            rows = self._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            return [r["name"] for r in rows]

    # ---- fault_sessions ----

    def save_fault_session(self, session_id: str, description: str, path: str) -> None:
        if self._conn is None:
            self.initialize()
        if self.backend == "mysql":
            with self._conn.cursor() as cur:
                cur.execute(
                    "REPLACE INTO fault_sessions (session_id, fault_description, path) VALUES (%s, %s, %s)",
                    (session_id, description, path),
                )
        else:
            with self._conn:
                self._conn.execute(
                    "INSERT OR REPLACE INTO fault_sessions (session_id, fault_description, path) VALUES (?, ?, ?)",
                    (session_id, description, path),
                )

    def get_fault_session(self, session_id: str) -> Optional[dict[str, Any]]:
        if self._conn is None:
            self.initialize()
        if self.backend == "mysql":
            with self._conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM fault_sessions WHERE session_id = %s", (session_id,)
                )
                row = cur.fetchone()
                if row:
                    cols = [d[0] for d in cur.description]
                    return dict(zip(cols, row))
                return None
        else:
            row = self._conn.execute(
                "SELECT * FROM fault_sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            return dict(row) if row else None

    # ---- collected_data ----

    def save_collected_data(self, session_id: str, device_ip: str, data: dict[str, Any]) -> None:
        if self._conn is None:
            self.initialize()
        data_str = json.dumps(data, ensure_ascii=False)
        if self.backend == "mysql":
            with self._conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO collected_data (session_id, device_ip, data_json) VALUES (%s, %s, %s)",
                    (session_id, device_ip, data_str),
                )
        else:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO collected_data (session_id, device_ip, data_json) VALUES (?, ?, ?)",
                    (session_id, device_ip, data_str),
                )

    def get_collected_data(self, session_id: str, device_ip: str) -> Optional[dict[str, Any]]:
        if self._conn is None:
            self.initialize()
        if self.backend == "mysql":
            with self._conn.cursor() as cur:
                cur.execute(
                    "SELECT data_json FROM collected_data WHERE session_id = %s AND device_ip = %s ORDER BY id DESC LIMIT 1",
                    (session_id, device_ip),
                )
                row = cur.fetchone()
                if row:
                    return json.loads(row[0])
                return None
        else:
            row = self._conn.execute(
                "SELECT data_json FROM collected_data WHERE session_id = ? AND device_ip = ? ORDER BY id DESC LIMIT 1",
                (session_id, device_ip),
            ).fetchone()
            if row:
                return json.loads(row["data_json"])
            return None

    # ---- diagnosis ----

    def save_diagnosis(self, session_id: str, root_cause: str, confidence: float, evidence: list[str]) -> None:
        if self._conn is None:
            self.initialize()
        evidence_str = json.dumps(evidence, ensure_ascii=False)
        if self.backend == "mysql":
            with self._conn.cursor() as cur:
                cur.execute(
                    "REPLACE INTO diagnosis (session_id, root_cause, confidence, evidence_json) VALUES (%s, %s, %s, %s)",
                    (session_id, root_cause, confidence, evidence_str),
                )
        else:
            with self._conn:
                self._conn.execute(
                    "INSERT OR REPLACE INTO diagnosis (session_id, root_cause, confidence, evidence_json) VALUES (?, ?, ?, ?)",
                    (session_id, root_cause, confidence, evidence_str),
                )

    def get_diagnosis(self, session_id: str) -> Optional[dict[str, Any]]:
        if self._conn is None:
            self.initialize()
        if self.backend == "mysql":
            with self._conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM diagnosis WHERE session_id = %s", (session_id,)
                )
                row = cur.fetchone()
                if row:
                    cols = [d[0] for d in cur.description]
                    d = dict(zip(cols, row))
                    d["evidence"] = json.loads(d.get("evidence_json", "[]"))
                    return d
                return None
        else:
            row = self._conn.execute(
                "SELECT * FROM diagnosis WHERE session_id = ?", (session_id,)
            ).fetchone()
            if row:
                d = dict(row)
                d["evidence"] = json.loads(d.pop("evidence_json", "[]"))
                return d
            return None