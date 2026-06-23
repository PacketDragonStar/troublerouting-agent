# 开发者指南 — Development Guide

> **读者：** 二次开发者、贡献者  
> **目的：** 如何扩展系统（加 Agent、加厂商、加故障场景）  
> **前提：** 已阅读 `README.md` 和 `docs/ARCHITECTURE.md`

---

## 目录

1. [如何新增一个设备厂商](#1-如何新增一个设备厂商)
2. [如何新增一个故障诊断场景](#2-如何新增一个故障诊断场景)
3. [如何修改或新增诊断规则](#3-如何修改或新增诊断规则)
4. [如何新增一个 Agent](#4-如何新增一个-agent)
5. [如何修改 Safety Officer 的规则](#5-如何修改-safety-officer-的规则)
6. [目录结构速查](#6-目录结构速查)

---

## 1. 如何新增一个设备厂商

**场景：** 你想让系统支持 H3C（或锐捷、Arista）设备。

**需要修改的文件：**

### Step 1：添加命令模板（`agent/investigator.py`）

在 `COMMAND_TEMPLATES` 字典中添加新厂商的 5 条诊断命令：

```python
COMMAND_TEMPLATES = {
    # ... 已有厂商 ...
    "h3c": [
        "display interface",
        "display version",
        "display cpu-usage",
        "display memory-usage",
        "display logbuffer",
    ],
}
```

### Step 2：添加重规划补充命令（`agent/diagnostician.py`）

在 `generate_replan_commands()` 的 `extra` 字典中添加：

```python
extra = {
    1: {
        # ... 已有厂商 ...
        "h3c": ["display interface counters error", "display ospf peer"],
    },
    # ...
}
```

### Step 3：添加 CMDB 记录（运行时或测试）

```python
# 在 CMDB 中注册设备
cmdb.add_device("10.0.0.100", "h3c-sw-1", "h3c", "access")
```

### Step 4：（可选）添加文本解析模板

如果 H3C 的 `display interface` 输出格式与 Huawei 不同，需要：
1. 在 ntc-templates 中找到或编写对应的 TextFSM 模板
2. 在 net-inspect 中添加归一化映射

**不需要修改的文件：** `agent/dispatcher.py`、`agent/diagnostician.py`（规则引擎部分）、`agent/solution_engineer.py`、`agent/safety_officer.py`、`agent/reporter.py`。

---

## 2. 如何新增一个故障诊断场景

**场景：** 你想加一个「HSRP 主备切换」的测试场景。

### Step 1：创建 YAML 场景剧本（`tests/scenarios/06_hsrp_failover.yml`）

```yaml
# 场景 6: HSRP 主备切换
fault: "核心交换机 HSRP 主备切换"
devices:
  - ip: "10.0.0.1"
    hostname: "core-sw-1"
    vendor: "cisco"
    role: "core"
mock_data:
  "10.0.0.1":
    - command: "show standby"
      raw_output: "Vlan1 - Group 1 State is Standby (was Active)"
      success: true
expected:
  root_cause_contains: "HSRP"
  min_confidence: 0.6
```

### Step 2：添加诊断规则（`agent/diagnostician.py`）

在 `diagnose()` 方法中添加新的检测模式：

```python
# HSRP 检测
if "standby" in raw_lower and ("active" in raw_lower or "hsrp" in combined):
    return DiagnosisResult(
        root_cause="HSRP 主备切换——可能原因：上行链路故障、优先级变化、抢占配置",
        confidence=0.78,
        evidence=[f"{device_ip}: HSRP 状态变更"],
        session_id=session_id,
    )
```

### Step 3：运行测试

```bash
python -m pytest tests/test_scenarios.py -v
```

新的 YAML 文件会被自动发现并作为参数化测试的一部分运行。

---

## 3. 如何修改或新增诊断规则

### 诊断规则的代码位置

所有诊断规则集中在 `agent/diagnostician.py` 的 `diagnose()` 方法中（约 53-92 行）。

### 规则结构

```python
# 每条规则的结构
if "关键词" in raw_lower:           # 检测条件
    return DiagnosisResult(
        root_cause="根因描述",       # 中文，会出现在报告中
        confidence=0.XX,             # 置信度 0.0~1.0
        evidence=["证据1", "证据2"], # 支撑证据
        session_id=session_id,
    )
```

### 注意事项

1. **检测顺序就是优先级。** `return` 意味着匹配到第一个规则就退出，后续规则不再检查。当前优先级：设备不可达 > CRC 错误 > BGP > OSPF > 接口 DOWN > 未知。
2. **使用 `combined` 而不是 `raw_lower`。** `combined = cmd + " " + raw_lower` 同时包含命令名和输出内容。因为 `show ip ospf neighbor` 的输出中可能不包含 "ospf" 字样，但命令名本身包含协议信息。
3. **修改规则后必须运行场景测试。** `pytest tests/test_scenarios.py` 会立刻告诉你是否破坏了已有场景的预期。
4. **置信度阈值不要随便改。** 60% 的重规划阈值是经过架构审问确定的。如果新规则的置信度必须低于 60%，请先创建 ADR。

---

## 4. 如何新增一个 Agent

**场景：** 你想在 Solution 和 Safety 之间加一个「Cost Analyst」（成本预估）Agent。

### Step 1：创建 Agent 模块（`agent/cost_analyst.py`）

```python
class CostAnalyst:
    def estimate(self, solution: dict) -> dict:
        """预估修复方案的成本"""
        risk = solution.get("risk_level", "low")
        # 规则引擎或 LLM 判断
        return {
            "downtime_minutes": 5,
            "cost_estimate": "低",
            "requires_maintenance_window": risk == "high",
        }
```

### Step 2：修改编排器（`agent/agents.py`）

在 `run_troubleshooting()` 的 `active_order` 中插入新 Agent：

```python
active_order = [
    "Dispatcher",
    "Investigator",
    "Diagnostician",
    "Solution",
    "CostAnalyst",   # ← 新增
    "Safety",
    "Reporter",
]
```

### Step 3：添加测试（`tests/test_cost_analyst.py`）

```python
def test_cost_analyst_estimates():
    from agent.cost_analyst import CostAnalyst
    analyst = CostAnalyst()
    result = analyst.estimate({"risk_level": "high"})
    assert result["requires_maintenance_window"] is True
```

---

## 5. 如何修改 Safety Officer 的规则

### 绝对禁止命令列表（`agent/safety_officer.py:22-29`）

```python
BLOCKED_COMMANDS = [
    "reload", "reboot", "reset bgp all",
    "clear ip bgp *", "write erase",
    "format flash:", "delete flash:",
    "copy running-config startup-config",
]
```

**注意：**
- 这里是**子串匹配**（`if blocked in cmd_lower`），不是精确匹配
- 添加新命令时注意不要太宽泛（如 "delete" 会匹配 "delete description"）
- **修改后必须同步更新测试** `tests/test_solution_safety.py` 中的 `test_safety_blocked_commands_always_rejected`

### 风险等级审核逻辑（`agent/safety_officer.py:56-74`）

```python
if risk_level == "high":
    return {"approved": False, "action": "manual", ...}
elif risk_level == "medium":
    return {"approved": True, "action": "notify", ...}
else:  # low
    return {"approved": True, "action": "auto", ...}
```

---

## 6. 目录结构速查

```
troublerouting_agent/
├── agent/               # 所有 Agent 和核心逻辑
│   ├── agents.py        # 编排器 + 6 Agent 定义
│   ├── diagnostician.py # 诊断规则（改规则在这里）
│   ├── dispatcher.py    # 意图识别 + 分流
│   ├── investigator.py  # 命令模板 + 并行收集
│   ├── safety_officer.py# 审核规则（禁止命令在这里）
│   ├── solution_engineer.py # 风险评级
│   ├── reporter.py      # 报告生成
│   ├── case_library.py  # 案例库
│   ├── state_store.py   # SQLite 存储
│   ├── fallback.py      # LLM 降级
│   ├── cmdb.py          # 设备信息
│   ├── pipeline.py      # 抽象接口
│   ├── device_adapter.py# 厂商适配器抽象
│   └── device_pool.py   # 连接池抽象
│
├── mcp/                 # MCP 工具层（独立包）
│   ├── command_whitelist.py # 命令安全
│   └── audit_log.py     # 审计日志
│
├── tests/
│   ├── scenarios/       # YAML 测试场景（加测试在这里）
│   └── test_*.py        # 测试文件
│
└── docs/
    ├── ARCHITECTURE.md  # 系统设计原理
    ├── ADR.md           # 架构决策记录
    └── DEVELOPMENT.md   # 本文档
```

---

*本文档覆盖二次开发最常见的 5 个场景。如果有其他问题，先查 `docs/ARCHITECTURE.md` 和 `docs/ADR.md`。*