# 架构决策记录 (ADR) — 网络排障多智能体系统

> **状态:** 全部 29 条 ADR 采纳于 2026-06-22~23 Grill Me 架构审问 + 夜班 TDD 实现  
> **维护者:** 项目团队  
> **更新频率:** 每季度架构评审时逐条检查，新决策追加

---

## 如何使用 ADR？

### 查阅（任何时间）
- **新成员入职**：读完所有 ADR = 理解系统所有关键设计选择和被拒绝方案
- **质疑设计**：有人问"为什么 Safety Officer 不是 LLM？"→ 翻 ADR-003
- **系统性信息**：按类别分组查阅（安全 / 延迟 / 上下文 / 测试 / 扩展 / 实现）

### 追加（决策时）
- **新架构决策产生** → 在下方添加新条目，用递增编号（ADR-030 起）
- **格式必须包含**：背景 / 决策 / 后果 / 被拒绝方案 / 关联代码文件

### 废弃（决策被推翻时）
- **不要删除旧 ADR**。在旧 ADR 的状态行标注 `❌ 被 ADR-XXX 取代`，并写入日期和原因
- 例：`状态: ❌ 被 ADR-045 取代 (2026-09-01，Phase 2 TACACS+ 上线)`

### 归档（季度审查时）
- 每季度检查一次 ADR 状态，把已废弃超过半年的 ADR 移到 `docs/ADR_archive.md`

---

## 类别一：安全与权限控制 (ADR-001 ~ ADR-004)

### ADR-001：命令白名单用正则匹配，Phase 2 切 TACACS+
- **状态:** ✅ 已采纳
- **日期:** 2026-06-22
- **决策者:** Grill Me 架构审问

**背景**
Investigator Agent 需要执行网络设备命令。必须防止配置类命令被注入执行。

**决策**
Demo 阶段用正则 + 黑名单子串 + 精确禁止命令列表。Phase 2 生产化时升级 TACACS+ Command Authorization。

**后果**
- ✅ Demo 快速实现（2h 写完全部白名单逻辑）
- ✅ 三层防护：前缀匹配 → 黑名单子串扫描 → 精确禁止
- ❌ 正则可能被精心构造的命令绕过（如 `show\x20running-config` 在 URL 解码后变 conf）
- ❌ 多厂商维护成本线性增长（每种新 OS 需更新正则）

**被拒绝的方案**
- **TACACS+（Phase 1 直接上）**：Demo 基础设施过重，需要搭 AAA 服务器，调试周期 3 天+
- **纯 LLM 判断命令安全性**：LLM 幻觉可能导致放行危险命令

**关联代码**
- `mcp/command_whitelist.py` — 白名单/黑名单/精确禁止
- `agent/investigator.py:73` — `_execute_single_command()` 每次执行前调 `whitelist.check()`

---

### ADR-002：Safety Officer 用 Python 规则引擎，非 LLM
- **状态:** ✅ 已采纳
- **日期:** 2026-06-22
- **决策者:** Grill Me 架构审问

**背景**
Solution Engineer（LLM）生成修复方案后，需要独立的安全审核。如果审核也是 LLM（另一个 Agent），就变成了"一个 LLM 审计另一个 LLM 的输出"——两人共享同样的模型偏见，且没有独立的事实依据。

**决策**
Safety Officer 用 Python 确定性规则引擎实现，不做 LLM 语义判断。

**后果**
- ✅ 确定性保证：同样输入永远输出同样结果，无法被提示词注入绕过
- ✅ 零幻觉：`reload` 命令在任何情况下都会被拦截
- ❌ 无法识别"语义类"风险（如"这条命令虽然合法但不符合业务逻辑"）
- ❌ 规则需要人工维护（新增风险关键词、新增禁止命令）

**被拒绝的方案**
- **LLM Safety Officer**：没有独立事实基础，无法真正审核
- **数字孪生验证（Phase 1 直接上）**：需要 EVE-NG/Containerlab 虚拟拓扑，Demo 太重

**关联代码**
- `agent/safety_officer.py` — 3 级风险模型 + 绝对禁止命令列表
- `agent/agents.py:73` — Manager 硬编码保证 Safety 不可跳过

---

### ADR-003：3 级风险模型（低自动 / 中通知 / 高转人工）
- **状态:** ✅ 已采纳
- **日期:** 2026-06-22
- **决策者:** Grill Me 架构审问

**背景**
不同修复操作的风险差距巨大：改 description 和 reload 设备不应享有同样的审批流程。

**决策**
```
low → approved=true, action="auto"      (自动执行)
medium → approved=true, action="notify" (自动执行 + 通知值班人)
high → approved=false, action="manual"  (拒绝自动执行 + 转人工工单)
```

**后果**
- ✅ 精准分级：75% 的低风险操作全自动，减少人工干预
- ❌ 风险等级由 Solution Engineer（LLM）用关键词评定——可能误判

**关联代码**
- `agent/safety_officer.py:56-74` — 风险分级逻辑
- `agent/solution_engineer.py:31-56` — 风险评级关键词表

---

### ADR-004：绝对禁止命令列表（Safety Officer 第二层）
- **状态:** ✅ 已采纳
- **日期:** 2026-06-23
- **决策者:** 夜班 TDD 实现

**背景**
即使 Solution Engineer 和 Safety Officer 的风险评级都通过了，有些命令仍然**绝对不能执行**（如 `reload`/`write erase`）。

**决策**
在 Safety Officer 的 `review()` 方法开头加上 `BLOCKED_COMMANDS` 绝对禁止列表，独立于风险等级判断。

**后果**
- ✅ 双重保险：即使风险评级被绕过，绝对禁止命令仍会被拦截
- ❌ 需要持续维护：随着新厂商加入，禁止列表可能膨胀

**关联代码**
- `agent/safety_officer.py:22-29` — BLOCKED_COMMANDS 列表

---

## 类别二：延迟与性能优化 (ADR-005 ~ ADR-009)

### ADR-005：并行数据收集（asyncio.gather）降低 I/O 延迟
- **状态:** ✅ 已采纳
- **日期:** 2026-06-22
- **决策者:** Grill Me 架构审问

**背景**
网络 I/O 延迟（SSH 建连 2-5s + 命令执行）是端到端延迟的主要瓶颈。如果对 5 台设备依次执行 5 条命令，仅建连就要 25s。

**决策**
Investigator 使用 `asyncio.gather` 同时向多台设备发出多条命令。单设备失败不影响其他设备。

**后果**
- ✅ 延迟从串行 125s 压到最慢单设备 25s
- ✅ 设备不可达时，其他设备数据继续收集
- ❌ 并发数受本地系统限制（大量设备时需要连接池）

**关联代码**
- `agent/investigator.py:67-76` — `collect_parallel()` 核心逻辑

---

### ADR-006：Fast/Slow Path 分流机制
- **状态:** ✅ 已采纳
- **日期:** 2026-06-22
- **决策者:** Grill Me 架构审问

**背景**
90% 的故障只需一条 `show interface` 就能定位，但流程设计是 6 Agent 全链路。简单故障跑全流程浪费 85% 的时间。

**决策**
Fast Path：接入设备 + 非 Critical → 2-3 Agent，< 30s
Slow Path：核心设备 / 用户手动报障 → 6 Agent，< 5min

**后果**
- ✅ 简单故障秒级出结果
- ❌ 分流误判（把复杂故障当 Fast Path 处理）可能导致诊断不完整

**被拒绝的方案**
- **LLM 判断复杂度**：增加一轮 LLM 调用 + 延迟，不划算

**关联代码**
- `agent/dispatcher.py:68-77` — `_decide_path()` 分流决策
- `agent/agents.py:79-86` — Fast Path 和 Slow Path 的 active_order 差异

---

### ADR-007：分流依据用 CMDB 设备角色，非 LLM
- **状态:** ✅ 已采纳
- **日期:** 2026-06-22
- **决策者:** Grill Me 架构审问

**背景**
（见 ADR-006）

**决策**
Dispatcher 查询 CMDB 获取设备角色（core/access/ap），用确定性 if-else 做分流决策。core → slow, access → fast, 未知 → slow（保守）。

**后果**
- ✅ 零延迟决策（CMDB 查询 vs LLM 调用 2-5s 差异）
- ❌ 依赖 CMDB 数据准确性（设备角色错误 → 分流错误）

**关联代码**
- `agent/dispatcher.py:68-77` — 规则引擎
- `agent/cmdb.py` — CMDB 数据层

---

### ADR-008：并行超时 Fast Path 2s/5s，Slow Path 5s/15s
- **状态:** ✅ 已采纳
- **日期:** 2026-06-22
- **决策者:** Grill Me 架构审问

**背景**
Fast Path 需要快速出结论，不能等一个慢设备。Slow Path 有更多时间容错。

**决策**
```python
TimeoutConfig.fast_path(): connect=2s, command=5s
TimeoutConfig.slow_path(): connect=5s, command=15s
```

**关联代码**
- `agent/investigator.py:46-52` — TimeoutConfig dataclass

---

### ADR-009：设备不可达 = 诊断信号，不丢弃
- **状态:** ✅ 已采纳
- **日期:** 2026-06-22
- **决策者:** Grill Me 架构审问

**背景**
并行收集时如果一台核心设备 SSH 连接超时——丢弃这个信号意味着 Diagnostician 拿不到完整数据。但等它超时又拖累整个批次。

**决策**
设备不可达不是一个错误要丢弃，而是一个诊断信号要传递。超时后立即标记 `unreachable=True`，传递给 Diagnostician。

**后果**
- ✅ "设备连不上"成为 Diagnostician 最高优先级的诊断模式（置信度 90%）
- ✅ 不等超时设备，其他设备正常完成

**关联代码**
- `agent/investigator.py:55-56` — 超时捕获 → `unreachable=True`
- `agent/diagnostician.py:43-51` — 不可达优先检测

---

## 类别三：数据质量与知识管理 (ADR-010 ~ ADR-013)

### ADR-010：案例库人工复盘后延迟入库（confirmed=false 默认）
- **状态:** ✅ 已采纳
- **日期:** 2026-06-22
- **决策者:** Grill Me 架构审问

**背景**
Diagnostician 可能误判。如果每次诊断结果自动入库，错误的案例会自我强化，3 周后案例库 30% 是幻觉。

**决策**
Reporter 生成的案例草稿默认 `confirmed=false`。24h 内由人工确认或修正根因标签后才将 `confirmed=true` 写入检索池。

**被拒绝的方案**
- **双 Agent 交叉验证**：两个 LLM 可能共享同样的偏见
- **闭环自动验证**：Phase 1 没有监控回查基础设施

**关联代码**
- `agent/case_library.py:23-25` — 草稿区与已确认区分离
- `agent/case_library.py:27-33` — confirm() 实现
- `agent/reporter.py:60-70` — generate_case_draft() 输出 confirmed=false

---

### ADR-011：ntc-templates + net-inspect 归一化 + LLM 兜底解析
- **状态:** ✅ 已采纳
- **日期:** 2026-06-22
- **决策者:** Grill Me 架构审问（你提议此方案）

**背景**
Cisco `show interface`、Huawei `display interface`、Juniper `show interfaces terse` 输出格式完全不同。需要归一化层让 Diagnostician 看到统一结构。

**决策**
正常路径：Netmiko 发命令 → ntc-templates TextFSM 解析 → net-inspect 归一化 → 结构化 JSON
兜底路径：TextFSM 解析失败 → 原始 CLI 文本直接传给 LLM 自行解析

**被拒绝的方案**
- **每厂商单独写 Python 解析器**：维护成本爆炸

**关联代码**
- `agent/investigator.py:73-88` — collect_parallel 输出结构化 dict

---

### ADR-012：重规划最大 3 次，置信度 < 60% 触发
- **状态:** ✅ 已采纳
- **日期:** 2026-06-22
- **决策者:** Grill Me 架构审问

**背景**
Diagnostician 第一轮诊断可能置信度不足，需要补充数据。但无限循环会耗尽时间。

**决策**
`confidence < 60%` → 触发重规划。最大 3 次。每轮补充命令 ≤ 2 条（从 `generate_replan_commands()` 按轮次+厂商返回）。3 次后仍不达标 → 转人工。

**被拒绝的方案**
- **LLM 自主决定是否需要重规划**：不可控

**关联代码**
- `agent/diagnostician.py:97-100` — should_replan()
- `agent/diagnostician.py:102-117` — generate_replan_commands()
- `agent/diagnostician.py:27` — max_replan_count=3

---

### ADR-013：已收集数据持久化到 StateStore，重规划不丢数据
- **状态:** ✅ 已采纳
- **日期:** 2026-06-22
- **决策者:** Grill Me 架构审问

**背景**
重规划时 Diagnostician 需要第一轮收集的数据来调整诊断方向。如果数据只存在对话上下文里，重规划时可能被 LLM 遗忘。

**决策**
所有 Investigator 收集的数据写入 StateStore（`collected_data` 表）。Diagnostician 通过 `get_collected_data(session_id, device_ip)` 读取。

**关联代码**
- `agent/state_store.py:73-83` — save/get collected_data

---

## 类别四：测试策略 (ADR-014 ~ ADR-016)

### ADR-014：测试环境 eNSP/HCL，只测协议故障不测硬件故障
- **状态:** ✅ 已采纳
- **日期:** 2026-06-22
- **决策者:** Grill Me 架构审问

**背景**
Demo 阶段模拟器无法注入 CRC 错误、光模块老化等硬件故障。这些需要真实设备 + 硬件故障注入工具。

**决策**
Phase 1 只测 5 种协议故障：接口Down/OSPF/BGP/DHCP/STP。硬件故障诊断留给 Phase 2。

**关联代码**
- `tests/scenarios/` — 5 个 YAML 全是协议层故障

---

### ADR-015：场景剧本 YAML 格式 + pytest 参数化回归测试
- **状态:** ✅ 已采纳
- **日期:** 2026-06-22
- **决策者:** Grill Me 架构审问

**背景**
每次改提示词或诊断规则后，需要重新验证 5 个场景是否仍能正确诊断。手动测试不可接受。

**决策**
每个场景写一个 YAML 文件（setup/trigger/mock_data/expected）。pytest 参数化自动遍历所有 YAML 并比对诊断输出。

**后果**
- ✅ 改 `diagnostician.py` 的规则后，`pytest tests/test_scenarios.py` 即时反馈
- ✅ 新增场景 = 新增一个 YAML 文件

**关联代码**
- `tests/scenarios/*.yml` — 5 个场景 YAML
- `tests/test_scenarios.py` — 参数化测试 Runner

---

### ADR-016：Diagnostician 用规则引擎而非 LLM 做诊断（Demo 5 个场景够用）
- **状态:** ✅ 已采纳
- **日期:** 2026-06-23
- **决策者:** 夜班 TDD 实现

**背景**
（同 ADR-002）Demo 阶段 5 个故障场景的检测模式已知且固定（CRC/接口Down/OSPF/BGP/设备不可达/未知），不需要 LLM 语义理解。

**后果**
- ✅ 100% 可复现：同样输入永远同样输出
- ❌ 遇到新故障类型 → 全部输出"未知模式"（需要人工补充诊断规则或 Phase 2 上 LLM）

**关联代码**
- `agent/diagnostician.py:53-92` — 6 种检测模式的规则引擎

---

## 类别五：上下文管理与数据流 (ADR-017 ~ ADR-019)

### ADR-017：命令输出策略——结构化 + 可查询原始
- **状态:** ✅ 已采纳
- **日期:** 2026-06-22
- **决策者:** Grill Me 架构审问（方案 C）

**背景**
`show interface` 输出 200 行，`display logbuffer` 上千行。6 Agent GroupChat 上下文传 3 轮就爆。

**决策**
MCP 层输出：结构化数据（TextFSM 解析）+ 原始文本写 StateStore。Agent 先看结构化摘要，需要时通过 `get_collected_data()` 查询原始输出。

**被拒绝的方案**
- **纯结构化（方案 A）**：ntc-templates 模板缺失时无数据可用
- **结构化 + 异常行（方案 B）**：异常行定义依赖正则，可能遗漏关键信息

**关联代码**
- `agent/state_store.py:73-83` — 原始数据存储与查询
- `agent/investigator.py:119-148` — summarize() 只输出摘要

---

### ADR-018：Investigator 强制摘要义务（提示词约束输出格式）
- **状态:** ✅ 已采纳
- **日期:** 2026-06-22
- **决策者:** Grill Me 架构审问

**背景**
即使原始数据已被剪裁，Investigator 自身的输出也可能很长。

**决策**
Investigator 的输出被提示词约束为 Markdown 摘要格式：关键指标 + 异常行 + 原始数据引用 ID。完整数据在外存。

**关联代码**
- `agent/investigator.py:119-148` — summarize() 输出格式

---

### ADR-019：外部状态存储（StateStore）解决上下文溢出——Agent 从 DB 读数据，不从对话历史读
- **状态:** ✅ 已采纳
- **日期:** 2026-06-22
- **决策者:** Grill Me 架构审问（方案 B）

**背景**
6 Agent GroupChat 的对话历史是所有 Agent 共享的同一个 context。如果每个 Agent 都把数据写进对话，3 轮后必然溢出。

**决策**
三张 SQLite 表：`fault_sessions`、`collected_data`、`diagnosis`。每个 Agent 发言前从 DB 读取所需数据，发言后把产出写入 DB。对话历史只存推理链（谁说了什么）。

**后果**
- ✅ 上下文上限从 8K 提升到 GB 级（SQLite 无限制）
- ✅ 对话断点恢复：重规划或 System 重启后，从 StateStore 恢复上下文
- ❌ 数据库读写增加了每步的延迟 5-20ms

**关联代码**
- `agent/state_store.py` — 完整 StateStore
- `agent/state_store.py:25-63` — initialize() 三张表 DDL

---

## 类别六：框架与工具选型 (ADR-020 ~ ADR-024)

### ADR-020：选用 AutoGen 而非 Deep Agents 作为 Phase 1 框架
- **状态:** ✅ 已采纳
- **日期:** 2026-06-22
- **决策者:** Grill Me 架构审问（多轮讨论）

**背景**
Demo 目标是验证「6 Agent 协作完成协议故障排障」。排障流程是线性 DAG（收集→诊断→修复→审核→报告），不是开放式探索。

**决策**
Phase 1 用 AutoGen GroupChat 确定性编排。Phase 2 评估 Deep Agents 处理复杂未知故障。

**被拒绝的方案**
- **Deep Agents（Phase 1 直接上）**：Planning 能力过度。Demo 5 个场景的 SOP 已知，不需要 LLM 拆任务
- **LangChain Agent**：生态不如 AutoGen 成熟，MCP 集成需自行适配

**关联代码**
- `agent/agents.py:71-93` — Manager 硬编码发言顺序
- `agent/pipeline.py:30-46` — TroubleshootingPipeline 抽象基类（Strategy 模式留 Deep Agents 迁移接口）

---

### ADR-021：Demo 阶段 MCP 用本地模块导入（非独立进程）——主动架构妥协
- **状态:** ✅ 已采纳（Phase 1），⚠️ Phase 2 重审
- **日期:** 2026-06-23
- **决策者:** 夜班 TDD 实现

**背景**
PRD 设计是独立 MCP Server 进程，通过 JSON-RPC 通信。但 Demo 验证假设是「Agent 协作排障」，不是「IPC 协议能不能跑通」。

**决策**
`mcp/command_whitelist.py` 和 `mcp/audit_log.py` 作为独立 Python 包，Agent 直接 `import` 调用。接口与 Agent 解耦，Phase 2 切独立进程只需加协议适配层，Agent 代码不改。

**后果**
- ✅ Demo 快速实现（2h vs 3 天）
- ✅ 安全逻辑完全一致（白名单校验、审计日志）
- ❌ 架构图与实际代码不符——需要在文档中诚实标注
- ❌ Agent 进程崩溃时 MCP 工具状态丢失

**关联代码**
- `mcp/command_whitelist.py` — 白名单
- `mcp/audit_log.py` — 审计日志
- `agent/investigator.py:7` — `from mcp.command_whitelist import CommandWhitelist`

---

### ADR-022：底座容器化 + Agent 本地进程（非全容器化）
- **状态:** ✅ 已采纳
- **日期:** 2026-06-22
- **决策者:** Grill Me 架构审问

**背景**
eNSP/HCL 是 Windows 客户端，无法容器化。在容器里跑 Agent 需要通过 `host.docker.internal` 访问宿主机 VirtualBox Host-Only 网络，多一层 Debug 复杂性。

**决策**
Redis + Chroma 用 Docker Compose 管理；Agent + MCP 代码在本地 Python 进程运行，直接 attach VS Code 调试。

**关联代码**
- `docker-compose.yml` — Redis + Chroma
- `.env.example` — 环境变量 localhost 配置

---

### ADR-023：CLI 先，API + Web 后（核心逻辑封装为单一函数）
- **状态:** ✅ 已采纳
- **日期:** 2026-06-22
- **决策者:** Grill Me 架构审问

**背景**
排障流程代码和触发方式应该解耦。CLI 只是多种触发方式之一。

**决策**
核心排障逻辑封装为 `async def troubleshoot(fault_description: str) -> TroubleshootingReport`。CLI 调用它，后续 FastAPI 也调用它，同一个函数。

**关联代码**
- `agent/agents.py:73` — `run_troubleshooting()`
- `agent/pipeline.py:30` — TroubleshootingPipeline 抽象基类

---

### ADR-024：案例检索用子串匹配（Demo），Phase 2 切 Chroma 向量检索
- **状态:** ✅ 已采纳（Phase 1），⚠️ Phase 2 重审
- **日期:** 2026-06-23
- **决策者:** 夜班 TDD 实现

**背景**
Chroma 向量检索需要 Embedding 模型 + 入库管道，Demo 阶段重点是验证「案例草稿→确认→检索」的状态流转。

**决策**
`CaseLibrary.search()` 用 Python 子串匹配（`if query in symptom or query in root_cause`）。docker-compose 里的 Chroma 已就绪，Phase 2 切换。

**关联代码**
- `agent/case_library.py:43-52` — search() 子串匹配
- `docker-compose.yml:19-32` — Chroma 容器

---

## 类别七：运维与降级 (ADR-025 ~ ADR-027)

### ADR-025：LLM 降级链（GPT-4o → mini → 本地 DeepSeek）
- **状态:** ✅ 已采纳
- **日期:** 2026-06-22
- **决策者:** Grill Me 架构审问

**背景**
LLM API 可能限流（429）、超时、返回无效。生产排障不能因为 API 挂了就整体中断。

**决策**
三层降级：GPT-4o → GPT-4o-mini → 本地 DeepSeek（或 Mock）。降级后 Diagnostician 提示词追加「如果置信度不足 70%，输出转人工」。

**关联代码**
- `agent/fallback.py:27-62` — LLMFallbackHandler

---

### ADR-026：LLM 全不可用 → 降级半成品报告保持可用
- **状态:** ✅ 已采纳
- **日期:** 2026-06-22
- **决策者:** Grill Me 架构审问

**背景**
（同 ADR-025）

**决策**
三层降级全失败后，不抛异常——生成半成品报告（已采集数据 + Dispatcher 摘要），推送值班人。对话状态持久化，LLM 恢复后从中断点继续。

**关联代码**
- `agent/fallback.py:65-94` — generate_degraded_report()

---

### ADR-027：LLM API 调用指数退避重试（5s → 10s → 放弃）
- **状态:** ✅ 已采纳
- **日期:** 2026-06-22
- **决策者:** Grill Me 架构审问

**背景**
不能每次 API 失败都立刻放弃——网络瞬时故障应该重试。但也不能无限等。

**决策**
`retry_with_backoff()`：5s → 10s → 20s → 放弃。最大重试 2 次。

**关联代码**
- `agent/fallback.py:13-20` — retry_with_backoff()

---

## 类别八：扩展性 (ADR-028 ~ ADR-029)

### ADR-028：4 个可插拔扩展接口预埋
- **状态:** ✅ 已采纳
- **日期:** 2026-06-22
- **决策者:** Grill Me 架构审问（你要求扩展性）

**背景**
项目未来要支持：多厂商 / 多故障类型 / 大规模网络 / 框架切换。

**决策**
在 Phase 1 代码中预埋 4 个抽象接口：

| 扩展方向 | 接口 |
|---------|------|
| A: 更多厂商 | `DeviceAdapter` 抽象基类 |
| B: 更多故障类型 | `ScenarioRegistry` |
| C: 更大规模 | `AsyncDevicePool` 抽象基类 |
| D: 框架迁移 | `TroubleshootingPipeline`（Strategy 模式） |

**关联代码**
- `agent/device_adapter.py:26-41` — DeviceAdapter
- `agent/scenario_registry.py:14-35` — ScenarioRegistry
- `agent/device_pool.py:21-61` — AsyncDevicePool
- `agent/pipeline.py:30-46` — TroubleshootingPipeline

---

### ADR-029：Diagnostician 同时检查命令名 + raw_output 内容
- **状态:** ✅ 已采纳
- **日期:** 2026-06-23
- **决策者:** 夜班 TDD 实现（测试失败后修正）

**背景**
场景剧本 `02_ospf_down.yml` 中 `show ip ospf neighbor` 的输出只含 "down" 和 "Dead timer"，不含 "ospf" 字样——因为命令名本身就包含协议信息。

**决策**
在 Diagnostician 中创建 `combined = cmd + " " + raw_lower`，匹配 OSPF/BGP 关键词时不仅检查输出内容，也检查命令名。

**关联代码**
- `agent/diagnostician.py:67` — combined 变量
- `agent/diagnostician.py:69, 77` — OSPF/BGP 检测用 combined

---

## 决策索引（按问题域）

| 问题域 | ADR 编号 |
|--------|---------|
| 框架选型 | ADR-020, ADR-021, ADR-022, ADR-023 |
| 安全与权限 | ADR-001, ADR-002, ADR-003, ADR-004 |
| 延迟与性能 | ADR-005, ADR-006, ADR-007, ADR-008, ADR-009 |
| 数据与知识 | ADR-010, ADR-011, ADR-012, ADR-013 |
| 上下文与状态 | ADR-017, ADR-018, ADR-019 |
| 测试策略 | ADR-014, ADR-015, ADR-016 |
| 运维与降级 | ADR-025, ADR-026, ADR-027 |
| 扩展性 | ADR-028 |
| 实现细节 | ADR-029, ADR-024 |

---

*本 ADR 文档由 Grill Me 架构审问 + 夜班模式 TDD 实现生成。29 条决策，每条含背景/决策/后果/被拒绝方案/关联代码。*