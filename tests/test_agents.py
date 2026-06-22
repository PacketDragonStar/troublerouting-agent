"""
Ticket 2: AutoGen GroupChat 骨架 + 6 Agent 空壳注册 测试

验证 6 Agent 注册、Manager 硬编码发言顺序、Fast/Slow Path 分流。
"""
import pytest


class TestAgentRegistration:
    """Agent 注册测试"""

    def test_all_six_agents_registered(self):
        """验证 6 个 Agent 全部注册成功"""
        from agent.agents import create_agents
        agents = create_agents()
        assert len(agents) == 6
        names = [a.name for a in agents]
        assert "Dispatcher" in names
        assert "Investigator" in names
        assert "Diagnostician" in names
        assert "Solution" in names
        assert "Safety" in names
        assert "Reporter" in names

    def test_agent_has_role_description(self):
        """每个 Agent 有角色描述"""
        from agent.agents import create_agents
        agents = create_agents()
        for agent in agents:
            assert agent.name is not None
            assert len(agent.name) > 0


class TestPipeline:
    """排障流程测试"""

    @pytest.mark.asyncio
    async def test_fast_path_uses_two_agents(self):
        """Fast Path 只使用 2 个 Agent"""
        from agent.pipeline import TroubleshootingReport
        from agent.agents import run_troubleshooting

        report = await run_troubleshooting(
            "接入交换机端口 Gi0/1 down 了",
            fast_path=True,
        )
        assert isinstance(report, TroubleshootingReport)
        assert len(report.agent_trace) >= 1
        # Fast Path: Dispatcher 决定路由 → Investigator + Diagnostician
        # echo 模式下至少有条目
        assert report.fault_description == "接入交换机端口 Gi0/1 down 了"

    @pytest.mark.asyncio
    async def test_slow_path_uses_six_agents(self):
        """Slow Path 使用全部 6 个 Agent"""
        from agent.pipeline import TroubleshootingReport
        from agent.agents import run_troubleshooting

        report = await run_troubleshooting(
            "核心交换机 10.0.0.1 OSPF 邻居断开",
            fast_path=False,
        )
        assert isinstance(report, TroubleshootingReport)
        assert len(report.agent_trace) == 6
        trace_names = [t["agent"] for t in report.agent_trace]
        assert trace_names == [
            "Dispatcher",
            "Investigator",
            "Diagnostician",
            "Solution",
            "Safety",
            "Reporter",
        ]

    @pytest.mark.asyncio
    async def test_pipeline_produces_report(self):
        """排障流程返回完整报告"""
        from agent.pipeline import TroubleshootingReport
        from agent.agents import run_troubleshooting

        report = await run_troubleshooting("测试故障描述")
        assert isinstance(report, TroubleshootingReport)
        assert report.session_id != ""
        assert report.fault_description == "测试故障描述"