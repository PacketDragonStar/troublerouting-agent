"""Diagnostician Agent——诊断专家

综合分析症状数据，给出根因分析和置信度评分。
重规划：置信度 < 60% → 补充数据（最多 3 次）。
"""

import re
from dataclasses import dataclass, field
from typing import Any

from .cmdb import CMDB
from .device_adapter import DeviceInfo


@dataclass
class DiagnosisResult:
    """诊断结果"""
    root_cause: str
    confidence: float
    evidence: list[str] = field(default_factory=list)
    session_id: str = ""


class Diagnostician:
    """诊断专家——规则引擎 + 模式匹配"""

    max_replan_count: int = 3

    def __init__(self, cmdb: CMDB):
        self.cmdb = cmdb

    def diagnose(
        self,
        fault_summary: str,
        investigator_data: dict[str, list[dict[str, Any]]],
        session_id: str = "",
    ) -> DiagnosisResult:
        """分析数据输出根因"""
        evidence: list[str] = []

        for device_ip, results in investigator_data.items():
            # 设备不可达
            if results and results[0].get("unreachable"):
                record = self.cmdb.lookup(device_ip)
                name = record.hostname if record else device_ip
                return DiagnosisResult(
                    root_cause=f"设备 {name} ({device_ip}) 不可达——疑似宕机、链路中断",
                    confidence=0.90,
                    evidence=[f"设备 {device_ip} 连接超时"],
                    session_id=session_id,
                )

            # 分析每条命令输出
            for r in results:
                raw = r.get("raw_output", "")
                cmd = r.get("command", "").lower()
                if not isinstance(raw, str):
                    continue
                raw_lower = raw.lower()
                # combined: 命令名 + 输出，用于 OSPF/BGP 等命令名中包含关键词的场景
                combined = cmd + " " + raw_lower

                # CRC 错误
                if "crc" in raw_lower:
                    nums = re.findall(r"\d+", raw)
                    crc_count = int(nums[0]) if nums else 0
                    return DiagnosisResult(
                        root_cause=f"接口存在大量 CRC 错误（{crc_count}），疑似光模块老化或线缆故障",
                        confidence=0.85,
                        evidence=[f"{device_ip}: CRC 错误 {crc_count}"],
                        session_id=session_id,
                    )

                # BGP 检测（命令名或输出含 bgp + idle/active/notification）
                if "bgp" in combined and ("idle" in raw_lower or "active" in raw_lower or "notification" in raw_lower):
                    return DiagnosisResult(
                        root_cause="BGP Peer 未建立——可能原因：AS Number 错误、TCP 179 不通、邻居 IP 不可达",
                        confidence=0.78,
                        evidence=[f"{device_ip}: BGP Peer 异常"],
                        session_id=session_id,
                    )

                # OSPF 检测
                if "ospf" in combined and ("down" in raw_lower or "init" in raw_lower or "dead" in raw_lower):
                    return DiagnosisResult(
                        root_cause="OSPF 邻居状态异常——可能原因：Hello 参数不匹配、MTU 不一致、认证失败",
                        confidence=0.75,
                        evidence=[f"{device_ip}: OSPF 邻居异常"],
                        session_id=session_id,
                    )

                # 接口 Down 检测（多种模式）
                if ("current state : down" in raw_lower
                        or "line protocol is down" in raw_lower
                        or ("down" in raw_lower and "interface" in combined)):
                    return DiagnosisResult(
                        root_cause="接口状态为 DOWN——可能原因：对端故障、线缆断开、管理性 shutdown",
                        confidence=0.80,
                        evidence=[f"{device_ip}: 接口 DOWN"],
                        session_id=session_id,
                    )

        return DiagnosisResult(
            root_cause="未检测到已知故障模式，需补充数据排查",
            confidence=0.40,
            evidence=evidence,
            session_id=session_id,
        )

    def should_replan(self, confidence: float) -> bool:
        """置信度 < 60% 触发重规划"""
        return confidence < 0.60

    def generate_replan_commands(
        self, device: DeviceInfo, previous_diagnosis: str, iteration: int,
    ) -> list[str]:
        """生成补充命令"""
        if iteration > self.max_replan_count:
            return []
        vendor = device.vendor.lower()
        extra = {
            1: {"cisco": ["show interfaces counters errors", "show ip ospf neighbor"],
                "huawei": ["display interface counters error", "display ospf peer"]},
            2: {"cisco": ["show ip bgp summary", "show logging"],
                "huawei": ["display bgp peer", "display logbuffer"]},
            3: {"cisco": ["show tech-support"], "huawei": ["display diagnostic-information"]},
        }
        cmds = extra.get(iteration, {}).get(vendor, ["show version"])
        return cmds[:2]