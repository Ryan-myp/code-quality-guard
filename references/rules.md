# 规则详解

## 安全规则（Critical）

### security.eval_exec
- **触发条件**: 代码中使用 `eval()` 或 `exec()`
- **风险等级**: Critical
- **修复建议**: 使用 `json.loads()` 或 `ast.literal_eval()`
- **置信度**: 0.95

### security.hardcoded_secret
- **触发条件**: 硬编码密码、API 密钥、token
- **风险等级**: Critical
- **修复建议**: 使用环境变量或密钥管理服务
- **置信度**: 0.90

### security.sql_injection
- **触发条件**: SQL 语句中包含字符串拼接
- **风险等级**: Critical
- **修复建议**: 使用参数化查询
- **置信度**: 0.85

### security.ssl_disabled
- **触发条件**: `verify=False` 或未启用 SSL 验证
- **风险等级**: Critical
- **修复建议**: 启用 SSL 验证
- **置信度**: 0.95

### security.command_injection
- **触发条件**: 使用 `os.system()` 或字符串拼接命令
- **风险等级**: Critical
- **修复建议**: 使用 subprocess 参数列表
- **置信度**: 0.90

## 错误处理规则（High）

### ai_slop.bare_except
- **触发条件**: 裸 `except:` 无异常类型
- **风险等级**: High
- **修复建议**: 捕获具体异常类型
- **置信度**: 0.95

### ai_slop.swallow_exception
- **触发条件**: `except` 后仅有 `pass`
- **风险等级**: High
- **修复建议**: 记录日志并重新抛出
- **置信度**: 0.90

### ai_slop.generic_exception
- **触发条件**: 捕获 `Exception` 而非具体类型
- **风险等级**: High
- **修复建议**: 捕获具体异常
- **置信度**: 0.85

## 代码质量规则（Warning）

### code_quality.function_too_long
- **触发条件**: 函数超过 50 行
- **风险等级**: Warning
- **修复建议**: 拆分为多个小函数
- **置信度**: 0.80

### code_quality.too_many_parameters
- **触发条件**: 参数超过 7 个
- **风险等级**: Warning
- **修复建议**: 使用对象封装参数
- **置信度**: 0.85

### code_quality.deep_nesting
- **触发条件**: 嵌套深度超过 4 层
- **风险等级**: Warning
- **修复建议**: 提取为独立函数
- **置信度**: 0.80

### ai_slop.redundant_todo
- **触发条件**: TODO/FIXME 超过 30 天未处理
- **风险等级**: Info
- **修复建议**: 创建任务或直接修复
- **置信度**: 0.70
