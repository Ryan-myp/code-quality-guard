import json

import pytest

from engines.feedback_collector import Feedback, FeedbackCollector


def make_feedback(issue_id="issue-1"):
    return Feedback(
        issue_id=issue_id,
        rule_id="security.eval_exec",
        false_positive=False,
        reason="confirmed",
        timestamp="2026-09-24T00:00:00Z",
    )


def test_feedback_is_persisted_and_reloaded(tmp_path):
    path = tmp_path / "feedback.json"
    FeedbackCollector(path).collect(make_feedback())

    loaded = FeedbackCollector(path)

    assert loaded.feedbacks == [make_feedback()]
    assert loaded.get_statistics()["total"] == 1


def test_corrupt_feedback_is_reported_instead_of_silently_discarded(tmp_path):
    path = tmp_path / "feedback.json"
    path.write_text("{broken", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid feedback JSON"):
        FeedbackCollector(path)


def test_invalid_feedback_shape_is_rejected(tmp_path):
    path = tmp_path / "feedback.json"
    path.write_text(
        json.dumps({"feedbacks": [{"issue_id": "missing-fields"}]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Invalid feedback entry"):
        FeedbackCollector(path)


def test_collect_rolls_back_memory_when_persistence_fails(tmp_path, monkeypatch):
    collector = FeedbackCollector(tmp_path / "feedback.json")

    def fail_save(feedbacks=None):
        raise OSError("disk full")

    monkeypatch.setattr(collector, "_save", fail_save)
    with pytest.raises(OSError, match="disk full"):
        collector.collect(make_feedback())

    assert collector.feedbacks == []


def test_export_report_creates_parent_directory(tmp_path):
    collector = FeedbackCollector(tmp_path / "feedback.json")
    output = tmp_path / "reports" / "nested" / "feedback.json"

    returned = collector.export_report(output)

    assert returned == output
    assert json.loads(output.read_text(encoding="utf-8"))["statistics"]["total"] == 0
