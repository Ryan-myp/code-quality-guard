"""
Code Quality Guard v22 - CLI 主程序
"""
import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from engines.spec_parser import SpecParser, ProjectSpec
from engines.enhanced_analyzer import EnhancedAnalyzer, Issue
from engines.quality_gate import QualityGate, GateResult
from engines.fix_suggester import FixSuggester
from engines.feedback_collector import FeedbackCollector


def discover_files(project_path: Path, extensions: List[str] = None) -> List[Path]:
    """发现项目中的源代码文件"""
    if extensions is None:
        extensions = ['.py', '.ts', '.js', '.go', '.rs']
    
    files = []
    for ext in extensions:
        files.extend(project_path.glob(f'**/*{ext}'))
    
    # 排除隐藏目录和虚拟环境
    excluded = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', '.idea'}
    files = [f for f in files if not any(part in excluded for part in f.parts)]
    
    return sorted(files)


def run_analysis(
    project_path: Path,
    spec: ProjectSpec,
    verbose: bool = False
) -> dict:
    """运行完整分析"""
    analyzer = EnhancedAnalyzer(spec)
    gate = QualityGate()
    suggester = FixSuggester()
    
    files = discover_files(project_path)
    all_issues: List[Issue] = []
    file_results = {}
    
    for file_path in files:
        try:
            code = file_path.read_text(encoding='utf-8')
            issues = analyzer.analyze(code, file_path)
            
            if issues:
                file_results[str(file_path)] = [
                    {
                        'rule_id': issue.rule_id,
                        'severity': issue.severity.value,
                        'line': issue.line,
                        'column': issue.column,
                        'message': issue.message,
                        'fix': issue.fix,
                        'confidence': issue.confidence,
                        'context': issue.context,
                    }
                    for issue in issues
                ]
                all_issues.extend(issues)
            
            if verbose:
                print(f"  ✓ {file_path}")
        
        except Exception as e:
            if verbose:
                print(f"  ✗ {file_path}: {e}")
    
    # 运行质量门禁
    gate_result = gate.check(all_issues)
    score = gate.get_score(all_issues)
    badge = gate.get_badge(score)
    
    # 生成修复建议
    suggestions = suggester.prioritize(suggester.suggest_batch(all_issues))
    
    return {
        'project': str(project_path),
        'files_scanned': len(files),
        'files_with_issues': len(file_results),
        'total_issues': len(all_issues),
        'gate_result': gate_result.value,
        'quality_score': score,
        'quality_badge': badge,
        'issues_by_severity': {
            'critical': sum(1 for i in all_issues if i.severity.value == 'critical'),
            'high': sum(1 for i in all_issues if i.severity.value == 'high'),
            'warning': sum(1 for i in all_issues if i.severity.value == 'warning'),
            'info': sum(1 for i in all_issues if i.severity.value == 'info'),
        },
        'file_results': file_results,
        'suggestions': suggestions,
        'summary': analyzer.get_summary(),
    }


def main():
    parser = argparse.ArgumentParser(
        description='Code Quality Guard - AI Coding Agent 代码质量守护',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 扫描项目
  python qguard.py /path/to/project
  
  # 详细输出
  python qguard.py /path/to/project --verbose
  
  # 生成规范文档
  python qguard.py . --spec-only --output spec.yaml
  
  # 生成 Agent 规则
  python qguard.py . --agent-rules --output rules.yaml
  
  # 生成 SARIF 报告
  python qguard.py /path/to/project --sarif --output report.sarif
        """
    )
    
    parser.add_argument('path', help='项目路径或文件路径')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')
    parser.add_argument('--spec-only', action='store_true', help='仅生成规范文档')
    parser.add_argument('--agent-rules', action='store_true', help='生成 Agent 规则')
    parser.add_argument('--sarif', action='store_true', help='生成 SARIF 报告')
    parser.add_argument('--output', '-o', help='输出文件路径')
    parser.add_argument('--config', '-c', help='规范配置文件路径')
    
    args = parser.parse_args()
    
    project_path = Path(args.path).resolve()
    
    if not project_path.exists():
        print(f"错误: 路径不存在: {project_path}", file=sys.stderr)
        sys.exit(1)
    
    # 加载规范
    spec_parser = SpecParser()
    if args.config:
        spec = spec_parser.load(Path(args.config))
    else:
        spec = spec_parser.auto_generate(project_path)
    
    # 仅生成规范
    if args.spec_only:
        output_path = Path(args.output) if args.output else project_path / 'spec.yaml'
        spec_parser.spec = spec
        spec_parser.save(output_path)
        print(f"✓ 规范已保存到: {output_path}")
        return
    
    # 运行分析
    print(f"\n🔍 Code Quality Guard v22")
    print(f"📁 项目: {project_path}")
    print(f"📝 语言: {spec.language}")
    print("=" * 60)
    
    result = run_analysis(project_path, spec, args.verbose)
    
    # 输出结果
    if args.sarif:
        # 生成 SARIF 报告
        from engines.sarif_generator import generate_sarif
        sarif = generate_sarif(result, project_path)
        output_path = Path(args.output) if args.output else project_path / 'report.sarif.json'
        output_path.write_text(json.dumps(sarif, indent=2, ensure_ascii=False))
        print(f"\n✓ SARIF 报告已保存到: {output_path}")
    
    elif args.agent_rules:
        # 生成 Agent 规则
        from engines.agent_ruleset import generate_agent_rules
        rules = generate_agent_rules(result)
        output_path = Path(args.output) if args.output else project_path / 'agent_rules.yaml'
        import yaml
        with open(output_path, 'w') as f:
            yaml.dump(rules, f, default_flow_style=False, allow_unicode=True)
        print(f"\n✓ Agent 规则已保存到: {output_path}")
    
    else:
        # 输出摘要
        print(f"\n📊 分析结果:")
        print(f"   扫描文件: {result['files_scanned']}")
        print(f"   发现问题: {result['total_issues']}")
        print(f"   质量评分: {result['quality_score']} ({result['quality_badge']})")
        print(f"   门禁状态: {result['gate_result'].upper()}")
        
        print(f"\n📈 问题分布:")
        for severity, count in result['issues_by_severity'].items():
            if count > 0:
                emoji = {'critical': '🔴', 'high': '🟠', 'warning': '🟡', 'info': '⚪'}[severity]
                print(f"   {emoji} {severity.upper()}: {count}")
        
        if result['suggestions']:
            print(f"\n🔧 优先修复建议:")
            for i, suggestion in enumerate(result['suggestions'][:5], 1):
                print(f"   {i}. [{suggestion['severity']}] {suggestion['rule_id']}")
                print(f"      行 {suggestion['line']}: {suggestion['message']}")
                if suggestion.get('suggestions'):
                    print(f"      建议: {suggestion['suggestions'][0][1]}")
    
    # 保存完整结果
    if args.output and not (args.sarif or args.agent_rules):
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\n✓ 结果已保存到: {output_path}")
    
    # 返回退出码
    if result['gate_result'] == 'fail':
        sys.exit(2)
    elif result['gate_result'] == 'warn':
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
