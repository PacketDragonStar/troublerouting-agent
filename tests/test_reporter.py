"""
Ticket 7: Reporter Agent + 案例草稿生成 测试

验证汇总全流程数据 → Markdown 报告 + 案例草稿 JSON。
"""

import pytest
import os
import json
import tempfile


@pytest.fixture
def reporter():
    from agent.reporter import Reporter
    return Reporter(output_dir=tempfile.mkdtemp())


@pytest.fixture
def sample_report_data():
    from agent.pipeline import TroubleshootingReport
    return TroubleshootingReport(
        session_id="test-session-001",
        fault_description="核心交换机 10.0.0.1 OSPF 邻居断开",
        root_cause="OSPF Hello 参数不匹配",
        confidence=0.85,
        risk_level="high",
        solution="检查 OSPF Hello 间隔配置",
        agent_trace=[
            {"agent": "Dispatcher", "role": "调度员", "response": "路由到 Slow Path", "timestamp": "2024-01-01T00:00:00"},
            {"agent": "Investigator", "role": "调查员", "response": "收集到设备数据", "timestamp": "2024-01-01T00:00:10"},
            {"agent": "Diagnostician", "role": "诊断专家", "response": "OSPF Hello 不匹配", "timestamp": "2024-01-01T00:00:20"},
            {"agent": "Solution", "role": "方案工程师", "response": "生成修复命令", "timestamp": "2024-01-01T00:00:30"},
            {"agent": "Safety", "role": "安全审计官", "response": "高风险需人工审批", "timestamp": "2024-01-01T00:00:40"},
            {"agent": "Reporter", "role": "报告员", "response": "生成报告", "timestamp": "2024-01-01T00:00:50"},
        ],
    )


class TestReporter:
    """报告生成测试"""

    def test_generate_markdown_report(self, reporter, sample_report_data):
        """生成 Markdown 报告文件"""
        md_content = reporter.generate_markdown(sample_report_data)
        assert "核心交换机" in md_content
        assert "OSPF" in md_content
        assert "85%" in md_content or "0.85" in md_content
        assert "高" in md_content

    def test_generate_case_draft(self, reporter, sample_report_data):
        """生成案例草稿 JSON"""
        draft = reporter.generate_case_draft(sample_report_data)
        assert draft["session_id"] == "test-session-001"
        assert draft["confirmed"] is False
        assert "symptom" in draft
        assert "root_cause" in draft
        assert "confidence" in draft

    def test_save_report_to_file(self, reporter, sample_report_data):
        """保存报告到文件"""
        path = reporter.save_report(sample_report_data)
        assert os.path.exists(path)
        assert path.endswith(".md")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "test-session-001" in content

    def test_save_case_draft_json(self, reporter, sample_report_data):
        """保存案例草稿 JSON"""
        path = reporter.save_case_draft(sample_report_data)
        assert os.path.exists(path)
        assert path.endswith(".json")
        with open(path, "r", encoding="utf-8") as f:
            draft = json.load(f)
        assert draft["confirmed"] is False

    def test_multiple_reports_unique_filenames(self, reporter, sample_report_data):
        """多次保存不会覆盖"""
        path1 = reporter.save_report(sample_report_data)
        # 修改 session_id 生成第二份报告
        sample_report_data.session_id = "test-session-002"
        path2 = reporter.save_report(sample_report_data)
        assert path1 != path2
        assert os.path.exists(path1)
        assert os.path.exists(path2)


class TestCaseDraft:
    """案例草稿测试"""

    def test_draft_is_not_confirmed_by_default(self, reporter, sample_report_data):
        draft = reporter.generate_case_draft(sample_report_data)
        assert draft["confirmed"] is False

    def test_draft_contains_required_fields(self, reporter, sample_report_data):
        draft = reporter.generate_case_draft(sample_report_data)
        required = ["session_id", "symptom", "root_cause", "confidence", "risk_level", "confirmed"]
        for field in required:
            assert field in draft, f"Missing field: {field}"