"""Safety Officer Agent——安全审计官

基于 Python 规则引擎（非 LLM），拥有否决权。

3 级风险模型：
- 低（description 修改、只读操作）：自动批准
- 中（端口 shutdown、VLAN 变更）：批准 + 通知值班人
- 高（reload、BGP 变更、OSPF 进程重启）：拒绝 + 强制转人工工单

所有命令在审核前二次检查 MCP 白名单。
"""

from typing import Any


class SafetyOfficer:
    """安全审计官——规则引擎"""

    # 绝对禁止的命令（即使风险评级为 low 也不放行）
    BLOCKED_COMMANDS = [
        "reload",
        "reboot",
        "reset bgp all",
        "clear ip bgp *",
        "write erase",
        "format flash:",
        "delete flash:",
        "copy running-config startup-config",
    ]

    def review(
        self, commands: list[str], risk_level: str, device: str
    ) -> dict[str, Any]:
        """审核修复方案

        Args:
            commands: 待执行的命令列表
            risk_level: 方案工程师评估的风险级别
            device: 目标设备标识

        Returns:
            {
                "approved": bool,
                "action": "auto" | "notify" | "manual",
                "notification": str,
                "reason": str,
            }
        """
        # 0. 绝对禁止命令拦截
        for cmd in commands:
            cmd_lower = cmd.lower().strip()
            for blocked in self.BLOCKED_COMMANDS:
                if blocked in cmd_lower:
                    return {
                        "approved": False,
                        "action": "manual",
                        "notification": f"高危命令 {cmd} 已被规则引擎拦截，强制转人工处理",
                        "reason": f"命令含禁止关键字: {blocked}",
                    }

        # 1. 高风险 → 拒绝自动执行，转人工
        if risk_level == "high":
            return {
                "approved": False,
                "action": "manual",
                "notification": f"高风险变更——设备 {device}，命令: {commands}。已转人工工单，需值班工程师确认后执行。",
                "reason": "高风险操作，需人工确认",
            }

        # 2. 中风险 → 批准但通知
        if risk_level == "medium":
            return {
                "approved": True,
                "action": "notify",
                "notification": f"中风险变更——设备 {device}，命令: {commands}。已自动批准但请人工确认后执行。",
                "reason": "",
            }

        # 3. 低风险 → 自动批准
        return {
            "approved": True,
            "action": "auto",
            "notification": "",
            "reason": "",
        }