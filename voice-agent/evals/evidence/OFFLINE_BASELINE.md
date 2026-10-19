# Offline baseline — 2026-10-19

Run from `voice-agent/`:

```bash
../.venv/bin/python -m evals.cli offline --trials 2 --workers 2 \
  --output evals/results/final-verification
```

## Result

- 62/62 scripted grader assessments were correct across 31 scripts and two
  isolated trials each.
- All 15 scenarios were represented: critical 38/38, high 16/16, medium 8/8.
- Thirty-five harness/grader/isolation tests and eleven real-handler characterization
  tests passed.
- Production tool-schema parity passed.
- Live-model coverage was `NOT RUN` because no model API credential is
  available; it is excluded from pass rates.
- Generated artifacts: `report.json`, `summary.md`, and 62 complete JSON traces
  under the ignored `evals/results/final-verification/` run directory.

The repeated scripted pass rate establishes deterministic harness consistency;
it is not evidence that a live model behaves perfectly. Known production gaps
confirmed by characterization are: no backend ceiling enforcement, no backend
contact-name enforcement for a regular agreement, no backend verified-carrier
guard on transfer, and a retried `record_agreement` submitting a second quote.

Repository regression checks also passed:

- `voice-agent`: 62 tests and 17 subtests;
- `shared`: 91 tests.
