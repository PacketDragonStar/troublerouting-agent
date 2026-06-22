"""CaseLibrary——案例库闭环

- 案例草稿状态：confirmed=false → 人工确认 → confirmed=true
- 只有 confirmed=true 的案例进入检索池
- Demo 阶段用内存字典 + 简单子串搜索，Phase 2 接 Chroma 向量检索
"""

from typing import Any, Optional


class CaseLibrary:
    """案例库——草稿管理 + 检索"""

    def __init__(self):
        self._drafts: dict[str, dict[str, Any]] = {}
        self._confirmed: dict[str, dict[str, Any]] = {}

    def add_draft(self, session_id: str, data: dict[str, Any]) -> None:
        """添加案例草稿（不覆盖已有草稿）"""
        if session_id not in self._drafts:
            self._drafts[session_id] = data

    def get(self, session_id: str) -> Optional[dict[str, Any]]:
        """获取案例（先查草稿，再查已确认）"""
        return self._drafts.get(session_id) or self._confirmed.get(session_id)

    def confirm(self, session_id: str) -> bool:
        """确认案例——从草稿池移到已确认池，进入检索池"""
        if session_id in self._drafts:
            data = self._drafts.pop(session_id)
            data["confirmed"] = True
            self._confirmed[session_id] = data
            return True
        return False

    def is_confirmed(self, session_id: str) -> bool:
        """检查案例是否已确认"""
        return session_id in self._confirmed

    def search(self, query: str) -> list[dict[str, Any]]:
        """检索已确认案例（Demo：简单子串匹配）

        Args:
            query: 搜索关键词（从症状/根因中查找）

        Returns:
            匹配的已确认案例列表
        """
        query_lower = query.lower()
        results = []
        for data in self._confirmed.values():
            symptom = data.get("symptom", "").lower()
            root_cause = data.get("root_cause", "").lower()
            if query_lower in symptom or query_lower in root_cause:
                results.append(data)
        return results