"""ScenarioRegistry——场景剧本注册中心

新增故障场景 = 添加 YAML 场景剧本 + 注册到 ScenarioRegistry，
不修改 Agent 核心代码。
"""

from typing import Any, Optional


class ScenarioRegistry:
    """场景剧本注册中心

    支持按名称注册和查找故障场景剧本，
    每个场景包含 setup/trigger/expected/rollback 配置。
    """

    def __init__(self):
        self._scenarios: dict[str, dict[str, Any]] = {}

    def register(self, name: str, scenario: dict[str, Any]) -> None:
        """注册一个场景剧本"""
        self._scenarios[name] = scenario

    def get(self, name: str) -> Optional[dict[str, Any]]:
        """按名称获取场景剧本"""
        return self._scenarios.get(name)

    def list_all(self) -> list[str]:
        """列出所有已注册的场景名称"""
        return list(self._scenarios.keys())

    def unregister(self, name: str) -> None:
        """移除一个场景剧本"""
        self._scenarios.pop(name, None)