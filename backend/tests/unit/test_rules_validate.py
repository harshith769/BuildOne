from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from app.modules.rules import scenarios
from app.modules.rules.validate import validate

REPO_RULES = Path(__file__).resolve().parents[3] / "rules"


def _copy_rules(tmp_path: Path) -> Path:
    target = tmp_path / "rules"
    shutil.copytree(REPO_RULES, target)
    return target


def _example() -> dict:
    return yaml.safe_load((REPO_RULES / "examples" / "example_rule.yaml").read_text())


def test_repo_rules_are_valid() -> None:
    report = validate(REPO_RULES)
    assert report.errors == []
    assert report.checked >= 1


def test_unknown_fact_is_reported(tmp_path: Path) -> None:
    rules = _copy_rules(tmp_path)
    rule = _example()
    rule["applies_if"]["all"].append({"fact": "made_up_fact", "op": "is_true"})
    (rules / "examples" / "example_rule.yaml").write_text(yaml.safe_dump(rule))
    assert any("unknown fact 'made_up_fact'" in e for e in validate(rules).errors)


def test_published_rule_needs_ca_review(tmp_path: Path) -> None:
    rules = _copy_rules(tmp_path)
    rule = _example() | {"id": "company_law.example_published"}
    (rules / "published" / "company_law").mkdir(parents=True)
    (rules / "published" / "company_law" / "example.yaml").write_text(yaml.safe_dump(rule))
    errors = validate(rules).errors
    assert any("without a CA review" in e for e in errors)


def test_schema_violation_is_reported(tmp_path: Path) -> None:
    rules = _copy_rules(tmp_path)
    rule = _example()
    rule["criticality"] = "whenever"
    (rules / "examples" / "example_rule.yaml").write_text(yaml.safe_dump(rule))
    assert any("schema: criticality" in e for e in validate(rules).errors)


def test_scenario_gate_fails_once_scenarios_exist(tmp_path: Path) -> None:
    rules = _copy_rules(tmp_path)
    assert scenarios.main(["x", str(rules)]) == 0
    (rules / "scenarios" / "scn_one.yaml").write_text("id: scn_one\n")
    assert scenarios.main(["x", str(rules)]) == 1
