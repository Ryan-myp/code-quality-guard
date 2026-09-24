"""Load and validate the packaged YAML rule catalog."""

from pathlib import Path
from typing import Any, Dict

import yaml


VALID_SEVERITIES = {"critical", "high", "warning", "info"}


def load_rule_registry() -> Dict[str, Dict[str, Any]]:
    """Load rule metadata from the same catalog shipped in the wheel."""
    rule_path = Path(__file__).resolve().parent.parent / "rules" / "v22" / "v22_rules.yaml"
    with rule_path.open("r", encoding="utf-8") as rule_file:
        catalog = yaml.safe_load(rule_file)
    if not isinstance(catalog, dict) or not isinstance(catalog.get("rules"), list):
        raise ValueError("Rule catalog must contain a rules list")

    registry = {}
    for rule in catalog["rules"]:
        if not isinstance(rule, dict):
            raise ValueError("Each rule catalog entry must be a mapping")
        rule_id = rule.get("id")
        severity = rule.get("severity")
        confidence = rule.get("confidence")
        if not isinstance(rule_id, str) or not rule_id:
            raise ValueError("Every catalog rule must have a non-empty id")
        if rule_id in registry:
            raise ValueError("Duplicate rule id in catalog: {}".format(rule_id))
        if severity not in VALID_SEVERITIES:
            raise ValueError("Invalid severity for catalog rule {}".format(rule_id))
        if (
            isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not 0 <= confidence <= 1
        ):
            raise ValueError("Invalid confidence for catalog rule {}".format(rule_id))
        if not isinstance(rule.get("description"), str) or not rule["description"]:
            raise ValueError("Catalog rule {} is missing a description".format(rule_id))
        if not isinstance(rule.get("category"), str) or not rule["category"]:
            raise ValueError("Catalog rule {} is missing a category".format(rule_id))
        registry[rule_id] = rule
    return registry
