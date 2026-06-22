"""
Ticket 4: Investigator Agent + 并行数据收集 测试

验证并行执行器、超时控制、设备不可达标记、TextFSM 解析。
不依赖真实网络设备——用 Mock DeviceAdapter。
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch


@pytest.fixture
def investigator():
    from agent.investigator import Investigator
    from agent.device_adapter import DeviceInfo
    from mcp.command_whitelist import CommandWhitelist
    return Investigator(whitelist=CommandWhitelist())


@pytest.fixture
def sample_devices():
    from agent.device_adapter import DeviceInfo
    return [
        DeviceInfo(hostname="core-sw", ip="10.0.0.1", vendor="cisco", role="core"),
        DeviceInfo(hostname="acc-sw", ip="10.0.0.10", vendor="huawei", role="access"),
    ]


class TestInvestigatorBasic:
    """基础功能测试"""

    def test_create_investigator(self, investigator):
        assert investigator is not None

    def test_build_commands_for_cisco(self, investigator):
        from agent.device_adapter import DeviceInfo
        device = DeviceInfo(hostname="test", ip="10.0.0.1", vendor="cisco", role="core")
        commands = investigator.build_command_list(device)
        assert "show interface" in commands
        assert "show version" in commands
        assert "show processes cpu" in commands or "show cpu" in commands

    def test_build_commands_for_huawei(self, investigator):
        from agent.device_adapter import DeviceInfo
        device = DeviceInfo(hostname="test", ip="10.0.0.10", vendor="huawei", role="access")
        commands = investigator.build_command_list(device)
        assert any("display" in c for c in commands)
        assert any("interface" in c for c in commands)


class TestParallelExecution:
    """并行执行测试"""

    @pytest.mark.asyncio
    async def test_parallel_collects_from_all_devices(self, investigator, sample_devices):
        """并行收集：所有设备都返回结果"""
        with patch.object(
            investigator, '_execute_single_command',
            new_callable=AsyncMock,
            side_effect=lambda device, cmd, timeout: {
                "device": device.ip, "command": cmd,
                "raw_output": f"Mock output for {cmd}",
                "success": True, "error": ""
            }
        ):
            results = await investigator.collect_parallel(
                sample_devices,
                timeout_connect=2.0,
                timeout_command=5.0,
            )
        assert len(results) == 2
        assert "10.0.0.1" in results
        assert "10.0.0.10" in results

    @pytest.mark.asyncio
    async def test_unreachable_device_returns_signal(self, investigator, sample_devices):
        """设备不可达：返回 unreachable 信号"""
        async def mock_execute(device, cmd, timeout):
            if device.ip == "10.0.0.10":
                return {
                    "device": device.ip, "command": cmd,
                    "raw_output": "", "success": False,
                    "error": "Connection timeout",
                    "unreachable": True,
                }
            return {
                "device": device.ip, "command": cmd,
                "raw_output": f"Mock output for {cmd}",
                "success": True, "error": "",
            }

        with patch.object(investigator, '_execute_single_command', side_effect=mock_execute):
            results = await investigator.collect_parallel(sample_devices, 2.0, 5.0)
        assert "10.0.0.1" in results
        # 不可达设备也有结果
        assert "10.0.0.10" in results
        # 检查至少有一条标记为 unreachable
        device_results = results["10.0.0.10"]
        unreachable_commands = [
            r for r in device_results if r.get("unreachable")
        ]
        assert len(unreachable_commands) > 0


class TestTimeoutControl:
    """超时控制测试"""

    def test_fast_path_timeout_values(self, investigator):
        """Fast Path 超时配置：connect 2s, command 5s"""
        from agent.investigator import TimeoutConfig
        config = TimeoutConfig.fast_path()
        assert config.connect_timeout == 2.0
        assert config.command_timeout == 5.0

    def test_slow_path_timeout_values(self, investigator):
        """Slow Path 超时配置：connect 5s, command 15s"""
        from agent.investigator import TimeoutConfig
        config = TimeoutConfig.slow_path()
        assert config.connect_timeout == 5.0
        assert config.command_timeout == 15.0


class TestSummary:
    """Investigator 摘要输出测试"""

    def test_summary_includes_key_metrics(self):
        """摘要包含关键指标和异常行"""
        from agent.investigator import Investigator
        from mcp.command_whitelist import CommandWhitelist
        inv = Investigator(whitelist=CommandWhitelist())

        sample_data = {
            "10.0.0.1": [
                {"command": "show interface", "raw_output": "CRC errors: 12345", "success": True},
                {"command": "show cpu", "raw_output": "CPU 5%", "success": True},
            ]
        }
        summary = inv.summarize(sample_data, "test-session-001")
        assert "CRC" in summary
        assert "test-session-001" in summary
        # 摘要应引用原始数据 ID
        assert "session" in summary.lower() or "id" in summary.lower()