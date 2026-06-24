"""AutoGen GroupChat 骨架 + 6 Agent 定义 + 真实编排器

Phase 2: 已接入 Dispatcher -> Investigator -> Diagnostician -> Solution -> Safety -> Reporter 全链路。
"""

import asyncio
import os
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
    name: str
    role: str
    description: str


def create_agents() -> list[Agent]:
    return [
        Agent(name="Dispatcher", role="调度员", description="接收故障报告，提取关键信息，Fast/Slow 分流"),
        Agent(name="Investigator", role="调查员", description="执行只读网络诊断命令，收集设备数据"),
        Agent(name="Diagnostician", role="诊断专家", description="综合分析症状数据，定位根因并给出置信度"),
        Agent(name="Solution", role="方案工程师", description="基于诊断结果生成修复方案和风险评级"),
        Agent(name="Safety", role="安全审计官", description="审核修复方案，拥有否决权"),
        Agent(name="Reporter", role="报告员", description="汇总全流程数据，输出标准化排障报告"),
    ]


async def run_troubleshooting(
    fault_description: str,
    fast_path: bool = False,
    cmdb: Optional[CMDB] = None,
) -> "TroubleshootingReport":
    from agent.pipeline import TroubleshootingReport

    session_id = f"session-{uuid.uuid4().hex[:12]}"
    if cmdb is None:
        cmdb = CMDB()

    whitelist = CommandWhitelist()
    agent_trace: list[dict[str, Any]] = []

    # 1. Dispatcher
    print("=" * 60)
    print("[1/6] Dispatcher     | 解析故障 + 分流")
    dispatcher = Dispatcher(cmdb)
    summary = dispatcher.dispatch(fault_description)
    print(f"      -> path={summary.path}, devices={summary.devices}")
    agent_trace.append({
        "agent": "Dispatcher", "role": "调度员",
        "response": f"path={summary.path}, devices={summary.devices}",
        "timestamp": datetime.now().isoformat(),
    })

    # 2. Investigator
    print("[2/6] Investigator   | SSH 采集设备数据（并行）")
    investigator = Investigator(whitelist=whitelist)
    devices = [d for d in summary.device_records]
    if not devices:
        devices = [
            record for record in [cmdb.lookup(ip) for ip in summary.devices]
            if record is not None
        ]
    if devices:
        collected = await investigator.collect_parallel(devices)
        investigator_summary = investigator.summarize(collected, session_id)
        cmd_total = sum(len(v) for v in collected.values())
        print(f"      -> {len(devices)}台设备，{cmd_total}条命令")
    else:
        collected = {}
        investigator_summary = "no devices found"
        print("      -> 未找到匹配设备")
    agent_trace.append({
        "agent": "Investigator", "role": "调查员",
        "response": investigator_summary[:200],
        "timestamp": datetime.now().isoformat(),
    })

    # 3. Diagnostician
    print("[3/6] Diagnostician  | LLM 分析 CLI 输出")
    diagnostician = Diagnostician(cmdb=cmdb)
    diagnosis = diagnostician.diagnose(
        fault_summary=fault_description,
        investigator_data=collected,
        session_id=session_id,
    )
    print(f"      -> 根因: {diagnosis.root_cause[:80]}")
    print(f"      -> 置信度: {diagnosis.confidence:.0%}")
    agent_trace.append({
        "agent": "Diagnostician", "role": "诊断专家",
        "response": f"{diagnosis.root_cause[:100]} (confidence={diagnosis.confidence:.0%})",
        "timestamp": datetime.now().isoformat(),
    })

    # 4. Solution Engineer
    print("[4/6] Solution       | 生成修复方案")
    engineer = SolutionEngineer()
    target_device = summary.device_records[0].hostname if summary.device_records else "unknown"
    plan = engineer.generate(diagnosis.root_cause, diagnosis.confidence, target_device)
    cmds = plan.get("commands", [])
    print(f"      -> risk={plan.get('risk_level', '?')}, 方案命令数={len(cmds)}")
    for i, cmd in enumerate(cmds[:5]):
        print(f"         {i+1}. {cmd}")
    agent_trace.append({
        "agent": "Solution", "role": "方案工程师",
        "response": f"risk={plan.get('risk_level', 'unknown')}, commands={len(cmds)}",
        "timestamp": datetime.now().isoformat(),
    })

    # 5. Safety Officer
    print("[5/6] Safety         | 安全审核修复方案")
    officer = SafetyOfficer()
    review = officer.review(plan.get("commands", []), plan.get("risk_level", "low"), target_device)
    status = "通过" if review.get("approved") else "拒绝"
    print(f"      -> 审核结果: {status}")
    agent_trace.append({
        "agent": "Safety", "role": "安全审计官",
        "response": f"approved={review.get('approved', False)}",
        "timestamp": datetime.now().isoformat(),
    })

    # 6. Reporter + webhook
    print("[6/6] Reporter       | 生成并保存报告")
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

    webhook_sent = "WEBHOOK_URL not set"
    if os.getenv("WEBHOOK_URL"):
        from agent.webhook import WebhookClient
        client = WebhookClient()
        result = client.send({
            "session_id": report.session_id,
            "fault_description": report.fault_description,
            "root_cause": report.root_cause,
            "confidence": report.confidence,
            "risk_level": report.risk_level,
            "solution": report.solution,
            "created_at": report.created_at,
        })
        webhook_sent = f"webhook sent: {result.get('status_code', 0)}"

    agent_trace.append({
        "agent": "Reporter", "role": "报告员",
        "response": f"report_{session_id}.md saved, {webhook_sent}",
        "timestamp": datetime.now().isoformat(),
    })

    return report