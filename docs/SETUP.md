# 首次初始化配置指南

> 从零到跑通第一次真实设备排障的完整步骤。

---

## 1. 前置条件检查

```bash
# Python 版本 (≥3.9)
python --version

# 必需服务
redis-cli ping          # → PONG
curl http://localhost:8000/api/v2/heartbeat  # → 心跳 JSON (Chroma)
mysqladmin -u root -p ping   # → mysqld is alive
```

## 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，**至少修改以下 3 项**：

| 变量 | 说明 | 示例 |
|------|------|------|
| `LLM_API_KEY` | DeepSeek/OpenAI 密钥 | `sk-xxxx` |
| `DEVICE_USER` | HCL 设备 SSH 用户名 | `admin` |
| `DEVICE_PASS` | HCL 设备 SSH 密码 | `Huawei@123` |

> 如果不填 `DEVICE_USER`，Agent 仍可运行——Investigator 自动降级为 Mock 模式。

## 3. 创建 MySQL 数据库

```bash
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS troublerouting DEFAULT CHARSET utf8mb4;"
```

> 如果用 SQLite（默认），跳过此步。

## 4. 配置网络设备

编辑根目录下的 **`devices.yml`**，填入你的设备 IP、厂商和角色：

```yaml
devices:
  - ip: "192.168.41.88"
    hostname: "core-sw-1"
    vendor: "h3c"
    role: "core"
  - ip: "192.168.41.12"
    hostname: "acc-rou-2"
    vendor: "h3c"
    role: "access"
```

启动时 Agent 会自动将 `devices.yml` 中的所有设备注册到 CMDB。

## 5. 安装依赖

```bash
pip install -e ".[dev]"
pip install pyyaml pymysql netmiko  # 如果还没装
```

## 6. 验证系统

```bash
# 全部测试（Mock 模式下运行）
python -m pytest tests/ -q --tb=no
# 期望: 134 passed, 3 skipped

# 启动一次排障
python main.py "核心交换机 192.168.41.88 OSPF 邻居断开"
```

## 7. 首次真实设备排障

```bash
# 确保 HCL 设备在线 + SSH 可达
ping 192.168.41.88

# 确保 .env 里 DEVICE_USER 和 DEVICE_PASS 已正确填写

# 启动真实排障
python main.py "核心交换机 192.168.41.88 OSPF 邻居断开"
```

如果一切正常，你将看到 Agent 通过 Netmiko SSH 连接 HCL 设备，执行诊断命令，输出根因报告。

---

**排障完成后，输出文件位置：**
- `reports/report_{session_id}.md` — Markdown 排障报告
- `reports/case_{session_id}.json` — 案例草稿（可确认入库）