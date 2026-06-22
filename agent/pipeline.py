"""TroubleshootingPipeline——排障流程引擎（Strategy 模式）

所有排障流程封装为引擎无关的抽象基类。
Phase 1 用 AutoGenPipeline 实现，Phase 2 切换 DeepAgents 时注入 DeepAgentsPipeline，
Agent 核心代码无需修改。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class TroubleshootingReport:
    """排障报告"""
    session_id: str
    fault_description: str
    root_cause: str = ""
    confidence: float = 0.0
    risk_level: str = ""  # "low" | "medium" | "high"
    solution: str = ""
    agent_trace: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class TroubleshootingPipeline(ABC):
    """排障流程引擎抽象基类

    Strategy 模式：子类决定使用 AutoGen、DeepAgents 还是其他框架，
    外部调用者只依赖此抽象接口。
    """

    @abstractmethod
    async def run(self, fault_description: str) -> TroubleshootingReport:
        """执行一次完整的排障流程

        Args:
            fault_description: 自然语言故障描述

        Returns:
            TroubleshootingReport: 包含根因、置信度、方案、全链路的报告
        """
        ...