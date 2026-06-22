"""Investigator Agent——网络调查员

唯一有权访问网络设备执行只读命令的 Agent。
职责：并行数据收集、超时控制、摘要义务。
"""

import asyncio
from dataclasses import dataclass
from typing import Any

from .device_adapter import DeviceInfo


# ---- 厂商命令模板 ----

COMMAND_TEMPLATES: dict[str, list[str]] = {
    "cisco": [
        "show interface",
        "show version",
        "show processes cpu",
        "show memory",
        "show logging",
    ],
    "huawei": [
        "display interface",
        "display version",
        "display cpu-usage",
        "display memory-usage",
        "display logbuffer",
    ],
    "juniper": [
        "show interfaces terse",
        "show version",
        "show system processes",
        "show system memory",
        "show log messages",
    ],
}


@dataclass
class TimeoutConfig:
    """超时配置"""
    connect_timeout: float
    command_timeout: float

    @classmethod
    def fast_path(cls) -> "TimeoutConfig":
        return cls(connect_timeout=2.0, command_timeout=5.0)

    @classmethod
    def slow_path(cls) -> "TimeoutConfig":
        return cls(connect_timeout=5.0, command_timeout=15.0)


class Investigator:
    """网络调查员 Agent——并行执行诊断命令、收集设备数据"""

    def __init__(self, whitelist):
        self.whitelist = whitelist

    def build_command_list(self, device: DeviceInfo) -> list[str]:
        """根据设备厂商生成命令列表"""
        vendor = device.vendor.lower()
        return COMMAND_TEMPLATES.get(vendor, COMMAND_TEMPLATES["cisco"])

    async def collect_parallel(
        self,
        devices: list[DeviceInfo],
        timeout_connect: float = 5.0,
        timeout_command: float = 15.0,
    ) -> dict[str, list[dict[str, Any]]]:
        """并行向多台设备收集数据"""
        tasks = []
        for device in devices:
            commands = self.build_command_list(device)
            task = self._collect_from_device(
                device, commands, timeout_command
            )
            tasks.append(task)

        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        output: dict[str, list[dict[str, Any]]] = {}
        for device, results in zip(devices, results_list):
            if isinstance(results, Exception):
                output[device.ip] = [{
                    "device": device.ip,
                    "command": "ALL",
                    "raw_output": "",
                    "success": False,
                    "error": str(results),
                    "unreachable": True,
                }]
            else:
                output[device.ip] = results
        return output

    async def _collect_from_device(
        self, device: DeviceInfo, commands: list[str], timeout: float,
    ) -> list[dict[str, Any]]:
        """从单台设备收集数据"""
        coros = [
            self._execute_single_command(device, cmd, timeout)
            for cmd in commands
        ]
        return await asyncio.gather(*coros, return_exceptions=True)

    async def _execute_single_command(
        self, device: DeviceInfo, command: str, timeout: float,
    ) -> dict[str, Any]:
        """执行单条命令——Demo 阶段 Mock"""
        check = self.whitelist.check(command)
        if not check.allowed:
            return {
                "device": device.ip, "command": command,
                "raw_output": "", "success": False,
                "error": check.reason, "blocked": True,
            }
        await asyncio.sleep(0.01)
        return {
            "device": device.ip, "command": command,
            "raw_output": f"Mock output: {command} on {device.hostname}",
            "success": True, "error": "",
        }

    def summarize(
        self,
        collected_data: dict[str, list[dict[str, Any]]],
        session_id: str,
    ) -> str:
        """生成结构化摘要"""
        lines = ["## 数据收集报告", ""]
        for device_ip, results in collected_data.items():
            if results and results[0].get("unreachable"):
                lines.append(f"### {device_ip}: ❌ 设备不可达")
                lines.append("")
                continue
            lines.append(f"### {device_ip}: ✅ 数据已收集")
            success_count = sum(1 for r in results if r.get("success"))
            lines.append(f"- 命令: {success_count}/{len(results)} 成功")
            for r in results:
                raw = r.get("raw_output", "")
                if isinstance(raw, str) and "CRC" in raw:
                    lines.append(f"  - ⚠️ `{r['command']}`: CRC 检测")
            lines.append("")
        lines.append(f"*原始数据 ID: {session_id}*")
        return "\n".join(lines)