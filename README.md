# troublerouting-agent

**6 个 AI Agent 自动排查网络故障。**

输入自然语言故障描述 → 自动执行只读诊断命令 → 推理根因 → 生成修复建议 → 输出标准化报告。

---

## 5 分钟快速启动

### 前置条件

- Python 3.9+
- Docker（Redis + Chroma 底座）
- eNSP 或 HCL 网络模拟器（可选——Demo 阶段用 Mock 数据也能跑通测试）

### 启动

```bash
# 1. 配置密钥（只需要 LLM API Key）
cp .env.example .env
# 编辑 .env: LLM_API_KEY=sk-xxx

# 2. 启动底座
docker-compose up -d

# 3. 安装依赖
pip install -e ".[dev]"

# 4. 验证
python -m pytest tests/ -q
```

### 运行一次排障

```bash
python -m agent.agents "核心交换机 10.0.0.1 OSPF 邻居断开"
```

输出：`reports/report_{session_id}.md` + 案例草稿 JSON。

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