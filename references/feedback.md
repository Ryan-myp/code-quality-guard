# 反馈收集指南

## 为什么需要反馈？

反馈是系统学习进化的核心。通过收集误报和漏报，系统可以不断优化规则阈值。

## 如何提交反馈？

### 方式 1：命令行
```bash
python scripts/qguard.py /path/to/project --feedback-rule=security.eval_exec --feedback-type=false-positive
```

### 方式 2：交互式
分析完成后，系统会询问是否提交反馈：
```
是否提交反馈？(y/n): y
规则: security.eval_exec
反馈类型: [误报] [漏报] [建议改进]
原因: 
```

### 方式 3：直接编辑
编辑 `.qguard/feedback.json` 文件：
```json
{
  "feedbacks": [
    {
      "issue_id": "abc123",
      "rule_id": "security.eval_exec",
      "false_positive": true,
      "reason": "这是动态表单渲染，必须使用 eval",
      "timestamp": "2026-09-23T10:00:00Z"
    }
  ]
}
```

## 反馈的用途

1. **误报检测**: 识别过严的规则
2. **漏报发现**: 发现遗漏的检测场景
3. **阈值调整**: 自动优化规则参数
4. **规则进化**: 长期积累优化方向

## 隐私说明

- 反馈仅存储在本地，不会上传到服务器
- 不包含代码内容，只包含元数据
- 可以手动删除 `.qguard/feedback.json`
