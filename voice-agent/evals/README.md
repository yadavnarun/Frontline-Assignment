# Frontline text-agent evaluations

Run from `voice-agent/` with the repository virtual environment active:

```bash
../.venv/bin/python -m evals.cli offline
```

The offline suite validates production tool parity, trial isolation, all 15
scenarios with known-good and targeted bad scripts, and real-handler
characterization tests—including the current duplicate-quote behavior when
`record_agreement` is retried. Internal handlers stay real; only external
boundaries are replaced. JSON, Markdown, and complete JSON traces are written
to `evals/results/<run-id>/`.

Useful narrower commands are `contracts`, `scripted`, and `characterize`.
Repeat scripted cases with `--trials N`; this measures consistency and never
turns a recurring failure into a pass. Every trial starts from a fresh deep
copy of the declared initial state and outbound network access is blocked.
Use `--workers N` to run trials in separate worker processes; process isolation
prevents environment, module-global, and mock state from crossing parallel
trials while preserving deterministic report order.

Scenario catalogs and scripts are validated before execution. Missing fields,
unknown event types, malformed tool calls, contradictory pass/fail declarations,
and mock results without an earlier tool call fail with the source file path.

Live scenarios are intentionally unavailable without credentials:

```bash
../.venv/bin/python -m evals.cli live --trials 10
```

This reports `NOT RUN`; it does not count the live suite as passed.
