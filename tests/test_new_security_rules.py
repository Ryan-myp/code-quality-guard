"""
增强分析器测试 - v22 新增规则
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "engines"))

from enhanced_analyzer import EnhancedAnalyzer, Severity


def test_exec_detection():
    """测试 exec() 检测"""
    analyzer = EnhancedAnalyzer()
    code = "result = exec(user_input)"
    issues = analyzer.analyze(code)
    
    exec_issues = [i for i in issues if i.rule_id == 'security.exec']
    assert len(exec_issues) > 0, "应该检测到 exec()"
    assert exec_issues[0].severity == Severity.CRITICAL
    
    print("✅ 检测 exec()")


def test_unsafe_deserialization():
    """测试不安全反序列化检测"""
    analyzer = EnhancedAnalyzer()
    
    # yaml.load with Loader
    code1 = "data = yaml.load(f, Loader=yaml.FullLoader)"
    issues1 = analyzer.analyze(code1)
    assert any(i.rule_id == 'security.unsafe_deserialization' for i in issues1)
    
    # pickle.loads
    code2 = "obj = pickle.loads(data)"
    issues2 = analyzer.analyze(code2)
    assert any(i.rule_id == 'security.unsafe_deserialization' for i in issues2)
    
    print("✅ 检测不安全反序列化")


def test_insecure_random():
    """测试不安全随机数检测"""
    analyzer = EnhancedAnalyzer()
    
    code = """
import random
token = random.randint(1, 1000000)
choice = random.choice(['a', 'b', 'c'])
"""
    issues = analyzer.analyze(code)
    random_issues = [i for i in issues if i.rule_id == 'security.insecure_random']
    assert len(random_issues) >= 2, "应该检测到多个不安全随机数使用"
    
    print("✅ 检测不安全随机数")


def test_no_false_positive_safe_code():
    """测试无误报"""
    analyzer = EnhancedAnalyzer()
    
    # 安全的代码
    safe_code = """
import secrets
token = secrets.token_hex(32)
import yaml
data = yaml.safe_load(f)
"""
    issues = analyzer.analyze(safe_code)
    security_issues = [i for i in issues if i.rule_id.startswith('security.')]
    assert len(security_issues) == 0, f"安全代码不应有安全警告，但检测到: {security_issues}"
    
    print("✅ 安全代码无误报")


def test_eval_still_detected():
    """测试 eval() 仍然被检测"""
    analyzer = EnhancedAnalyzer()
    code = "result = eval(user_input)"
    issues = analyzer.analyze(code)
    
    eval_issues = [i for i in issues if i.rule_id == 'security.eval_exec']
    assert len(eval_issues) > 0, "应该检测到 eval()"
    
    print("✅ 检测 eval()")


def test_hardcoded_secret_still_works():
    """测试硬编码密钥检测仍然工作"""
    analyzer = EnhancedAnalyzer()
    code = 'password = "secret123"'
    issues = analyzer.analyze(code)
    
    secret_issues = [i for i in issues if i.rule_id == 'security.hardcoded_secret']
    assert len(secret_issues) > 0, "应该检测到硬编码密码"
    
    print("✅ 检测硬编码密钥")


if __name__ == "__main__":
    test_exec_detection()
    test_unsafe_deserialization()
    test_insecure_random()
    test_no_false_positive_safe_code()
    test_eval_still_detected()
    test_hardcoded_secret_still_works()
    
    print("\n" + "=" * 50)
    print("📈 新增规则测试全部通过!")
    print("=" * 50)
