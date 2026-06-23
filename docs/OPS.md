# 运维手册 — Operations Guide

> **读者：** 部署者、值班工程师  
> **目的：** 健康检查、备份恢复、日志查看、监控指标  
> **适用环境：** Phase 1 Demo 开发环境

---

## 目录

1. [服务健康检查](#1-服务健康检查)
2. [数据库备份与恢复](#2-数据库备份与恢复)
3. [日志查看](#3-日志查看)
4. [监控指标](#4-监控指标)
5. [常见运维操作](#5-常见运维操作)
6. [Phase 2 容器化迁移注意事项](#6-phase-2-容器化迁移注意事项)

---

## 1. 服务健康检查

### 检查 Redis

```bash
# 方式 1: docker exec
docker exec troublerouting-redis redis-cli ping
# 期望输出: PONG

# 方式 2: 从宿主机
redis-cli -h localhost -p 6379 ping
```

### 检查 ChromaDB

```bash
curl -f http://localhost:8001/api/v1/heartbeat
# 期望输出: {"nanosecond heartbeat": ...}
```

> 也可以用 docker-compose 自带的 healthcheck：
> ```bash
> docker ps --filter "name=troublerouting" --format "table {{.Names}}\t{{.Status}}"
> ```

### 检查 Agent 进程

```bash
# 运行冒烟测试
python -m pytest tests/test_e2e.py -q
# 期望输出: 3 passed

# 全量测试
python -m pytest tests/ -q
# 期望输出: 97 passed in 0.xxs
```

### 检查 SQLite 数据库完整性

```bash
sqlite3 data/troublerouting.db "PRAGMA integrity_check;"
# 期望输出: ok
```

---

## 2. 数据库备份与恢复

### 备份

```bash
# SQLite 备份（直接复制文件）
cp data/troublerouting.db "backups/troublerouting_$(date +%Y%m%d_%H%M%S).db"

# Redis 备份（触发 RDB 快照）
docker exec troublerouting-redis redis-cli BGSAVE
# 备份文件在 Docker volume: redis_data

# Chroma 备份（Docker volume）
docker run --rm -v troublerouting_agent_chroma_data:/data -v $(pwd)/backups:/backup alpine tar czf /backup/chroma_backup.tar.gz -C /data .
```

### 恢复

```bash
# SQLite 恢复
cp backups/troublerouting_20260623_120000.db data/troublerouting.db

# Redis 恢复（停止 Redis，替换 dump.rdb，重启）
docker-compose stop redis
# 替换 volume 中的 dump.rdb
docker-compose start redis

# Chroma 恢复
docker-compose stop chroma
docker run --rm -v troublerouting_agent_chroma_data:/data -v $(pwd)/backups:/backup alpine tar xzf /backup/chroma_backup.tar.gz -C /data
docker-compose start chroma
```

### 备份频率建议

| 数据 | 频率 | 原因 |
|------|------|------|
| SQLite（故障数据） | 每日 | 审计数据，不可丢失 |
| Redis（会话状态） | 按需 | 断点恢复，非核心持久化 |
| Chroma（案例库） | 每次确认案例后 | 案例库是知识资产 |

---

## 3. 日志查看

### 日志位置

| 日志类型 | 位置 | 格式 |
|---------|------|------|
| Python 应用日志 | `logs/*.log` | 标准 logging 格式 |
| Agent 审计日志 | `mcp/audit_log.py` → 内存 → StateStore | dict → SQLite |
| Redis 日志 | `docker logs troublerouting-redis` | 容器 stdout |
| Chroma 日志 | `docker logs troublerouting-chroma` | 容器 stdout |
| 测试输出 | 终端 stdout | pytest 格式 |

### 查看日志

```bash
# Docker 服务日志
docker-compose logs --tail=50 redis
docker-compose logs --tail=50 chroma

# SQLite 中的审计日志（通过代码查询）
python -c "
from agent.state_store import StateStore
store = StateStore()
store.initialize()
sessions = store.get_fault_session('session-xxx')
print(sessions)
"
```

### 日志级别配置

在 `.env` 中修改：
```bash
LOG_LEVEL=DEBUG   # DEBUG | INFO | WARNING | ERROR
LOG_PATH=logs/
```

---

## 4. 监控指标

### 关键指标

| 指标 | 正常范围 | 告警阈值 | 检查方式 |
|------|---------|---------|---------|
| Fast Path 延迟 | < 30s | > 30s | E2E 测试 |
| Slow Path 延迟 | < 5min | > 5min | E2E 测试 |
| 全量测试通过率 | 100% | < 100% | `pytest tests/ -q` |
| SQLite 完整性 | ok | 非 ok | `PRAGMA integrity_check` |
| Redis 响应 | PONG | 超时 | `redis-cli ping` |
| Chroma 心跳 | 200 | 非 200 | `curl /api/v1/heartbeat` |
| Agent 诊断准确率 | ≥ 60% | < 60% | 场景剧本测试 |
| 重规划触发率 | 越低越好 | > 50% | 查看 diagnosis 表 confidence 分布 |

### 快速健康检查脚本

```bash
#!/bin/bash
# check_health.sh
echo "=== Redis ==="
docker exec troublerouting-redis redis-cli ping || echo "❌ Redis DOWN"

echo "=== Chroma ==="
curl -sf http://localhost:8001/api/v1/heartbeat > /dev/null && echo "✅ Chroma OK" || echo "❌ Chroma DOWN"

echo "=== Tests ==="
python -m pytest tests/ -q --tb=no && echo "✅ All tests passed" || echo "❌ Tests FAILED"

echo "=== SQLite ==="
sqlite3 data/troublerouting.db "PRAGMA integrity_check;" 2>/dev/null || echo "❌ SQLite corrupted"
```

---

## 5. 常见运维操作

### 清理测试数据

```bash
# 删除 SQLite 测试数据（保留表结构）
rm data/troublerouting.db
# 重新初始化
python -c "from agent.state_store import StateStore; s=StateStore(); s.initialize()"

# 清理测试报告
rm -rf reports/*
```

### 重置 Redis 会话状态

```bash
docker exec troublerouting-redis redis-cli FLUSHDB
```

### 新增 CMDB 设备记录

```python
# 运行时添加设备
from agent.cmdb import CMDB
cmdb = CMDB()
cmdb.add_device("10.0.0.100", "new-switch-1", "cisco", "access")
```

### 手动确认案例入库

```python
from agent.case_library import CaseLibrary
lib = CaseLibrary()
lib.add_draft("session-xxx", {...})
lib.confirm("session-xxx")  # 进入检索池
```

---

## 6. Phase 2 容器化迁移注意事项

当前部署模式（底座容器化 + Agent 本地进程）的迁移路径：

| 当前 | Phase 2 目标 | 需要做的事 |
|------|-------------|-----------|
| `REDIS_HOST=localhost` | `REDIS_HOST=redis` | 改环境变量 |
| `CHROMA_HOST=localhost` | `CHROMA_HOST=chroma` | 改环境变量 |
| Agent 本地 Python | Agent 在容器内 | 写 Dockerfile + 编排到 docker-compose |
| MCP `import` 调用 | MCP JSON-RPC 调用 | 加 `mcp/server.py` + `mcp/client.py` |
| SQLite 本地文件 | SQLite 或 PostgreSQL | 挂载 volume 或换数据库 |
| eNSP 在宿主机 | eNSP 在宿主机 | 容器通过 `host.docker.internal` 访问 |

---

*Phase 1 运维操作适用于开发/测试环境。Phase 2 生产化部署后需补充：TLS 配置、日志轮转、Prometheus 指标暴露、备份自动化。*