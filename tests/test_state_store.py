"""
Ticket 8: 外部状态存储 + 上下文管理 测试

验证 SQLite 表创建、故障摘要/设备数据/诊断结论 读写。
"""

import pytest
import os
import tempfile


@pytest.fixture
def store():
    from agent.state_store import StateStore
    db_path = os.path.join(tempfile.mkdtemp(), "test.db")
    store = StateStore(db_path=db_path)
    store.initialize()
    yield store
    store.close()
    if os.path.exists(db_path):
        os.remove(db_path)


class TestStateStore:
    """状态存储测试"""

    def test_initialize_creates_tables(self, store):
        """初始化创建所有表"""
        tables = store.list_tables()
        assert "fault_sessions" in tables
        assert "collected_data" in tables
        assert "diagnosis" in tables

    def test_save_and_load_fault_session(self, store):
        """保存和加载故障摘要"""
        session_id = "test-session-001"
        store.save_fault_session(session_id, "核心交换机 OSPF 断开", "slow")
        session = store.get_fault_session(session_id)
        assert session is not None
        assert session["fault_description"] == "核心交换机 OSPF 断开"
        assert session["path"] == "slow"

    def test_save_and_load_collected_data(self, store):
        """保存和加载设备数据"""
        session_id = "test-session-001"
        store.save_collected_data(session_id, "10.0.0.1", {
            "show interface": "Gi0/1 is up, CRC 0",
            "show cpu": "CPU 5%",
        })
        data = store.get_collected_data(session_id, "10.0.0.1")
        assert data is not None
        assert "show interface" in data
        assert "CRC" in data["show interface"]

    def test_save_and_load_diagnosis(self, store):
        """保存和加载诊断结论"""
        session_id = "test-session-002"
        store.save_diagnosis(session_id, "OSPF Hello 不匹配", 0.85, ["接口参数错误"])
        diag = store.get_diagnosis(session_id)
        assert diag is not None
        assert diag["root_cause"] == "OSPF Hello 不匹配"
        assert diag["confidence"] == 0.85

    def test_large_data_not_stored_in_memory(self, store):
        """大日志数据写 DB 不占内存——验证数据完整性"""
        session_id = "test-large-data"
        large_output = "x" * 10240  # 10KB
        store.save_collected_data(session_id, "10.0.0.1", {
            "show interface": large_output,
        })
        data = store.get_collected_data(session_id, "10.0.0.1")
        assert data is not None
        assert len(data["show interface"]) == 10240
        # 数据从 DB 正确恢复
        assert "x" in data["show interface"]

    def test_multiple_sessions_isolated(self, store):
        """不同 Session 数据隔离"""
        store.save_fault_session("s1", "故障1", "fast")
        store.save_fault_session("s2", "故障2", "slow")

        s1 = store.get_fault_session("s1")
        s2 = store.get_fault_session("s2")
        assert s1["fault_description"] == "故障1"
        assert s2["fault_description"] == "故障2"