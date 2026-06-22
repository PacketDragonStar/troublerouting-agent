"""CMDB——配置管理数据库（Demo 用 SQLite 模拟）

存储网络设备信息：IP、主机名、厂商、角色。
分流规则引擎依据设备角色决定 Fast/Slow Path。
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class DeviceRecord:
    """CMDB 设备记录"""
    ip: str
    hostname: str
    vendor: str  # "cisco", "huawei", "juniper"
    role: str    # "core", "distribution", "access", "ap"


class CMDB:
    """简易 CMDB（Demo 阶段用内存字典，Phase 2 切 SQLite）"""

    def __init__(self):
        self._devices: dict[str, DeviceRecord] = {}

    def add_device(self, ip: str, hostname: str, vendor: str, role: str) -> None:
        """添加设备到 CMDB"""
        self._devices[ip] = DeviceRecord(
            ip=ip, hostname=hostname, vendor=vendor, role=role
        )

    def lookup(self, ip: str) -> Optional[DeviceRecord]:
        """按 IP 查询设备信息"""
        return self._devices.get(ip)

    def lookup_by_hostname(self, hostname: str) -> Optional[DeviceRecord]:
        """按主机名查询设备信息"""
        for device in self._devices.values():
            if device.hostname == hostname:
                return device
        return None