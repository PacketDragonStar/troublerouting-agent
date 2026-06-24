# 运维手册 — Operations Guide

> **读者：** 部署者、值班工程师  
> **目的：** 网络模拟器部署、Redis/Chroma 安装、健康检查、备份恢复  
> **适用环境：** Phase 1 Demo 开发环境

---

## 目录

1. [网络模拟器部署（EVE-NG）](#1-网络模拟器部署eve-ng)
2. [底座服务安装（Redis + Chroma）](#2-底座服务安装redis--chroma)
3. [服务健康检查](#3-服务健康检查)
4. [数据库备份与恢复](#4-数据库备份与恢复)
5. [日志查看](#5-日志查看)
6. [监控指标](#6-监控指标)
7. [常见运维操作](#7-常见运维操作)
8. [Phase 2 容器化迁移注意事项](#8-phase-2-容器化迁移注意事项)

---

## 1. 网络模拟器部署（EVE-NG）

> 为 Demo 阶段提供三厂商混合虚拟网络环境。

### 1.1 选型结论：EVE-NG（VMware Workstation + OVA）

**为什么选 EVE-NG：**
- 支持 Cisco / Huawei / H3C 三厂商在同一 Lab 中混合组网
- 和 Hyper-V 通过 Windows Hypervisor Platform 共存，不影响 Docker Desktop
- 不依赖特定 VirtualBox 版本

**为什么不用 Docker 版 EVE-NG：**
Windows Docker Desktop 不支持嵌套 KVM，只能编辑拓扑，无法启动设备镜像。

### 1.2 安装 VMware Workstation

1. 下载 [VMware Workstation Pro](https://www.vmware.com/products/workstation-pro.html)（个人免费）
2. 安装后确认 Windows 功能勾选：
   - ☑️ Windows 虚拟机监控程序平台
   - ☑️ 虚拟机平台
3. 重启

### 1.3 导入 EVE-NG Community Edition

1. 下载 [EVE-NG OVA](https://www.eve-ng.net/index.php/download/)
2. VMware Workstation → File → Open → 选择 `.ova` 文件
3. 虚拟机设置：
   - CPU：最少 4 核（勾选 Virtualize Intel VT-x/EPT）
   - 内存：最少 16 GB
   - 网络：**桥接模式**
4. 启动虚拟机，首次启动自动初始化
5. 访问 `https://<EVE-VM-IP>`，默认账号 `admin` / 密码 `eve`

### 1.4 Demo 拓扑

```
┌──────────────┐     ┌──────────────┐
│ R1: AR1000V  │←───→│ R2: vIOS     │   核心路由器
│  (Huawei)    │     │  (Cisco)     │
└──────┬───────┘     └──────┬───────┘
       │                    │
┌──────▼───────┐     ┌──────▼───────┐
│ SW1: IOL L2  │     │ SW2: vAC1000 │   交换机
│  (Cisco)     │     │   (H3C)      │
└──────┬───────┘     └──────┬───────┘
       │                    │
┌──────▼───────┐     ┌──────▼───────┐
│   PC1 (VPC)  │     │   PC2 (VPC)  │   测试终端
└──────────────┘     └──────────────┘
```

### 1.5 三厂商镜像清单

| 厂商 | 设备类型 | 推荐镜像 | 用途 | 获取方式 |
|------|---------|---------|------|---------|
| Cisco | L2 交换机 | **IOL L2** `i86bi-linux-l2-ipbasek9-15.1` | 接入交换机 | CML/VIRL 订阅 |
| Cisco | L3 交换机 | **IOL L3** `i86bi-linux-l3-p-15.3` | 核心交换机/路由器 | CML/VIRL 订阅 |
| Cisco | 路由器 | **vIOS** `vios-adventerprisek9-m` | 核心路由器 | CML/VIRL 订阅 |
| Huawei | 路由器 | **AR1000V** `V300R021C00` | 核心路由器 | Huawei 企业账号 |
| Huawei | 交换机 | **CE6800** `V200R005C10` | 核心交换机 | Huawei 企业账号 |
| H3C | 路由器 | **vSR1000** `V7.1.064` | 核心路由器 | H3C 合作伙伴账号 |
| H3C | 交换机 | **vAC1000** `V7.1.064` | 核心交换机 | H3C 合作伙伴账号 |
| H3C | 接入交换机 | **S5820V2** `V7.1.070` | 接入交换机 | H3C 合作伙伴账号 |

> ⚠️ 所有镜像须从官方渠道获取，EVE-NG 禁止未授权镜像。

### 1.6 CMDB 初始化

```python
from agent.cmdb import CMDB

cmdb = CMDB()
cmdb.add_device("10.0.0.1",   "R1-AR1000V", "huawei", "core")
cmdb.add_device("10.0.0.2",   "R2-vIOS",    "cisco",  "core")
cmdb.add_device("10.0.0.10",  "SW1-IOL",    "cisco",  "access")
cmdb.add_device("10.0.0.11",  "SW2-vAC",    "h3c",    "access")
```

---

## 2. 底座服务安装（Redis + Chroma）

### 2.1 方案一：Docker Compose（常规环境）

```bash
docker-compose up -d
# 启动 Redis (6379) + Chroma (8001)
```

适用于没有安装网络模拟器、或者使用 EVE-NG（VMware 版）的场景。

### 2.2 方案二：Windows 原生安装（HCL 用户专属）

> ⚠️ HCL 依赖 VirtualBox，必须关闭 Hyper-V，导致 Docker Desktop 不可用。用原生安装绕过 Docker。

**Redis for Windows：**

1. 下载 [tporadowski/redis](https://github.com/tporadowski/redis/releases) 的 `.msi` 安装包
2. 双击安装，默认端口 6379
3. 验证：`redis-cli ping` → `PONG`

**Chroma 原生 Python 模式：**

```bash
pip install chromadb
mkdir chroma_data
chroma run --path ./chroma_data --port 8000   # 新终端窗口保持运行
```

验证：`curl http://localhost:8000/api/v1/heartbeat`

**更新 `.env`：**

```bash
REDIS_HOST=localhost
REDIS_PORT=6379
CHROMA_HOST=localhost
CHROMA_PORT=8000
```

---

## 3. 服务健康检查

| 服务 | 检查命令 | 期望输出 |
|------|---------|---------|
| Redis | `redis-cli ping` | PONG |
| Chroma | `curl http://localhost:8001/api/v1/heartbeat` | 心跳 JSON |
| Agent | `python -m pytest tests/ -q` | 97 passed |
| SQLite | `sqlite3 data/troublerouting.db "PRAGMA integrity_check"` | ok |

---

## 4. 数据库备份与恢复

### 4.1 选择后端（SQLite vs MySQL）

| | SQLite（默认） | MySQL |
|------|---------|------|
| 适用场景 | Demo / 单机测试 | 生产 / 多 Agent 并发 |
| 配置 | 零配置，自动创建文件 | 需手动建库 + 改 `.env` |
| 并发 | 写锁排队 | 行级锁 + 连接池 |
| 备份 | 复制 `data/troublerouting.db` | `mysqldump` / 主从复制 |

**切换到 MySQL：**

```bash
# 1. 建库（只做一次）
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS troublerouting DEFAULT CHARSET utf8mb4;"

# 2. 改 .env
STATE_BACKEND=mysql
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASS=你的密码
MYSQL_DB=troublerouting

# 3. 重启 Agent——表结构自动创建（CREATE TABLE IF NOT EXISTS）
```

### 4.2 备份

```bash
# SQLite
cp data/troublerouting.db "backups/troublerouting_$(date +%Y%m%d_%H%M%S).db"

# MySQL
mysqldump -u root -p troublerouting > "backups/troublerouting_$(date +%Y%m%d_%H%M%S).sql"

# Redis（Docker 版）
docker exec troublerouting-redis redis-cli BGSAVE

# Chroma（Docker 版）
docker run --rm -v troublerouting_agent_chroma_data:/data -v $(pwd)/backups:/backup alpine tar czf /backup/chroma_backup.tar.gz -C /data .
```

### 备份频率

| 数据 | 频率 | 原因 |
|------|------|------|
| SQLite | 每日 | 审计数据，不可丢失 |
| Redis | 按需 | 断点恢复 |
| Chroma | 每次确认案例后 | 案例库是知识资产 |

---

## 5. 日志查看

| 日志类型 | 位置 |
|---------|------|
| Python 应用 | `logs/*.log` |
| 审计日志 | StateStore（SQLite） |
| Redis | `docker logs troublerouting-redis` |
| Chroma | `docker logs troublerouting-chroma` |
| 测试输出 | 终端 stdout |

日志级别在 `.env` 中配置：`LOG_LEVEL=DEBUG|INFO|WARNING|ERROR`

---

## 6. 监控指标

| 指标 | 正常范围 | 告警阈值 |
|------|---------|---------|
| Fast Path 延迟 | < 30s | > 30s |
| Slow Path 延迟 | < 5min | > 5min |
| 测试通过率 | 100% | < 100% |
| Redis 响应 | PONG | 超时 |
| Chroma 心跳 | 200 | 非 200 |
| 诊断准确率 | ≥ 60% | < 60% |

---

## 7. 常见运维操作

### 清理测试数据

```bash
rm data/troublerouting.db
python -c "from agent.state_store import StateStore; s=StateStore(); s.initialize()"
rm -rf reports/*
```

### 清除 Redis 会话

```bash
docker exec troublerouting-redis redis-cli FLUSHDB
```

### 运行时添加设备

```python
from agent.cmdb import CMDB
cmdb = CMDB()
cmdb.add_device("10.0.0.100", "new-switch", "cisco", "access")
```

### 手动确认案例入库

```python
from agent.case_library import CaseLibrary
lib = CaseLibrary()
lib.add_draft("session-xxx", data)
lib.confirm("session-xxx")   # 进入检索池
```

---

## 8. Phase 2 容器化迁移注意事项

| 当前 | Phase 2 目标 | 改动 |
|------|-------------|------|
| `REDIS_HOST=localhost` | `REDIS_HOST=redis` | 改环境变量 |
| `CHROMA_HOST=localhost` | `CHROMA_HOST=chroma` | 改环境变量 |
| Agent 本地 Python | Agent 在容器内 | 写 Dockerfile |
| MCP `import` 调用 | MCP JSON-RPC 调用 | 加 `mcp/server.py` + `mcp/client.py` |
| SQLite 本地文件 | PostgreSQL | 换数据库驱动 |
| EVE-NG 在宿主机 | 不变 | 容器通过 `host.docker.internal` 访问 |

---

*Phase 1 运维操作适用于开发/测试环境。Phase 2 生产化部署后需补充：TLS 配置、日志自动轮转、Prometheus 指标暴露、备份自动化。*