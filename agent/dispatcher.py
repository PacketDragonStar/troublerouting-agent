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
    devices: list[str] = field(default_factory=list)  # 提取到的 IP 列表
    device_records: list[DeviceRecord] = field(default_factory=list)
    path: str = "slow"  # "fast" 或 "slow"


# 正则：匹配 IPv4 地址
IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


class Dispatcher:
    """故障调度员"""

    def __init__(self, cmdb: CMDB):
        self.cmdb = cmdb

    def dispatch(self, raw_text: str) -> FaultSummary:
        """解析故障报告，生成故障摘要和分流决策

        Args:
            raw_text: 自然语言故障描述

        Returns:
            FaultSummary: 包含设备列表、CMDB 记录、分流路径
        """
        summary = FaultSummary(raw_text=raw_text)

        # 1. 提取 IP 地址
        ips = IP_PATTERN.findall(raw_text)
        # 过滤无效 IP（如 0.0.0.0、999.999.999.999）
        valid_ips = [ip for ip in ips if self._is_valid_ip(ip)]
        summary.devices = valid_ips

        # 2. 查询 CMDB
        for ip in valid_ips:
            record = self.cmdb.lookup(ip)
            if record:
                summary.device_records.append(record)

        # 3. 分流决策（规则引擎）
        summary.path = self._decide_path(summary.device_records)

        return summary

    def _decide_path(self, records: list[DeviceRecord]) -> str:
        """规则引擎：依据设备角色决定路径

        - 任何 core 设备 → slow
        - 没有查到 CMDB 记录 → slow（保守）
        - 全是 access/ap → fast
        """
        if not records:
            # 没有 CMDB 记录：未知设备，保守走 Slow Path
            return "slow"

        for record in records:
            if record.role == "core":
                return "slow"

        # 所有设备都是 access 或 ap
        return "fast"

    @staticmethod
    def _is_valid_ip(ip: str) -> bool:
        """校验 IP 地址合法性"""
        parts = ip.split(".")
        if len(parts) != 4:
            return False
        try:
            return all(0 <= int(p) <= 255 for p in parts)
        except ValueError:
            return False