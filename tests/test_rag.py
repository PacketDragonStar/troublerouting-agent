"""
Ticket 19: RAG 知识库（Chroma 向量检索落地） 测试

验证:
- CaseLibrary.search() 优先用 Chroma 语义检索
- Chroma 不可用时降级为子串匹配
- confirm() 自动向量化写入 Chroma
- 未确认案例不进入检索池
"""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def case_lib():
    from agent.case_library import CaseLibrary
    return CaseLibrary()


class TestChromaSearch:
    """Chroma 语义检索"""

    def test_search_uses_chroma_when_available(self, case_lib):
        """Chroma 可用时优先用向量检索"""
        case_lib.add_draft("s1", {"symptom": "OSPF 邻居断开", "root_cause": "Hello 参数不匹配"})
        case_lib.confirm("s1")

        with patch.object(case_lib, '_chroma_search', return_value=[
            {"session_id": "s1", "symptom": "OSPF 邻居断开", "root_cause": "Hello 参数不匹配"}
        ]):
            results = case_lib.search("OSPF")
            assert len(results) == 1
            assert "OSPF" in results[0]["symptom"]

    def test_search_falls_back_to_substring(self, case_lib):
        """Chroma 不可用时降级为子串匹配"""
        case_lib.add_draft("s1", {"symptom": "BGP down", "root_cause": "BGP AS mismatch"})
        case_lib.confirm("s1")

        # 模拟 Chroma 不可用
        case_lib._chroma_available = False
        results = case_lib.search("BGP")
        assert len(results) == 1
        assert "BGP" in results[0]["symptom"]

    def test_unconfirmed_not_in_chroma(self, case_lib):
        """未确认案例不进入 Chroma"""
        case_lib.add_draft("s99", {"symptom": "CRC 错误"})
        # 不确认
        results = case_lib.search("CRC")
        assert len(results) == 0


class TestChromaIndexing:
    """Chroma 向量化入库"""

    def test_confirm_triggers_chroma_add(self, case_lib):
        """confirm() 自动向量化写入 Chroma"""
        case_lib.add_draft("s1", {"symptom": "接口 Down", "root_cause": "光模块老化", "confidence": 0.85})

        with patch.object(case_lib, '_chroma_add') as mock_add:
            case_lib.confirm("s1")
            mock_add.assert_called_once()

    def test_confirm_increments_confirmed_count(self, case_lib):
        """确认后 confirmed 标记为 True"""
        case_lib.add_draft("s1", {"symptom": "test"})
        case_lib.confirm("s1")
        assert case_lib.is_confirmed("s1") is True


class TestEmbedding:
    """Embedding 模型集成"""

    def test_embed_text_returns_list(self):
        from agent.case_library import embed_text
        vec = embed_text("OSPF 邻居断开")
        assert isinstance(vec, list)
        assert len(vec) > 0

    def test_embed_text_fallback_to_zeros(self):
        """Embedding 失败时降级为零向量"""
        from agent.case_library import embed_text
        vec = embed_text("test", fallback_dim=128)
        assert isinstance(vec, list)
        assert len(vec) == 128
        assert all(v == 0.0 for v in vec)


class TestBackwardCompatibility:
    """向后兼容——原有接口不变"""

    def test_add_draft_still_works(self, case_lib):
        case_lib.add_draft("s1", {"symptom": "test"})
        assert case_lib.get("s1") is not None

    def test_confirm_still_works(self, case_lib):
        case_lib.add_draft("s1", {"symptom": "test"})
        result = case_lib.confirm("s1")
        assert result is True

    def test_is_confirmed_still_works(self, case_lib):
        case_lib.add_draft("s1", {"symptom": "test"})
        assert not case_lib.is_confirmed("s1")
        case_lib.confirm("s1")
        assert case_lib.is_confirmed("s1")