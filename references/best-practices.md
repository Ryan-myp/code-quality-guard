# AI Coding Agent 最佳实践

## 1. 安全优先

### 永远不要信任用户输入
```python
# ❌ 危险
result = eval(user_input)

# ✅ 安全
import ast
result = ast.literal_eval(user_input)
```

### 使用环境变量管理密钥
```python
# ❌ 危险
password = "my_secret_password"

# ✅ 安全
import os
password = os.environ.get('PASSWORD')
```

### 参数化查询
```python
# ❌ 危险
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")

# ✅ 安全
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
```

## 2. 错误处理

### 捕获具体异常
```python
# ❌ 不好
try:
    do_something()
except:
    pass

# ✅ 好
try:
    value = int(user_input)
except ValueError as e:
    logger.warning(f"Invalid input: {user_input}")
    return None
```

### 记录日志并重新抛出
```python
# ❌ 不好
except Exception:
    pass

# ✅ 好
except Exception as e:
    logger.error(f"Error processing: {e}")
    raise
```

## 3. 代码质量

### 保持函数简洁
- 单个函数不超过 50 行
- 参数不超过 7 个
- 单一职责原则

### 避免深层嵌套
```python
# ❌ 不好
def process(items):
    for item in items:
        if item.is_valid:
            if item.has_permission:
                if item.status == 'active':
                    do_something(item)

# ✅ 好
def process(items):
    valid_items = [i for i in items if i.is_valid]
    for item in valid_items:
        if not item.has_permission:
            continue
        if item.status != 'active':
            continue
        do_something(item)
```

## 4. 持续改进

### 定期审查
- 每周审查告警
- 每月审查规则阈值
- 每季度审查整体规范

### 团队共识
- 规范应该由团队讨论确定
- 变更需要团队评审
- 文档化所有决定
