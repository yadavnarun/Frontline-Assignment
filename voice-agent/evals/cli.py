from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from evals.harness.runner import discover_scripts, run_suite
from evals.harness.tool_parity import assert_harness_parity, production_tool_schemas
from evals.reporting.report_builder import build, write


VOICE_ROOT = Path(__file__).resolve().parent.parent
EVAL_ROOT = Path(__file__).resolve().parent


def _pytest(*paths: str) -> int:
    env = os.environ | {
        "SUPABASE_URL": "http://test-suite.local",
        "SUPABASE_SERVICE_ROLE_KEY": "test-key",
    }
    return subprocess.run([sys.executable, "-m", "pytest", *paths, "-q"], env=env).returncode


def scripted(output: Path, trials: int, workers: int = 1) -> int:
    if trials < 1:
        raise ValueError("--trials must be positive")
    results = run_suite(discover_scripts(), trials, workers)
    report = build(results)
    write(report, output)
    for result in report["results"]:
        marker = "PASS" if result["script_classification_correct"] else "FAIL"
        print(f"{marker} {result['script']} trial={result['trial']}: {result['failed_assertions'] or 'no failures'}")
    print(f"Reports: {output}")
    return 0 if report["summary"]["classification_failures"] == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Safe Frontline text-agent evaluations")
    parser.add_argument("command", choices=("contracts", "scripted", "characterize", "offline", "live"))
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--workers", type=int, default=1, help="isolated worker processes")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or EVAL_ROOT / "results" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if args.command == "contracts":
        schemas = production_tool_schemas(VOICE_ROOT)
        assert_harness_parity(VOICE_ROOT, schemas)
        print("PASS production tool-schema parity")
        return 0
    if args.command == "scripted":
        return scripted(output, args.trials, args.workers)
    if args.command == "characterize":
        return _pytest("evals/characterization")
    if args.command == "live":
        print("NOT RUN: No model API credentials are available")
        return 0

    statuses = [
        _pytest("evals/tests"),
        _pytest("evals/characterization"),
        scripted(output, args.trials, args.workers),
    ]
    return 1 if any(statuses) else 0


if __name__ == "__main__":
    raise SystemExit(main())
