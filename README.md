# Code Quality Guard v22

> **规范前置 · 过程指导 · 结果验证**

AI Coding Agent 的代码质量守护系统。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-22.0.0--alpha-orange.svg)](https://github.com/Ryan-myp/code-quality-guard)

---

## 🎯 核心目标

**指导 AI 写出更好的代码**，而非阻止 AI 写代码。

通过「规范前置 + 过程指导 + 结果验证」三重机制，帮助 AI Coding Agent：
- 在编码前理解质量标准
- 在编码中获得实时指导
- 在编码后自动验证结果
- 通过反馈持续学习进化

---

## 🚀 快速开始

### 安装

```bash
pip install -e .
```

### 扫描项目

```bash
# 基本扫描
python scripts/qguard.py /path/to/project

# 详细输出
python scripts/qguard.py /path/to/project --verbose

# 生成 Agent 规则
python scripts/qguard.py . --agent-rules --output rules.yaml
```

### 生成规范文档

```bash
# 基于项目自动生成规范
python scripts/qguard.py . --spec-only --output spec.yaml
```

---

## 📊 核心指标

| 指标 | 值 | 目标 | 状态 |
|------|-----|------|------|
| 样本数 | **228** | 100+ | ✅ |
| 精确率 | **待定** | ≥80% | ⏳ |
| 召回率 | **待定** | ≥70% | ⏳ |
| 误报率 | **<10%** | <20% | ⏳ |

> ⚠️ 当前版本处于 Alpha 学习阶段，指标正在通过真实样本验证中。

---

## 🔍 检测能力

### 安全规则（Critical）

| 规则 ID | 描述 | 修复建议 |
|---------|------|----------|
| `security.eval_exec` | 禁止 eval()/exec() | 使用 `json.loads()` 或 `ast.literal_eval()` |
| `security.hardcoded_secret` | 禁止硬编码密码/密钥 | 使用环境变量或密钥管理 |
| `security.sql_injection` | 检测 SQL 注入 | 使用参数化查询 |
| `security.ssl_disabled` | 检测 SSL 验证禁用 | 启用 SSL 验证 |
| `security.command_injection` | 检测命令注入 | 使用 subprocess 参数列表 |

### 错误处理规则（High）

| 规则 ID | 描述 | 修复建议 |
|---------|------|----------|
| `ai_slop.bare_except` | 禁止裸 except | 捕获具体异常类型 |
| `ai_slop.swallow_exception` | 禁止吞没异常 | 记录日志并重新抛出 |
| `ai_slop.generic_exception` | 推荐具体异常类型 | 捕获具体异常而非 Exception |

### 代码质量规则（Warning）

| 规则 ID | 描述 | 修复建议 |
|---------|------|----------|
| `code_quality.function_too_long` | 函数过长 | 拆分为多个小函数 |
| `code_quality.too_many_parameters` | 参数过多 | 使用对象封装参数 |
| `code_quality.deep_nesting` | 嵌套过深 | 提取为独立函数 |
| `ai_slop.redundant_todo` | 冗余 TODO/FIXME | 直接修复或创建任务 |

---

## 📁 项目结构

```
code-quality-guard/
├── SKILL.md              # Skill 定义（给 Agent 看）
├── README.md             # 项目说明（给人看）
├── LICENSE               # MIT 许可证
├── pyproject.toml        # Python 项目配置
├── scripts/
│   └── qguard.py         # 主程序
├── engines/
│   ├── spec_parser.py         # 规范解析器
│   ├── enhanced_analyzer.py   # AST + 文本分析
│   ├── quality_gate.py        # 质量门禁
│   ├── fix_suggester.py       # 修复建议生成
│   └── feedback_collector.py  # 反馈收集
├── rules/
│   ├── v22/                     # v22 规则定义
│   └── agent/                   # Agent 规则输出
├── tests/
│   └── test_cases.yaml          # 测试用例
├── references/                  # 参考文档
│   ├── spec-guide.md
│   ├── rules.md
│   ├── feedback.md
│   └── best-practices.md
└── benchmarks/                  # 基准测试样本
    └── v22/
        └── annotated_samples.json
```

---

## 🎯 设计哲学

### 1. 规范前置（Define）

在编码开始前，明确项目的质量标准：
- 安全基线
- 代码风格
- 架构约束
- 性能要求

### 2. 过程指导（Build）

在编码过程中，提供即时反馈：
- 实时提示潜在问题
- 提供修复建议
- 解释为什么这样不好

### 3. 结果验证（Verify）

在提交前，自动运行检查：
- 静态分析
- 规则匹配
- 置信度评分
- 质量门禁

### 4. 持续学习（Learn）

通过反馈不断优化：
- 收集误报/漏报
- 调整规则阈值
- 更新检测策略

---

## 📚 参考文档

- [规范定义指南](references/spec-guide.md)
- [规则详解](references/rules.md)
- [反馈收集](references/feedback.md)
- [最佳实践](references/best-practices.md)

---

## 🎯 底线

> 在证明自己能准确检测之前，
> 不夸大、不承诺、不伪装。

**当前位置：** Alpha 学习系统 — 通过数据验证  
**核心目标：** 指导 AI 写出好的代码

---

## 📝 许可证

MIT License

---

*最后更新：2026-09-23*
