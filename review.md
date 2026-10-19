# PR #1 review: LiveKit/Telnyx migration and warm transfer

## Recommendation

**Do not deploy to production or merge yet.** The migration has several
production-critical paths whose behavior is either demonstrably incomplete by
code inspection or unvalidated at the provider boundary. The supplied runtime
cannot install Python dependencies (`pip`, `venv`, and `pytest` are absent),
so no behavioral test result is claimed in this review. `python3 -m
compileall -q voice-agent shared` passed; that is syntax-only evidence.

`New in this PR` means the code/path is added or materially changed relative
to `5a98a662`. `Pre-existing` means it already existed and is not a reason to
block this PR by itself. `Static` findings must be reproduced with the listed
test before being treated as confirmed production behavior.

## Production blockers

| Severity | Status | Introduced | Location | What is incorrect | Required fix and proof |
| --- | --- | --- | --- | --- | --- |
| P0 | Confirmed by source-level dependency analysis; runtime test pending | New | `voice-agent/livekit_ingress.py:195-205` | The production SDK represents `ParticipantInfo.Kind.SIP` as the enum name `SIP`. For numeric kinds, this function reaches line 203 and tests `"SIP".endswith("_SIP")`, which is false. Thus a normal numeric SIP participant is rejected before bot startup. The unit test only supplies string `"SIP"`, so it masks the branch. | Compare the resolved enum name for equality (`== "SIP"`, accepting the explicit legacy spelling only if needed). Add a signed, SDK-decoded numeric SIP `participant_joined` fixture and assert `202` admission. |
| P0 | Confirmed by pinned Pipecat source; runtime test pending | New | `voice-agent/livekit_transfer_media.py:57-69`; `voice-agent/tests/test_livekit_transfer_media.py:9-16` | `pause_processing_frames()` does exist in Pipecat 0.0.95, but it pauses frame processing after frames have been accepted; LiveKit input continues to receive audio and the base input queues it. On resume, held caller speech can be replayed to STT/LLM, and a long hold can accumulate an unbounded queue. The fake only proves calls were made, not the audio behavior. | Add a supported input gate that drops/blocks caller audio while preserving required lifecycle frames, then flush buffered audio before resuming. Prove held speech cannot reach STT/LLM/tools, no delayed speech is replayed, and queue growth is bounded. |
| P1 | Static race | New | `voice-agent/orchestrator.py:171-259`, `316-324` | If the carrier disconnects while `create_room()` (or another resource-acquiring await) is pending, terminal cleanup can complete before `room2_name` is stored. When the await returns, the original coroutine continues into hold/Room2 setup/dialing with a terminal transfer state. | Tie work to an attempt task/ID, cancel and await it on terminal events, and re-check attempt liveness after every resource-acquiring await. Dispose of a late-created room. Add deterministic disconnect-during-create/dial/setup tests. |
| P1 | Static cleanup omission | New | `voice-agent/orchestrator.py:375-405`, `432-462` | If the broker has arrived in Room1 but `stop_hold()` or `detach_primary_publisher()` fails, `_recover_after_arrived_broker()` marks the transfer complete without calling `_cleanup_room2()`. The consultation pipeline/room can remain allocated. | Ensure arrived-broker recovery stops Room2 and deletes its room before terminal completion. Test both failing media operations and assert no Room2 resource remains. |
| P1 | Static concurrency flaw | New | `voice-agent/server.py:119-142`; `voice-agent/tests/test_server_livekit.py:48-78` | Webhook dedupe checks the event ID, awaits bot startup, then records the ID. Two simultaneous retries can both start an agent. The test is sequential, and the set is local/unbounded. | Reserve an idempotency key before awaiting startup; release/transition it deliberately on failure. Use a bounded shared store if ingress can be replicated. Add a concurrent-delivery test that blocks startup and proves exactly one start. |
| P1 | Static resource leak | New | `voice-agent/server.py:119-142` | Inbound calls already occupy a provider-created room. If `start_agent()` rejects/fails, the exception exits without removing the SIP participant or deleting/terminating the room. Outbound has a corresponding cleanup block; inbound does not. | Catch bot-start failure, clean up the inbound room/participant while preserving the startup error, and test the rejected-start path. |
| P1 | Static tenant/caller-ID mismatch | New | `voice-agent/server.py:147-181`; `voice-agent/livekit_telephony_service.py:100-124` | `/outbound-call` uses request `from_phone` as `AgentRequest.bot_phone` (organization lookup), but the SIP request always uses configured `livekit_outbound_number`. A caller can select one organization context while placing a call whose visible number belongs to another. | For one outbound number, reject any mismatch and use the configured value for both purposes. For multi-number operation, use an allow-listed caller-ID/trunk/tenant mapping. Add mismatched-number rejection tests. |

## Important, should resolve before production

| Severity | Status | Introduced | Location | What is incorrect | Required fix and proof |
| --- | --- | --- | --- | --- | --- |
| P0 | Confirmed by pinned Pipecat source and LiveKit API contract; runtime test pending | New | `voice-agent/room2_pipeline_service.py:246-279`; `voice-agent/tests/test_room2_pipeline_service.py:11-29` | Pipecat 0.0.95 emits a participant **SID** to these callbacks and its `get_participant_metadata(SID)` helper omits identity. LiveKit’s `remote_participants` mapping is keyed by **identity**, but line 254 indexes it with that SID. The lookup returns no participant, identity remains absent, and line 266 rejects the expected `broker-...` identity. Consequently `_broker_connected`/`_broker_media_ready` are not set and `wait_for_broker()` times out. The fake incorrectly makes `remote_participants` SID-keyed and hides the boundary mismatch. | Maintain an explicit SID-to-identity map from a correct SDK lookup/event payload, or query participants by identity and correlate safely. Use distinct real-shape SID/identity values in tests, covering connect-before-dial-return and media-before-answer. |
| P1 | Static cleanup-stuck path | New | `voice-agent/orchestrator.py:515-530` | If `Room2PipelineService.stop()` raises, `_room2_pipeline` remains non-null even though room deletion is attempted. The next transfer refuses to start because it treats that object as leaked state. | Clear/fence the pipeline object in `finally`, retain cleanup diagnostics separately, and test stop failure followed by a retry. |
| P1 | Static capacity constraint | New | `voice-agent/bot.py:69`, `689-704` | The replacement BotRunner stores one global task and returns 409 for any concurrent call. There is also global transfer state. A single shared runner cannot serve two rooms safely. | Use room/call-keyed tasks and orchestrators, or document and enforce an externally provisioned one-runner-per-call deployment model. Add an isolated two-call test. |
| P1 | Static endpoint-contract mismatch | New | `voice-agent/livekit_telephony_service.py:100-124`; `voice-agent/server.py:147-190` | The common dial boundary unconditionally uses `wait_until_answered=True`, so `/outbound-call` can wait for ringing, rejection, or timeout despite returning `202 Accepted`. | Make answer waiting explicit: true for broker consultation, false or bounded/explicit for the public endpoint. Test delayed answer, rejection, no answer, and timeout. |

## Non-blocking follow-ups

| Severity | Status | Introduced | Location | Concern | Recommended action |
| --- | --- | --- | --- | --- | --- |
| P2 | Static UX/observability gap | New | `voice-agent/orchestrator.py:197-199`; `livekit_transfer_media.py:71-109` | Room1 input/TTS is gated before the separate hold publisher reports connected, creating a possible silence interval with no metric. | Instrument gate-to-first-hold-audio duration, timeout, and failure counts. |
| P2 | Static deadline gap | New | `voice-agent/orchestrator.py:215-219`, `538-555` | Broker timing starts after awaiting the best-effort notifier. Exception handling does not bound a notifier that stalls. | Detach or bound notification work; start the consultation/dial deadline before notification. Test a non-returning notifier. |
| P2 | Static identity-lifecycle assumption | New | `voice-agent/bot.py:577-597`; `transfer_state.py:41-42` | Post-move disconnect handling compares the observed Room1 participant ID with the Room2-captured ID. The code does not reconcile a destination ID after movement. | Establish whether the provider preserves the callback identifier; otherwise resolve lifecycle events by identity or refresh destination participant data. Test distinct source/destination IDs. |
| P2 | Test coverage | New | `voice-agent/tests/` | New tests are largely hand-built fakes at precisely the ingress, media, and participant boundaries being changed. | Keep unit fakes, but add SDK/transport contract fixtures and failure/concurrency tests listed above. |

## Database migration and compatibility

`web/supabase/migrations/20260907000000_add_livekit_call_attribution.sql` is
additive: it retains `daily_call_id`, adds nullable `provider_call_id`, and
adds `telephony_provider NOT NULL DEFAULT 'daily'`. Existing Daily rows and
old writers that omit the new columns remain structurally compatible.

This is not a production blocker from static inspection. Before release,
apply the complete migration chain to a copy of an existing database and
verify that historical Daily records and new LiveKit records both render in
the dashboard. The provider check constraint intentionally permits only
`daily` and `livekit`; confirm that no other provider is required.

## Pre-existing items not charged to this PR

- The historical schema/migrations still retain `daily_call_id`; the PR does
  not drop or rewrite it.
- The dashboard model continues to carry `dailyCallId` for historical data;
  this is compatibility debt, not by itself a new migration break.

## Release gate

Production is **not ready** until every P0/P1 item has a passing regression
test against the installed dependency versions, the full voice test suite can
run in a Python environment with `pip`/`pytest`, migrations are trial-applied,
and provider-backed inbound/outbound/transfer qualification is completed in
an isolated development account.

## Deep-dive flow analysis and open pointers

### 1. Inbound LiveKit ingress

The intended path is signed LiveKit webhook -> `parse_verified_sip_event()` ->
SIP/trunk/rule/number validation -> inbound dedupe -> room token and
`AgentRequest` -> `start_agent()` -> bot joins the provider-created Room1.
The first gate is broken for a normal numeric SIP enum (P0 above), so the
remaining validation is unreachable for real inbound traffic.

After fixing it, the unclosed branches are missing/malformed SIP attributes,
wrong trunk/rule, replayed webhook while startup is pending, bot-start failure
after the provider made Room1, and carrier departure before the bot joins.
The tests use hand-written objects rather than an SDK-decoded signed webhook.

**Open pointer:** make a contract fixture through the installed
`api.WebhookReceiver`, with distinct SID and identity. Drive every rejection
branch and one success. Deliver the same event twice concurrently while bot
startup is paused; exactly one agent must result. On start failure, assert
that the provider room/participant cleanup path ran.

### 2. Room1 hold behavior

The sequence is `create Room2` -> gate Room1 -> start an output-only hold
publisher -> start Room2 -> dial broker. The hold publisher does not prevent
the existing Room1 input from accepting caller media. Pipecat's frame pause
halts downstream processing while its input continues queueing audio. On
resume, held speech can reach STT/LLM, and a long hold can grow memory.

**Open pointer:** feed recognisable audio before/during/after hold. Assert
that the during-hold transcript/tool action never appears after recovery,
audio buffering is bounded or dropped, and a hold-publisher connection
failure restores Room1. Also exercise carrier disconnect while hold connects
and while its observer is retained after handoff.

### 3. Room2 keying and readiness

Room2 starts before `dial_phone()` returns, so join/audio events may arrive in
either order. The code's SID-and-identity authentication intent is sound, but
it crosses incompatible keys: Pipecat passes a SID and LiveKit's room map is
identity-keyed. The fake makes the map SID-keyed, hiding the deterministic
rejection and consequent broker-media timeout described in the P0 finding.

**Open pointer:** put SID-to-identity resolution in a small adapter using a
documented SDK lookup (not private `_client` where avoidable). Contract-test
answer-before-connect, connect-before-answer, audio-before-answer, unexpected
participant, and broker departure with different values such as `PA_123` and
`broker-abc`.

### 4. Fake correctness

| Fake | Incorrect simplification | Hidden branch |
| --- | --- | --- |
| ingress participant | `kind="SIP"` | numeric enum rejection |
| transfer-media input | pause/resume has no audio queue semantics | stale caller audio and queue growth |
| Room2 client map | `remote_participants` keyed by `PA_broker` SID | identity lookup failure |
| orchestrator fakes | all resource awaits finish in one friendly order | disconnect/late-resource races |

Keep ordinary fakes for pure state logic, but replace provider-boundary fakes
with SDK-shaped contract fakes. The assertion must cover observable event and
media outcomes, not simply whether a method was called.

### 5. Transfer lifecycle branches

Nominally the lifecycle is `IDLE -> create Room2 -> CALLER_ON_HOLD ->
DIALING_BROKER -> CONSULTING -> HANDOFF_REQUESTED -> HANDOFF_COMPLETE ->
cleanup`. `_terminal_failure()` handles several failure routes, but these
branches remain unsafe: carrier disconnect during resource awaits; a Room2
stop exception that fences the next attempt; post-arrival recovery that omits
Room2 cleanup; a notifier that can delay the dial deadline forever; and SID
comparison after moving participants.

Each resource-acquiring await needs an attempt-generation/liveness check when
it returns. One idempotent terminal finalizer should clear references in a
`finally` block and own cleanup of both rooms.

### 6. Call end and transfer-end handling

Before movement, broker departure calls `_terminal_failure()` and should
restore Room1. An unknown move outcome instead quarantines Room1, which is a
reasonable safety choice. The remaining stuck risks are late resource creation
and the cleanup-reference leak. Provider actions use identity but callbacks
store/compare SIDs; post-move code needs a documented correlation rule rather
than assuming the Room2 SID remains valid in Room1.

**Open pointer:** test a move whose source/destination SIDs differ, then test
carrier-first and broker-first departure. Each must finish once, stop media,
and leave neither Room2 nor a held Room1 publisher.

### 7. Inbound versus outbound

Inbound authenticates a provider-created SIP participant and must validate,
deduplicate, then start the bot. Outbound creates Room1 itself, dials using
the configured global LiveKit caller ID, and has a local setup cleanup path.
Both make an `AgentRequest`, but they differ materially: inbound attribution
comes from verified SIP attributes; outbound request `from_phone` can select
a different organization than the actual configured caller ID; and the public
outbound endpoint waits for answer despite returning `202`. Warm transfer is a
third outbound SIP leg with its own bounded answer/media deadline while
preserving the original Room1.

**Open pointer:** add a matrix test for inbound valid/replay/start failure;
outbound caller-ID mismatch/dial reject/no-answer; and transfer answer/connect
ordering. Assert room ownership and cleanup per row, not only HTTP status.

### 8. Migration/database compatibility

The migration is additive for in-repository callers: it retains
`daily_call_id`, defaults `telephony_provider` to `daily`, and makes the new
provider ID nullable. It has no destructive rewrite or backfill. The remaining
operational question is whether existing data/external writers contain another
provider, which would violate the new two-value check constraint; the chain,
permissions, and index creation have not run here.

**Open pointer:** apply the full chain to a production-shaped database copy,
insert old Daily and new LiveKit rows, run dashboard queries, roll back on the
copy, and enumerate external writers before relying on the constraint.

## Dependency evidence

- Pipecat v0.0.95's [frame processor](https://github.com/pipecat-ai/pipecat/blob/v0.0.95/src/pipecat/processors/frame_processor.py)
  implements pause as processing/queue control; its [base input transport](https://github.com/pipecat-ai/pipecat/blob/v0.0.95/src/pipecat/transports/base_input.py)
  continues queueing incoming audio.
- Pipecat v0.0.95's [LiveKit transport](https://github.com/pipecat-ai/pipecat/blob/v0.0.95/src/pipecat/transports/livekit/transport.py)
  sends participant SIDs to callbacks and its metadata helper omits identity.
- LiveKit documents [`Room.remote_participants`](https://docs.livekit.io/reference/python/livekit/rtc/room.html)
  as identity-keyed. These facts confirm the Room2 boundary finding; an
  executable regression test against the project pins is still required.
