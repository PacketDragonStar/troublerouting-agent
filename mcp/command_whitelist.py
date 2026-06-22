"""MCP 命令白名单——正则匹配 + 黑名单子串

Demo 阶段用正则实现命令安全拦截。
Phase 2 升级为 TACACS+ Command Authorization。
"""

import re
from dataclasses import dataclass, field


@dataclass
class WhitelistResult:
    """白名单检查结果"""
    command: str
    allowed: bool
    risk_level: str = ""  # "low" | "medium" | "high"
    reason: str = ""


# 白名单正则：只允许以这些前缀开头的只读类命令
ALLOW_PREFIXES = [
    r"^show\b",
    r"^display\b",
    r"^ping\b",
    r"^traceroute\b",
    r"^tracert\b",
    r"^terminal\s+length",
    r"^screen-length\s+disable",
]

# 黑名单子串：即使匹配白名单前缀，含这些子串也拦截
BLOCK_SUBSTRINGS = [
    "tftp",
    "ftp",
    "redirect",
    "copy running",
    "copy startup",
    "erase",
    "format",
    "delete",
    "rm ",
]

# 完全禁止的命令（无论前缀匹配与否）
BLOCK_EXACT = [
    "configure terminal",
    "configure",
    "conf t",
    "config t",
    "system-view",
    "sys",
    "reload",
    "reboot",
    "write memory",
    "write",
    "wr",
    "copy run start",
    "copy running-config startup-config",
]


class CommandWhitelist:
    """命令白名单引擎

    双层检查：
    1. 白名单前缀正则匹配
    2. 黑名单子串扫描
    两步都通过才能执行。
    """

    def __init__(self):
        self._allow_patterns = [re.compile(p, re.IGNORECASE) for p in ALLOW_PREFIXES]

    def check(self, command: str, vendor: str = "cisco") -> WhitelistResult:
        """检查一条命令是否允许执行

        Args:
            command: 原始命令字符串
            vendor: 设备厂商（cisco/huawei/juniper），目前仅影响日志

        Returns:
            WhitelistResult: 包含 allowed、risk_level、reason
        """
        command_lower = command.lower().strip()

        # 1. 精确禁止匹配
        for blocked in BLOCK_EXACT:
            if command_lower == blocked:
                return WhitelistResult(
                    command=command,
                    allowed=False,
                    risk_level="high",
                    reason=f"BLOCKED: forbidden command '{command}'"
                )

        # 2. 黑名单子串扫描
        for sub in BLOCK_SUBSTRINGS:
            if sub in command_lower:
                return WhitelistResult(
                    command=command,
                    allowed=False,
                    risk_level="high",
                    reason=f"BLOCKED: command contains forbidden substring '{sub}'"
                )

        # 3. 白名单前缀匹配
        for pattern in self._allow_patterns:
            if pattern.match(command_lower):
                return WhitelistResult(
                    command=command,
                    allowed=True,
                    risk_level="low",
                    reason=""
                )

        # 4. 未匹配任何白名单
        return WhitelistResult(
            command=command,
            allowed=False,
            risk_level="medium",
            reason=f"BLOCKED: command '{command}' not in allowlist"
        )