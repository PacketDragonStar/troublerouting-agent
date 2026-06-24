"""Solution Engineer Agent——LLM 驱动的方案工程师

基于诊断结果生成可执行的修复方案，包含具体设备、命令、风险评级。
"""

from typing import Any, Optional
from .llm_client import LLMClient


class SolutionEngineer:
    """方案工程师——LLM 分析 + 规则兜底"""

    def __init__(self):
        self.llm = LLMClient()

    def generate(
        self, root_cause: str, confidence: float, device: str
    ) -> dict[str, Any]:
        """生成修复方案"""
        # 尝试 LLM 生成
        llm_plan = self._llm_generate_plan(root_cause, confidence, device)
        if llm_plan:
            return llm_plan

        # 规则兜底
        return self._rules_fallback(root_cause, confidence, device)

    def _llm_generate_plan(
        self, root_cause: str, confidence: float, device: str
    ) -> Optional[dict[str, Any]]:
        """调用 LLM 生成具体修复方案"""
        import json
        from .safety_officer import SafetyOfficer
        blocked = ", ".join(SafetyOfficer.BLOCKED_COMMANDS)
        prompt = f"""你是网络排障专家。根据诊断结果生成修复方案。

### 诊断结果
- 根因: {root_cause}
- 置信度: {confidence:.0%}
- 目标设备: {device}

### 要求
1. 给出具体可执行的配置命令（精确到设备、接口、参数）
2. 如果涉及多台设备，列出每台设备上需要执行的命令
3. 给出风险评级（low/medium/high）
4. 如果命令有破坏性，必须警告
5. 禁止使用以下命令（会被安全规则拦截）：{blocked}

返回 JSON 格式:
{{"commands":["命令1","命令2"],"risk_level":"medium","description":"说明","warnings":[],"rollback":["回滚命令"]}}
只返回 JSON，不要其他内容。"""
        print("  [LLM] 正在调用 DeepSeek 生成修复方案...", flush=True)
        response = self.llm.analyze(prompt)
        if not response:
            return None
        try:
            # 提取 JSON
            cleaned = response.strip()
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0]
            elif "```" in cleaned:
                parts = cleaned.split("```")
                if len(parts) >= 3:
                    cleaned = parts[1]
            if "{" in cleaned:
                cleaned = cleaned[cleaned.index("{"):cleaned.rindex("}") + 1]
            return json.loads(cleaned.strip())
        except (json.JSONDecodeError, KeyError, IndexError, ValueError):
            return {
                "commands": [],
                "risk_level": "medium",
                "description": response[:500],
                "warnings": [],
                "rollback": [],
            }

    def _rules_fallback(
        self, root_cause: str, confidence: float, device: str
    ) -> dict[str, Any]:
        """规则引擎兜底"""
        cause_lower = root_cause.lower()

        if "重启" in cause_lower or "reload" in cause_lower:
            return {
                "commands": [f"[{device}] reload"],
                "risk_level": "high",
                "description": root_cause,
                "warnings": ["重启将中断所有业务"],
                "rollback": ["不可回滚"],
            }

        if "ospf" in cause_lower:
            return {
                "commands": [
                    f"[{device}] display ospf peer",
                    f"[{device}] display current-configuration configuration ospf",
                    "[分析] 检查 Hello/Dead 间隔、area 配置、认证设置",
                ],
                "risk_level": "high",
                "description": root_cause,
                "warnings": ["修改 OSPF 参数可能导致邻居重建"],
                "rollback": ["恢复原 OSPF 配置"],
            }

        if "bgp" in cause_lower:
            return {
                "commands": [
                    f"[{device}] display bgp peer",
                    "[分析] 检查 AS number、邻居 IP、认证",
                ],
                "risk_level": "high",
                "description": root_cause,
                "warnings": ["修改 BGP 配置可能导致路由中断"],
                "rollback": ["恢复原 BGP 配置"],
            }

        if "down" in cause_lower or "接口" in cause_lower:
            return {
                "commands": [
                    f"[{device}] display interface",
                    f"[{device}] undo shutdown  # 如果是管理性 shutdown",
                ],
                "risk_level": "medium",
                "description": root_cause,
                "warnings": ["确认对端设备状态正常再操作"],
                "rollback": ["shutdown"],
            }

        return {
            "commands": [
                f"[{device}] display diagnostic-information",
                "[分析] 请根据诊断结果进一步排查",
            ],
            "risk_level": "low",
            "description": root_cause,
            "warnings": [],
            "rollback": [],
        }