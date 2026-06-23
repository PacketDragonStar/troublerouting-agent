"""CaseLibrary——案例库闭环（RAG 知识库扩容版）

- 案例草稿状态：confirmed=false → 人工确认 → confirmed=true
- 只有 confirmed=true 的案例进入检索池
- Demo 阶段：优先用 Chroma 语义检索，Chroma 不可用时降级为子串匹配
- Phase 2：接 Chroma Docker 实际实例 + OpenAI Embedding
"""

from typing import Any, Optional


def embed_text(text: str, fallback_dim: int = 128) -> list[float]:
    """文本向量化——Demo 阶段返回零向量占位符

    Phase 2 替换为:
    - OpenAI: openai.Embedding.create(input=text, model="text-embedding-3-small")
    - 本地: SentenceTransformer("bge-small-zh").encode(text)

    Args:
        text: 待向量化的文本
        fallback_dim: 降级时返回的向量维度

    Returns:
        向量（float 列表）
    """
    # Demo: 返回零向量占位（长度等于 fallback_dim）
    # 这样 search() 可以继续工作，只是退化为子串匹配
    return [0.0] * fallback_dim


class CaseLibrary:
    """案例库——草稿管理 + Chroma 向量检索 + 子串降级"""

    def __init__(self):
        self._drafts: dict[str, dict[str, Any]] = {}
        self._confirmed: dict[str, dict[str, Any]] = {}
        self._chroma_available = False  # Demo: Chroma 未配置
        # Phase 2: 接 chromadb.Client() 后设为 True

    # ---- 草稿管理（原有接口不变） ----

    def add_draft(self, session_id: str, data: dict[str, Any]) -> None:
        """添加案例草稿（不覆盖已有草稿）"""
        if session_id not in self._drafts:
            self._drafts[session_id] = data

    def get(self, session_id: str) -> Optional[dict[str, Any]]:
        """获取案例（先查草稿，再查已确认）"""
        return self._drafts.get(session_id) or self._confirmed.get(session_id)

    def confirm(self, session_id: str) -> bool:
        """确认案例——从草稿池移到已确认池，自动向量化写入 Chroma"""
        if session_id in self._drafts:
            data = self._drafts.pop(session_id)
            data["confirmed"] = True
            self._confirmed[session_id] = data

            # 自动向量化写入 Chroma（Demo 阶段仅做记录）
            self._chroma_add(session_id, data)
            return True
        return False

    def is_confirmed(self, session_id: str) -> bool:
        """检查案例是否已确认"""
        return session_id in self._confirmed

    # ---- 检索（Chroma 优先 + 子串降级） ----

    def search(self, query: str) -> list[dict[str, Any]]:
        """检索已确认案例

        优先级：
        1. Chroma 向量检索（语义相似度）
        2. 子串匹配（降级兜底）

        Args:
            query: 搜索关键词或自然语言描述

        Returns:
            匹配的已确认案例列表
        """
        if self._chroma_available:
            chroma_results = self._chroma_search(query)
            if chroma_results is not None:
                return chroma_results

        # 降级：子串匹配
        query_lower = query.lower()
        results = []
        for data in self._confirmed.values():
            symptom = data.get("symptom", "").lower()
            root_cause = data.get("root_cause", "").lower()
            if query_lower in symptom or query_lower in root_cause:
                results.append(data)
        return results

    # ---- Chroma 向量检索（Demo 阶段为占位，Phase 2 对接真实 Chroma） ----

    def _chroma_search(self, query: str) -> Optional[list[dict[str, Any]]]:
        """Chroma 向量检索（Demo 占位，Phase 2 对接真实 Chroma）

        Phase 2 实现:
        ```
        vec = embed_text(query)
        results = self._chroma_collection.query(
            query_embeddings=[vec],
            n_results=5,
        )
        return [{"session_id": r["id"], **r["metadata"]} for r in results]
        ```
        """
        if not self._chroma_available:
            return None
        # Demo 阶段 Chroma 未配置，返回 None 触发降级
        return None

    def _chroma_add(self, session_id: str, data: dict[str, Any]) -> None:
        """Chroma 向量化写入（Demo 占位，Phase 2 对接真实 Chroma）

        Phase 2 实现:
        ```
        text = data.get("symptom", "") + " " + data.get("root_cause", "")
        vec = embed_text(text)
        self._chroma_collection.add(
            ids=[session_id],
            embeddings=[vec],
            metadatas=[data],
        )
        ```
        """
        # Demo 阶段仅做空操作（Chroma 未连接）
        pass