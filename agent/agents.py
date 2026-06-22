"""AutoGen GroupChat 骨架 + 6 Agent 注册 + 确定性编排

Demo 阶段不依赖真实 AutoGen LLM 调用，使用简化版确定性编排器。
后续 Ticket 逐步接入真实 AutoGen GroupChat 和 LLM。
"""

import uuid
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any


# ---- 简化版 Agent 定义（不依赖 AutoGen） ----

@dataclass
class Agent:
    """Agent 空壳——Demo 阶段只 echo 角色名"""
    name: str
    role: str
    description: str

    def respond(self, message: str) -> str:
        """Agent 响应——Ticket 2 阶段只 echo 角色"""
        return f"[{self.name}] 收到消息: {message[:50]}... | 角色: {self.role}"


# ---- Agent 工厂 ----

def create_agents() -> list[Agent]:
    """创建 6 个 Agent 并返回列表"""
    return [
        Agent(
            name="Dispatcher",
            role="调度员",
            description="接收故障报告，提取关键信息，分流到 Fast/Slow Path",
        ),
        Agent(
            name="Investigator",
            role="调查员",
            description="执行只读网络诊断命令，收集设备数据",
        ),
        Agent(
            name="Diagnostician",
            role="诊断专家",
            description="综合分析症状数据，定位根因并给出置信度",
        ),
        Agent(
            name="Solution",
            role="方案工程师",
            description="基于诊断结果生成修复方案和风险评级",
        ),
        Agent(
            name="Safety",
            role="安全审计官",
            description="审核修复方案，拥有否决权",
        ),
        Agent(
            name="Reporter",
            role="报告员",
            description="汇总全流程数据，输出标准化排障报告",
        ),
    ]


# ---- 确定性编排器 ----

async def run_troubleshooting(
    fault_description: str,
    fast_path: bool = False,
) -> "TroubleshootingReport":
    """执行一次排障流程

    Args:
        fault_description: 自然语言故障描述
        fast_path: True=Fast Path（2 Agent），False=Slow Path（6 Agent）

    Returns:
        TroubleshootingReport: 包含根因、置信度、全链路的报告
    """
    # 延迟导入避免循环依赖
    from agent.pipeline import TroubleshootingReport

    session_id = f"session-{uuid.uuid4().hex[:12]}"
    agents = create_agents()
    agent_trace: list[dict[str, Any]] = []

    if fast_path:
        # Fast Path: 只需要 2 个 Agent
        active_order = ["Dispatcher", "Investigator", "Diagnostician"]
    else:
        # Slow Path: 全部 6 个 Agent 按顺序发言
        active_order = [
            "Dispatcher",
            "Investigator",
            "Diagnostician",
            "Solution",
            "Safety",
            "Reporter",
        ]

    current_message = fault_description
    for name in active_order:
        agent = next(a for a in agents if a.name == name)
        response = agent.respond(current_message)
        agent_trace.append({
            "agent": agent.name,
            "role": agent.role,
            "response": response,
            "timestamp": datetime.now().isoformat(),
        })
        current_message = response  # 传递给下一个 Agent

    # 生成报告
    last_agent_name = agent_trace[-1]["agent"] if agent_trace else "Unknown"
    report = TroubleshootingReport(
        session_id=session_id,
        fault_description=fault_description,
        root_cause=f"Demo 阶段: {last_agent_name} 完成处理",
        confidence=1.0 if fast_path else 0.95,
        risk_level="low",
        solution="Demo 阶段：无实际操作",
        agent_trace=agent_trace,
    )
    return report