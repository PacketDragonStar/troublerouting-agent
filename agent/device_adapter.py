"""DeviceAdapter 抽象基类——多厂商设备适配器"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CommandResult:
    """命令执行结果"""
    command: str
    raw_output: str
    parsed_output: dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: str = ""


@dataclass
class DeviceInfo:
    """设备信息"""
    hostname: str
    ip: str
    vendor: str  # "cisco", "huawei", "juniper"
    role: str     # "core", "distribution", "access"
    model: str = ""


class DeviceAdapter(ABC):
    """多厂商设备适配器抽象基类

    每种厂商实现一个子类（CiscoAdapter、HuaweiAdapter、JuniperAdapter），
    提供厂商特定的命令模板和解析逻辑。
    新增厂商无需修改 Agent 核心代码，只需添加适配器子类。
    """

    @abstractmethod
    async def execute_readonly_command(
        self, device: DeviceInfo, command: str
    ) -> CommandResult:
        """执行只读命令并返回结构化结果"""
        ...

    @abstractmethod
    def get_device_info(self, hostname_or_ip: str) -> DeviceInfo:
        """获取设备信息"""
        ...