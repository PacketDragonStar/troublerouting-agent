"""
Ticket 5: Diagnostician Agent + 重规划循环 测试

验证根因分析、置信度评分、案例库检索、重规划逻辑。
"""

import pytest


@pytest.fixture
def diagnostician():
    from agent.diagnostician import Diagnostician
    from agent.cmdb import CMDB
    cmdb = CMDB()
    cmdb.add_device("10.0.0.1", "core-sw", "cisco", "core")
    cmdb.add_device("10.0.0.10", "acc-sw", "huawei", "access")
    return Diagnostician(cmdb=cmdb)


class TestDiagnosis:
    """诊断测试"""

    def test_diagnose_crc_error(self, diagnostician):
        """CRC 错误 → 诊断光模块/线缆问题"""
        investigator_data = {
            "10.0.0.1": [
                {"command": "show interface", "raw_output": "Gi0/1 is up, CRC errors: 50000, input errors: 0", "success": True},
                {"command": "show cpu", "raw_output": "CPU 5%", "success": True},
            ]
        }
        result = diagnostician.diagnose(
            fault_summary="核心交换机 10.0.0.1 接口异常",
            investigator_data=investigator_data,
            session_id="test-001",
        )
        assert result.root_cause != ""
        assert result.confidence > 0
        assert result.confidence <= 1.0

    def test_diagnose_device_unreachable(self, diagnostician):
        """设备不可达 → 诊断物理/链路故障"""
        investigator_data = {
            "10.0.0.1": [
                {"command": "show interface", "raw_output": "", "success": False, "unreachable": True, "error": "Connection timeout"},
            ]
        }
        result = diagnostician.diagnose(
            fault_summary="核心交换机 10.0.0.1 无法连接",
            investigator_data=investigator_data,
            session_id="test-002",
        )
        assert result.root_cause != ""
        assert "不可达" in result.root_cause or "unreachable" in result.root_cause.lower()

    def test_confidence_is_between_0_and_1(self, diagnostician):
        """置信度在 0~1 之间"""
        investigator_data = {
            "10.0.0.10": [
                {"command": "display interface", "raw_output": "GigabitEthernet0/0/1 current state : DOWN", "success": True},
            ]
        }
        result = diagnostician.diagnose(
            fault_summary="接入交换机端口 down",
            investigator_data=investigator_data,
            session_id="test-003",
        )
        assert 0 <= result.confidence <= 1.0


class TestReplanning:
    """重规划逻辑测试"""

    def test_low_confidence_triggers_replan(self, diagnostician):
        """置信度 < 60% 触发重规划"""
        assert diagnostician.should_replan(0.55) is True
        assert diagnostician.should_replan(0.30) is True
        assert diagnostician.should_replan(0.59) is True

    def test_high_confidence_no_replan(self, diagnostician):
        """置信度 ≥ 60% 不触发重规划"""
        assert diagnostician.should_replan(0.60) is False
        assert diagnostician.should_replan(0.85) is False
        assert diagnostician.should_replan(1.0) is False

    def test_max_replan_count_is_3(self, diagnostician):
        """最大重规划次数为 3"""
        assert diagnostician.max_replan_count == 3

    def test_replan_generates_new_commands(self, diagnostician):
        """重规划生成补充命令列表"""
        from agent.device_adapter import DeviceInfo
        device = DeviceInfo(hostname="core-sw", ip="10.0.0.1", vendor="cisco", role="core")
        extra = diagnostician.generate_replan_commands(
            device=device,
            previous_diagnosis="无法确定根因，需要更多物理层数据",
            iteration=1,
        )
        assert len(extra) > 0
        assert isinstance(extra, list)