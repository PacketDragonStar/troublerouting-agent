"""Diagnostician Agent——LLM 驱动的诊断专家

Phase 2: 将 Investigator 采集的 CLI 输出通过 LLM 分析，给出根因和置信度。
规则引擎仅作为 LLM 不可用时的降级兜底。
"""

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from .cmdb import CMDB
from .device_adapter import DeviceInfo
from .llm_client import LLMClient


@dataclass
class DiagnosisResult:
    root_cause: str
    confidence: float
    evidence: list[str] = field(default_factory=list)
    session_id: str = ""


class Diagnostician:
    """诊断专家——LLM 分析 + 规则引擎兜底"""

    max_replan_count: int = 3

    def __init__(self, cmdb: CMDB):
        self.cmdb = cmdb
        self.llm = LLMClient()

    def diagnose(
        self,
        fault_summary: str,
        investigator_data: dict[str, list[dict[str, Any]]],
        session_id: str = "",
    ) -> DiagnosisResult:
        """分析数据输出根因——优先 LLM，失败时规则引擎兜底"""
        evidence: list[str] = []

        # 设备不可达优先检测
        for device_ip, results in investigator_data.items():
            if results and results[0].get("unreachable"):
                record = self.cmdb.lookup(device_ip)
                name = record.hostname if record else device_ip
                return DiagnosisResult(
                    root_cause=f"设备 {name} ({device_ip}) 不可达——疑似宕机、链路中断",
                    confidence=0.90,
                    evidence=[f"设备 {device_ip} 连接超时"],
                    session_id=session_id,
                )

        # ---- LLM 驱动的深度分析 ----
        llm_result = self._llm_analyze(fault_summary, investigator_data)
        if llm_result:
            return DiagnosisResult(
                root_cause=llm_result["root_cause"],
                confidence=llm_result.get("confidence", 0.70),
                evidence=llm_result.get("evidence", evidence),
                session_id=session_id,
            )

        # ---- 规则引擎兜底 ----
        return self._rules_fallback(fault_summary, investigator_data, evidence, session_id)

    def _llm_analyze(
        self, fault_summary: str, investigator_data: dict[str, list[dict[str, Any]]],
    ) -> Optional[dict[str, Any]]:
        """将采集数据发送给 LLM 分析"""
        # 构造 prompt：设备 + 命令 + 输出
        data_blocks = []
        for device_ip, results in investigator_data.items():
            record = self.cmdb.lookup(device_ip)
            hostname = record.hostname if record else device_ip
            for r in results:
                cmd = r.get("command", "")
                raw = r.get("raw_output", "")
                if not raw:
                    continue
                data_blocks.append(
                    f"设备: {hostname} ({device_ip})\n命令: {cmd}\n输出:\n{raw[:3000]}\n"
                )

        if not data_blocks:
            return None

        prompt_parts = [
            "你是网络排障专家。根据设备CLI输出分析故障原因。",
            "",
            f"### 故障描述\n{fault_summary}",
            "",
            "### 设备采集数据",
        ] + data_blocks + [
            "",
            "### 分析要求",
            "1. 根据采集数据判断根本原因，不要泛泛而谈",
            "2. 引用具体设备名/IP和命令输出中的关键信息",
            "3. 给出0.0到1.0之间的置信度",
            "4. 如果数据不足以判断，根据证据给出最可能的结论",
            "",
            '返回 JSON 格式: {"root_cause":"...","confidence":0.xx,"evidence":["..."]}',
        ]
        prompt = "\n".join(prompt_parts)

        print("  [LLM] 正在调用 DeepSeek 分析 CLI 输出...", flush=True)
        response = self.llm.analyze(prompt)
        if not response:
            print("  [LLM] 分析失败，回退规则引擎", flush=True)
            return None

        # 解析 JSON 响应
        try:
            # 提取 JSON 块
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            result = json.loads(response.strip())
            print(f"  [LLM] 分析完成: {result.get('root_cause', '')[:80]}...", flush=True)
            return result
        except (json.JSONDecodeError, KeyError, IndexError):
            print(f"  [LLM] JSON 解析失败，使用原始回复", flush=True)
            return {
                "root_cause": response[:500],
                "confidence": 0.60,
                "evidence": [],
            }

    def _rules_fallback(
        self,
        fault_summary: str,
        investigator_data: dict[str, list[dict[str, Any]]],
        evidence: list[str],
        session_id: str,
    ) -> DiagnosisResult:
        """规则引擎兜底——当 LLM 不可用时的备选方案"""
        import re
        for device_ip, results in investigator_data.items():
            for r in results:
                raw = r.get("raw_output", "")
                cmd = r.get("command", "").lower()
                if not isinstance(raw, str) or not raw:
                    continue
                raw_lower = raw.lower()
                combined = cmd + " " + raw_lower

                # CRC > 0
                if "crc" in raw_lower:
                    nums = re.findall(r"\d+", raw)
                    count = int(nums[0]) if nums else 0
                    if count > 0:
                        return DiagnosisResult(
                            root_cause=f"接口存在 {count} 次 CRC 错误——疑似物理链路问题",
                            confidence=0.85,
                            evidence=[f"{device_ip}: CRC={count}"],
                            session_id=session_id,
                        )

                # OSPF not configured
                if "ospf" in combined and "not configured" in raw_lower:
                    return DiagnosisResult(
                        root_cause=f"设备 {device_ip} OSPF 进程未启用——display ospf peer 返回 'OSPF is not configured'",
                        confidence=0.95,
                        evidence=[f"{device_ip}: OSPF 未配置"],
                        session_id=session_id,
                    )

                # OSPF down
                if "ospf" in combined and ("down" in raw_lower or "init" in raw_lower):
                    return DiagnosisResult(
                        root_cause="OSPF 邻居状态异常——请检查 peer 状态、Hello/Dead 间隔、area 配置",
                        confidence=0.70,
                        evidence=[f"{device_ip}: OSPF peer 异常"],
                        session_id=session_id,
                    )

                # BGP
                if "bgp" in combined and ("idle" in raw_lower or "active" in raw_lower):
                    return DiagnosisResult(
                        root_cause="BGP Peer 未建立——检查 AS number、TCP 连通性",
                        confidence=0.78,
                        evidence=[f"{device_ip}: BGP peer 异常"],
                        session_id=session_id,
                    )

                # Interface down
                if "current state : down" in raw_lower or "line protocol is down" in raw_lower:
                    return DiagnosisResult(
                        root_cause=f"设备 {device_ip} 接口状态为 DOWN",
                        confidence=0.80,
                        evidence=[f"{device_ip}: 接口 DOWN"],
                        session_id=session_id,
                    )

        # 从故障描述关键词推断
        fl = fault_summary.lower()
        if "ospf" in fl:
            return DiagnosisResult(
                root_cause="OSPF 相关故障——请检查 display ospf peer 输出确认具体状态",
                confidence=0.65,
                evidence=evidence,
                session_id=session_id,
            )
        if "bgp" in fl:
            return DiagnosisResult(
                root_cause="BGP 相关故障——请检查 display bgp peer 输出确认具体状态",
                confidence=0.65,
                evidence=evidence,
                session_id=session_id,
            )
        return DiagnosisResult(
            root_cause="根据已有数据无法确定根因，建议补充诊断命令",
            confidence=0.40,
            evidence=evidence,
            session_id=session_id,
        )

    def should_replan(self, confidence: float) -> bool:
        return confidence < 0.60

    def generate_replan_commands(
        self, device: DeviceInfo, previous_diagnosis: str, iteration: int,
    ) -> list[str]:
        if iteration > self.max_replan_count:
            return []
        vendor = device.vendor.lower()
        extra = {
            1: {"cisco": ["show ip ospf neighbor", "show ip interface brief"],
                "huawei": ["display ospf peer", "display ip interface brief"],
                "h3c": ["display ospf peer", "display ip interface brief"]},
            2: {"cisco": ["show ip bgp summary", "show logging"],
                "huawei": ["display bgp peer", "display logbuffer"],
                "h3c": ["display bgp peer", "display logbuffer"]},
            3: {"cisco": ["show tech-support"], "huawei": ["display diagnostic-information"]},
        }
        cmds = extra.get(iteration, {}).get(vendor, ["show version"])
        return cmds[:2]