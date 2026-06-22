"""
Ticket 3: Dispatcher Agent + CMDB 分流器 测试

验证自然语言故障报告解析、CMDB 设备角色查询、Fast/Slow Path 分流。
"""

import pytest


@pytest.fixture
def dispatcher():
    from agent.dispatcher import Dispatcher
    from agent.cmdb import CMDB
    cmdb = CMDB()
    # 注入测试数据
    cmdb.add_device("10.0.0.1", "core-switch-1", "cisco", "core")
    cmdb.add_device("10.0.0.2", "core-router-1", "cisco", "core")
    cmdb.add_device("10.0.0.10", "access-switch-3f", "huawei", "access")
    cmdb.add_device("10.0.0.11", "ap-3f-01", "huawei", "ap")
    return Dispatcher(cmdb)


class TestDispatcherParsing:
    """故障报告解析测试"""

    def test_extract_device_ip(self, dispatcher):
        summary = dispatcher.dispatch("核心交换机 10.0.0.1 OSPF 邻居断了，请排查")
        assert summary is not None
        assert "10.0.0.1" in summary.raw_text
        assert "OSPF" in summary.raw_text

    def test_extract_fault_phenomenon(self, dispatcher):
        summary = dispatcher.dispatch("办公楼三层无线用户无法获取 IP 地址")
        assert summary is not None
        assert "IP" in summary.raw_text or "三层" in summary.raw_text

    def test_empty_input_handled(self, dispatcher):
        summary = dispatcher.dispatch("")
        assert summary is not None
        assert summary.devices == []


class TestCMDB:
    """CMDB 查询测试"""

    def test_lookup_core_device_returns_core(self, dispatcher):
        info = dispatcher.cmdb.lookup("10.0.0.1")
        assert info is not None
        assert info.role == "core"

    def test_lookup_access_device_returns_access(self, dispatcher):
        info = dispatcher.cmdb.lookup("10.0.0.10")
        assert info is not None
        assert info.role == "access"

    def test_lookup_unknown_device_returns_none(self, dispatcher):
        info = dispatcher.cmdb.lookup("192.168.99.99")
        assert info is None


class TestPathRouting:
    """分流路由测试"""

    def test_core_device_triggers_slow_path(self, dispatcher):
        summary = dispatcher.dispatch("核心交换机 10.0.0.1 OSPF 邻居断了")
        assert summary.path == "slow"

    def test_access_device_triggers_fast_path(self, dispatcher):
        summary = dispatcher.dispatch("接入交换机 10.0.0.10 端口 Gi0/1 down 了")
        assert summary.path == "fast"

    def test_ap_device_triggers_fast_path(self, dispatcher):
        summary = dispatcher.dispatch("AP 10.0.0.11 离线了")
        assert summary.path == "fast"

    def test_multiple_core_devices_stay_slow(self, dispatcher):
        summary = dispatcher.dispatch("核心设备 10.0.0.1 和 10.0.0.2 之间 BGP 断了")
        assert summary.path == "slow"

    def test_unknown_device_defaults_to_slow(self, dispatcher):
        summary = dispatcher.dispatch("设备 192.168.99.99 无法访问")
        assert summary.path == "slow"