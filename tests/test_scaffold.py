"""
Ticket 0: 项目脚手架测试
验证扩展接口存在且为抽象类/Protocol，不可直接实例化，但可被正确导入。
"""
import pytest


class TestDeviceAdapter:
    """DeviceAdapter 抽象基类——多厂商设备适配器"""

    def test_import_device_adapter(self):
        """验证 DeviceAdapter 可导入"""
        from agent.device_adapter import DeviceAdapter
        assert DeviceAdapter is not None

    def test_device_adapter_is_abstract(self):
        """验证 DeviceAdapter 是抽象类，无法直接实例化"""
        from agent.device_adapter import DeviceAdapter
        with pytest.raises(TypeError):
            DeviceAdapter()  # type: ignore[abstract]

    def test_device_adapter_has_required_methods(self):
        """验证 DeviceAdapter 定义了核心抽象方法"""
        from agent.device_adapter import DeviceAdapter
        assert hasattr(DeviceAdapter, 'execute_readonly_command')
        assert hasattr(DeviceAdapter, 'get_device_info')


class TestScenarioRegistry:
    """ScenarioRegistry——场景剧本注册中心"""

    def test_import_scenario_registry(self):
        from agent.scenario_registry import ScenarioRegistry
        assert ScenarioRegistry is not None

    def test_scenario_registry_can_register_and_lookup(self):
        """验证 ScenarioRegistry 支持注册和查找场景"""
        from agent.scenario_registry import ScenarioRegistry
        registry = ScenarioRegistry()
        registry.register("ospf_down", {"name": "OSPF Neighbor Down"})
        scenario = registry.get("ospf_down")
        assert scenario is not None
        assert scenario["name"] == "OSPF Neighbor Down"


class TestAsyncDevicePool:
    """AsyncDevicePool——异步设备连接池"""

    def test_import_async_device_pool(self):
        from agent.device_pool import AsyncDevicePool
        assert AsyncDevicePool is not None

    def test_async_device_pool_is_abstract(self):
        """验证 AsyncDevicePool 是抽象类"""
        from agent.device_pool import AsyncDevicePool
        with pytest.raises(TypeError):
            AsyncDevicePool()  # type: ignore[abstract]


class TestTroubleshootingPipeline:
    """TroubleshootingPipeline——排障流程引擎（Strategy 模式）"""

    def test_import_troubleshooting_pipeline(self):
        from agent.pipeline import TroubleshootingPipeline
        assert TroubleshootingPipeline is not None

    def test_pipeline_is_abstract(self):
        """验证 TroubleshootingPipeline 是抽象基类"""
        from agent.pipeline import TroubleshootingPipeline
        with pytest.raises(TypeError):
            TroubleshootingPipeline()  # type: ignore[abstract]

    def test_pipeline_has_run_method(self):
        """验证 TroubleshootingPipeline 定义了 run 方法"""
        from agent.pipeline import TroubleshootingPipeline
        assert hasattr(TroubleshootingPipeline, 'run')