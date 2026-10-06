"""Rule file validation: `python -m app.modules.rules.validate <rules_dir>` (used by `make rules-validate`).

Checks, for `rules/examples/*.yaml` (format only) and every file under `rules/published/`:
1. the file matches `rules/schema/rule.schema.json` (dates normalised to ISO strings first: PyYAML turns
   `2026-01-01` into a date object, which JSON Schema would reject);
2. every fact the rule reads (`fact:` in conditions, schedule `anchor` / `start_anchor`) exists in
   `rules/facts.yaml`;
3. published rules carry a CA review (`review.reviewed_by` and `review.reviewed_on`), never filled by code;
4. no two files share the same (id, version).

The evaluator itself arrives in M6; this module only checks files.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator


@dataclass
class Report:
    checked: int = 0
    errors: list[str] = field(default_factory=list)

    def add(self, path: Path, message: str) -> None:
        self.errors.append(f"{path}: {message}")


def normalise(value: Any) -> Any:
    """Convert YAML-parsed dates back to ISO strings, recursively."""
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: normalise(v) for k, v in value.items()}
    if isinstance(value, list):
        return [normalise(v) for v in value]
    return value


def fact_references(rule: dict[str, Any]) -> Iterator[str]:
    """Every fact key a rule reads: condition leaves plus schedule anchors."""

    def walk(node: Any) -> Iterator[str]:
        if isinstance(node, dict):
            if isinstance(node.get("fact"), str):
                yield node["fact"]
            for value in node.values():
                yield from walk(value)
        elif isinstance(node, list):
            for item in node:
                yield from walk(item)

    yield from walk(rule.get("applies_if", {}))
    schedule = (rule.get("obligation") or {}).get("schedule") or {}
    for key in ("start_anchor",):
        if isinstance(schedule.get(key), str):
            yield schedule[key]
    due = schedule.get("due") or {}
    if isinstance(due.get("anchor"), str):
        yield due["anchor"]


def load_fact_keys(rules_dir: Path) -> set[str]:
    registry = yaml.safe_load((rules_dir / "facts.yaml").read_text(encoding="utf-8")) or {}
    return {fact["key"] for fact in registry.get("facts", [])}


def rule_files(rules_dir: Path) -> Iterator[tuple[Path, bool]]:
    """(path, is_published) for every rule file to check."""
    for path in sorted((rules_dir / "examples").glob("*_rule.yaml")):
        yield path, False
    for path in sorted((rules_dir / "published").rglob("*.yaml")):
        yield path, True


def validate(rules_dir: Path) -> Report:
    schema = json.loads((rules_dir / "schema" / "rule.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    fact_keys = load_fact_keys(rules_dir)
    report = Report()
    seen: dict[tuple[str, int], Path] = {}

    for path, published in rule_files(rules_dir):
        report.checked += 1
        try:
            rule = normalise(yaml.safe_load(path.read_text(encoding="utf-8")))
        except yaml.YAMLError as exc:
            report.add(path, f"not valid YAML: {exc}")
            continue
        if not isinstance(rule, dict):
            report.add(path, "expected a mapping at the top level")
            continue

        for error in sorted(validator.iter_errors(rule), key=lambda e: list(e.absolute_path)):
            where = "/".join(str(p) for p in error.absolute_path) or "(root)"
            report.add(path, f"schema: {where}: {error.message}")

        for key in sorted(set(fact_references(rule)) - fact_keys):
            report.add(path, f"unknown fact '{key}' (add it to rules/facts.yaml first)")

        if published:
            review = rule.get("review") or {}
            if not review.get("reviewed_by") or not review.get("reviewed_on"):
                report.add(
                    path, "published rule without a CA review (review.reviewed_by / reviewed_on)"
                )

        ident = (str(rule.get("id")), int(rule.get("version") or 0))
        if ident in seen:
            report.add(path, f"duplicate id/version {ident} (also in {seen[ident]})")
        seen[ident] = path

    return report


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m app.modules.rules.validate <rules_dir>", file=sys.stderr)  # noqa: T201
        return 2
    report = validate(Path(argv[1]))
    for line in report.errors:
        print(line, file=sys.stderr)  # noqa: T201
    print(f"rules-validate: {report.checked} file(s) checked, {len(report.errors)} error(s)")  # noqa: T201
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
