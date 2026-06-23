"""
Ticket 20: Netmiko 真实设备接入 测试

验证:
- Netmiko 连接和命令执行
- 白名单校验仍然生效
- 超时控制
- 不可达标记
"""
import pytest
import os


@pytest.fixture
def investigator():
    from agent.investigator import Investigator
    from mcp.command_whitelist import CommandWhitelist
    return Investigator(whitelist=CommandWhitelist())


@pytest.fixture
def cisco_device():
    from agent.device_adapter import DeviceInfo
    return DeviceInfo(
        hostname="test-router",
        ip=os.getenv("TEST_DEVICE_IP", "192.0.2.1"),
        vendor="cisco",
        role="core",
    )


class TestNetmikoExecution:
    """Netmiko 执行测试（无外部设备时跳过）"""

    @pytest.mark.skipif(
        not os.getenv("TEST_DEVICE_IP"),
        reason="TEST_DEVICE_IP not set——skip real device test"
    )
    def test_real_device_show_version(self, investigator, cisco_device):
        """真实设备执行 show version"""
        result = investigator._execute_single_command_real(
            cisco_device, "show version", timeout=10
        )
        assert result["success"] is True
        assert len(result.get("raw_output", "")) > 0

    @pytest.mark.skipif(
        not os.getenv("TEST_DEVICE_IP"),
        reason="TEST_DEVICE_IP not set——skip real device test"
    )
    def test_real_device_blocked_command(self, investigator, cisco_device):
        """白名单拦截仍然生效"""
        result = investigator._execute_single_command_real(
            cisco_device, "reload", timeout=10
        )
        assert result["success"] is False
        assert result.get("blocked") is True

    @pytest.mark.skipif(
        not os.getenv("TEST_DEVICE_IP"),
        reason="TEST_DEVICE_IP not set——skip real device test"
    )
    def test_real_device_unreachable(self, investigator):
        """不可达设备返回 unreachable 信号"""
        from agent.device_adapter import DeviceInfo
        unreachable = DeviceInfo(
            hostname="no-such-device",
            ip="192.0.2.99",
            vendor="cisco",
            role="core",
        )
        result = investigator._execute_single_command_real(
            unreachable, "show version", timeout=3
        )
        assert result["success"] is False
        assert result.get("unreachable") is True


class TestNetmikoDeviceTypes:
    """Netmiko device_type 映射测试"""

    def test_cisco_ios_mapping(self):
        from agent.investigator import DEVICE_TYPE_MAP, get_device_type
        dt = get_device_type("cisco")
        assert dt == "cisco_ios"

    def test_huawei_mapping(self):
        from agent.investigator import get_device_type
        dt = get_device_type("huawei")
        assert dt == "huawei_vrpv8"

    def test_h3c_mapping(self):
        from agent.investigator import get_device_type
        dt = get_device_type("h3c")
        assert dt == "hp_comware"

    def test_unknown_vendor_defaults_to_cisco(self):
        from agent.investigator import get_device_type
        dt = get_device_type("unknown-vendor")
        assert dt == "cisco_ios"


class TestMockCompatibility:
    """确保 Mock 模式不受影响"""

    def test_mock_mode_still_works(self, investigator, cisco_device):
        """Mock 模式仍然可用"""
        result = investigator._execute_single_command(
            cisco_device, "show version", timeout=5
        )
        assert result["success"] is True
        assert "Mock" in result.get("raw_output", "")

    def test_mock_mode_blocked_command(self, investigator, cisco_device):
        """Mock 模式下白名单仍然生效"""
        result = investigator._execute_single_command(
            cisco_device, "configure terminal", timeout=5
        )
        assert result["success"] is False