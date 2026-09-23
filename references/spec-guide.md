# 规范定义指南

## 什么是规范（Spec）？

规范是项目质量标准的定义文件，告诉 Code Quality Guard 如何检查代码。

## 规范格式

```yaml
# spec.yaml
name: my-project
language: python

security:
  max_severity: critical  # 只报告 critical 及以上
  ignore_patterns:
    - "test_*.py"         # 测试文件不检查
    - "__init__.py"       # 包初始化文件忽略
  allowed_eval_contexts:
    - "ast.literal_eval"  # 允许的 eval 替代方案

code_quality:
  max_function_length: 50      # 函数最大行数
  max_nesting_depth: 4         # 最大嵌套深度
  max_parameters: 7            # 最大参数数量
  max_line_length: 100         # 最大行长度
  require_docstrings: true     # 是否要求文档字符串
  max_todo_age_days: 30        # TODO 最长保留天数

feedback:
  enable_learning: true        # 启用反馈学习
  min_confidence: 0.7          # 最低置信度
```

## 自动推断

如果不需要自定义规范，可以运行：

```bash
python scripts/qguard.py . --spec-only
```

会根据项目结构自动生成默认规范。

## 规范层级

1. **项目级** (`spec.yaml`): 项目整体规范
2. **模块级** (`modules/*/spec.yaml`): 特定模块的规范
3. **文件级** (文件头部注释): 单个文件的特殊规范

## 最佳实践

1. **从严格开始**：先用默认规范，根据反馈调整
2. **逐步放宽**：不要一次性禁用所有规则
3. **团队共识**：规范应该经过团队讨论
4. **定期审查**：每季度回顾一次规范有效性
