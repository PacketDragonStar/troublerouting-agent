"""
Ticket 21: StateStore MySQL 切换 测试

验证:
- MySQL 建表
- 故障会话/设备数据/诊断结论 读写
- 大日志场景
- SQLite 向后兼容（原有测试不破坏）
"""
import pytest
import os
import json


# skip if no MYSQL_* env vars
MYSQL_READY = all(
    os.getenv(k) for k in ["MYSQL_HOST", "MYSQL_USER", "MYSQL_PASS", "MYSQL_DB"]
)


@pytest.fixture
def mysql_store():
    """MySQL-backed StateStore fixture"""
    if not MYSQL_READY:
        pytest.skip("MYSQL_* env vars not set")
    from agent.state_store import StateStore
    store = StateStore(backend="mysql")
    store.initialize()
    yield store
    store.close()


class TestMySQLInit:
    def test_initialize_creates_tables(self, mysql_store):
        tables = mysql_store.list_tables()
        assert "fault_sessions" in tables
        assert "collected_data" in tables
        assert "diagnosis" in tables


class TestMySQLCRUD:
    def test_fault_session_roundtrip(self, mysql_store):
        sid = "mysql-test-001"
        mysql_store.save_fault_session(sid, "core switch OSPF down", "slow")
        row = mysql_store.get_fault_session(sid)
        assert row is not None
        assert row["fault_description"] == "core switch OSPF down"

    def test_collected_data_roundtrip(self, mysql_store):
        sid = "mysql-test-001"
        mysql_store.save_collected_data(sid, "10.0.0.1", {"show ver": "IOS 15.2"})
        data = mysql_store.get_collected_data(sid, "10.0.0.1")
        assert data is not None
        assert data["show ver"] == "IOS 15.2"

    def test_diagnosis_roundtrip(self, mysql_store):
        sid = "mysql-test-002"
        mysql_store.save_diagnosis(sid, "OSPF Hello mismatch", 0.85, ["mtu=1500"])
        diag = mysql_store.get_diagnosis(sid)
        assert diag is not None
        assert diag["root_cause"] == "OSPF Hello mismatch"
        assert diag["confidence"] == 0.85
        assert "mtu=1500" in diag["evidence"]

    def test_large_payload(self, mysql_store):
        sid = "mysql-large"
        big = {"raw": "x" * 100_000}  # 100KB
        mysql_store.save_collected_data(sid, "10.0.0.1", big)
        data = mysql_store.get_collected_data(sid, "10.0.0.1")
        assert data is not None
        assert len(data["raw"]) == 100_000


class TestMySQLIsolation:
    def test_sessions_isolated(self, mysql_store):
        mysql_store.save_fault_session("s1", "fault A", "fast")
        mysql_store.save_fault_session("s2", "fault B", "slow")
        assert mysql_store.get_fault_session("s1")["fault_description"] == "fault A"
        assert mysql_store.get_fault_session("s2")["fault_description"] == "fault B"


class TestSQLiteBackwardCompat:
    """原有 SQLite 测试不得破坏"""

    def test_sqlite_still_works(self):
        from agent.state_store import StateStore
        import tempfile
        store = StateStore(backend="sqlite", db_path=os.path.join(tempfile.mkdtemp(), "test.db"))
        store.initialize()
        store.save_fault_session("s1", "test", "slow")
        assert store.get_fault_session("s1") is not None
        store.close()