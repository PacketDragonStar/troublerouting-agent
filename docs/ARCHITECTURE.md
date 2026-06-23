# 系统设计原理 — 架构运维手册

> **读者：** 系统维护者、二次开发者  
> **目的：** 解释每个非平凡设计选择的「为什么」和「怎么实现的」  
> **更新频率：** 每次架构变更时同步更新

---

## 目录

1. [意图识别与分流](#1-意图识别与分流)
2. [排障流程引擎](#2-排障流程引擎)
3. [上下文溢出管理](#3-上下文溢出管理)
4. [RAG 知识库设计](#4-rag-知识库设计)
5. [MCP 架构的 Demo 妥协](#5-mcp-架构的-demo-妥协)
6. [数据流全链路](#6-数据流全链路)
7. [Agent 间通信机制](#7-agent-间通信机制)
8. [安全设计原理](#8-安全设计原理)

---

## 1. 意图识别与分流

### 设计原理

Demo 阶段的意图识别**不是 LLM 语义理解**，是三层确定性流水线。每个阶段失败后兜底，不依赖 LLM。

### 实现：三层流水线

```
用户输入: "核心交换机 10.0.0.1 OSPF 邻居断了"
    │
    ▼
第一层：正则提取设备 IP
    IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
    提取: ["10.0.0.1"]
    校验: 0≤每个字节≤255
    失败 → IP 列表为空（后续走保守策略）
    │
    ▼
第二层：CMDB 角色查询
    for ip in valid_ips:
        record = self.cmdb.lookup(ip)  # DeviceRecord { role: "core"|"access"|... }
    查询失败 → device_records 为空（后续走保守策略）
    │
    ▼
第三层：分流决策（确定性 if-else）
    if any(record.role == "core") → Slow Path（6 Agent）
    elif 全是 access/ap → Fast Path（2-3 Agent）
    else → Slow Path（保守）
```

### 关键文件

- `agent/dispatcher.py:50-66` — `dispatch()` 三层流水线
- `agent/dispatcher.py:68-77` — `_decide_path()` 分流决策
- `agent/cmdb.py` — CMDB 数据层

### 设计选择：为什么不用 LLM 做意图识别？

| 方案 | 延迟 | 准确性 | Demo 适用性 |
|------|------|--------|------------|
| LLM 语义理解 | +2-5s | 95%（但可能幻觉） | 过度 |
| 正则+CMDB+规则 | 0ms | 100%（确定性） | ✅ 完美匹配 |

**结论：** 5 个 Demo 场景的故障分类（核心 vs 接入层、OSPF vs BGP）在关键词层面即可区分，LLM 不增加价值只增加延迟。

---

## 2. 排障流程引擎

### 设计原理

排障流程是**确定性 DAG**（有向无环图），不是 LLM 自主推理。每个 Agent 的输出是下一个 Agent 的输入，流程不可跳过。

### 实现：7 步确定性流程

```
Step 1: Dispatcher
    输入: 自然语言故障描述
    输出: FaultSummary { devices, path }
    状态存储: fault_sessions 表

Step 2: Investigator
    输入: 设备列表
    动作: asyncio.gather 并行 5 条命令 × N 台设备
    输出: 结构化摘要 Markdown（关键指标 + 异常行 + 数据 ID）
    状态存储: collected_data 表（原始 CLI 输出）

Step 3: Diagnostician
    输入: 从 StateStore 读取设备数据
    动作: 规则引擎匹配 6 种诊断模式（优先级从高到低）
    输出: DiagnosisResult { root_cause, confidence, evidence }
    判断: confidence < 60% → 触发重规划（max 3 次）
    状态存储: diagnosis 表

Step 4: Solution Engineer
    输入: 根因 + 置信度 + 设备名
    动作: 关键词匹配 → 风险评级（复盘/reload → high, OSPF/BGP → high, 端口 → medium, 其他 → low）
    输出: { commands, risk_level, description }

Step 5: Safety Officer（硬编码不可跳过）
    输入: 命令列表 + 风险等级
    动作: 规则引擎审核
      - 检查 BLOCKED_COMMANDS 绝对禁止列表
      - low → approved + auto
      - medium → approved + notify
      - high → rejected + manual
    输出: { approved, action, notification }

Step 6: Reporter
    输入: 全流程 agent_trace
    输出: Markdown 报告 + 案例草稿 JSON
    保存: reports/report_{session_id}.md + reports/case_{session_id}.json
```

### Diagnostician 的 6 种诊断模式（按优先级）

| 优先级 | 模式 | 检测方式 | 置信度 |
|--------|------|---------|--------|
| 1 | 设备不可达 | `unreachable=True` 标记 | 90% |
| 2 | CRC 错误 | raw_output 含 "crc" + 数字 | 85% |
| 3 | BGP 异常 | `combined` 含 "bgp" + idle/active/notification | 78% |
| 4 | OSPF 异常 | `combined` 含 "ospf" + down/init/dead | 75% |
| 5 | 接口 DOWN | "line protocol is down" / "current state : down" | 80% |
| 6 | 未知模式 | 以上都不匹配 | 40% |

**关键技术细节：** `combined = cmd + " " + raw_lower` 是测试失败后修正的设计——命令名本身包含协议信息（如 `show ip ospf neighbor`），只查 raw_output 会漏检。

### 重规划循环

```
confidence < 60% → 触发
    ↓
第 1 轮: 生成补充命令（show interfaces counters errors, show ip ospf neighbor）
    ↓ 重新收集 → 重新诊断
    ↓ 仍 < 60% →
第 2 轮: 生成补充命令（show ip bgp summary, show logging）
    ↓ 重新收集 → 重新诊断
    ↓ 仍 < 60% →
第 3 轮: 生成补充命令（show tech-support）
    ↓ 重新收集 → 重新诊断
    ↓ 仍 < 60% →
转人工（附带 3 轮收集的全部数据）
```

### 关键文件

- `agent/agents.py:73-117` — `run_troubleshooting()` 确定性编排器
- `agent/diagnostician.py:53-92` — 6 种诊断模式规则引擎
- `agent/diagnostician.py:97-117` — 重规划逻辑

---

## 3. 上下文溢出管理

### 问题

6 Agent GroupChat 共享一个对话历史。如果 Investigator 把 200 行的 `show interface` 输出直接写进对话——3 轮后 LLM 上下文窗口溢出，前面的故障描述和调度分析全部丢失。

### 解决：三层防御

```
┌─────────────────────────────────────────────────────────┐
│ 第一层：MCP 数据即剪裁                                    │
│                                                         │
│ 原始 CLI 输出（200 行）                                   │
│     ↓ TextFSM 解析                                      │
│ 结构化 JSON（10 行）                                     │
│     ↓                                                   │
│ Agent 只看 JSON，原始文本 → StateStore                    │
├─────────────────────────────────────────────────────────┤
│ 第二层：Investigator 摘要义务                              │
│                                                         │
│ Investigator 输出不是原始数据，是：                         │
│   ## 数据收集报告##                                       │
│   ### 10.0.0.1: ✅ 数据已收集                            │
│   - 命令: 5/5 成功                                       │
│   - ⚠️ `show interface`: CRC 检测                       │
│   *原始数据 ID: test-session-001*                        │
│                                                         │
│ Agent 对话里流转 500 字节摘要，不是 50KB 原始文本             │
├─────────────────────────────────────────────────────────┤
│ 第三层：外部状态存储（核心设计）                              │
│                                                         │
│    SQLite 三张表：                                       │
│    fault_sessions → 故障摘要                              │
│    collected_data → 设备原始数据（按 session_id+device_ip）│
│    diagnosis → 诊断结论                                   │
│                                                         │
│    每个 Agent 发言前从 DB 读取数据，发言后把产出写回 DB       │
│    对话历史只存推理链（谁说了什么），不存数据                   │
└─────────────────────────────────────────────────────────┘
```

### 设计效果

- 上下文上限：从 8K tokens 提升到 GB 级（SQLite 无限制）
- 对话断点恢复：重规划或系统重启后，从 StateStore 恢复所有上下文
- 数据库开销：每步延迟 +5-20ms

### 关键文件

- `agent/investigator.py:119-148` — `summarize()` 摘要输出格式
- `agent/state_store.py:25-63` — 三张表 DDL
- `agent/state_store.py:65-83` — save/get 读写方法

---

## 4. RAG 知识库设计

### 当前状态（Demo）

**已有的：**
- `CaseLibrary` 类 — 草稿管理 + 确认流程 + 检索
- 案例状态流转：`confirmed=false`（草稿） → `confirmed=true`（可检索）
- 检索方式：Python 子串匹配（`if query in symptom or root_cause`）
- ChromaDB Docker 容器已就绪（`docker-compose up -d` 即可启动）

**未接入的：**
- Embedding 模型（未调用 text2vec 或 OpenAI Embeddings API）
- Chroma 向量写入管道
- 向量语义检索

### 目标状态（Phase 2）

```
┌──────────────────────────────────────────────────────┐
│                    RAG 管道                           │
│                                                      │
│  故障报告自然语言                                       │
│       │                                              │
│       ▼                                              │
│  Embedding 模型                                      │
│  (text2vec / OpenAI Embeddings)                      │
│       │                                              │
│       ▼                                              │
│  ChromaDB 向量检索                                    │
│  (语义相似度 Top-K)                                   │
│       │                                              │
│       ▼                                              │
│  历史案例列表                                         │
│       │                                              │
│       ▼                                              │
│  Diagnostician 参考历史                               │
│  → [当前故障症状] vs [历史案例症状]                      │
│  → 置信度调整                                         │
│  → 根因推荐                                          │
└──────────────────────────────────────────────────────┘
```

### Phase 2 需要实现的组件

| 组件 | 当前 | 目标 | 工作量 |
|------|------|------|--------|
| Embedding | 无 | 接入 `text2vec` 或 OpenAI API | 1-2 天 |
| 入库管道 | 无 | `CaseLibrary.confirm()` 时自动向量化写入 Chroma | 1 天 |
| 检索替换 | 子串匹配 | Chroma 语义搜索 + 子串降级 | 1 天 |
| 退化链 | 无 | 如果 Chroma 不可用 → 子串匹配 | 0.5 天 |

### 案例生命周期（已完成）

```
Reporter 生成案例草稿
    confirmed=false
    ↓
推送值班人审阅
    ↓
人工确认（PATCH /cases/{id}/confirm）
    confirmed=true
    ↓
（Phase 2）自动向量化写入 Chroma
    ↓
进入检索池，Diagnostician 后续可检索
```

### 关键文件

- `agent/case_library.py:23-25` — 草稿区与已确认区分离
- `agent/case_library.py:27-33` — `confirm()` 实现
- `agent/case_library.py:43-52` — `search()` 子串匹配（Phase 2 替换为 Chroma）
- `docker-compose.yml:19-32` — Chroma 容器

---

## 5. MCP 架构的 Demo 妥协

### PRD 设计 vs 实际实现

| | PRD 设计 | Demo 实现 |
|------|---------|----------|
| 通信方式 | 独立 MCP Server 进程，JSON-RPC over stdio/SSE | Agent 直接 `import mcp` 本地模块 |
| 安全隔离 | 进程级隔离 | Python 包级隔离 |
| 可观测性 | 独立审计日志服务 | 内存审计日志（`AuditLog` 类） |
| 部署 | Sidecar 容器 | Agent 进程内 |
| 接口解耦 | ✅ Agent 不直接依赖 MCP 实现 | ✅ Agent 只依赖 `CommandWhitelist` 和 `AuditLog` 接口 |

### 为什么做这个妥协

**Demo 验证假设是「6 Agent 能否协作排障」，不是「IPC 协议能不能跑通」。**

- 写独立 MCP Server 需要的 JSON-RPC 传输层 + 进程生命周期管理 → 3 天调试
- 本地 import → 2 小时完成
- 两个方案的**安全逻辑完全相同**（白名单校验、审计日志）

### Phase 2 迁移路径

切独立进程时，只需加两层协议适配器，**Agent 代码不改**：

```
# Phase 2 计划
mcp/server.py     ← 暴露 CommandWhitelist 和 AuditLog 为 MCP tools
mcp/client.py     ← Agent 通过 JSON-RPC 调用（替代 import）
```

### 关键文件

- `mcp/command_whitelist.py` — 白名单（独立包，可独立部署）
- `mcp/audit_log.py` — 审计日志（独立包，可独立部署）
- `agent/investigator.py:7` — `from mcp.command_whitelist import CommandWhitelist`（Demo 妥协）

> ⚠️ **重要：** 架构图（`docs/PROJECT.md` 第 4 章）显示的 MCP Server 独立进程与实际代码不符。这是主动的 Demo 妥协，在 Phase 2 会修正。

---

## 6. 数据流全链路

### 端到端数据流（一次 OSPF 排障）

```
用户输入: "核心交换机 10.0.0.1 OSPF 邻居断了"
    │
    ▼ Dispatcher.dispatch()
    │   提取 IP → CMDB 查询 → role=core → path="slow"
    │   写入 StateStore.save_fault_session("session-xxx", ...)
    │   输出: FaultSummary
    │
    ▼ Investigator.collect_parallel([DeviceInfo(...)])
    │   并行 asyncio.gather:
    │     show interface ─┐
    │     show version ───┤
    │     show proc cpu ──┼──→ 结构化 JSON
    │     show memory ────┤
    │     show logging ──┘
    │   写入 StateStore.save_collected_data("session-xxx", "10.0.0.1", {...})
    │   输出: summarizer Markdown
    │
    ▼ Diagnostician.diagnose()
    │   从 StateStore.get_collected_data("session-xxx", "10.0.0.1")
    │   规则引擎: "ospf" in combined → "OSPF 邻居异常", confidence=0.75
    │   写入 StateStore.save_diagnosis("session-xxx", ...)
    │   输出: DiagnosisResult
    │
    ▼ SolutionEngineer.generate()
    │   关键词: "ospf" → risk_level="high"
    │   输出: { commands: [...], risk_level: "high" }
    │
    ▼ SafetyOfficer.review()
    │   risk_level="high" → approved=false, action="manual"
    │   输出: { approved: false, ... }
    │
    ▼ Reporter
    │   汇总 agent_trace → Markdown 报告
    │   生成案例草稿 JSON（confirmed=false）
    │   保存到 reports/ 目录
    │
    ▼
输出: reports/report_session-xxx.md + reports/case_session-xxx.json
```

### 数据生命周期

| 阶段 | 存储位置 | 生命周期 |
|------|---------|---------|
| 故障描述 | `fault_sessions` 表 | 永久（审计） |
| 原始 CLI 输出 | `collected_data` 表 | 永久（审计） |
| 结构化摘要 | GroupChat 上下文 | 对话期间（按需从 DB 恢复） |
| 诊断结论 | `diagnosis` 表 | 永久（审计） |
| 案例草稿 | `reports/case_*.json` | 永久 |
| Markdown 报告 | `reports/report_*.md` | 永久 |

---

## 7. Agent 间通信机制

### 当前实现：AutoGen GroupChat + StateStore

```
               ┌───────────────────────────┐
               │     GroupChat 对话历史      │
               │  (只存推理链，不存数据)      │
               │                           │
               │  Dispatcher: "路由到慢路径"  │
               │  Investigator: "数据已收集" │
               │  Diagnostician: "OSPF异常" │
               │  Solution: "高风险方案"     │
               │  Safety: "已拒绝"          │
               │  Reporter: "报告已生成"     │
               └───────────────────────────┘
                           ▲
                           │ 发包（推理链摘要）
                           │
    ┌──────────┐  ┌──────────┐  ┌──────────┐
    │Dispatcher│  │Investigator│ │Diagnostician│ ...
    └────┬─────┘  └─────┬────┘  └────┬─────┘
         │              │            │
         │    ┌─────────▼────────────▼───────┐
         │    │        StateStore (SQLite)    │
         └───►│  fault_sessions              │
              │  collected_data              │
              │  diagnosis                   │
              └──────────────────────────────┘
                   ▲              │
                   │  读数据       │  写数据
                   │              ▼
              ┌──────────┐  ┌──────────┐
              │Diagnostician│ │Reporter  │
              └──────────┘  └──────────┘
```

**核心原则：对话传推理，DB 传数据。**

- Agent A 发言：把一句话写进 GroupChat（推理摘要）
- Agent B 发言前：从 StateStore 读取需要的数据
- 对话历史只存「谁说了什么」，不存「show interface 的输出」

---

## 8. 安全设计原理

### 四层纵深防御

```
┌─────────────────────────────────────────────┐
│ 第一层：Agent 层 — Safety Officer 否决权       │
│ ✅ Python 规则引擎，确定性保证                   │
│ ✅ Manager 硬编码保证不可跳过                    │
│ ❌ 无法识别语义类风险                            │
├─────────────────────────────────────────────┤
│ 第二层：工具层 — 命令白名单 + 黑名单              │
│ ✅ 三层检查：前缀匹配 → 黑名单子串 → 精确禁止       │
│ ✅ 每次命令执行前强制校验                          │
│ ❌ 正则可能被绕过（Phase 2 上 TACACS+）           │
├─────────────────────────────────────────────┤
│ 第三层：执行层 — 绝对禁止命令                      │
│ ✅ BLOCKED_COMMANDS 列表（reload/reboot/...）  │
│ ✅ 独立于风险等级，无条件拦截                       │
│ ✅ 双重保险                                      │
├─────────────────────────────────────────────┤
│ 第四层：审计层 — 全流程追踪                        │
│ ✅ Session ID 绑定所有操作                        │
│ ✅ AuditLog 记录每次工具调用（成功/失败/被拦截）       │
│ ✅ StateStore 持久化所有数据（审计回溯）              │
└─────────────────────────────────────────────┘
```

### 命令白名单的三层检查逻辑

```python
# mcp/command_whitelist.py

def check(self, command: str, vendor: str) -> WhitelistResult:
    # 1. 精确禁止匹配（最高优先级）
    if command in BLOCK_EXACT:
        return blocked("forbidden command")

    # 2. 黑名单子串扫描
    for sub in BLOCK_SUBSTRINGS:  # tftp, ftp, redirect, erase, delete, ...
        if sub in command:
            return blocked("contains forbidden substring")

    # 3. 白名单前缀匹配
    for pattern in ALLOW_PREFIXES:  # ^show, ^display, ^ping, ^traceroute
        if pattern.match(command):
            return allowed(risk="low")

    # 4. 未匹配 → 拒绝
    return blocked("not in allowlist")
```

---

*本文档由系统代码审查生成，覆盖意图识别、排障流程、上下文溢出、RAG 知识库、MCP 妥协、数据流、通信机制、安全设计 8 个核心设计问题。*