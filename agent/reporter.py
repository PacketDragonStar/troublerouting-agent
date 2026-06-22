"""Reporter Agent——报告员

汇总全流程数据，生成标准化排障报告（Markdown）和案例草稿（JSON）。
案例草稿默认 confirmed=false，等待人工复盘确认后入库。
"""

import json
import os
from datetime import datetime
from typing import Any

from .pipeline import TroubleshootingReport


class Reporter:
    """报告员 Agent——生成报告和案例草稿"""

    def __init__(self, output_dir: str = "reports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    RISK_LABELS = {"low": "低", "medium": "中", "high": "高"}

    def generate_markdown(self, report: TroubleshootingReport) -> str:
        """生成 Markdown 报告内容"""
        confidence_pct = f"{report.confidence * 100:.0f}%"
        risk_label = self.RISK_LABELS.get(report.risk_level, report.risk_level)

        lines = [
            f"# 网络故障处理报告",
            "",
            f"**Session ID:** {report.session_id}",
            f"**时间:** {report.created_at}",
            "",
            "## 故障描述",
            "",
            report.fault_description,
            "",
            "## 诊断结论",
            "",
            f"- **根因:** {report.root_cause}",
            f"- **置信度:** {confidence_pct}",
            f"- **风险等级:** {risk_label}",
            "",
            "## 修复方案",
            "",
            report.solution,
            "",
            "## Agent 执行链路",
            "",
        ]

        for i, step in enumerate(report.agent_trace, 1):
            lines.append(f"{i}. **{step['agent']}** ({step['role']}) — {step['timestamp']}")

        lines.extend([
            "",
            "---",
            f"*报告由 Reporter Agent 自动生成*",
        ])
        return "\n".join(lines)

    def generate_case_draft(self, report: TroubleshootingReport) -> dict[str, Any]:
        """生成案例草稿 JSON（confirmed=false）"""
        return {
            "session_id": report.session_id,
            "symptom": report.fault_description,
            "root_cause": report.root_cause,
            "confidence": report.confidence,
            "risk_level": report.risk_level,
            "solution": report.solution,
            "agent_trace": report.agent_trace,
            "created_at": report.created_at,
            "confirmed": False,
        }

    def save_report(self, report: TroubleshootingReport) -> str:
        """保存 Markdown 报告到文件"""
        content = self.generate_markdown(report)
        filename = f"report_{report.session_id}.md"
        path = os.path.join(self.output_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def save_case_draft(self, report: TroubleshootingReport) -> str:
        """保存案例草稿 JSON 到文件"""
        draft = self.generate_case_draft(report)
        filename = f"case_{report.session_id}.json"
        path = os.path.join(self.output_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(draft, f, ensure_ascii=False, indent=2)
        return path