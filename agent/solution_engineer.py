"""Solution Engineer Agent——方案工程师

基于诊断结果生成修复方案，包含变更命令、验证步骤、风险评级。
"""

from typing import Any


class SolutionEngineer:
    """方案工程师——基于规则模板生成修复方案"""

    def generate(
        self, root_cause: str, confidence: float, device: str
    ) -> dict[str, Any]:
        """生成修复方案

        Returns:
            {"commands": [...], "risk_level": "low"|"medium"|"high", "description": ""}
        """
        cause_lower = root_cause.lower()

        # 重启/重置类 → high
        if any(kw in cause_lower for kw in ("重启", "reload", "reboot", "reset")):
            return {
                "commands": [f"reload {device}"],
                "risk_level": "high",
                "description": root_cause,
            }

        # 端口操作类 → medium
        if any(kw in cause_lower for kw in ("端口", "interface", "shutdown", "no shut")):
            return {
                "commands": [
                    f"interface Gi0/1",
                    "shutdown",
                    "no shutdown",
                ],
                "risk_level": "medium",
                "description": root_cause,
            }

        # OSPF/BGP 修改 → high
        if any(kw in cause_lower for kw in ("ospf", "bgp", "邻居")):
            return {
                "commands": [
                    "show ip ospf neighbor",
                    "show ip bgp summary",
                ],
                "risk_level": "high",
                "description": root_cause,
            }

        # 默认：低风险只读操作
        return {
            "commands": [
                "show interface",
                "show version",
            ],
            "risk_level": "low",
            "description": root_cause,
        }