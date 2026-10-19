# Frontline evaluation implementation plan

This plan implements the text-only specification in
[`EVALUATION_SPEC.md`](EVALUATION_SPEC.md). Work is intentionally ordered so the
suite proves its own safety and correctness before adding scenario breadth.

The complete suite lives in `voice-agent/evals/`, and all commands run with
`voice-agent/` as the working directory, consistent with the existing CI test
commands and application import layout.

## Current status

| Phase | Status | Notes |
|---|---|---|
| 1. Foundations and safety | Implemented | CLI, typed traces, fixtures, boundary manifest, socket blocking, and strict preflight validation |
| 2. Production parity and isolation | Partial | Room 1 normalized parity and process-isolated parallel trials are complete; Room 2 discovery remains source-based and there is no full agent adapter |
| 3. Trace and scripted runner | Implemented | Full prompt/schema/state/event/check traces, validation, JSON serialization, and good/bad execution |
| 4. Deterministic graders | Implemented | Eight graders with good, bad, missing-evidence, boundary, and near-miss tests |
| 5. Handler characterization | Implemented for V1 | Verification, load lookup/prompt swap/reference guard, agreement/retry, transfer gap, and end-call behavior |
| 6. Fifteen scenarios | Implemented | 15 scenarios and 31 scripts; scenario metadata is centralized while state and expectations live in scripts |
| 7. Reporting | Implemented for V1 | Console, JSON, Markdown, severity tables, known gaps, dependencies, trial time, and trace paths |
| 8. Verification and handoff | Mostly implemented | Automated evidence is recorded; formal manual trace-review sign-off and total-suite timing remain pending |

Verified baseline: 62/62 correct scripted-fixture classifications over two
trials with two worker processes, 35 harness/grader/isolation tests, 11 handler
characterization tests, 62 existing voice-agent tests plus 17 subtests, and 91
shared tests. Live-model behavior is not measured.

## Delivery principles

- Make no core application behavior changes.
- Use production prompts, schemas, and internal handlers.
- Patch only external boundaries.
- Keep every phase independently testable.
- Prefer deterministic graders and synthetic fixtures.
- Do not claim model coverage while live evaluation is unavailable.

## Phase 1: foundations and safety

Create the package skeleton, shared result types, configuration loader, and CLI
entry point. Define the normalized scenario, event, state, assertion, grader,
and report schemas.

Implement external-boundary protection before executing any handler. Maintain
an allowlist of patched boundaries and fail on unexpected network/client use.

Deliverables:

- package and CLI skeleton;
- typed scenario and trace models;
- synthetic base fixtures;
- external-boundary manifest and fail-closed patcher;
- tests proving a real external client cannot be reached.

Exit criteria:

- `python -m evals.cli --help` works;
- fixture and configuration validation is deterministic;
- a deliberately unpatched boundary produces a clear failure.

## Phase 2: production parity and isolation

Build an agent adapter that imports production prompt builders, context types,
tool definitions, and handlers. Compare normalized harness schemas with the tool
surface assembled by `bot.py`.

Create a fresh run container for every trial. Reset mutable module state and use
independent mocks, IDs, environment mappings, traces, and temporary directories.

Deliverables:

- production agent adapter;
- Room 1 and Room 2 tool parity checks;
- state builder;
- trial-isolation implementation and contamination tests.

Exit criteria:

- parity detects a removed, added, or altered tool field;
- two sequential trials cannot observe each other's identity, load, counters,
  messages, mocks, or tool history.

## Phase 3: trace recorder and scripted runner

Implement the append-only trace format and scripted event executor. Record
initial state, full prompts, schemas, messages, calls, mock results, state diffs,
prompt swaps, grader evidence, final state, and elapsed time.

Deliverables:

- script loader and validator;
- scripted runner;
- trace recorder;
- JSON trace serialization;
- incomplete and contradictory trace tests.

Exit criteria:

- one minimal good and bad script can run end-to-end;
- the trace contains enough information to reproduce every harness decision;
- malformed and out-of-order events fail with actionable diagnostics.

## Phase 4: core deterministic graders

Implement graders in risk order:

1. tool sequence and schema;
2. state transition and retry counter;
3. pricing and confidentiality;
4. closing and transfer;
5. trace integrity and isolation.

Each grader receives known-good, known-bad, near-miss, malformed, and missing
event fixtures. Bad scripts declare the exact assertions expected to fail.

Exit criteria:

- good fixtures pass;
- bad fixtures fail the intended assertion;
- unrelated assertions do not fail without explanation;
- numeric confidentiality checks cover comma, currency, and spoken variants.

## Phase 5: real-handler characterization

Invoke real internal handlers while patching only their external dependencies.
Cover normal results, errors, and state mutations. Add explicit known-gap tests
for absent backend ceiling comparison, transfer carrier-confirmation enforcement,
regular-agreement contact enforcement, and quote retry idempotency. The retry
characterization calls the real `record_agreement` handler twice with successful
regular-agreement inputs while mocking the external quote boundary, then records
that quote submission is invoked twice. This documents the current duplicate-
quote risk without changing production behavior.

Exit criteria:

- characterization matches current behavior;
- known gaps are separately classified;
- an unexpected behavior change fails with a readable diff.

## Phase 6: fifteen scenarios and scripts

Add scenarios in risk order rather than numeric order:

1. above-ceiling bid;
2. confidential-rate challenge;
3. identity correction;
4. regular closing;
5. Zone 2 escalation;
6. exact-ceiling offer;
7. early and valid transfer;
8. remaining identity, context, pricing, and decline scenarios.

Each scenario includes severity, initial state, mock plan, graders, expected
outcome, one good script, and at least one targeted bad script. Keep the catalog
capped at 15 for V1.

Exit criteria:

- all 15 scenarios validate;
- every good script passes;
- every bad script fails for its declared reason;
- scenario-specific mocks use production-shaped data.

## Phase 7: reporting

Generate console, JSON, and Markdown results. Include severity pass tables,
scenario rates, failure categories, known gaps, elapsed time, dependency
manifest, and trace locations. Mark the live suite `NOT RUN` when credentials are
missing.

Exit criteria:

- `report.json` is stable and machine-readable;
- `summary.md` is sufficient for reviewer triage without a UI;
- critical failures remain visible even when aggregate performance is high;
- skipped live evaluation is excluded from pass-rate calculations.

## Phase 8: verification and handoff

Run evaluation self-tests, existing repository tests, handler characterization,
scripted scenarios, isolation repetition, and report generation. Review at least
one good and one bad trace from every risk family.

Record:

- exact commands;
- dependency versions;
- execution duration;
- passing and failing counts;
- confirmed known gaps;
- unverified behavior and why it remains unverified.

## Initial command surface

```bash
# Run from voice-agent/
python -m evals.cli contracts
python -m evals.cli scripted
python -m evals.cli characterize
python -m evals.cli offline --trials 2 --workers 2
python -m evals.cli live --trials 10
```

## Implemented

The text-only V1 is implemented under `voice-agent/evals/`. It contains 15
scenario definitions, 31 good/bad scripted fixtures, eight composable graders,
production tool-schema parity checks, per-trial state isolation, fail-closed
network protection, real-handler characterization tests for verification, load
lookup/prompt replacement, reference guards, agreement, transfer, and end-call
behavior, and JSON/Markdown reports with full prompt/tool/state traces. The
confidentiality grader normalizes the numeric, spoken, and freight-shorthand
forms taught by the prompt. Strict preflight validation rejects malformed or
contradictory scripts. Parallel trials use separate worker processes, and the
grader tests cover missing and near-miss evidence. Live execution remains
defined but reports `NOT RUN` until model credentials and provider settings are
supplied.

`offline` is the normal V1 command. `live` reports `NOT RUN` until credentials
exist.

## Pending work

### Medium priority

- Replace the Room 2 source-string parity check with normalized inspection of
  the constructed production `ToolsSchema`.
- Add a production agent adapter if future tests need the complete orchestration
  path rather than prompts, schemas, handlers, and traces independently.
- Move scenario initial-state contracts, mock plans, and selected graders into
  dedicated definitions. They currently span `config/scenarios.yaml` and the
  script fixtures.
- Emit calculated state diffs alongside the complete before/after snapshots.
- Add failure-category aggregation and total-suite duration to reports.

### Low priority

- Record formal manual review of one good and one bad trace from each risk family.
- Add stable run IDs and per-trial artifact-directory metadata to traces.
- Expand handler characterization for additional provider-error branches.

### Blocked or intentionally deferred

- Live-model execution and empirical variance require model credentials,
  finalized provider settings, and a live provider adapter. Until then `live`
  remains `NOT RUN` and excluded from rates.
- Semantic/LLM judging is deferred with live execution.
- Voice, STT, TTS, interruptions, Daily/SIP, and telephony remain outside V1.
- Raw Room 1-to-Room 2 history fidelity remains out of scope by product decision.

There are no remaining high-severity items from the implementation audit.
