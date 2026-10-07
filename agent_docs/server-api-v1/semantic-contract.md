# Player API v1: meanings and implementation ownership

This document supplies the cross-field and temporal rules that ordinary JSON
Schema cannot express. It is a finite specification, not a proposed validation
framework. `player-api-v1.schema.json` defines all field shapes. `openapi.json`
defines route/parameter bindings and response roots. Source fields, defaults,
requiredness and proposed changes are enumerated in `field-ledger.json` and
`owner-deltas.json`. The existing Python owners remain authoritative.

## Transport records

Protocol version is 1; proposed player schema version is 4. Current source is
version 3. The schema SHA-256 identifies the published bundle. The protocol
identity repeats in bootstrap, initialization, stream-ready and operation records
so a saved record remains attributable without an online server. Only the
supported version/digest is accepted; legacy migrations remain offline.

`PlayerCursor` identifies game, game epoch, audience and a nonnegative sequence.
Sequence 0 is the immutable initialization; complete operations start at 1.
The sequence is not a native EventQueue index or subevent count. It advances only
for an admitted operation, including an authorized HUD/log/control-only result.
Audience-local occurrence indices preserve order inside those operations.

| Root | Exact meaning beyond its field shape |
|---|---|
| HealthResponse | Host liveness only; no game or player state |
| BootstrapResponse | Bound seat's game/epoch/audience and protocol; null audience/content/head while native initialization is pending |
| StatusResponse | Current cached authorized boundary/delivery state; no live Entity or native discovery work |
| AttachmentRequest | Acquisition UUID plus compare-and-swap prior epoch; null means no previous attachment |
| AttachmentResponse | Same acquisition returns same epoch/result; status contains next command number, pending IDs and catch-up cursor |
| InitializationResponse | Exact sequence-zero snapshot and permitted catalog seed; no private startup requests, test seed or registry dump |
| AckRequest / AckResponse | Highest contiguous safely consumed cursor; identity must match current attachment and delivered history |
| ChoicesRequest / ChoicesResponse | Exact actor, state revision, force-attack mode and correlation; result retains native discovery generation |
| PreviewRequest / PreviewResponse | Echo exact ordered selection and discovery; no mutation, RNG draw or client-computed path |
| CommandRequest | Stable per-seat number, actor, state revision and one finite intent; only execute-selection and handler-toggle need discovery generation |
| ReceiptResponse | Pending, committed, rejected, indeterminate, expired or unknown; never infer success from HTTP acceptance |
| ContentResponse | Immutable PUBLIC descriptors for this revision; OBSERVED descriptors travel in authorized additions |
| StreamReady | Unnumbered acknowledgement of requested resume point and captured committed head; validate before operations |
| StreamStatus | Unnumbered delivery/boundary state; cannot contain gameplay changes or advance consumed cursor |
| PlayerOperation | One complete authorized result: content additions, current audience, ordered lineages, standalone log appends, HUD after-value and boundary |
| ApiError | Finite code, status and retry policy; bounded incident reference, no input echo, stack, native class or foreign-seat state |

All game paths require `X-Game-Epoch` and `X-Audience-Id`; mutating/subscription
attachment paths also require `X-Attachment-Epoch`. Credentials are a bearer header,
never a query parameter. Content is PUBLIC-only and still seat-authenticated.
Initialization has a fixed relative route; an attachment does not supply an
arbitrary download URL. Outbound redirects are rejected.

A state revision is an opaque audience-local admission token, not an event index.
A hidden operation does not rotate it. Discovery generations are scoped to the
current actor/seat/revision and retained query. Negative action/target indices are
invalid; signed map coordinates remain valid. Counters fit exact JS safe integers;
finite numeric values only, no clamping/coercion/default insertion in SDKs.

## One socket for several units

The configured seat authorizes one `PlayerAudience`: unique `controlled` and
`observers` lists plus a local membership revision. Observers must be nonempty;
the recorded anchor observer belongs to that list. Control and observation are
separate permissions; neither is inferred from faction or a client-supplied list.

One SSE connection covers that whole audience. Members' admitted observations
are combined by the existing audience functions before delivery. Selecting a unit
is local UI state. It opens no socket and changes no visibility/history. A single
unit is the same shape with one-member lists. Several separately controlled teams
receive independent streams of the same native game. There is no arbitrary seat
count limit and no N-socket requirement for an N-unit party.

Membership changes, if the game assigns/revokes a unit, use the required operation
`audience` after-value and existing reducer. Publish membership before consuming
that operation's facts. Prior admitted knowledge is retained; removed observers
provide no future sensory grants. Automatic summon AI and command ownership are
separate: becoming a summon does not manufacture a human turn or an extra seat.
The engine checks acting-body range, senses, resources and turn even when another
member makes a target known to the player.

## Boundary and receipt invariants

- `waiting_for_human` plus nonnull input actor refers only to this seat's controlled
  actor. Another seat's undisclosed waiting/AI state is represented as neutral
  `advancing`, without identifying that actor or publishing hidden transitions.
- Before initialization: published/final/acknowledged/catch-up cursors and state
  revision can be null. After initialization, a published head exists. An acquired
  attachment need not yet have acknowledged initialization.
- Terminal/failed/closed states retain a final committed cursor F if initialization
  succeeded. Consumers may drain to F. A receipt for an admitted failure after
  dispatch is indeterminate with incident ID; it is never “rejected, try again.”
- Only a committed receipt has a result cursor. A rejected receipt consumed its
  reserved number without gameplay mutation. A pre-admission error reserved no
  number. Unknown means never reserved; expired means its retained result was
  evicted but its number cannot execute again.
- One unresolved command per seat; one native mutation at a time. Same logical
  command number/payload returns its retained result. Different payload conflicts.
  Attachment replacement does not cancel already admitted work.
- Stage every audience's complete result before atomically publishing the batch
  heads and own-command receipt. Only its seat receives `command_number`; foreign
  results have null. No cross-audience sequence or private transaction ID is sent.

## Stream handling

SSE event names are `ready`, `status`, `operation`. Only `operation` has an `id`,
whose decimal value equals its cursor sequence. Each server operation is one JSON
UTF-8 data line; the SDK parser handles legal SSE framing, comments, CRLF and split
UTF-8 without assuming network chunk boundaries. An incomplete EOF record is
discarded. A malformed complete record fails explicitly.

Call the consumer serially and await it. Only after it commits does the SDK advance
consumed and ACK. Retain the original operation bytes for recording. Reconnect
from consumed, not received. Discard duplicates <= consumed; a forward gap fails.
Ready/status/heartbeats do not commit gameplay or advance the cursor. Wait-for-cursor
uses consumed, and terminates explicitly above terminal F. See the stream plan for
backpressure, attachment and quota rules; there is no animation-complete ACK.

## Shared reducer order

The existing Python public reducer gains one operation helper, used by live host
verification, the Python script and cold replay: validate envelope identity/order;
stage permitted descriptor additions and audience after-value; apply complete
lineages in order; apply standalone log appends once using their local append
indices; apply the operation-end HUD; commit the staged state and cursor together.
Lineage-local HUD values are earlier recorded boundaries; the final HUD wins.
No SDK independently implements mechanics. TypeScript initially retains exact
operations and acts from authorized discovery/status; the future renderer ports
this same passive contract rather than deriving state from combat-log prose.

## Nested causal/privacy policy

| Fields | Disposition |
|---|---|
| PlayerNode parent_event/parent_lineage/children_lineages | Reference admitted nodes/groups only; null or filtered list for unknown ancestry; no placeholders revealing hidden chain length |
| PlayerLineage root/lineage_uuid | Root is nullable. Group identity is the admitted root identity or an opaque audience-local group for a witnessed consequence; no fabricated source action |
| PlayerNode resolution_ref and application references | Preserve when owner occurrence/application is admitted. Otherwise retain consequence in the unknown-cause group and omit unavailable causal reference |
| ActionReaction triggered_lineage_uuid | Nullable when the original triggering spell is hidden; keep the observed reaction result |
| ConditionFact event_uuid | Nullable when a current condition is observed but its application was not; do not fabricate history |
| Node turn_execution_id | Null unless the referenced turn execution is admitted |
| ContentAttribution source/trigger/emitted refs | Filter or null undisclosed actors/occurrences; provided_by/origin descriptors require their own admission, not automatic closure over private metadata |
| VersionRow source_index; lineage/init boundaries | Dense audience-local occurrence order; consistent remapping for every reference to the same occurrence |
| ConditionState and ItemEffectPresentationState applied_source_event_cursor | Mapped admitted application index, otherwise null; quiet reacquisition does not replay cast VFX |
| ObservedChangeRef source_index/source_event_uuid/resolution_ref | Same local mapping; only admitted observation provenance, no hidden source header to satisfy a reference; omit undisclosed provenance entry while retaining admitted after-value |
| PerceivedSpatialEffect owner_revision | Local observed-state revision; unseen mutations do not advance it or invalidate remembered state |
| HUD revision; CombatLogAppend encounter_log_index/operation_end_cursor | Local HUD/append/boundary counters, independent of hidden native events |
| PlayerAudience revision; discovery generation | Local membership/query admission order; never global activity counters |
| Source/target/provider/anchor/item UUIDs | Identity permission is independent of location permission. Condition/effect instance identity does not grant its hidden caster or equipment |
| World bounds/content | Configured public bounds and admitted tiles; PUBLIC catalog independent of hidden encounter instances; no current secret-room inventory |

Unknown-source impact, doorway opportunity death and known-actor turn-end are
explicit in [COMBAT_LOG_CONTRACT.md](COMBAT_LOG_CONTRACT.md). Current projector
raw ancestry/indices and dictionary log behavior require the owner changes above;
this schema document is not evidence that those repairs are already live.

## Duration and native preview additions

One `ConditionDurationSummary` uses the existing `DurationType` and required
nullable `remaining_rounds`. Rounds carries the native stored integer, including
terminal zero/negative; other modes carry null. The enclosing duration field is
required nullable: null means the duration is not admitted, not permanent.
Default exact-duration permission is the controlled owner; an observed enemy does
not gain automatic disclosure of its private duration. Remembered state does not
silently tick to the unseen latest state.

`BaseCondition.snapshot_state` copies mode/count without calling conditional
expiration logic. Surviving progression publishes through existing condition-state
change capture under its native turn cause; expiration uses existing removal.
Item effects and spatial effects reuse this summary in their existing after-state
records and progression captures. No timer service or client duration simulation.

`PlayerCharacterSheet.handler_details` reuses `AvailableHandlerInfo`, recorded at
initialization and operation boundaries even for eventless toggles. No separate
handler-preference registry. `AvailableSelectionPreview.selected_route` is required
nullable; null for nonmovement/incomplete selection. A value is the actual native
selected normal/safe path, cost, affordable endpoint and admitted hazards/OA
exposure. Query and execution call the same native route decision. Never derive
this path in HTTP or SDK code.

## Existing validators: exact disposition

`source-validators.json` includes source text/locations for the reachable decorated
validators and serializers. The following semantics remain owned by their native
model; SDKs need no duplicate gameplay validator framework.

| Invariant | Owner / wire policy |
|---|---|
| Target-effect included/excluded creature types disjoint; save metadata iff save branch | ActionTargetEffectBranchProfile; native producer validates, public schema carries its exact values |
| Target branch effect IDs unique | ActionTargetEffectProfile; producer only, no SDK evaluation of effects |
| Information/topology shape and radius paired; sense type iff grant-sense | Existing profiles; producer only |
| World-effect profile contains at least one information/topology effect | Existing profile; producer only |
| source_unaffordable iff !can_afford; available iff valid_targets nonempty | AvailableActionInfo native validation; complete query result must satisfy this before export |
| Namespaced IDs and SHA-256 syntax | Existing ContentRef/action/handler validators; syntax copied as schema constraints, no registry lookup in client |
| Unique canonical equipment slot/layer presentations | ContentPresentation; producer sorts once, SDK never silently reorders |
| Centered cube lacks direction; directional cube requires it | Existing geometry owner; finite schema/captured values, no client geometry engine |
| Positive wall segments; nonduplicate consecutive polyline vertices | Existing geometry validators; producer only |
| Object support uniqueness/anchor, vertical interval, removed bands, center/boundary shape | WorldObjectPlacement; current legacy support filling remains offline migration, not SDK coercion |
| Unique canonical boundary channel order | BoundaryStructure; producer only |
| Sorted set serialization | Existing serializers; preserve emitted arrays; uniqueItems enforces set members where applicable |
| Legacy SpellFact area-policy upgrade | Historical input migration only; version 4 requires current producer fields |
| Audience uniqueness/membership; envelope identity/order; current controlled inventory/committed exact HP; spatial commit reference completeness | Existing audience/reducer ordinary functions; retained shared reducer checks, not duplicated SDK mechanics |
| Log category/tag, target index membership, no hidden counters/text | Existing log/projection changes specified separately; no dictionary escape hatch |

The SDK's finite behavioral checks are transport checks: matching identity/version,
contiguous sequence, current attachment, consumed-cursor/ACK/final-boundary rules.
These are tested once across both languages when transport is implemented. Source
schema parity and focused regressions cover native model semantics. Do not regenerate
SDKs or repeat broad suites after unrelated implementation edits.
