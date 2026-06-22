"""StateStore——外部状态存储 + 上下文管理

Agent 不从对话历史传递数据，统一从 SQLite 读取。
对话历史仅存推理链，大日志数据写入 DB 避免上下文溢出。
"""

import json
import sqlite3
from typing import Any, Optional


class StateStore:
    """外部状态存储

    三张表：
    - fault_sessions: 故障摘要
    - collected_data: 设备数据（含大日志）
    - diagnosis: 诊断结论
    """

    def __init__(self, db_path: str = "data/troublerouting.db"):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    def initialize(self) -> None:
        """初始化数据库连接和建表"""
        import os
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

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def _ensure_conn(self) -> None:
        if self._conn is None:
            self.initialize()

    def list_tables(self) -> list[str]:
        self._ensure_conn()
        rows = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        return [r["name"] for r in rows]

    # ---- fault_sessions ----

    def save_fault_session(self, session_id: str, description: str, path: str) -> None:
        self._ensure_conn()
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO fault_sessions (session_id, fault_description, path) VALUES (?, ?, ?)",
                (session_id, description, path),
            )

    def get_fault_session(self, session_id: str) -> Optional[dict[str, Any]]:
        self._ensure_conn()
        row = self._conn.execute(
            "SELECT * FROM fault_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        return dict(row) if row else None

    # ---- collected_data ----

    def save_collected_data(self, session_id: str, device_ip: str, data: dict[str, Any]) -> None:
        self._ensure_conn()
        with self._conn:
            self._conn.execute(
                "INSERT INTO collected_data (session_id, device_ip, data_json) VALUES (?, ?, ?)",
                (session_id, device_ip, json.dumps(data, ensure_ascii=False)),
            )

    def get_collected_data(self, session_id: str, device_ip: str) -> Optional[dict[str, Any]]:
        self._ensure_conn()
        row = self._conn.execute(
            "SELECT data_json FROM collected_data WHERE session_id = ? AND device_ip = ? ORDER BY id DESC LIMIT 1",
            (session_id, device_ip),
        ).fetchone()
        if row:
            return json.loads(row["data_json"])
        return None

    # ---- diagnosis ----

    def save_diagnosis(self, session_id: str, root_cause: str, confidence: float, evidence: list[str]) -> None:
        self._ensure_conn()
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO diagnosis (session_id, root_cause, confidence, evidence_json) VALUES (?, ?, ?, ?)",
                (session_id, root_cause, confidence, json.dumps(evidence, ensure_ascii=False)),
            )

    def get_diagnosis(self, session_id: str) -> Optional[dict[str, Any]]:
        self._ensure_conn()
        row = self._conn.execute(
            "SELECT * FROM diagnosis WHERE session_id = ?", (session_id,)
        ).fetchone()
        if row:
            d = dict(row)
            d["evidence"] = json.loads(d.pop("evidence_json", "[]"))
            return d
        return None