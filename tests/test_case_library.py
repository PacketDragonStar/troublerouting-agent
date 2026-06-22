"""
Ticket 11: 案例库闭环（人工复盘接口） 测试

验证案例草稿状态流转、确认入库、检索接口。
"""
import pytest


class TestCaseDraftLifecycle:
    """案例草稿生命周期"""

    def test_draft_created_with_confirmed_false(self):
        from agent.pipeline import TroubleshootingReport
        from agent.reporter import Reporter
        import tempfile, os
        report = TroubleshootingReport(
            session_id="case-test-001",
            fault_description="核心交换机 OSPF 断开",
            root_cause="OSPF Hello 不匹配",
            confidence=0.85,
            risk_level="high",
            solution="检查 Hello 间隔",
            agent_trace=[],
        )
        reporter = Reporter(output_dir=tempfile.mkdtemp())
        draft = reporter.generate_case_draft(report)
        assert draft["confirmed"] is False

    def test_confirm_case_sets_confirmed_true(self):
        from agent.case_library import CaseLibrary
        lib = CaseLibrary()
        lib.add_draft("s1", {"symptom": "OSPF down", "root_cause": "OSPF Hello mismatch", "confidence": 0.85})
        assert lib.is_confirmed("s1") is False
        lib.confirm("s1")
        assert lib.is_confirmed("s1") is True


class TestCaseLibrary:
    """案例库检索"""

    def test_library_can_store_and_retrieve(self):
        from agent.case_library import CaseLibrary
        lib = CaseLibrary()
        lib.add_draft("s1", {"symptom": "接口 Down", "root_cause": "光模块老化"})
        lib.confirm("s1")
        entry = lib.get("s1")
        assert entry is not None
        assert entry["root_cause"] == "光模块老化"

    def test_unconfirmed_case_not_in_search(self):
        from agent.case_library import CaseLibrary
        lib = CaseLibrary()
        lib.add_draft("s1", {"symptom": "BGP down", "root_cause": "BGP AS mismatch"})
        results = lib.search("BGP")
        assert len(results) == 0  # 未确认的不进检索池

    def test_confirmed_case_in_search(self):
        from agent.case_library import CaseLibrary
        lib = CaseLibrary()
        lib.add_draft("s1", {"symptom": "BGP down", "root_cause": "BGP AS mismatch"})
        lib.confirm("s1")
        results = lib.search("BGP")
        assert len(results) == 1
        assert "BGP" in results[0]["symptom"]

    def test_case_not_overwritten(self):
        from agent.case_library import CaseLibrary
        lib = CaseLibrary()
        lib.add_draft("s1", {"symptom": "first", "root_cause": "rc1"})
        lib.add_draft("s1", {"symptom": "second", "root_cause": "rc2"})
        entry = lib.get("s1")
        assert entry["symptom"] == "first"

    def test_not_confirmed_not_in_library_search(self):
        from agent.case_library import CaseLibrary
        lib = CaseLibrary()
        lib.add_draft("s99", {"symptom": "CRC错误"})
        results = lib.search("CRC")
        assert results == []