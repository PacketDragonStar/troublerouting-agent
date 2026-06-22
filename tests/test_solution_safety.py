"""
Ticket 6: Solution Engineer + Safety Officer 规则引擎 测试

验证修复方案生成、3级风险评级、审批/否决/人工兜底。
"""

import pytest


@pytest.fixture
def safety_engineer():
    from agent.solution_engineer import SolutionEngineer
    return SolutionEngineer()


@pytest.fixture
def safety_officer():
    from agent.safety_officer import SafetyOfficer
    return SafetyOfficer()


class TestSolutionEngineer:
    """方案工程师测试"""

    def test_generate_solution_for_interface_down(self, safety_engineer):
        plan = safety_engineer.generate(
            root_cause="接口 Gi0/1 CRC 错误，疑似光模块老化",
            confidence=0.85,
            device="core-switch",
        )
        assert plan["commands"] is not None
        assert "risk_level" in plan
        assert plan["risk_level"] in ("low", "medium", "high")

    def test_generate_solution_returns_commands_list(self, safety_engineer):
        plan = safety_engineer.generate(
            root_cause="OSPF 邻居断开，Hello 参数不匹配",
            confidence=0.75,
            device="core-router",
        )
        assert isinstance(plan["commands"], list)
        assert len(plan["commands"]) > 0

    def test_reload_root_cause_gives_high_risk(self, safety_engineer):
        plan = safety_engineer.generate(
            root_cause="设备需要重启才能恢复 BGP 进程",
            confidence=0.70,
            device="core-router",
        )
        assert plan["risk_level"] == "high"


class TestSafetyOfficer:
    """安全审计官测试"""

    def test_low_risk_approved(self, safety_officer):
        result = safety_officer.review(
            commands=["show interface description"],
            risk_level="low",
            device="access-switch",
        )
        assert result["approved"] is True

    def test_medium_risk_notifies(self, safety_officer):
        result = safety_officer.review(
            commands=["interface Gi0/1", "shutdown"],
            risk_level="medium",
            device="access-switch",
        )
        assert result["approved"] is True
        assert "notification" in result or result.get("notification") is not None
        assert "人工确认" in result.get("notification", "")

    def test_high_risk_rejected(self, safety_officer):
        result = safety_officer.review(
            commands=["reload", "yes"],
            risk_level="high",
            device="core-router",
        )
        assert result["approved"] is False

    def test_high_risk_forces_manual(self, safety_officer):
        result = safety_officer.review(
            commands=["reset bgp all"],
            risk_level="high",
            device="core-router",
        )
        assert "manual" in result or result.get("action") == "manual"

    def test_safety_blocked_commands_always_rejected(self, safety_officer):
        """安全拦截命令列表中的命令永远被拒绝"""
        for cmd in safety_officer.BLOCKED_COMMANDS:
            result = safety_officer.review(
                commands=[cmd], risk_level="low", device="test"
            )
            assert result["approved"] is False, f"Should block: {cmd}"

    def test_low_risk_commands_list_is_safe(self, safety_officer):
        """低风险命令列表都安全"""
        result = safety_officer.review(
            commands=["show interface", "display version", "ping 10.0.0.1"],
            risk_level="low",
            device="test",
        )
        assert result["approved"] is True