# 文档导航 — Documentation Index

> **谁该读什么——按角色和场景索引。**

---

## 文档地图

```
troublerouting_agent/
├── README.md                     ← 所有人第一眼
│
├── docs/
│   ├── README.md                 ← 📍 你在这里（文档索引）
│   ├── PRD.md                    ← 产品需求文档
│   ├── ADR.md                    ← 29 条架构决策记录
│   ├── ARCHITECTURE.md           ← 系统设计原理
│   ├── PROJECT.md                ← 完整项目文档
│   ├── DEVELOPMENT.md            ← 开发者扩展指南
│   ├── TROUBLESHOOTING.md        ← 故障排除指南
│   └── OPS.md                    ← 运维手册
│
└── BOARD.md                      ← 任务看板（13/13 ✅）
```

---

## 按角色推荐阅读顺序

### 🆕 新成员（第一天入职）

| 顺序 | 文档 | 时间 | 目的 |
|------|------|------|------|
| 1 | `README.md` | 5 min | 知道项目是什么、怎么跑起来 |
| 2 | `docs/PRD.md` 第 1-2 章 | 10 min | 理解项目背景和用户故事 |
| 3 | `docs/ARCHITECTURE.md` 第 1-2 章 | 15 min | 理解意图识别和排障流程 |
| 4 | `docs/ADR.md` 按类别浏览 | 30 min | 理解为什么这样设计 |
| 5 | `docs/DEVELOPMENT.md` | 15 min | 知道怎么改代码 |

**第一天目标：** 能把项目跑起来，理解 6 Agent 的协作流程，知道「为什么 Safety Officer 不是 LLM」。

---

### 🔧 开发者（要改代码）

| 你在做什么 | 读这份 |
|-----------|--------|
| 加新的设备厂商 | `docs/DEVELOPMENT.md` 第 1 章 |
| 加新的故障诊断场景 | `docs/DEVELOPMENT.md` 第 2 章 |
| 改诊断规则 | `docs/DEVELOPMENT.md` 第 3 章 |
| 加新的 Agent | `docs/DEVELOPMENT.md` 第 4 章 |
| 理解某个设计为什么这样 | `docs/ADR.md`（搜索关键词） |
| 理解数据流 | `docs/ARCHITECTURE.md` 第 6 章 |
| 理解上下文管理 | `docs/ARCHITECTURE.md` 第 3 章 |
| 理解 RAG 怎么接 | `docs/ARCHITECTURE.md` 第 4 章 |

---

### 🏗️ 架构师（要评审设计）

| 你在做什么 | 读这份 |
|-----------|--------|
| 评审新增设计决策 | `docs/ADR.md`（看是否有冲突的旧决策） |
| 追加新的 ADR | `docs/ADR.md` 顶部的「如何使用 ADR」 |
| 理解系统设计原理 | `docs/ARCHITECTURE.md` 全文 |
| 理解安全模型 | `docs/ARCHITECTURE.md` 第 8 章 |
| 评估 Phase 2 迁移风险 | `docs/ADR.md` 中标记 ⚠️ Phase 2 重审的条目 |

---

### 🚨 值班/运维（系统出问题了）

| 你在做什么 | 读这份 |
|-----------|--------|
| pytest 卡住了 | `docs/TROUBLESHOOTING.md` 第 1 章 |
| docker-compose 起不来 | `docs/TROUBLESHOOTING.md` 第 2 章 |
| git commit 后没反应 | `docs/TROUBLESHOOTING.md` 第 3 章 |
| Diagnostician 总是输出"未知模式" | `docs/TROUBLESHOOTING.md` 第 4 章 |
| 健康检查 | `docs/OPS.md` 第 1 章 |
| 数据库恢复 | `docs/OPS.md` 第 2 章 |
| 看日志 | `docs/OPS.md` 第 3 章 |

---

### 📋 产品经理/项目经理

| 你在做什么 | 读这份 |
|-----------|--------|
| 理解产品功能范围 | `docs/PRD.md` |
| 看当前进度 | `BOARD.md`（全部 ✅） |
| 看技术决策理由 | `docs/ADR.md`（只需读背景和决策部分） |
| 看已知限制 | `docs/PROJECT.md` 第 12 章 |

---

## 文档维护规则

| 文档 | 触发更新的条件 |
|------|---------------|
| `README.md` | 项目名/描述/启动方式变了 |
| `PRD.md` | 产品功能需求变了 |
| `ADR.md` | 做了新的架构决策 |
| `ARCHITECTURE.md` | 核心设计原理变了（如换框架） |
| `PROJECT.md` | 新增模块、测试数据变了 |
| `DEVELOPMENT.md` | 扩展方式变了 |
| `TROUBLESHOOTING.md` | **任何人踩了新坑** → 立刻追加 |
| `OPS.md` | 部署方式/监控/备份策略变了 |
| `BOARD.md` | 新 Ticket 开始或完成 |

---

## 文档之间的引用关系

```
README.md
  ├→ PRD.md（项目背景）
  ├→ ADR.md（设计理由）
  └→ PROJECT.md（完整文档）

ARCHITECTURE.md（系统设计原理）
  ├→ ADR.md（引用决策编号，如 ADR-019）
  └→ DEVELOPMENT.md（引用扩展入口）

DEVELOPMENT.md（怎么改代码）
  ├→ ARCHITECTURE.md（引用设计原理）
  └→ ADR.md（引用决策背景）

TROUBLESHOOTING.md（踩坑记录）
  └→ 引用 commit hash 定位修复版本
```

---

*这份索引本身也应该被维护——如果有新文档加入，在这里加一行。*