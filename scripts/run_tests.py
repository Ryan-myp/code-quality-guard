"""
测试运行器
"""
import json
import sys
import yaml
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from engines.spec_parser import SpecParser
from engines.enhanced_analyzer import EnhancedAnalyzer


def load_test_cases(test_file: Path) -> List[Dict[str, Any]]:
    """加载测试用例"""
    with open(test_file, 'r') as f:
        data = yaml.safe_load(f)
    return data.get('test_cases', [])


def run_test_case(test_case: Dict[str, Any]) -> Dict[str, Any]:
    """运行单个测试用例"""
    spec = SpecParser().load()
    analyzer = EnhancedAnalyzer(spec)
    
    code = test_case['code']
    issues = analyzer.analyze(code)
    
    # 验证预期结果
    passed = True
    errors = []
    
    for expected in test_case.get('expected_issues', []):
        rule_id = expected['rule_id']
        expected_count = expected.get('count', 1)
        
        actual_count = sum(1 for i in issues if i.rule_id == rule_id)
        
        if actual_count != expected_count:
            passed = False
            errors.append(
                f"Rule {rule_id}: expected {expected_count}, got {actual_count}"
            )
    
    # 检查是否有意外的额外问题
    expected_rules = {e['rule_id'] for e in test_case.get('expected_issues', [])}
    actual_rules = {i.rule_id for i in issues}
    unexpected = actual_rules - expected_rules
    
    if unexpected:
        passed = False
        errors.append(f"Unexpected issues: {unexpected}")
    
    return {
        'test_id': test_case['id'],
        'name': test_case['name'],
        'passed': passed,
        'errors': errors,
        'issues_found': len(issues),
    }


def main():
    print("\n" + "=" * 60)
    print("🧪 Code Quality Guard v22 测试套件")
    print("=" * 60 + "\n")
    
    # 加载测试用例
    test_file = Path(__file__).parent.parent / 'tests' / 'test_cases_v22.yaml'
    if not test_file.exists():
        print(f"❌ 测试用例文件不存在: {test_file}")
        sys.exit(1)
    
    test_cases = load_test_cases(test_file)
    print(f"📊 测试用例数: {len(test_cases)}\n")
    
    # 运行测试
    results = []
    for test_case in test_cases:
        result = run_test_case(test_case)
        results.append(result)
        
        status = "✅" if result['passed'] else "❌"
        print(f"{status} {result['name']}")
        if not result['passed']:
            for error in result['errors']:
                print(f"   └─ {error}")
    
    # 统计
    passed_count = sum(1 for r in results if r['passed'])
    total_count = len(results)
    
    print(f"\n{'=' * 60}")
    print(f"📈 测试结果: {passed_count}/{total_count} 通过")
    print(f"{'=' * 60}\n")
    
    if passed_count == total_count:
        print("🎉 所有测试通过！\n")
        sys.exit(0)
    else:
        print(f"⚠️ {total_count - passed_count} 个测试失败\n")
        sys.exit(1)


if __name__ == '__main__':
    main()
