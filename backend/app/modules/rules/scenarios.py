"""Scenario runner entry point: `python -m app.modules.rules.scenarios <rules_dir>` (`make eval-rules`).

The evaluator and the real runner arrive in M6 (docs/build-plan.md). Until then this gate passes only while
`rules/scenarios/` is empty, so a CA-verified scenario can never be silently skipped.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m app.modules.rules.scenarios <rules_dir>", file=sys.stderr)  # noqa: T201
        return 2
    scenarios = sorted((Path(argv[1]) / "scenarios").glob("*.yaml"))
    if scenarios:
        print(  # noqa: T201
            f"eval-rules: {len(scenarios)} scenario(s) found but the evaluator lands in M6; failing so none is skipped",
            file=sys.stderr,
        )
        return 1
    print("eval-rules: 0 scenarios (the evaluator lands in M6)")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
