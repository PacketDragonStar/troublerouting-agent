"""LLM 降级 + 故障恢复

- 指数退避重试（5s → 10s → 放弃）
- 模型降级链（GPT-4o → GPT-4o-mini → local）
- 全部不可用 → 生成半成品报告
"""

import time
from datetime import datetime
from typing import Optional


def retry_with_backoff(
    max_retries: int = 2,
    base_delay: float = 5.0,
    backoff_factor: float = 2.0,
) -> list[float]:
    """计算指数退避延迟序列

    Returns:
        每次重试的等待时间（秒）
    """
    return [base_delay * (backoff_factor ** i) for i in range(max_retries + 1)]


class LLMFallbackHandler:
    """LLM 降级处理器

    Demo 阶段仅管理模型降级状态，不实际调用 LLM。
    后续 Ticket 接入真实 API 调用时注入此 handler。
    """

    max_retries: int = 2

    model_chain: list[str] = [
        "gpt-4o",
        "gpt-4o-mini",
        "local",
    ]

    def __init__(self):
        self._current_index = 0

    @property
    def current_model(self) -> str:
        """当前使用的模型"""
        return self.model_chain[self._current_index]

    def fallback(self) -> Optional[str]:
        """降级到下一个模型

        Returns:
            降级后的模型名，如果已是最低级返回 None
        """
        if self._current_index < len(self.model_chain) - 1:
            self._current_index += 1
            return self.current_model
        return None

    def reset(self) -> None:
        """重置到初始模型"""
        self._current_index = 0


def generate_degraded_report(
    fault_description: str,
    collected_data_summary: str = "",
    dispatcher_summary: str = "",
) -> str:
    """生成降级半成品报告（所有 LLM 不可用时）

    Args:
        fault_description: 原始故障描述
        collected_data_summary: 已采集的数据摘要
        dispatcher_summary: Dispatcher 的分析

    Returns:
        Markdown 格式的半成品报告
    """
    lines = [
        "# ⚠️ 降级报告——Agent 推理中断",
        "",
        f"**时间:** {datetime.now().isoformat()}",
        "",
        "## 故障描述",
        "",
        fault_description or "(无)",
        "",
        "## 调度分析",
        "",
        dispatcher_summary or "(未完成)",
        "",
        "## 已采集数据",
        "",
        collected_data_summary or "(未采集到数据)",
        "",
        "---",
        "",
        "**状态:** 所有 LLM 服务不可用，推理流程已中断。",
        "已采集的原始数据和调度分析已保存在数据库中，请人工排查。",
        "LLM 恢复后将自动从中断点继续处理。",
    ]
    return "\n".join(lines)