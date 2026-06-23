# 故障排除指南 — Troubleshooting Guide

> **目的：** 记录已知问题、常见错误及解决方案。团队里任何人踩过的坑，第二个人不需要再踩一次。

---

## 目录

1. [测试相关](#1-测试相关)
2. [运行环境相关](#2-运行环境相关)
3. [Git 相关](#3-git-相关)
4. [Agent 行为相关](#4-agent-行为相关)

---

## 1. 测试相关

### 问题：运行 `pytest tests/` 结果卡住了，长时间不退出

**原因：** 旧版 `test_e2e.py` 中的 `test_all_10_test_files_pass` 测试在 pytest 内部通过 `subprocess.run` 再次调用了 `pytest tests/`，形成了无限递归。

**解决方案：** 该测试已被删除（commit `58caf02`）。确保你使用的是最新代码：

```bash
git log --oneline -1 tests/test_e2e.py
# 应该显示: 58caf02 feat(ticket-12): E2E 集成验证 + Demo 跑分 (red→green)
```

---

### 问题：`ModuleNotFoundError: No module named 'agent.xxx'`

**原因：** 新添加的模块文件未被 pytest 发现，或者 Python 路径配置不正确。

**解决方案：**
1. 确保 `pyproject.toml` 中有 `pythonpath = ["."]`：
   ```toml
   [tool.pytest.ini_options]
   testpaths = ["tests"]
   pythonpath = ["."]
   ```
2. 确保模块文件在正确的目录下（`agent/` 或 `mcp/`）
3. 运行 `pip install -e ".[dev]"` 安装项目

---

### 问题：场景剧本测试失败——`AssertionError: assert 'OSPF' in '未检测到已知故障模式...'`

**原因：** Diagnostician 的规则引擎没有匹配到 YAML 场景的 mock_data 内容。可能是 raw_output 中的文本模式与规则引擎的正则不匹配。

**解决方案：**
1. 检查 YAML 文件中的 `raw_output` 是否包含 Diagnostician 期望的关键词（如 "line protocol is down"、"idle"、"dead" 等）
2. 注意 Diagnostician 使用 `combined = cmd + " " + raw_lower` 来匹配 OSPF/BGP——命令名本身也参与匹配
3. 调试方法：在 `agent/diagnostician.py` 的 `diagnose()` 方法中添加 `print` 语句查看哪些模式被检测到了

---

### 问题：Python 3.9 上报错 `TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'`

**原因：** Python 3.9 不支持 `X | None` 联合类型语法（这是 Python 3.10+ 的特性）。

**解决方案：** 使用 `Optional[X]` 替代 `X | None`，并从 `typing` 导入 `Optional`。

```python
# ❌ Python 3.9 不支持
def get_entries(self, session_id: str | None = None):

# ✅ Python 3.9 兼容
from typing import Optional
def get_entries(self, session_id: Optional[str] = None):
```

**影响文件（已修复）：** `agent/scenario_registry.py`、`agent/device_pool.py`、`mcp/audit_log.py`

---

## 2. 运行环境相关

### 问题：`docker-compose up -d` 起不来

**原因：** Redis 端口 6379 或 Chroma 端口 8001 被占用。

**解决方案：**
```bash
# 检查端口占用
netstat -ano | findstr :6379
netstat -ano | findstr :8001

# 或在 .env 中修改端口
REDIS_PORT=6380
CHROMA_PORT=8002
```

---

### 问题：Windows 上 `pip install` 报依赖冲突（fastapi/pydantic/starlette）

**原因：** 本地已有旧版 fastapi 和 starlette，与 pyautogen 依赖的 pydantic v2 冲突。

**解决方案：**
```bash
pip install --upgrade fastapi starlette
pip install -e ".[dev]"
```

或使用虚拟环境隔离：
```bash
python -m venv venv
venv\Scripts\activate
pip install -e ".[dev]"
```

---

### 问题：运行时找不到 `.env` 文件

**原因：** 未从模板复制 `.env`。

**解决方案：**
```bash
cp .env.example .env
# 编辑 .env，至少填入 LLM_API_KEY
```

---

## 3. Git 相关

### 问题：PowerShell 中 `git add -A && git commit` 报语法错误

**原因：** PowerShell 不支持 `&&` 作为命令分隔符。

**解决方案：** 分步执行：
```bash
git add -A
git commit -m "your message"
```

---

### 问题：git commit 后模型/终端没有反应（进度不更新）

**原因：** `git commit` 在 PowerShell 下返回后偶尔不产生后续输出，导致自动化流程停顿。

**解决方案：** 这不是 Bug——是终端超时行为。运行以下命令确认 commit 是否成功：
```bash
git log --oneline -1
```
如果 commit 已存在，可以手动继续下一步，不需要重来。

---

## 4. Agent 行为相关

### 问题：Diagnostician 总是输出"未检测到已知故障模式"

**原因：** 输入的 raw_output 不包含规则引擎定义的任何关键词（CRC、down、ospf、bgp 等）。

**解决方案：**
1. 确认 Investigator 返回的数据中包含正确的 raw_output 内容
2. 检查 `agent/diagnostician.py` 中的 6 种检测模式的触发条件
3. 如果需要新增检测模式，在 `diagnose()` 方法中添加新的 `if` 块，并同步更新场景剧本的 expected 字段

---

### 问题：Safety Officer 拦截了看似安全的命令

**原因：** 命令包含 `BLOCKED_COMMANDS` 列表中的关键词。`reload`、`reboot`、`write erase` 等在任何情况下都会被拦截。

**解决方案：**
- 如果确实需要执行这些命令（如测试环境），可以临时修改 `agent/safety_officer.py` 的 `BLOCKED_COMMANDS` 列表
- **不要在生产环境这样做**

---

### 问题：案例库搜索不到刚刚确认的案例

**原因：** 案例需要先 `confirm()` 才会进入检索池。草稿区的案例（`confirmed=false`）不参与检索。

**解决方案：**
```python
lib = CaseLibrary()
lib.add_draft("session-xxx", data)
lib.confirm("session-xxx")  # 必须确认
results = lib.search("OSPF")  # 现在可以搜到了
```

---

*如果你踩了新的坑，请追加到本文档。格式：问题 + 原因 + 解决方案。*