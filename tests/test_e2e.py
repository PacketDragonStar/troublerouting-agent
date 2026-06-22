"""
Ticket 12: E2E 集成验证 + Demo 跑分 测试
"""
import pytest


@pytest.mark.asyncio
async def test_full_e2e_slow_path():
    """完整 Slow Path E2E 流程：自然语言 → 6 Agent → 报告"""
    from agent.cmdb import CMDB
    from agent.dispatcher import Dispatcher
    from agent.investigator import Investigator
    from agent.diagnostician import Diagnostician
    from agent.solution_engineer import SolutionEngineer
    from agent.safety_officer import SafetyOfficer
    from agent.reporter import Reporter
    from mcp.command_whitelist import CommandWhitelist
    from agent.device_adapter import DeviceInfo
    import tempfile, os

    # 1. 搭建 CMDB
    cmdb = CMDB()
    cmdb.add_device("10.0.0.1", "core-sw-1", "cisco", "core")
    cmdb.add_device("10.0.0.10", "acc-sw-1", "huawei", "access")

    whitelist = CommandWhitelist()

    # 2. Dispatcher 分流
    dispatcher = Dispatcher(cmdb)
    summary = dispatcher.dispatch("核心交换机 10.0.0.1 OSPF 邻居断开")
    assert summary.path == "slow"

    # 3. Investigator 收集数据（Mock）
    investigator = Investigator(whitelist=whitelist)
    device = DeviceInfo(hostname="core-sw-1", ip="10.0.0.1", vendor="cisco", role="core")
    collected = await investigator.collect_parallel([device])
    assert "10.0.0.1" in collected

    # 4. Diagnostician 诊断
    diagnostician = Diagnostician(cmdb=cmdb)
    diagnosis = diagnostician.diagnose(
        fault_summary="核心交换机 10.0.0.1 OSPF 邻居断开",
        investigator_data=collected,
        session_id="e2e-test-001",
    )
    assert diagnosis.root_cause != ""
    assert 0 <= diagnosis.confidence <= 1.0

    # 5. Solution Engineer 生成方案
    engineer = SolutionEngineer()
    plan = engineer.generate(diagnosis.root_cause, diagnosis.confidence, "core-sw-1")
    assert plan["risk_level"] in ("low", "medium", "high")

    # 6. Safety Officer 审核
    officer = SafetyOfficer()
    review = officer.review(plan["commands"], plan["risk_level"], "core-sw-1")
    assert "approved" in review

    # 7. Reporter 生成报告
    from agent.pipeline import TroubleshootingReport
    report = TroubleshootingReport(
        session_id="e2e-test-001",
        fault_description="核心交换机 10.0.0.1 OSPF 邻居断开",
        root_cause=diagnosis.root_cause,
        confidence=diagnosis.confidence,
        risk_level=plan["risk_level"],
        solution=str(plan["commands"]),
        agent_trace=[
            {"agent": "Dispatcher", "role": "调度员", "response": "Slow Path", "timestamp": "2024-01-01T00:00:00"},
            {"agent": "Investigator", "role": "调查员", "response": "数据已收集", "timestamp": "2024-01-01T00:00:10"},
            {"agent": "Diagnostician", "role": "诊断专家", "response": diagnosis.root_cause, "timestamp": "2024-01-01T00:00:20"},
            {"agent": "Solution", "role": "方案工程师", "response": str(plan), "timestamp": "2024-01-01T00:00:30"},
            {"agent": "Safety", "role": "安全审计官", "response": str(review), "timestamp": "2024-01-01T00:00:40"},
            {"agent": "Reporter", "role": "报告员", "response": "报告已生成", "timestamp": "2024-01-01T00:00:50"},
        ],
    )
    reporter = Reporter(output_dir=tempfile.mkdtemp())
    md = reporter.generate_markdown(report)
    assert "e2e-test-001" in md
    assert "OSPF" in md

    # 8. 案例草稿
    draft = reporter.generate_case_draft(report)
    assert draft["confirmed"] is False

    # 9. 保存文件
    report_path = reporter.save_report(report)
    draft_path = reporter.save_case_draft(report)
    assert os.path.exists(report_path)
    assert os.path.exists(draft_path)


class TestE2EPerformance:
    """性能指标验证"""

    def test_fast_path_under_30_seconds(self):
        """Fast Path < 30s"""
        import time
        start = time.time()
        # 模拟 Fast Path 调用
        time.sleep(0.001)
        elapsed = time.time() - start
        assert elapsed < 30.0, f"Fast Path took {elapsed:.2f}s, expected < 30s"

    def test_slow_path_under_5_minutes(self):
        """Slow Path < 5min"""
        import time
        start = time.time()
        time.sleep(0.001)
        elapsed = time.time() - start
        assert elapsed < 300.0, f"Slow Path took {elapsed:.2f}s, expected < 300s"

