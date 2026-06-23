"""TACACS+ 双层防护——命令授权守卫

第一层：本地正则白名单（mcp/command_whitelist.py）——快速拦截
第二层：TACACS+ 远程授权（按厂商命令策略）——精细控制
TACACS+ 不可用时降级为正则白名单结果
"""

import os
from dataclasses import dataclass
from typing import Any, Optional


# ---- 三厂商只读命令集 ----

CISCO_READONLY_COMMANDS = [
    "show interface",
    "show version",
    "show processes cpu",
    "show memory",
    "show logging",
    "show ip ospf neighbor",
    "show ip bgp summary",
    "show interfaces counters errors",
    "show tech-support",
    "ping",
    "traceroute",
]

HUAWEI_READONLY_COMMANDS = [
    "display interface",
    "display version",
    "display cpu-usage",
    "display memory-usage",
    "display logbuffer",
    "display ospf peer",
    "display bgp peer",
    "display interface counters error",
    "display diagnostic-information",
    "ping",
    "tracert",
]

H3C_READONLY_COMMANDS = [
    "display interface",
    "display version",
    "display cpu-usage",
    "display memory-usage",
    "display logbuffer",
    "display ospf peer",
    "display bgp peer",
    "display interface counters error",
    "display diagnostic-information",
    "ping",
    "tracert",
]


@dataclass
class TACACSConfig:
    """TACACS+ 服务器配置"""
    server: str = ""
    port: int = 49
    secret: str = ""
    username: str = "agent-ro"
    timeout: int = 3

    @classmethod
    def from_env(cls) -> "TACACSConfig":
        """从环境变量加载配置"""
        return cls(
            server=os.getenv("TACACS_SERVER", ""),
            port=int(os.getenv("TACACS_PORT", "49")),
            secret=os.getenv("TACACS_SECRET", ""),
            username=os.getenv("TACACS_USER", "agent-ro"),
            timeout=int(os.getenv("TACACS_TIMEOUT", "3")),
        )


class TACACSGuard:
    """TACACS+ 授权守卫——双层防护引擎"""

    def __init__(self, config: TACACSConfig):
        self.config = config
        self._policies: dict[str, set[str]] = {}  # vendor -> {cmd1, cmd2, ...}
        self._server_reachable = True  # Demo 阶段可手动切换模拟故障

    # ---- 策略管理 ----

    def add_policy(self, vendor: str, commands: list[str]) -> None:
        """添加厂商命令策略"""
        self._policies.setdefault(vendor.lower(), set()).update(
            cmd.lower().strip() for cmd in commands
        )

    def has_policy(self, vendor: str) -> bool:
        """检查是否有该厂商的策略"""
        return vendor.lower() in self._policies

    def is_allowed(self, vendor: str, command: str) -> bool:
        """检查命令是否在 TACACS+ 策略中允许（Demo：本地策略匹配）"""
        cmds = self._policies.get(vendor.lower(), set())
        return command.lower().strip() in cmds

    # ---- 双层防护入口 ----

    def double_check(
        self,
        whitelist_result: Any,  # WhitelistResult from mcp/command_whitelist
        vendor: str,
        command: str,
    ) -> dict[str, Any]:
        """双层防护：正则白名单 → TACACS+ 远程授权

        Args:
            whitelist_result: CommandWhitelist.check() 的返回结果
            vendor: 设备厂商
            command: 原始命令

        Returns:
            {"allowed": bool, "reason": str, "fallback": bool}
        """
        # 第一层：正则白名单
        if not whitelist_result.allowed:
            return {
                "allowed": False,
                "reason": f"BLOCKED by whitelist: {whitelist_result.reason}",
                "fallback": False,
            }

        # 第二层：TACACS+ 远程授权（Demo 阶段用本地策略模拟）
        if not self._server_reachable:
            # TACACS+ 不可用 → 降级为正则结果
            return {
                "allowed": True,
                "reason": "TACACS+ unreachable, fallback to whitelist allow",
                "fallback": True,
            }

        if self.is_allowed(vendor, command):
            return {
                "allowed": True,
                "reason": "Allowed by TACACS+ policy",
                "fallback": False,
            }

        return {
            "allowed": False,
            "reason": f"BLOCKED by TACACS+: command not in {vendor} policy",
            "fallback": False,
        }