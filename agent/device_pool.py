"""AsyncDevicePool——异步设备连接池

大规模网络扩展时，通过连接池管理多设备并发连接。
"""
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator, Optional

from .device_adapter import CommandResult, DeviceAdapter, DeviceInfo


@dataclass
class PoolConfig:
    """连接池配置"""
    max_connections: int = 10
    connection_timeout: float = 5.0
    command_timeout: float = 15.0


class AsyncDevicePool(ABC):
    """异步设备连接池抽象基类

    管理多台网络设备的并发连接，支持异步上下文管理器。
    大规模网络时通过连接池复用连接，避免重复 SSH 握手。
    """

    def __init__(self, config: Optional[PoolConfig] = None):
        self.config = config or PoolConfig()

    @abstractmethod
    async def connect(self, device: DeviceInfo) -> None:
        """建立到设备的连接"""
        ...

    @abstractmethod
    async def disconnect(self, device: DeviceInfo) -> None:
        """断开设备连接"""
        ...

    @abstractmethod
    async def execute(
        self, device: DeviceInfo, command: str,
        adapter: DeviceAdapter
    ) -> CommandResult:
        """通过指定适配器执行命令"""
        ...

    @abstractmethod
    async def execute_parallel(
        self,
        devices: list[DeviceInfo],
        commands: dict[str, list[str]],  # device_ip -> [commands]
        adapter: DeviceAdapter,
    ) -> dict[str, list[CommandResult]]:
        """并行向多台设备执行多条命令"""
        ...

    async def __aenter__(self) -> "AsyncDevicePool":
        return self

    async def __aexit__(self, *args) -> None:
        pass