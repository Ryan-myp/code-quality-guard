# Feedback Storage

`engines.feedback_collector.FeedbackCollector` stores user-reviewed feedback locally in `.qguard/feedback.json` by default. It can summarize false-positive reports and export a JSON report.

This storage helper does **not** connect to the CLI, change rule thresholds, train a model, or automatically tune rules. Invalid feedback files raise an error instead of being silently discarded. The collector does not persist source code, but feedback reasons and user IDs may contain personal or sensitive information; review the file before sharing it.

```python
from engines.feedback_collector import Feedback, FeedbackCollector

collector = FeedbackCollector()
collector.collect(
    Feedback(
        issue_id="finding-123",
        rule_id="security.eval_exec",
        false_positive=True,
        reason="The call is to ast.literal_eval, not the builtin eval.",
        timestamp="2026-09-24T12:00:00Z",
    )
)
report_path = collector.export_report()
```

Delete `.qguard/feedback.json` to remove locally stored feedback.
