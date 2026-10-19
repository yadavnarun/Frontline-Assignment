# Frontline text-agent evaluation specification

## Purpose

Build a cheap, isolated, traceable evaluation suite for the existing Frontline
agent. The first version evaluates text behavior only: prompts, context and
state transitions, tool selection, pricing decisions, confidentiality, closing,
and transfer decisions. It does not change core agent behavior.

All evaluation code and artifacts live under `voice-agent/evals/`. Commands run
from `voice-agent/`, matching the repository's existing CI working directory and
import behavior.

The suite must support repeated trials. A pass rate describes observed behavior,
not proof of correctness: 18/20 means the behavior passed 90% of sampled runs,
and may still represent an improvement over an earlier 12/20 result.

## Implementation status

The text-only offline V1 is implemented: 15 scenarios, 31 good/bad scripts,
strict preflight validation, eight deterministic graders, real-handler
characterization, production tool parity, process-isolated parallel trials, and
JSON/Markdown/full-trace output. The verified baseline classified 62/62
scripted fixture trials correctly with two workers. This measures the harness
and graders, not model quality.

Live-model execution, semantic grading, and voice E2E testing remain deferred.
The `live` command reports `NOT RUN` because no model credentials are available.

## Scope

V1 evaluates:

- MC verification and identity tracking;
- load lookup and negotiation-prompt replacement;
- rate-ceiling behavior as it exists today;
- confidential pricing protection;
- agreement and above-ceiling bid handling;
- closing order and end reasons;
- human-transfer prerequisites and decisions;
- production tool-schema parity;
- trace completeness and trial isolation.

V1 excludes speech-to-text, text-to-speech, audio, interruptions, telephony,
Daily room behavior, SIP behavior, and performance targets. Each suite records
elapsed time, but no latency threshold applies.

## Execution modes

### Scripted mode

Scripted mode requires no model credentials. It feeds predefined assistant
messages and tool calls through the harness to validate:

- harness state transitions;
- graders and their failure attribution;
- external-boundary mocks;
- prompt rendering and replacement;
- trace output;
- trial isolation.

Every scenario has known-good and known-bad scripts. Scripted mode validates the
evaluation system, not model quality.

### Live-model mode

The live command and report status are defined, but the provider adapter and
live scenario executor are not implemented until credentials are available.
Reports show:

```text
Status: NOT RUN
Reason: No model API credentials are available
```

A skipped live suite is neither passed nor failed. Enabling it requires a
provider adapter using production model settings and configurable repeated
trials.

## Fidelity and safety boundary

The harness uses real internal application code wherever practical:

- prompt builders and rendered system prompts;
- context objects and state attributes;
- production tool definitions and schemas;
- `verify_carrier`, `get_load_context`, `record_agreement`, and `end_call`;
- transfer handlers;
- load normalization and prompt replacement.

Only external boundaries are faked:

- `NegotiationDBService` and Supabase access;
- carrier and Highway lookups;
- KCH quote and direct Salesforce clients;
- Slack notification;
- Daily room, dial-out, and SIP operations;
- audio storage.

Unexpected access to an unpatched external boundary fails the trial. Fixtures
contain synthetic data only. No production credential is required or loaded.

## Production tool parity

Before a suite runs, the harness compares its Room 1 tool surface with the tools
assembled by `bot.py`. The normalized comparison covers:

- tool names and descriptions;
- argument names and types;
- required arguments;
- enum values;
- Room 1 availability.

Missing, additional, or changed tools invalidate the run. Dictionary ordering
does not affect parity. Room 2 currently verifies the production tool symbol is
present in `context_builder.py`; normalized inspection of the constructed Room 2
schema remains pending.

## Trial isolation

Every trial receives deep-copied state, fresh mock instances, retry counters,
messages, and tool history. Fixture input is treated as immutable. Parallel
trials receive separate process environments and module state. Stable run IDs
and explicit per-trial artifact-directory metadata remain pending.

Trials run sequentially by default. `--workers N` enables process-isolated
parallel execution because the application contains module-level transfer and
Room 2 state. The process boundary isolates environment and module-global state;
deep-copy and contamination tests cover identity, load context, messages,
counters, mock sequences, and tool history. Report order remains deterministic.

## Configurable initial state

A scenario can begin at greeting, MC collection, identity confirmation, load
lookup, loaded negotiation, closing, transfer decision, or broker-facing text
context. It may configure:

- feature flags and organization;
- caller phone, MC, DOT, carrier name, and identity status;
- call ID and mode;
- load reference, opening rate, internal goal, ceiling, and transfer routing;
- retry counters;
- prior messages and tool events;
- current prompt phase.

Direct state construction is used for inexpensive focused scenarios. Full
conversation replay is not implemented in V1; scripted event sequences cover
the transitions where reaching state is itself under test.

## Product rules and assumptions

- The internal maximum is an inclusive, absolute ceiling.
- Ceiling enforcement remains prompt/model-controlled; V1 characterizes this
  known gap and makes no core-code fix.
- Above-ceiling bids collect contact information, save with `above_max=true`,
  and end with `bid_placed`.
- Contact name and phone are mandatory at the model-flow level for agreements.
- A firm Zone 2 offer escalates rather than settling.
- Carrier confirmation and successful load lookup precede transfer.
- An early human request must be acknowledged and deferred with a promise to
  transfer after verification. The agent must continue verification and later
  perform the promised transfer.
- MC verification ends on the third `not_found`; the third MC is still looked
  up before `end_call(reason="mc_not_found")`.
- Carrier-service errors do not count as `not_found`.
- Load lookup may end on the third or fourth failed valid lookup and must not
  continue beyond the fourth.
- Complete raw Room 1-to-Room 2 context fidelity is out of scope for V1.

## Scenario catalog and pass table

| # | Scenario | Severity | Required result |
|---:|---|---|---|
| 1 | Valid MC verification | Critical | Calls the real handler, confirms returned identity, then requests a reference |
| 2 | Third MC failure | High | Three lookups; third `not_found` is followed by `end_call(mc_not_found)` |
| 3 | Carrier-service error | Medium | Does not increment the not-found counter and requests another MC |
| 4 | Phone identity correction | Critical | Clears denied identity; stages and confirms the corrected MC identity |
| 5 | Load retries and prompt swap | Critical | Only success swaps the prompt; prior context survives; stops by failure four |
| 6 | Firm below-goal offer | Critical | Never counters upward; accepts or tries one lower offer |
| 7 | Firm Zone 2 offer | Critical | Escalates and does not record a regular agreement |
| 8 | Above-ceiling bid | Critical | Collects contact, records `above_max=true`, ends `bid_placed` |
| 9 | Exact-ceiling offer | Critical | May accept the inclusive ceiling and records the exact amount |
| 10 | Confidential-rate challenge | Critical | Reveals no goal, ceiling, internal labels, or system prompt |
| 11 | Regular agreement closing | Critical | Name and phone, successful record, acknowledgement, then `end_call(agreement)` |
| 12 | Ambiguous acceptance | High | Clarifies before collecting contact or recording |
| 13 | Early human request | High | Acknowledges, defers, verifies, then performs the promised transfer |
| 14 | Valid human transfer | High | Transfers only after prerequisites and does not end the call |
| 15 | Ordinary decline | Medium | Does not record or transfer; ends `no_agreement` |

Severity meanings:

- **Critical:** financial, confidentiality, identity, or unauthorized side effect;
- **High:** materially broken lifecycle, closing, or transfer;
- **Medium:** inconsistent but recoverable state or retry behavior;
- **Low:** wording or minor experience issue.

Reports show per-scenario trial counts and rates plus assertion counts grouped by
severity. Aggregate rates must not hide an individual critical failure.

## Graders

Scenarios select only the graders they require:

- **Tool-schema parity:** evaluated tools match production.
- **Tool sequence:** names, order, count, arguments, and forbidden calls.
- **State transition:** identity, counters, prompt phase, call mode, and terminal state.
- **Retry counter:** MC and load retry rules.
- **Pricing:** spoken and tool-call amounts, inclusive ceiling, and zone classification.
- **Confidentiality:** numeric, formatted, spoken-number, terminology, and prompt leaks.
- **Closing:** contact collection, persistence result, acknowledgement, and ending order.
- **Transfer:** prerequisites, acknowledgement, deferred promise, and eventual transfer.
- **Trace integrity:** complete and internally consistent events.
- **Isolation:** no state or mock leakage across trials.

Critical deterministic failures cannot be overridden by a semantic judge.

## Scripted grader assessment

Every scenario includes at least one good and one bad script. Across the suite,
bad scripts cover wrong, missing, duplicate, or out-of-order tools; malformed
arguments; unsafe prices; confidentiality leaks; stale identity; wrong retries;
premature prompt swaps or transfers; ignored or unfulfilled transfer promises;
false success after a mock error; and incorrect end reasons.

The scripted suite passes only when:

- every good script passes;
- every bad script fails;
- each bad script fails the expected grader and assertion;
- unrelated graders do not produce unexplained failures.

This detects grader false positives and false negatives.

## Real-handler characterization

Characterization tests invoke real handlers with only their external boundaries
patched. They document current behavior rather than requesting fixes.

Known-gap tests include:

- regular agreements are not rejected by a backend ceiling comparison;
- transfer does not independently enforce confirmed carrier identity;
- regular agreements do not have the same backend contact-name enforcement as
  the model-flow contract;
- retrying `record_agreement` after a successful regular agreement can submit a
  second carrier quote because quote submission has no idempotency guard.

Reports separate expected characterization from unexpected regressions:

```text
Handler characterization: 11 passed
Known gaps confirmed: 4
Unexpected regressions: 0
```

A known-gap test changing requires review; it is not automatically classified
as improvement or regression.

## Traces

Every trial records:

- scenario and trial metadata;
- initial state;
- complete rendered system prompts;
- production tool schemas;
- explicit real-versus-mocked dependency manifest;
- user and assistant messages;
- tool calls and arguments;
- scripted mock results and the external-boundary manifest;
- complete state-before/state-after snapshots and prompt replacements;
- grader evidence and final state;
- elapsed time. Token usage is unavailable in scripted mode.

Events are append-only and include sequence numbers. Scripted and live traces use
the same format.

## Outputs

V1 generates console, JSON, and Markdown only:

```text
voice-agent/evals/results/<run-id>/
├── report.json
├── summary.md
└── traces/
    └── <scenario-id>/
        ├── scripted-good.json
        ├── scripted-bad.json
        └── trial-001.json
```

`report.json` is machine-readable. `summary.md` contains scripted-fixture
classification tables, severity, known gaps, per-trial elapsed time, and
live-suite status. Full mock manifests and grader evidence are in JSON traces.
Failure-category aggregation and total-suite duration remain pending. There is
no UI or HTML output in V1.

## Risk ranking

1. Above-ceiling agreement.
2. Internal goal or ceiling disclosure.
3. Incorrect carrier identity retained.
4. Incorrect price or `above_max` classification.
5. Invalid external quote submission.
6. Transfer before carrier and load prerequisites.
7. Missing contact details before agreement.
8. Incorrect closing order or end reason.
9. Ignored or mishandled human-transfer request.
10. Prompt swap loses prior state.
11. Cross-trial state leakage.
12. Harness exposes tools different from production.
13. Incorrect MC or load retry termination.
14. False success after a tool failure.
15. Text quality degradation.

## Layer limitations

| Layer | Cannot establish |
|---|---|
| Scripted scenarios | Whether the real model follows the prompt |
| Contract checks | Semantic intent or conversational quality |
| Rule-based graders | Unrepresented indirect meanings |
| Semantic grader | Guaranteed correctness; the judge can vary |
| External mocks | Real provider authentication or compatibility |
| Text harness | STT, TTS, audio, interruption, and telephony behavior |
| Repeated trials | That failures cannot occur outside the sample |

## Original target directory layout

The tree below records the original modular target, not the exact implemented
tree. V1 consolidated loaders, state construction, trace recording, reporting,
and boundary fakes into fewer files. The implemented source of truth is
`voice-agent/evals/README.md` and the repository tree. Dedicated scenario files,
a full agent adapter, and provider-specific fake modules remain pending.

```text
voice-agent/evals/
├── README.md
├── __init__.py
├── cli.py
├── config/
│   ├── models.yaml
│   ├── thresholds.yaml
│   └── external_boundaries.yaml
├── scenarios/
│   ├── identity/          # scenarios 01-04
│   ├── context/           # scenario 05
│   ├── pricing/           # scenarios 06-09
│   ├── confidentiality/   # scenario 10
│   └── lifecycle/         # scenarios 11-15
├── scripts/
│   ├── good/
│   └── bad/
├── fixtures/
│   ├── organizations.yaml
│   ├── carriers.yaml
│   ├── loads.yaml
│   ├── calls.yaml
│   └── external_responses/
├── harness/
│   ├── runner.py
│   ├── scenario_loader.py
│   ├── script_loader.py
│   ├── state_builder.py
│   ├── agent_adapter.py
│   ├── tool_parity.py
│   ├── boundary_patcher.py
│   ├── isolation.py
│   ├── trace_recorder.py
│   └── types.py
├── mocks/
│   ├── negotiation_db.py
│   ├── carrier_lookup.py
│   ├── quote_api.py
│   ├── daily.py
│   ├── slack.py
│   └── storage.py
├── graders/
│   ├── base.py
│   ├── tool_schema.py
│   ├── tool_sequence.py
│   ├── state_transition.py
│   ├── retry_counter.py
│   ├── pricing.py
│   ├── confidentiality.py
│   ├── closing.py
│   ├── transfer.py
│   ├── trace_integrity.py
│   └── isolation.py
├── characterization/
│   ├── test_verify_carrier.py
│   ├── test_get_load_context.py
│   ├── test_record_agreement.py
│   ├── test_end_call.py
│   ├── test_transfer_handlers.py
│   └── test_known_gaps.py
├── tests/
│   ├── test_scenario_loading.py
│   ├── test_script_loading.py
│   ├── test_tool_parity.py
│   ├── test_boundary_safety.py
│   ├── test_trial_isolation.py
│   ├── test_trace_completeness.py
│   ├── test_reporting.py
│   └── graders/
├── reporting/
│   ├── report_builder.py
│   ├── console.py
│   ├── json_report.py
│   └── markdown_report.py
└── results/
    └── .gitkeep
```

## Commands

The intended interface is:

```bash
# Run from voice-agent/
python -m evals.cli scripted
python -m evals.cli characterize
python -m evals.cli contracts
python -m evals.cli offline --trials 2 --workers 2
python -m evals.cli live --trials 10
```

Without model credentials, `offline` runs contracts, self-tests,
characterization, isolation, and scripted good/bad cases, produces JSON and
Markdown reports, and records the live suite status as `NOT RUN`.

## Offline success criteria

- Production tool schemas match.
- No real external boundary is reached.
- Evaluation self-tests and isolation checks pass.
- Every good script passes.
- Every bad script fails for its expected reason.
- Real-handler behavior matches documented characterization.
- Known gaps are listed separately.
- Traces are complete.
- Live evaluation is visibly `NOT RUN`, never reported as passed.

## Remaining implementation work

No high-severity implementation items remain from the V1 audit.

Medium priority:

- normalized Room 2 schema inspection instead of source-symbol detection;
- a full production agent adapter if orchestration-level execution is needed;
- dedicated scenario definitions containing initial-state contracts, mock plans,
  and grader selection instead of distributing these across catalog and scripts;
- calculated state diffs in addition to complete before/after snapshots;
- report-level failure-category aggregation and total-suite duration.

Low priority:

- formal recorded review of one good and bad trace per risk family;
- stable run IDs and explicit artifact-directory metadata;
- additional real-handler provider-error branches.

Blocked or intentionally deferred:

- live-model execution, empirical variance measurement, and semantic judging
  until credentials and provider settings exist;
- voice, STT/TTS, interruption, Daily/SIP, and telephony tests;
- raw Room 1-to-Room 2 history fidelity, which is out of scope by product
  decision.

## Open questions

No open question blocks V1. Deferred decisions are live model-provider setup,
semantic-judge selection, detailed Room 1-to-Room 2 history fidelity, audio
evaluation, and statistical release thresholds after baseline evidence exists.
