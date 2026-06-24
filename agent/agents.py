"""AutoGen GroupChat 骨架 + 6 Agent 定义 + 真实编排器

Phase 2: 已接入 Dispatcher → Investigator → Diagnostician → Solution → Safety → Reporter 全链路。
"""

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from .cmdb import CMDB
from .dispatcher import Dispatcher
from .investigator import Investigator
from .diagnostician import Diagnostician
from .solution_engineer import SolutionEngineer
from .safety_officer import SafetyOfficer
from .reporter import Reporter
from mcp.command_whitelist import CommandWhitelist


@dataclass
class Agent:
    """Agent 定义"""
    name: str
    role: str
    description: str


def create_agents() -> list[Agent]:
    """创建 6 个 Agent 并返回列表"""
    return [
        Agent(name="Dispatcher", role="调度员", description="接收故障报告，提取关键信息，Fast/Slow 分流"),
        Agent(name="Investigator", role="调查员", description="执行只读网络诊断命令，收集设备数据"),
        Agent(name="Diagnostician", role="诊断专家", description="综合分析症状数据，定位根因并给出置信度"),
        Agent(name="Solution", role="方案工程师", description="基于诊断结果生成修复方案和风险评级"),
        Agent(name="Safety", role="安全审计官", description="审核修复方案，拥有否决权"),
        Agent(name="Reporter", role="报告员", description="汇总全流程数据，输出标准化排障报告"),
    ]


# ---- 真实编排器 ----

async def run_troubleshooting(
    fault_description: str,
    fast_path: bool = False,
    cmdb: Optional[CMDB] = None,
) -> "TroubleshootingReport":
    """执行一次完整排障流程（接入真实组件链）

    Dispatcher(分流) → Investigator(采集) → Diagnostician(诊断)
    → Solution(方案) → Safety(审核) → Reporter(报告)
    """
    from agent.pipeline import TroubleshootingReport

    session_id = f"session-{uuid.uuid4().hex[:12]}"
    if cmdb is None:
        cmdb = CMDB()

    whitelist = CommandWhitelist()
    agent_trace: list[dict[str, Any]] = []

    # ---- 1. Dispatcher：解析故障 + 分流 ----
    dispatcher = Dispatcher(cmdb)
    summary = dispatcher.dispatch(fault_description)
    agent_trace.append({
        "agent": "Dispatcher", "role": "调度员",
        "response": f"路径={summary.path}, 设备={summary.devices}",
        "timestamp": datetime.now().isoformat(),
    })

    # ---- 2. Investigator：并行采集数据 ----
    investigator = Investigator(whitelist=whitelist)
    devices = [d for d in summary.device_records]
    if not devices:
        # 回退：从 CMDB 全量查找
        devices = [
            record for record in [cmdb.lookup(ip) for ip in summary.devices]
            if record is not None
        ]
    if devices:
        collected = await investigator.collect_parallel(devices)
        investigator_summary = investigator.summarize(collected, session_id)
    else:
        collected = {}
        investigator_summary = "未找到匹配设备，无法采集数据"
    agent_trace.append({
        "agent": "Investigator", "role": "调查员",
        "response": investigator_summary[:200],
        "timestamp": datetime.now().isoformat(),
    })

    # ---- 3. Diagnostician：诊断 ----
    diagnostician = Diagnostician(cmdb=cmdb)
    diagnosis = diagnostician.diagnose(
        fault_summary=fault_description,
        investigator_data=collected,
        session_id=session_id,
    )
    agent_trace.append({
        "agent": "Diagnostician", "role": "诊断专家",
        "response": f"根因={diagnosis.root_cause[:100]}, 置信度={diagnosis.confidence:.0%}",
        "timestamp": datetime.now().isoformat(),
    })

    # ---- 4. Solution Engineer：生成修复方案 ----
    engineer = SolutionEngineer()
    target_device = summary.device_records[0].hostname if summary.device_records else "unknown"
    plan = engineer.generate(diagnosis.root_cause, diagnosis.confidence, target_device)
    agent_trace.append({
        "agent": "Solution", "role": "方案工程师",
        "response": f"风险={plan.get('risk_level', 'unknown')}, 命令数={len(plan.get('commands', []))}",
        "timestamp": datetime.now().isoformat(),
    })

    # ---- 5. Safety Officer：安全审核 ----
    officer = SafetyOfficer()
    review = officer.review(plan.get("commands", []), plan.get("risk_level", "low"), target_device)
    agent_trace.append({
        "agent": "Safety", "role": "安全审计官",
        "response": f"审核结果={'通过' if review.get('approved') else '拒绝'}",
        "timestamp": datetime.now().isoformat(),
    })

    # ---- 6. Reporter：生成报告 ----
    reporter = Reporter()
    report = TroubleshootingReport(
        session_id=session_id,
        fault_description=fault_description,
        root_cause=diagnosis.root_cause,
        confidence=diagnosis.confidence,
        risk_level=plan.get("risk_level", "low"),
        solution=", ".join(plan.get("commands", [])),
        agent_trace=agent_trace,
    )
    reporter.save_report(report)
    reporter.save_case_draft(report)

    agent_trace.append({
        "agent": "Reporter", "role": "报告员",
        "response": f"report_{session_id}.md + case_{session_id}.json saved",
        "timestamp": datetime.now().isoformat(),
    })

    return report