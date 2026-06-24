# Deep Agents 框架迁移评估报告

版本：v1.0
日期：2026-06-24
决策者：Grill Me 架构审问 + 夜班模式实现

---

## 1. 背景

Phase 1 用 AutoGen GroupChat 实现了 6 Agent 确定性编排，成功验证了"Agent 协作排障"的假设。当前看板预留了 Ticket 14（Deep Agents 框架迁移），作为 Phase 2 的中优先级项目。

本报告评估 LangChain Deep Agents 替代 AutoGen 的可行性和风险。

---

## 2. Deep Agents 对你的排障场景的价值

### 2.1 当前 AutoGen 的局限性

| 场景 | AutoGen 现状 | 问题 |
|------|-------------|------|
| 未知故障 | Diagnostician 输出"未检测到已知故障模式，置信度 40%" | 无法自主探索新故障类型 |
| 复杂多点故障 | 重规划最多 3 次，每次固定 2 条补充命令 | 僵化，无法动态调整调查策略 |
| 新厂商设备 | 需要在 `COMMAND_TEMPLATES` 中手动添加命令 | 无法自主发现设备能力 |

### 2.2 Deep Agents 的差异化能力

| 能力 | AutoGen | Deep Agents |
|------|---------|-------------|
| 任务拆解 | 固定顺序（Manager 硬编码） | LLM 自主规划子任务 DAG |
| 工具选择 | Investigator 固定 5 条命令 | 子 Agent 动态决定需要什么数据 |
| 未知故障处理 | 输出"未知模式"后转人工 | 多轮探索直到收敛或超时 |
| 并发 | `asyncio.gather` 并行收集 | 子 Agent 并行执行，任务级并发 |

### 2.3 对 Demo 5 个场景的价值

| 场景 | AutoGen 已能处理 | Deep Agents 增值 |
|------|-----------------|-----------------|
| 接口 Down | ✅ 规则引擎匹配 "line protocol is down" | 无增值——确定性故障 |
| OSPF Down | ✅ 规则引擎匹配 "ospf" + "down" | 无增值——确定性故障 |
| BGP Down | ✅ 规则引擎匹配 "bgp" + "idle" | 无增值——确定性故障 |
| DHCP 故障 | ⚠️ 置信度仅 40%，但能输出 | 可能通过多轮探索找到 DHCP 服务器不可达 |
| STP 拓扑变化 | ⚠️ 置信度仅 40% | 可能通过多轮探索确认拓扑变化原因 |

**结论：** Demo 5 个场景中，3 个确定性故障不需要 Deep Agents。2 个低置信度场景（DHCP、STP）在 Deep Agents 下可能有改善，但改善幅度未知。

---

## 3. 迁移风险分析

### 3.1 Safety Officer 一票否决权的保障

**AutoGen（当前）：** Manager 硬编码 `Solution → Safety → Reporter`，不可跳过。

**Deep Agents：** Safety 检查点是主 Agent 规划时嵌入的"强制任务节点"。如果主 Agent 在规划时忘记插入 Safety 任务——安全审查被跳过。

**缓解方案：** 在任务执行器中硬编码拦截——任何包含 `config`/`reload`/`shutdown` 等关键词的子任务，强制执行前必须经过 Safety Officer（Python 规则引擎），不依赖 LLM 规划。

### 3.2 重规划循环的替换

**AutoGen（当前）：** `confidence < 60%` → 重规划，最多 3 次，确定性触发。

**Deep Agents：** 主 Agent 自己评估子任务结果，决定是否继续探索。优点是更灵活，缺点是无法保证探索深度上限。

**缓解方案：** 设置全局 `max_iterations=10`，超时后不管置信度多少都输出当前结论。

### 3.3 MCP 工具集成

**AutoGen（当前）：** 本地 `import mcp`，零延迟。

**Deep Agents：** 需要将 MCP 工具包装为 LangChain Tool（`@tool` 装饰器），或通过 `langchain-mcp` 社区适配层连接。

**工作量：** 约 2-3 天（工具包装 + 测试）。

### 3.4 测试回归

**AutoGen（当前）：** 5 个 YAML 场景剧本 + pytest 参数化回归。

**Deep Agents：** 由于 Agent 行为变成 LLM 自主决策，同样的输入可能产生不同的探索路径。场景剧本的 "expected" 断言可能不再精确。

**缓解方案：** 改用"结果约束"而不是"路径约束"——测试只断言最终根因分类正确，不检查中间过程。

---

## 4. 迁移成本估算

| 组件 | 改动量 | 风险 |
|------|--------|------|
| `TroubleshootingPipeline` 抽象基类 | 已有 Strategy 模式接口，零改动 | 低 |
| `DeepAgentsPipeline` 实现 | 新建 1 个类，约 200 行 | 中 |
| MCP 工具 → LangChain Tool 适配 | 新建 `mcp/langchain_tools.py`，约 150 行 | 中 |
| Safety Officer 硬编码拦截 | 改造 `safety_officer.py` 为独立服务 | 高 |
| 测试重写 | 场景剧本 expected 改结果约束 | 中 |
| 调试与调优 | 未知 | 高 |

**总工作量估算：1-2 周。**

---

## 5. 建议

**短期（Phase 2 剩余工作时间）：不建议迁移。**

理由：
1. Demo 5 个场景中 3 个是确定性故障，Deep Agents 无增值
2. 2 个低置信度场景（DHCP、STP）可以通过扩展 Diagnostician 的规则引擎覆盖，不需要 LLM 自主探索
3. Safety Officer 的硬编码保证是当前架构的核心安全底线，Deep Agents 会削弱这一保证
4. 当前没有遇到 AutoGen 无法处理的复杂未知故障——缺乏迁移的实际动机

**中长期（Phase 3+）：当以下条件之一满足时重新评估：**
- 诊断场景扩展到 20+ 种，规则引擎维护成本超过迁移成本
- 出现真实的复杂多点故障需要多轮自主探索
- Deep Agents 社区成熟，有生产案例验证

---

## 6. 决策

**暂不迁移。** 保留 `TroubleshootingPipeline` Strategy 模式接口作为未来切换点。当前 AutoGen 确定性编排满足 Demo 所有需求。

> 本评估写入 ADR，编号 ADR-032。