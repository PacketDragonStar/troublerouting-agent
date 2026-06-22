"""MCP 审计日志——所有工具调用自动生成审计记录"""

from datetime import datetime
from typing import Any, Optional


class AuditLog:
    """简易审计日志（Demo 阶段用内存存储，Phase 2 切 Elasticsearch）"""

    def __init__(self):
        self._entries: list[dict[str, Any]] = []

    def record(
        self,
        session_id: str,
        command: str,
        allowed: bool,
        reason: str = "",
    ) -> None:
        """记录一条工具调用"""
        self._entries.append({
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "command": command,
            "allowed": allowed,
            "reason": reason,
        })

    def get_entries(self, session_id: Optional[str] = None) -> list[dict[str, Any]]:
        """获取审计记录

        Args:
            session_id: 可选，按 Session 过滤

        Returns:
            审计记录列表
        """
        if session_id is None:
            return list(self._entries)
        return [e for e in self._entries if e["session_id"] == session_id]