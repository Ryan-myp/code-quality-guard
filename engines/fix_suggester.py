"""
修复建议生成器
"""
from typing import List, Optional, Dict
from .enhanced_analyzer import Issue, Severity


class FixSuggester:
    """修复建议生成器"""
    
    # 修复模板库
    FIX_TEMPLATES = {
        'security.eval_exec': {
            'template': '将 eval() 替换为安全的替代方案',
            'examples': [
                ('eval(user_input)', 'json.loads(user_input)'),
                ('eval(code)', 'ast.literal_eval(code)'),
            ]
        },
        'security.hardcoded_secret': {
            'template': '使用环境变量或密钥管理服务',
            'examples': [
                ('password = "secret"', "password = os.environ.get('PASSWORD')"),
                ('api_key = "sk-xxx"', "api_key = get_secret('api_key')"),
            ]
        },
        'security.sql_injection': {
            'template': '使用参数化查询',
            'examples': [
                ("f'SELECT * FROM users WHERE id = {user_id}'",
                 "cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))"),
            ]
        },
        'security.ssl_disabled': {
            'template': '启用 SSL 验证',
            'examples': [
                ('requests.get(url, verify=False)', 'requests.get(url, verify=True)'),
            ]
        },
        'security.command_injection': {
            'template': '使用 subprocess.run() 参数列表',
            'examples': [
                ('os.system(cmd)', 'subprocess.run(cmd.split())'),
                ('subprocess.call(cmd, shell=True)', 'subprocess.run(cmd)'),
            ]
        },
        'ai_slop.bare_except': {
            'template': '捕获具体异常类型',
            'examples': [
                ('except:', 'except ValueError:'),
                ('except:', 'except (ValueError, TypeError):'),
            ]
        },
        'ai_slop.swallow_exception': {
            'template': '记录日志并重新抛出',
            'examples': [
                ('except:\n    pass', 'except Exception as e:\n    logger.error(f"Error: {e}")\n    raise'),
            ]
        },
        'code_quality.function_too_long': {
            'template': '拆分为多个小函数',
            'examples': [
                # 示例由 Agent 根据上下文生成
            ]
        },
        'code_quality.too_many_parameters': {
            'template': '使用对象封装参数',
            'examples': [
                ('def func(a, b, c, d, e, f, g, h):', 
                 'def func(params: MyParams):\n    ...'),
            ]
        },
        'code_quality.deep_nesting': {
            'template': '提取为独立函数或使用 early return',
            'examples': [
                # 示例由 Agent 根据上下文生成
            ]
        },
    }
    
    def suggest(self, issue: Issue) -> Dict[str, str]:
        """为单个问题生成修复建议"""
        rule_id = issue.rule_id
        
        # 查找匹配的模板
        template_data = self.FIX_TEMPLATES.get(rule_id)
        
        if template_data:
            return {
                'rule_id': rule_id,
                'template': template_data['template'],
                'severity': issue.severity.value,
                'line': issue.line,
                'message': issue.message,
                'original': issue.context,
                'suggestions': template_data['examples'][:3],  # 最多 3 个示例
            }
        
        # 如果没有匹配模板，使用通用建议
        return {
            'rule_id': rule_id,
            'template': '请根据上下文手动修复',
            'severity': issue.severity.value,
            'line': issue.line,
            'message': issue.message,
            'original': issue.context,
            'suggestions': [],
        }
    
    def suggest_batch(self, issues: List[Issue]) -> List[Dict[str, str]]:
        """批量生成修复建议"""
        return [self.suggest(issue) for issue in issues]
    
    def prioritize(self, suggestions: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """按优先级排序建议"""
        severity_order = {
            'critical': 0,
            'high': 1,
            'warning': 2,
            'info': 3,
        }
        
        return sorted(
            suggestions,
            key=lambda x: severity_order.get(x['severity'], 99)
        )
