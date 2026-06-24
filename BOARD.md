# BOARD.md — 网络排障多智能体系统 任务看板

> 每个 Ticket 为垂直切片（贯穿 MCP 工具 → Agent 逻辑 → 验证），可独立交付。
> Phase 1 Demo 目标：验证「6 个 AI Agent 通过确定性编排协作完成一次网络协议故障排障」。

---

## Phase 1：Demo 交付（13 Tickets）

- [x] **Ticket 0: 项目脚手架 + Docker 底座 + 扩展接口**
  搭项目目录结构、`pyproject.toml`、`docker-compose.yml`（Redis + Chroma）、环境变量配置（`REDIS_HOST`/`CHROMA_HOST`/`LLM_API_KEY`）。预埋扩展接口：`DeviceAdapter` 抽象基类、`ScenarioRegistry`、`AsyncDevicePool`、`TroubleshootingPipeline`（Strategy 模式）。
  验收：`docker-compose up -d` 启动 Redis + Chroma；`python -c "from agent import TroubleshootingPipeline"` 无报错；扩展接口为抽象类/Protocol，不实例化。
  完成 commit: 92df138
  - 依赖：无

- [x] **Ticket 1: MCP 工具层搭建 + 命令安全白名单**
  交付 MCP Server 骨架：命令白名单（正则+黑名单子串）、只读命名空间（`network.readonly`）、审计日志。不涉及实际网络设备，用 Mock 验证拦截逻辑。
  验收：白名单放行 `show interface`，拦截 `conf t`/`reload`/含 `tftp` 命令。
  完成 commit: 69545d4

- [x] **Ticket 2: AutoGen GroupChat 骨架 + 6 Agent 空壳注册**
  搭 AutoGen 项目骨架，注册 6 个 Agent（Dispatcher/Investigator/Diagnostician/Solution/Safety/Reporter），Manager 硬编码发言顺序。Agent 暂时只 echo 角色名。
  验收：`python main.py "测试故障"` 后 6 Agent 按顺序发言，Redis 持久化对话状态。
  完成 commit: abeaf73
  - 依赖：Ticket 0（环境配置）、Ticket 1（MCP 工具注册需要工具层存在）

- [x] **Ticket 3: Dispatcher Agent + CMDB 分流器**
  实现 Dispatcher 完整提示词（提取设备/时间/现象，不诊断）。实现分流规则引擎（查 CMDB 设备角色 → Fast Path 或 Slow Path）。CMDB 先用 SQLite 模拟。
  验收：输入"核心交换机 10.0.0.1 OSPF 邻居断了" → Dispatcher 输出结构化摘要 + 路由到 Slow Path；输入"接入交换机端口 down" → Fast Path。
  完成 commit: 3e798ac
  - 依赖：Ticket 2（需要 GroupChat 骨架才能注册 Dispatcher）

- [x] **Ticket 4: Investigator Agent + 并行数据收集**
  实现 Investigator 完整提示词（工具绑定、摘要义务）。实现并行执行器：一次对多台设备发出 ping/show/CPU/内存/日志。超时控制（Fast 2s/5s，Slow 5s/15s）。设备不可达标记为 `unreachable`。ntc-templates TextFSM 解析 + net-inspect 归一化 + LLM 兜底。先接 eNSP/HCL 虚拟设备验证。
  验收：并行 5 条命令，30 秒内返回结构化数据（CRC/CPU/内存/状态）+ 异常行 + 原始数据引用 ID。
  完成 commit: b6f0495
  - 依赖：Ticket 0（扩展接口 DeviceAdapter）、Ticket 1（MCP 工具层提供命令执行接口）、Ticket 3（Dispatcher 输出目标设备列表）

- [x] **Ticket 5: Diagnostician Agent + 重规划循环**
  实现 Diagnostician 提示词（综合分析症状/拓扑/案例）。接入 Chroma 向量库（初始为空，支持后续案例注入）。CMDB 拓扑查询。置信度评分。重规划逻辑：置信度 < 60% → 要求 Investigator 补充数据（最多 3 次/每轮补查≤2 次）。
  验收：给定 Investigator 输出 → Diagnostician 输出根因 + 置信度 > 60%（或触发重规划）。
  完成 commit: 5db1aa6
  - 依赖：Ticket 4（需要 Investigator 输出作为输入）

- [x] **Ticket 6: Solution Engineer + Safety Officer 规则引擎**
  实现 Solution Engineer（基于诊断结果生成修复命令 + 风险评级）。实现 Safety Officer Python 规则引擎（3 级风险模型：低自动/中通知/高转人工）。Manager 硬编码：Solution 后必须调用 Safety，不可跳过。
  验收：低风险命令生成 + 自动放行；中风险命令生成 + 通知输出；高风险命令生成 + 拒绝输出 + 转人工标记。
  完成 commit: b1398ed
  - 依赖：Ticket 5（需要 Diagnostician 输出作为输入）

- [x] **Ticket 7: Reporter Agent + 案例草稿生成**
  实现 Reporter（汇总全流程数据 → 输出 Markdown 报告）。生成案例草稿（症状/推理链/结论/操作），标记 `confirmed=false`。Webhook 通知模拟。
  验收：完整流程后输出 `report_<session_id>.md` + 案例草稿 JSON。
  完成 commit: 3798406
  - 依赖：Ticket 6（需要完整 6 Agent 流程产出）

- [x] **Ticket 8: 外部状态存储 + 上下文管理**
  建 SQLite 表：`fault_sessions`（故障摘要）、`collected_data`（设备数据）、`diagnosis`（诊断结论）。改造 Agent：不从对话历史读数据，统一从 DB 取。对话历史仅存推理链。
  验收：Agent 发言前后数据正确读写 DB；大日志场景（10KB+ CLI 输出）下上下文不超过 50% 上限。
  完成 commit: cf88d0b
  - 依赖：Ticket 0（环境配置）、Ticket 2（需在 Agent 骨架注入 DB 读写层）

- [x] **Ticket 9: 场景剧本 + 自动化回归测试**
  写 5 个 YAML 场景剧本（接口Down/OSPF/BGP/DHCP/STP），含 setup/trigger/expected/rollback。测试 Runner：自动执行设备快照恢复 → 注入故障 → 运行 Agent → 比对 expected。每个场景可独立运行。
  验收：`pytest tests/scenarios/` 5 个测试全部通过，预期根因匹配实际输出。
  完成 commit: a328482
  - 依赖：Ticket 7（需要完整流程可跑通）、eNSP/HCL 环境就绪（用户自行搭建）

- [x] **Ticket 10: LLM 降级 + 故障恢复**
  实现指数退避重试（5s→10s→放弃）。模型降级链（GPT-4o→mini→本地 DeepSeek 模拟）。全部不可用 → 生成半成品报告（已采集数据 + Dispatcher 摘要）推送。
  验收：手动断开 API → 系统输出半成品报告，不抛异常；恢复 API → 下一个 Session 正常推理。
  完成 commit: 60750fe
  - 依赖：Ticket 7（需要完整流程才能验证降级后继续）

- [x] **Ticket 11: 案例库闭环（人工复盘接口）**
  案例草稿 → 「待复盘」状态 → 人工确认 API（`PATCH /cases/{id}/confirm`）→ Chroma 向量化入库（`confirmed=true`）。检索接口：按症状向量返回 Top-K 案例。
  验收：确认案例后，下一次类似故障 Diagnostician 能在 Top-3 中检索到该案例。
  完成 commit: e890fe5
  - 依赖：Ticket 7（Reporter 生成案例草稿）、Ticket 5（Chroma 库已搭建）

- [x] **Ticket 12: E2E 集成验证 + Demo 跑分**
  跑通 5 个场景的完整 E2E 流程（自然语言输入 → 6 Agent → 报告）。度量指标：Fast Path < 30s、Slow Path < 5min、置信度达标率。输出 Demo 演示文档。
  验收：5 个场景全部通过，性能指标达标，可对外演示。
  完成 commit: 58caf02
  - 依赖：Ticket 9（场景剧本）、Ticket 10（降级可用）、Ticket 11（案例库可用）

---

## Phase 2：生产化

- [x] **Ticket 20: Netmiko 真实设备接入**
  替换 Investigator Mock 为 Netmiko SSH 真实执行，支持三厂商 device_type 映射，白名单校验保留，不可达自动降级 Mock。
  验收：`tests/test_netmiko.py` 6 passed, 3 skipped（真实设备测试需配置 `DEVICE_USER` 环境变量）。
  完成 commit: 428ced0
  - 依赖：Ticket 4（Investigator）

- [x] **Ticket 13: TACACS+ 命令授权替代正则白名单**
  双层防护：本地正则白名单（第一道） + TACACS+ 远程授权（第二道）。TACACS+ 不可用时降级为正则结果。
  验收：`tests/test_tacacs.py` 13 passed.
  完成 commit: c05ecf4
  - 依赖：Ticket 20（Netmiko）

- [x] **Ticket 19: RAG 知识库（Chroma 向量检索落地）**
   CaseLibrary.search() 从子串匹配升级为 Chroma 语义检索，接入 Embedding 模型，confirm() 自动向量化入库。Chroma 不可用时降级子串匹配。
   验收：`tests/test_rag.py` 10 passed.
   完成 commit: 15c5a93
   - 依赖：Ticket 11（CaseLibrary）

- [x] **Ticket 21: StateStore SQLite → MySQL 双后端**
   StateStore 支持 `backend="mysql"`，建表自动初始化（`CREATE TABLE IF NOT EXISTS`），SQLite 100% 向后兼容。MySQL 需提前手动 `CREATE DATABASE troublerouting`。
   验收：`tests/test_state_store.py` 6 passed + `tests/test_mysql_store.py` 7 passed/6 skipped（MySQL 测试需配置 MYSQL_* 环境变量）。
   完成 commit: 49cef2d
   - 依赖：Ticket 8（StateStore）

- [ ] Ticket 14: Deep Agents 框架迁移评估与 POC
- [ ] Ticket 15: Docker Compose / K8s 容器化部署
- [ ] Ticket 16: 真实工单系统（ServiceNow/Jira）对接
- [ ] Ticket 17: 闭环自动验证（监控回查 CRC/告警消除）
- [ ] Ticket 18: 大规模网络（>50 设备）性能压测

---

*拆分原则：每 Ticket 为垂直切片（MCP→Agent→验证），可独立交付。依赖关系在 Ticket 注释中标注。*