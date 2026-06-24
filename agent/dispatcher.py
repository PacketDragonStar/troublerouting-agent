"""Dispatcher Agent——故障调度员

接收自然语言故障报告，提取关键信息（设备IP、故障现象），
查询 CMDB 获取设备角色，依据规则引擎分流到 Fast/Slow Path。

分流规则（规则引擎，非 LLM）：
- 包含 core 设备 → Slow Path
- 未知设备 → Slow Path（保守策略）
- 纯 access/ap 设备 → Fast Path
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from .cmdb import CMDB, DeviceRecord


@dataclass
class FaultSummary:
    """故障摘要"""
    raw_text: str
    devices: list[str] = field(default_factory=list)
    device_records: list[DeviceRecord] = field(default_factory=list)
    path: str = "slow"


IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


class Dispatcher:
    """故障调度员"""

    def __init__(self, cmdb: CMDB):
        self.cmdb = cmdb

    def dispatch(self, raw_text: str) -> FaultSummary:
        """解析故障报告，生成故障摘要和分流决策"""
        summary = FaultSummary(raw_text=raw_text)

        # 1. 正则提取完整 IP 地址
        ips = IP_PATTERN.findall(raw_text)
        valid_ips = [ip for ip in ips if self._is_valid_ip(ip)]

        # 2. 智能补全短 IP（如 192.168.41.12,14,16 → 3 个 IP）
        expanded_ips = self._expand_short_ips(raw_text, valid_ips)
        summary.devices = expanded_ips

        # 3. 查询 CMDB
        for ip in expanded_ips:
            record = self.cmdb.lookup(ip)
            if record:
                summary.device_records.append(record)

        # 4. 分流决策
        summary.path = self._decide_path(summary.device_records)
        return summary

    # ---- private ----

    def _decide_path(self, records: list[DeviceRecord]) -> str:
        if not records:
            return "slow"
        for record in records:
            if record.role == "core":
                return "slow"
        return "fast"

    @staticmethod
    def _expand_short_ips(raw_text: str, existing_ips: list[str]) -> list[str]:
        """将 192.168.41.12,14,16 展开为完整 IP 列表"""
        m = re.search(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.)(\d{1,3}(?:,\d{1,3})+)", raw_text)
        if m:
            prefix = m.group(1)
            suffixes = m.group(2).split(",")
            expanded = [f"{prefix}{s.strip()}" for s in suffixes]
            result = []
            seen = set()
            for ip in existing_ips + expanded:
                if ip not in seen:
                    result.append(ip)
                    seen.add(ip)
            return result
        return existing_ips

    @staticmethod
    def _is_valid_ip(ip: str) -> bool:
        parts = ip.split(".")
        if len(parts) != 4:
            return False
        try:
            return all(0 <= int(p) <= 255 for p in parts)
        except ValueError:
            return False