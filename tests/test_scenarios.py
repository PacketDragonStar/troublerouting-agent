"""
Ticket 9: 场景剧本 + 自动化回归测试

5个YAML场景：接口Down/OSPF/BGP/DHCP/STP
不依赖真实eNSP/HCL——用Mock数据验证诊断结果。
"""
import pytest
import yaml
import os

SCENARIOS_DIR = os.path.join(os.path.dirname(__file__), "scenarios")
SCENARIO_FILES = [f for f in os.listdir(SCENARIOS_DIR) if f.endswith(".yml") or f.endswith(".yaml")] if os.path.isdir(SCENARIOS_DIR) else []


def load_scenario(filename: str) -> dict:
    with open(os.path.join(SCENARIOS_DIR, filename), "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class TestScenarios:
    """场景剧本集成测试"""

    @pytest.mark.parametrize("filename", SCENARIO_FILES)
    def test_scenario_diagnosis_matches_expected(self, filename):
        scenario = load_scenario(filename)
        # 用Mock数据跑诊断
        from agent.diagnostician import Diagnostician
        from agent.cmdb import CMDB
        cmdb = CMDB()
        for dev in scenario.get("devices", []):
            cmdb.add_device(dev["ip"], dev["hostname"], dev["vendor"], dev["role"])
        diag = Diagnostician(cmdb=cmdb)
        result = diag.diagnose(
            fault_summary=scenario["fault"],
            investigator_data=scenario.get("mock_data", {}),
        )
        expected = scenario.get("expected", {})
        assert result.root_cause != ""
        if "root_cause_contains" in expected:
            assert expected["root_cause_contains"] in result.root_cause
        if "min_confidence" in expected:
            assert result.confidence >= float(expected["min_confidence"])