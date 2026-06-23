"""
Ticket 13: TACACS+ 双层防护 测试

验证:
- 本地正则白名单（第一道防线）
- TACACS+ 远程授权（第二道防线，Mock 测试）
- TACACS+ 超时降级为正则结果
- 三厂商命令集配置
"""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def tacacs_client():
    from agent.tacacs_guard import TACACSGuard, TACACSConfig
    config = TACACSConfig(
        server="127.0.0.1",
        port=49,
        secret="test-secret",
        username="agent-ro",
        timeout=3,
    )
    return TACACSGuard(config)


class TestTACACSConfig:
    """TACACS+ 配置"""

    def test_config_has_required_fields(self):
        from agent.tacacs_guard import TACACSConfig
        config = TACACSConfig(
            server="10.0.0.1", port=49,
            secret="secret", username="agent-ro",
            timeout=5,
        )
        assert config.server == "10.0.0.1"
        assert config.port == 49
        assert config.timeout == 5

    def test_config_uses_env_vars_by_default(self):
        import os
        from agent.tacacs_guard import TACACSConfig
        os.environ["TACACS_SERVER"] = "192.168.1.1"
        os.environ["TACACS_SECRET"] = "env-secret"
        config = TACACSConfig.from_env()
        assert config.server == "192.168.1.1"
        assert config.secret == "env-secret"


class TestTACACSGuard:
    """TACACS+ 授权守卫"""

    def test_add_command_policy(self, tacacs_client):
        """添加命令策略"""
        tacacs_client.add_policy("cisco", ["show interface", "show version"])
        assert tacacs_client.has_policy("cisco")

    def test_policy_contains_command(self, tacacs_client):
        """策略包含预期命令"""
        tacacs_client.add_policy("cisco", ["show interface", "show version"])
        assert tacacs_client.is_allowed("cisco", "show interface")
        assert tacacs_client.is_allowed("cisco", "show version")

    def test_policy_rejects_unknown_command(self, tacacs_client):
        """策略拒绝未授权命令"""
        tacacs_client.add_policy("cisco", ["show interface"])
        assert not tacacs_client.is_allowed("cisco", "reload")

    def test_double_layer_allow(self, tacacs_client):
        """双层防护：正则通过 + TACACS+ 通过 → 允许"""
        from mcp.command_whitelist import CommandWhitelist
        whitelist = CommandWhitelist()
        tacacs_client.add_policy("cisco", ["show interface", "show version"])

        result = tacacs_client.double_check(
            whitelist.check("show interface", vendor="cisco"),
            "cisco",
            "show interface",
        )
        assert result["allowed"] is True

    def test_double_layer_block_by_whitelist(self, tacacs_client):
        """双层防护：正则拦截 → 不进入 TACACS+"""
        from mcp.command_whitelist import CommandWhitelist
        whitelist = CommandWhitelist()
        tacacs_client.add_policy("cisco", ["reload"])  # 即使 TACACS+ 允许

        result = tacacs_client.double_check(
            whitelist.check("reload", vendor="cisco"),
            "cisco",
            "reload",
        )
        assert result["allowed"] is False

    def test_double_layer_block_by_tacacs(self, tacacs_client):
        """双层防护：正则通过 + TACACS+ 拒绝 → 拒绝"""
        from mcp.command_whitelist import CommandWhitelist
        whitelist = CommandWhitelist()
        # 不添加任何策略 → TACACS+ 默认拒绝

        result = tacacs_client.double_check(
            whitelist.check("show version", vendor="cisco"),
            "cisco",
            "show version",
        )
        assert result["allowed"] is False

    def test_timeout_fallback_to_whitelist_result(self, tacacs_client):
        """TACACS+ 超时 → 降级为正则白名单结果"""
        from mcp.command_whitelist import CommandWhitelist
        whitelist = CommandWhitelist()
        tacacs_client._server_reachable = False  # 模拟不可达

        result = tacacs_client.double_check(
            whitelist.check("show interface", vendor="cisco"),
            "cisco",
            "show interface",
        )
        assert result["allowed"] is True  # 正则放行
        assert result.get("fallback") is True  # 标注降级

    def test_timeout_fallback_blocked(self, tacacs_client):
        """TACACS+ 超时 + 正则拒绝 → 拒绝"""
        from mcp.command_whitelist import CommandWhitelist
        whitelist = CommandWhitelist()
        tacacs_client._server_reachable = False

        result = tacacs_client.double_check(
            whitelist.check("reload", vendor="cisco"),
            "cisco",
            "reload",
        )
        assert result["allowed"] is False  # 正则拒绝


class TestVendorPolicies:
    """三厂商命令策略"""

    def test_cisco_policy(self):
        from agent.tacacs_guard import TACACSGuard, TACACSConfig, CISCO_READONLY_COMMANDS
        guard = TACACSGuard(TACACSConfig.from_env())
        guard.add_policy("cisco", CISCO_READONLY_COMMANDS)
        assert guard.is_allowed("cisco", "show interface")
        assert guard.is_allowed("cisco", "show version")
        assert not guard.is_allowed("cisco", "configure terminal")

    def test_huawei_policy(self):
        from agent.tacacs_guard import TACACSGuard, TACACSConfig, HUAWEI_READONLY_COMMANDS
        guard = TACACSGuard(TACACSConfig.from_env())
        guard.add_policy("huawei", HUAWEI_READONLY_COMMANDS)
        assert guard.is_allowed("huawei", "display interface")
        assert guard.is_allowed("huawei", "display version")
        assert not guard.is_allowed("huawei", "system-view")

    def test_h3c_policy(self):
        from agent.tacacs_guard import TACACSGuard, TACACSConfig, H3C_READONLY_COMMANDS
        guard = TACACSGuard(TACACSConfig.from_env())
        guard.add_policy("h3c", H3C_READONLY_COMMANDS)
        assert guard.is_allowed("h3c", "display interface")
        assert guard.is_allowed("h3c", "display version")
        assert not guard.is_allowed("h3c", "system-view")