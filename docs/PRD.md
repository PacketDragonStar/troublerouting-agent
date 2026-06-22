# 网络排障多智能体系统 — 产品需求文档

版本：v1.0
日期：2026-06-22
状态：架构审问完成，待看板拆分

---

## 1. 项目背景与目标

### 1.1 背景
生产网络运维中，80% 的故障处理时间消耗在「信息收集→交叉比对→定位根因」这一重复性劳动上。一线工程师在不同厂商设备 CLI 之间切换、手动关联监控数据、翻查历史工单寻找相似案例——这些步骤适合由 AI Agent 团队自动化执行。

### 1.2 目标
构建一个 **7×24 小时自动化网络排障智能体团队**（Phase 1 基于 AutoGen GroupChat），实现：

- 接收自然语言故障报告
- 自动执行只读诊断命令（ping/traceroute/show/display，多厂商）
- 6 角色智能体协作推理根因
- 生成修复建议，低风险变更自动执行，高风险转人工
- 输出标准化排障报告和操作记录
- 支持故障案例人工复盘后入库，持续增强诊断能力

### 1.3 Demo 阶段核心验证假设
> "6 个 AI Agent 能通过确定性编排协作完成一次网络协议故障排障。"

### 1.4 运行环境

**底座容器化，Agent 本地跑，接口标准化：**

| 组件 | 运行方式 | 说明 |
|------|---------|------|
| Agent 进程 | 本地 Python（Windows 宿主） | 直接 attach VS Code 调试 |
| Redis | Docker（`docker-compose`） | GroupChat 状态持久化 |
| Chroma | Docker（`docker-compose`） | 向量案例库 |
| MCP Server | 本地 Python 独立进程 | 安全隔离，后续容器化零成本 |
| eNSP/HCL | Windows 客户端 | 虚拟设备通过 VirtualBox Host-Only 网卡暴露 |

- 所有外部依赖通过 `docker-compose up -d` 一键启动
- 所有地址通过环境变量配置（`REDIS_HOST=localhost` / `CHROMA_HOST=localhost`）
- 移植容器化时：Agent 进程 COPY 进 Dockerfile，环境变量改 `redis`/`chroma` 即可

### 1.5 触发方式

- **Phase 1：CLI**——`python main.py "三楼无线用户获取不到 IP"`
- **Phase 2：HTTP API + Web 对话界面**——核心排障逻辑封装为 `async def troubleshoot(fault_description: str) -> Report`，CLI 和 FastAPI 共用同一函数

### 1.6 网络拓扑

- 模拟器：eNSP（Huawei）或 HCL（H3C）
- 拓扑：2×Router + 2×Switch + 2×PC（标准三层拓扑）
- 虚拟设备通过 VirtualBox Host-Only 网卡与本机通信，Agent 通过 Netmiko/SSH 连接虚拟设备
- 拓扑搭建由用户自行完成（非 Agent 项目 Ticket 范围）

### 1.7 扩展性设计（四个方向全保留接口）

以下四个方向均在 Phase 1 架构中预留可插拔接口，不增加 Demo 阶段的代码量，但保证后续无需重构：

| 扩展方向 | Phase 1 预留接口 | 接口形式 |
|---------|-----------------|---------|
| **A: 更多厂商** | 新增厂商 = 添加 ntc-templates 模板 + net-inspect 映射文件，不修改 Agent 核心代码 | MCP 工具层 `DeviceAdapter` 抽象基类 |
| **B: 更多故障类型** | 新增故障场景 = 添加 YAML 场景剧本 + 注册 Diagnostician 提示词模板 | `ScenarioRegistry` + PromptTemplate 字典 |
| **C: 更大规模** | 并行收集已支持多设备并发；状态管理用外部 DB（非对话上下文） | `AsyncDevicePool` 连接池 |
| **D: 框架迁移** | 排障流程封装为引擎无关的 `TroubleshootingPipeline` | Strategy 模式：`AutoGenPipeline` / `DeepAgentsPipeline` |

---

## 2. 核心用户故事

### US-1：一线运维工程师报障
> 作为一线网络运维工程师，我希望能用自然语言描述故障现象（如"办公楼三层无线用户无法获取 IP 地址"），系统自动执行诊断流程，5 分钟内返回根因分析和修复建议，而不是我手动登录 5 台设备逐条敲命令。

**验收标准：**
- 输入自然语言描述，Dispatcher 正确提取设备、时间、现象
- 全流程 < 5 分钟（含网络命令执行）
- 输出含根因、置信度、建议方案的标准化报告

---

### US-2：值班工程师处理高风险变更
> 作为值班工程师，当 AI 诊断出需要设备配置变更时，我希望高风险操作（如 BGP 进程重启、设备 reload）不自动执行，而是推送完整的诊断上下文和推荐方案到我手机上，由我确认后再实施。

**验收标准：**
- 低风险操作（description 修改等）自动执行
- 中风险操作（端口 shutdown）通知值班人并附推荐
- 高风险操作（reload、BGP 变更）强制转人工工单
- Safety Officer 不可被任何 Agent 绕过

---

### US-3：网络主管复盘与知识沉淀
> 作为网络主管，我希望能审查 AI 的每次诊断结果，确认正确后将其加入案例库。这样下次类似故障发生时，系统能秒级匹配历史案例，减少重复推理。

**验收标准：**
- Reporter 自动生成「案例草稿」（症状、推理过程、结论、操作）
- 草稿推送到工单系统，标记"待复盘"
- 人工确认后案例写入 Chroma 向量库，`confirmed=true`
- 案例入库后，同类故障优先检索匹配

---

## 3. 功能性需求

### 3.1 智能体角色（6 人团队）

**FR-1: Dispatcher（调度员）**
- 接收自然语言故障报告或监控告警 Webhook
- 提取关键字段：时间、设备标识、故障现象
- 生成结构化「故障摘要」，不进行诊断
- 路由到 Fast Path 或 Slow Path（基于设备角色 + 影响范围）

**FR-2: Investigator（调查员）**
- 唯一有权访问网络设备执行只读命令的 Agent
- 工具集：ping、traceroute、show/display 命令、SNMP GET、监控 API 查询
- 输出：结构化「症状数据报告」+ 关键指标分析 + 原始数据引用 ID
- MCP 命令白名单/黑名单强制拦截，禁止 config 模式
- 支持多厂商：Cisco、Huawei、Juniper（ntc-templates + net-inspect 归一化）

**FR-3: Diagnostician（诊断专家）**
- 综合分析症状数据、拓扑信息、历史案例
- 工具集：向量案例库检索（Chroma + text2vec）、CMDB 拓扑查询
- 输出：根因分析报告 + 置信度评分
- 置信度 < 60% 触发重规划（最多 3 次），要求 Investigator 补充数据
- 补查次数≤2 次（每次规划内）

**FR-4: Solution Engineer（方案工程师）**
- 基于诊断结果生成修复方案
- 输出：变更命令、验证步骤、风险评级
- 低风险方案可直接传递给执行层

**FR-5: Safety Officer（安全/合规审计官）**
- **非纯 LLM，基于 Python 规则引擎**
- 3 级风险模型：
  - 低（description 修改、只读操作）：自动批准
  - 中（端口 shutdown、VLAN 变更）：生成推荐 + 通知值班人
  - 高（reload、BGP 变更、OSPF 进程重启）：强制转人工工单
- 检查变更窗口策略、设备维护状态
- 拥有否决权，不可被 Manager 跳过

**FR-6: Reporter（报告员）**
- 收集全流程对话、工具调用、决策链
- 生成《故障处理报告》（Markdown/JSON）
- 生成「案例草稿」推送到工单系统，标记"待复盘"
- 支持邮件/IM 通知

---

### 3.2 协作流程

**FR-7: GroupChat 确定性编排**
- Manager 硬编码发言顺序：Dispatcher → Investigator → Diagnostician → Solution → Safety → Reporter
- 最大轮次：20 轮（含重规划）
- 对话状态持久化到 Redis

**FR-8: Fast/Slow Path 分流**
- Fast Path：单台接入设备 + 非 Critical 告警 → 2 Agent（Investigator + Diagnostician），< 30 秒
- Slow Path：核心设备或用户手动报障 → 完整 6 Agent 流程
- 分流依据：CMDB 设备角色 + 受影响设备数量（规则引擎，非 LLM）

**FR-9: 重规划循环**
- 触发条件：Diagnostician 置信度 < 60%
- 最大重规划次数：3 次
- 每轮重规划前，主 Agent 基于已收集数据调整诊断方向
- 3 次后仍不达标 → 转人工，附带已收集的全部数据

**FR-10: 并行数据收集**
- Investigator 一次并行发出多条命令（ping + show interface + CPU + 内存 + 日志）
- Fast Path 超时：连接 2s，命令执行 5s
- Slow Path 超时：连接 5s，命令执行 15s
- 设备不可达标记为 `unreachable` 信号，作为诊断输入

---

### 3.3 工具与集成

**FR-11: MCP 工具层**
- 命名空间隔离：`network.readonly`（只读命令）、`network.case`（案例检索）、`system.ticket`（工单）、`system.notify`（通知）
- 命令白名单：正则匹配 + 黑名单子串（`redirect`、`tftp`、`|` 管道危险组合）
- 多厂商适配：ntc-templates TextFSM 解析 → net-inspect 归一化 → LLM 兜底解析原始输出
- 所有工具调用生成审计日志

**FR-12: 命令输出处理**
- MCP 层输出：结构化数据（ntc-templates 解析）+ 可查询原始文本（按需获取）
- Investigator 输出：强制摘要格式（关键指标 + 异常行 + 原始数据引用 ID）
- 原始 CLI 输出存入数据库，不在 Agent 间传递

**FR-13: 案例库**
- 向量库：Chroma + text2vec
- 案例入库：人工复盘确认后写入（`confirmed=true`）
- 案例检索：Diagnostician 按症状向量相似度检索 Top-K
- 支持「案例草稿」→「待复盘」→「已确认/已驳回」状态流转

**FR-14: 降级与容错**
- LLM 调用失败：指数退避重试（5s → 10s → 放弃）
- 模型降级链：GPT-4o → GPT-4o-mini → 本地 DeepSeek
- 全部 LLM 不可用：生成半成品报告（已采集数据 + Dispatcher 摘要）推送值班人
- 对话状态持久化，LLM 恢复后可从中断点继续

**FR-15: 外部状态存储**
- 故障摘要 → `fault_sessions` 表
- 设备数据 → `collected_data` 表
- 诊断结论 → `diagnosis` 表
- Agent 不依赖对话历史传递数据，每次都从 DB 读取

---

## 4. 非功能性需求

### 4.1 性能
- **NFR-1:** Fast Path 端到端延迟（从报障到出结论）< 30 秒
- **NFR-2:** Slow Path 端到端延迟 < 5 分钟
- **NFR-3:** 并行工具调用数 ≥ 5（同时 ping + show interface + CPU + 内存 + 日志）
- **NFR-4:** LLM API 调用延迟（单次）< 10 秒（P95）

### 4.2 安全
- **NFR-5:** 所有网络设备命令必须经过 MCP 白名单校验，配置类命令 100% 拦截
- **NFR-6:** Safety Officer 不可被代码或提示词绕过（硬编码保证）
- **NFR-7:** 高风险操作必须人工确认，系统不得自动执行
- **NFR-8:** 全部对话和工具调用记录持久化存储，绑定 Session ID，满足审计要求

### 4.3 可维护性
- **NFR-9:** 新增厂商支持通过添加 ntc-templates 模板 + net-inspect 映射实现，不修改 Agent 核心代码
- **NFR-10:** 新增故障场景通过添加场景剧本（YAML）+ 注册诊断提示词实现
- **NFR-11:** MCP 工具与 Agent 逻辑解耦，可独立测试、独立部署

### 4.4 可观测性
- **NFR-12:** 每个 Agent 发言附带时间戳和调用链 ID
- **NFR-13:** 工具调用记录输入/输出/耗时/状态
- **NFR-14:** 全流程 Session ID 可追踪

---

## 5. 关键技术决策与理由

| # | 决策 | 理由 |
|---|------|------|
| 1 | Phase 1 用 AutoGen GroupChat，非 Deep Agents | Demo 目标是验证「Agent 协作排障」，非「LLM 自主拆解未知故障」。确定性编排更适合协议故障场景的固定排查 SOP。Phase 2 按需迁移。 |
| 2 | 命令白名单用正则，非 TACACS+ | Demo 阶段设备少、厂商少，正则+黑名单足以。TACACS+ 等生产级 AAA 在 Phase 2 引入，避免 Demo 基础设施过重。 |
| 3 | Safety Officer 基于 Python 规则引擎，非纯 LLM | LLM 无法提供确定性安全保证。规则引擎可硬编码风险等级、变更窗口策略，且不会被提示词注入绕过。 |
| 4 | 并行数据收集 + Fast/Slow Path 分流 | 网络 I/O 延迟是主要瓶颈，并行化直接降低延迟。分流避免简单故障走全流程浪费。 |
| 5 | 分流依据用 CMDB 设备角色，不用 LLM | CMDB 数据是确定性标签，零延迟。LLM 判断复杂度和延迟不划算。 |
| 6 | ntc-templates + net-inspect + LLM 兜底 | 归一化解决多厂商命令差异，TextFSM 解析失败时 LLM 直接读原始输出，不阻断流程。 |
| 7 | 命令输出：结构化 + 可查询原始 | 避免 Agent 上下文被 CLI 回显撑爆。先给摘要（结构化数据），需要时再查原文。 |
| 8 | 外部 DB 状态存储（非对话上下文传数据） | 6 Agent 对话中夹带 200 行 show 命令输出必然溢出。DB 持久化让 Agent 各取所需。 |
| 9 | 案例库延迟入库 + 人工复盘 | 防止 Agent 自我强化错误结论。24h 内由人工确认根因标签。 |
| 10 | LLM 降级链（GPT-4o→mini→本地） | 保证 LLM API 不可用时系统仍可降级服务，不丢失已采集数据。 |
| 11 | 测试用 eNSP/HCL，只测协议故障 | Demo 阶段不模拟硬件故障（光模块/光纤），降低测试复杂度。5 个协议场景剧本覆盖最常故障。 |

---

## 6. 测试策略

### 6.1 测试环境
- 模拟器：eNSP（Huawei）或 HCL（H3C）
- 设备：2×Router + 2×Switch + 2×PC（标准三层拓扑）
- 不模拟硬件故障（光模块老化、光纤中断等）

### 6.2 单元测试
- MCP 工具函数独立测试：白名单校验、TextFSM 解析、net-inspect 归一化
- Safety Officer 规则引擎：3 级风险分类正确性
- CMDB 查询、案例库检索

### 6.3 集成测试：场景剧本（YAML）
5 个核心剧本，每个含 setup/trigger/expected/rollback：

1. **接口 Down**（接口管理性 shutdown 后恢复通路检测）
2. **OSPF Neighbor Down**（修改 Hello 间隔导致邻居断开）
3. **BGP Peer Down**（修改 AS Number 导致 Peer 断开）
4. **DHCP 故障**（删除 DHCP 地址池）
5. **STP 拓扑变化**（修改 Bridge Priority 后验证拓扑收敛）

每个场景剧本回放时从快照恢复设备状态，回归测试可重复执行。

### 6.4 端到端测试
- 自然语言输入 → 完整 6 Agent 流程 → 根因报告
- Fast Path 和 Slow Path 分别测试
- LLM 降级链：手动模拟 API 故障
- 上下文溢出：注入大日志量

---

## 7. Out of Scope（Phase 1 明确不做）

- 容器化/K8s 部署（本地 Python 进程即可）
- TACACS+ 集成（正则白名单替代）
- Deep Agents 框架（Phase 2 评估）
- 数字孪生/网络仿真验证（Safety Officer 用规则引擎替代）
- 闭环自动验证（换光模块后需监控回查 CRC——硬件故障外）
- 多语言支持（仅中文）
- 与真实工单系统（ServiceNow/Jira）对接（Webhook 模拟即可）
- 灰度发布/告警风暴抑制
- 硬件故障诊断（光模块、光纤、电源等）
- 大规模网络（>50 台设备）性能测试

---

## 8. 附录

### A. 术语表
| 术语 | 定义 |
|------|------|
| AutoGen | 微软开源多智能体框架 |
| GroupChat | AutoGen 的多 Agent 群聊协作模式 |
| MCP | Model Context Protocol，工具协议层 |
| ntc-templates | 开源 TextFSM 模板库，解析网络设备 CLI 输出 |
| net-inspect | 多厂商网络命令归一化库 |
| Chroma | 开源向量数据库 |
| eNSP/HCL | Huawei/H3C 官方网络模拟器 |

### B. 架构决策记录（ADR）索引
（见第 5 章，共 11 条 ADR）

---

*本 PRD 经 13 轮架构审问生成，覆盖安全、延迟、上下文、测试、降级、多厂商、案例库等关键决策点。*