# troublerouting-agent

**6 个 AI Agent 自动排查网络故障。**

输入自然语言故障描述 → 自动执行只读诊断命令 → 推理根因 → 生成修复建议 → 输出标准化报告。

---

## 快速启动

> 所有命令都在项目根目录 `troublerouting_agent/` 下执行。

### 1. 安装依赖

```bash
# 在项目根目录下
pip install -e ".[dev]"
```

### 2. 配置 LLM API Key

```bash
cp .env.example .env
# 编辑 .env，填入: LLM_API_KEY=sk-你的密钥
```

### 3. 配置你的网络设备

编辑根目录下的 **`devices.yml`** 文件，填入你的设备 IP、厂商和角色：

```yaml
devices:
  - ip: "10.0.0.1"
    hostname: "core-sw-1"
    vendor: "cisco"
    role: "core"
```

> 不需要网络模拟器也能跑——Agent 会自动降级为 Mock 模式。

### 4. 启动底座服务（Redis + Chroma）

**Docker 在这做什么？** Redis 存 Agent 对话状态，Chroma 存历史故障案例的向量数据。代码里 `agent/agents.py` 调 Redis，`agent/case_library.py` 调 Chroma。

**二选一：**

| 你的环境 | 命令 |
|---------|------|
| 有 Docker Desktop（Hyper-V 开着） | `docker-compose up -d` |
| 用 HCL/eNSP（Hyper-V 关了，Docker 不能用） | 看 `docs/OPS.md` 第 2 节——装 Windows 原生 Redis + Chroma |

**如果暂时什么都不装**，Agent 也能跑——Investigator 会自动降级为 Mock 模式（返回假数据），不影响测试和 Demo 演示。

### 4. 验证

```bash
python -m pytest tests/ -q
# 期望输出: 129 passed in 0.xxs
```

### 5. 运行一次排障

```bash
python main.py "核心交换机 10.0.0.1 OSPF 邻居断开"
```

输出：`reports/report_{session_id}.md` + 案例草稿 JSON。

> **注意：** 之前 README 里写的 `python -m agent.agents` 不生效——`agents.py` 没有 `__main__` 入口。已通过 `main.py` 修复。

> **不需要网络模拟器也能跑。** Demo 阶段 Investigator 用 Mock 数据（不连真实设备），Diagnostician 照样能输出诊断结果。接入真实 eNSP/HCL/EVE-NG 设备的方法见 `docs/OPS.md` 第 1 节。

---

## 它能做什么

| 场景 | 输入示例 | 结果 |
|------|---------|------|
| 接口 Down | "接入交换机端口 Gi0/1 down 了" | 根因 + 置信度 + 修复命令 |
| OSPF 邻居断 | "核心路由器 OSPF neighbor 10.0.0.1 down" | 同上 |
| BGP Peer 断 | "核心路由器 BGP peer 10.0.0.3 断了" | 同上 |
| DHCP 故障 | "三楼用户获取不到 IP 地址" | 同上 |
| STP 拓扑变化 | "核心交换机 STP 拓扑变化" | 同上 |

---

## 架构一览

```
用户输入 → Dispatcher（分流）→ Investigator（采集5条命令）
  → Diagnostician（诊断+置信度）→ Solution Engineer（修复命令）
  → Safety Officer（否决权）→ Reporter（Markdown报告）
```

全部 6 个 Agent 按确定性顺序协作，中间通过 SQLite 外存储传递数据，对话上下文不爆。

---

## 文档导航

| 你在找什么 | 去这里 |
|-----------|--------|
| 项目背景和功能需求 | [`docs/PRD.md`](docs/PRD.md) |
| 为什么这样设计（29 条架构决策） | [`docs/ADR.md`](docs/ADR.md) |
| 完整项目文档（代码/测试/安全/扩展） | [`docs/PROJECT.md`](docs/PROJECT.md) |
| 任务看板 | [`BOARD.md`](BOARD.md) |

---

## 测试

```bash
python -m pytest tests/ -q      # 全部 97 个测试（< 1s）
python -m pytest tests/ -v      # 详细输出
```

---

**Phase 1 Demo 交付完成。** 6 个 AI Agent 通过确定性编排协作完成网络协议故障排障。97 测试全部通过。