# Summons follow their caster's control

Date: 2026-10-22. Status: complete, with validation and performance limits recorded below.
Source baseline: `feature/rules-checking`, `9ead58f825`.

Follow-up: the human identified missing dismissal at caster zero HP regardless
of concentration. See the
[caster defeat cleanup plan](SUMMON_CASTER_DEFEAT_CLEANUP_PLAN_2026-10-22.md).
The implementation receipt below remains historical; a weapon surviving its
downed caster is no longer accepted lifetime behavior. The correction is
implemented; its regressions and source review passed. The fresh independent
match ended naturally with both SDKs and replay passing. All summons departed
before caster defeat, so direct live dismissal is not exercised; native and
real-worker cases qualify that boundary separately.
It also supersedes the earlier released-Fey survival assumption: the original
caster's defeat dismisses that body even after it became hostile.

The human agreed that human and Codex casters should retain direct control of
their summons, with native AI retained for native AI casters and genuinely
uncontrolled creatures. The human subsequently authorized implementation, with
pre-change timings, a sub-agent tracking adherence/performance, and an actual
fair Monty agent-versus-agent summoner match as additional acceptance.
This amendment supersedes the autonomous-only control restriction in the
[original summon plan](../SUMMONING_BACKEND_PLAN_2026-10-03.md) and subsequent
spell plans. Their creature definitions, spell costs, duration, concentration,
placement, initiative, retirement and item rules otherwise remain applicable.

## 1. Observable result and scope

A player casts a summon, finishes the caster's turn, receives the summon as the
next applicable input actor, discovers its own actions, chooses movement and
attacks, and ends its turn through the ordinary command API. Codex uses the same
external command path with its own controller identity. Native AI summons still
act through the existing native AI executor.

| Caster / transition | Result |
| --- | --- |
| Human external controller | Summon borrows that controller and belongs to the caster's existing seat. |
| Codex external controller | Same ownership rule; preserve Codex identity and external-input behavior. |
| Native AI caster | Keep a summon-owned native AI controller and the existing policy/knowledge path. Do not resize the caster's fixed AI assignment. |
| Fey loses its actual control condition while existence remains | Revoke external control if present, retain or create the summon-owned native AI controller, and apply existing hostile allegiance. |
| Dismissal, defeat, expiry, concentration/family replacement or close | Remove that summon from control and observation; retain the existing exact retirement rules. |
| Surviving summon enters a later encounter | Resolve the current caster controller and seat again. An uncontrolled Fey remains independent. |

All eight current families are included: Animals, Fey, Fiend, Elemental, Planar
Ally, Dragon, Spiritual Weapon and Flaming Sphere. The last two retain their
current creature-based mechanics. This work adds no spells, packs of summons,
command action costs, default Dodge policy, spell balance changes, AI tactics,
new turn scheduler, remote ownership service, artwork or client UI implementation.
Ordinary control reassignment unrelated to summons is not a new feature here.

**Observation policy accepted with this plan:** control and observation
remain distinct. In the owning seat, a summon participates as an observer if its
caster already participates there. This extends the ordinary default where a
seat observes its controlled party. A customized seat that controls but does not
observe the caster gains control only. Other seats' authored observer grants do
not expand automatically. Individual actors still target, move and attack using
their own senses; the composed display never grants shared mechanical sight.

## 2. Current obstacles verified in source

| Owner | Existing behavior that must be addressed |
| --- | --- |
| `dnd/summoning/system.py` | `SummonMembership.controller` is native-AI-only. Prepare and rebind create AI unconditionally; rollback, retirement and reset close it unconditionally. Fey control loss currently only changes faction. |
| `dnd/encounter.py` | Existing live join and controller replacement support external controllers, but set `is_player_companion=True`; controller replacement has no recorded assignment-change publication. |
| `dnd/controller.py` | Human and Codex already advertise `ControllerExecutionMode.EXTERNAL`; both wait for external commands. |
| `dnd/player/session.py` | `player_uuids` is fixed at startup and drives action admission, sheets and outside-combat handling. Authored composition currently turns every external actor into HumanController, despite the roster supporting Codex. |
| `server/worker.py` | Boundary detection and automatic advancement check HumanController specifically. Seat authorization and publications hold the startup audience. |
| `dnd/player/{capture,application,projection,reduction,facts,audience}.py` | Capture/projection assume a fixed audience; private actor disclosure and member masks depend on it. PlayerUpdate explicitly declares membership fixed at Start. |
| Protocol and SDKs | Current player schema is 16. Initialization carries audience membership; ordinary operations cannot record a membership transition. |

Changing only the controller constructor leaves summons unusable through the
player API. Applying an operation's final audience to its whole history can
retroactively expose observations or hide facts that were authorized earlier.

## 3. Native control and resource ownership

Extend the existing summon membership with a general controller reference and
an optional summon-owned native AI handle. These are resource ownership data,
not a new controller hierarchy or second authority registry.

- For an external caster, borrow its existing controller. Never start, close or
  unregister it from summon rollback, dismissal, reset or rebind. Several summons
  sharing an external controller must remain independently removable.
- For an autonomous caster, retain the existing per-summon native AI route.
  Start it only after committed membership and publication, as today. Do not
  accidentally borrow a fixed AI assignment for a new actor UUID.
- Resolve the controller through Encounter. An absent/unusable assignment must
  produce a bounded native admission error, not silently change player control.
  Preserve existing behavior of supported nonexternal test controllers without
  adding a new controller factory or policy selector.
- Use the existing prepared join, concentration replacement, retirement and
  condition-graph-settled boundaries. Keep precommit cancellation distinct from
  errors after authority has committed. Preserve costs and old-summon survival
  on failed preparation.
- On Fey control loss, switch authority and allegiance at the settled removal
  boundary, before another command or AI step. Preserve actor UUID, HP, items,
  remaining duration, current turn execution ID and already spent resources.
  Whole-body removal must not briefly create a hostile AI assignment.
  Prepare any required AI assignment through the existing removal-admission
  participant before commit; dispose of it on voluntary veto. A failure after
  mandatory control loss cannot restore former command authority: revoke it and
  report the committed failure through the existing failure path. Preserve the
  removal batch's existing exclusion for a body whose existence also ends.
- Rebind borrows the new encounter's external controller or creates the required
  new owned AI assignment. Closing the old assignment must never close a caster.
  Keep the existing requirement for a controlled survivor's caster to be present.
- External control must not silently promote a temporary body into permanent
  companion gameplay. Separate that existing live-join side effect narrowly for
  summons; preserve initial-party companion flags, companion-only spell rules,
  terminal zero-HP summon removal and ordinary death-save behavior.

Record a passive native assignment transition at the existing committed
join/controller-change/leave owners. It identifies the actor, previous/new
controller identities and external/autonomous mode, with the existing causal
parent. It contains no seat credential, SDK object or executable callback.
Previous/new external owner actor UUIDs identify the actual caster, since a
shared controller's source UUID may identify another caster. Keep the current
anchor beside the controller assignment in CombatantState; no parallel registry.
Ordinary initial-party assignments have no summon owner anchor and do not change
the seat's initial observer membership when leaving an encounter.
Publish actual changes once. Canceled preparation publishes no committed change.
Birth keeps creation provenance; faction keeps allegiance. Neither substitutes
for current command authority, including for an unseen released Fey.

## 4. Session authority and external turns

The application maps existing external controller identities to authorized seats
from actual session composition. Apply committed assignment transitions to
current seat control before publishing the next command boundary. Keep an
indexed controller-to-seat lookup only if needed to avoid rescanning seats; it
is derived from that composition, not an independently editable ownership store.

Use current seat control as the source for action authorization, sheet
publication and existing outside-combat access. Audit every use of
`Session.player_uuids`; retain it only where initial-party identity is genuinely
needed, or remove it if it has no remaining independent purpose. Avoid a second
mutable roster that can disagree with seats. The roster must settle before the
operation publishes new owned actors' sheets.

Honor authored HUMAN/CODEX choices, including per-member overrides, during
session construction. Replace HumanController-specific wait/admission checks
with the existing external execution-mode contract plus seat ownership. Native
AI advancement must stop at either external controller. Keep the existing
human lifecycle value; add `waiting_for_codex` to the finite wire contract where
the native controller reports it, and update host scheduling, status/attachment
and SDK consumers of the waiting states.
This does not add a Codex orchestration service.

Add/remove/revoke operations invalidate applicable discovery/preview state and
command revisions through existing mechanisms. A stale selection, forged summon
UUID or former owner's command must fail before spending resources. Refresh
Publication.audience as well as live seat authority so bootstrap/reconnect does
not return the original roster.

## 5. Recorded membership and sensory composition

Add one finite, ordered player membership fact to the existing fact/node stream.
Its after-value is the affected seat's controlled and observer tuples with a
membership revision. It is emitted only on a real transition. Native controller
identities and unrelated seats remain private to the backend. The event order,
not an end-of-operation replacement field, determines when it takes effect.

Capture and projection must consume the recorded native assignment changes in
causal order. Grant precedes the new owned body's private/sheet facts and admitted
observer evidence; revocation precedes later evidence that is no longer
authorized. A single operation may contain both grant and removal. Preserve the
shared capture/walk and existing objective rows. Do not rewalk the full history
for each membership change or query final live entities during detached replay.

Live authorization and recorded projection are distinct consumers of the same
committed transitions. Validate that their final membership agrees without
using final membership to filter earlier events. Controller ownership facts
reach the affected seat even when it cannot visually observe the summon.

For observation changes:

- Initialize a newly admitted observer from its actual recorded native initial
  senses at the transition, using existing sensory publication/folding. Do not
  copy caster senses, fabricate a sight radius or disclose earlier private history.
- Remove a revoked/retired observer's contribution from AudienceComposition and
  its membership indexes. Recompose only the affected cells/contacts/effects/light
  sources; keep other observers' contributions and existing client exploration
  memory semantics. No full sensory refresh on every command.
- Keep the stream's stable observer UUID and original observer ordering. Append
  new members. On removal, the ordered transition supplies the new tuple; remap
  retained object/contact/effect member bits from old UUID positions to new ones
  once at that transition. Do not reinterpret old bits under new indices or keep
  an ever-growing list of dead observers. Explicitly cover implicit single-member
  encoding when crossing one/two observers.
- Record the transition before facts encoded against its new member order. All
  current membership-bearing caches/rows must follow the same rule. Preserve
  historical packets unchanged and replay them under their historical membership.
  A shared sensory table spanning a change uses explicit member columns whenever
  any consuming segment has multiple observers; a final single-member audience
  cannot justify omitting those columns. Decode each row under the membership
  active at its consuming fact, including one→two→one within one group.
- Grant normal controlled-body details once; on revocation stop private sheet,
  inventory and sensory updates, and apply existing visibility/retained-knowledge
  rules to the now-uncontrolled actor. Loss of authority is not evidence of death.
  Membership reduction removes the actor from active sheet/HUD/control affordances
  even if the actor remains visible. Retained historical facts are not deleted.

Extend the current finite codec, backend reference reducer, and both SDKs'
existing contracts/decoders/transport validation for this fact. The SDKs are
transport-only; do not add game-state reducers to them. Recorded state folding
stays in the backend reference reducer and the consuming client.
Bump the player schema once from the implementation baseline, regenerate through
`devtools/export_player_protocol.py`, and use existing compatibility rejection.
Do not create a second snapshot endpoint, per-spell client exception, protocol
migration service or gameplay-time schema building.

## 6. Implementation sequence

| Step | Deliverable and completion evidence |
| --- | --- |
| 1. Baseline and failing cases | Record current branch/environment and relevant timing baselines. Reproduce a human and Codex summon being auto-driven or rejected at public encounter/worker boundaries. Define the finite transition ordering with a recorded grant/revoke example. |
| 2. Native ownership and lifecycle | General/owned-AI membership data; external borrowing; native assignment publications; prepare/rollback/rebind/retirement and Fey handover. Native tests demonstrate correct turn ownership and unchanged costs/lifetimes. |
| 3. Session and recorded delivery | Dynamic seat membership, authored Codex preservation, external turn boundaries, sheets, ordered capture/projection/reduction and observer admission/removal. Complete one real cast-to-summon-command journey before expanding the matrix. Steps 2–3 are one functional slice, not separately finished features. |
| 4. Protocol and SDK integration | Schema/export, Python and TypeScript transport decoding/validation, authority changes in publications, reconnect/catch-up and cross-seat rejection. Supply an actual generated recording and backend reference-fold result for the client. |
| 5. Regression, timings and handoff | Run the scoped matrix and broader suites below, compare timings, resolve scoped failures, finish independent reviews and write the client handoff. |

Update current authored descriptions that still promise autonomous-only control
where they conflict with this amendment. Historical receipts remain historical.

Implementation must have a sub-agent tracking adherence to this plan. Anti-slop
and anti-OOP reviewers review the complete change and its evidence, with special
attention to ordered authority/observation and controller teardown. No separate
subsystem, class hierarchy or import-cycle workaround is needed. Low owners must
not import player/server/summoning runtime; passive lower-owned facts cross the
existing dependency direction.

## 7. Behavioral acceptance

Follow [HOW_TO_TEST.MD](../../HOW_TO_TEST.MD). Use current character-creation
fixtures with the original specialized builds, installed canonical creatures,
real casts and normal commands. Keep native composition tests where that is the
boundary being tested. Never replace a level/feature-dependent scenario with a
generic premade just to get a green result.

| Case | Observable acceptance |
| --- | --- |
| All eight families × human/Codex/native AI | Correct input/automation boundary after caster; one representative body per family and legal cast level. Existing all-form/stat/action tests retain their scope. |
| External play | Actual choices, movement, attack and end-turn succeed for the owner; no autonomous action occurs while waiting. Dragon's extra breath and existing bonus/contact phases remain usable under their current rules. |
| Two seats, multiple summons | Each seat controls only its own summons. Removing one body preserves caster and sibling control. Two casters in one seat are also supported. |
| Fey loss | Voluntary drop, concentration replacement, failed concentration and caster death switch to hostile AI. Former commands/dismissal fail; partial movement/action budgets and turn identity remain unchanged. |
| Retirement and cancellation | Dismissal, zero HP, expiry, family replacement, failed admission, paid interruption, committed publication failure, close/reset and rebind retain existing guarantees; no leaked or prematurely closed controller authority. |
| Unchanged native AI | AI-cast allies actually attack enemies; released Fey can attack former allies. Preserve the existing autonomous tests by assigning an actual AI caster for that scenario, rather than deleting their behavioral coverage. |
| Observation and replay | Grant/use/revoke in one operation, hidden control loss, shared sight overlaps, customized control-without-observation seats, one→two→one observers, removal of a middle observer, repeated summon churn. Live projection equals detached decoded replay and does not mutate saved history. |
| Private facts | Other seats receive no extra control or privileged sheets; former owners receive no later private observations. Another surviving observer still seeing a subject retains it. |
| HTTP and SDKs | One representative real worker/HTTP journey per external mode; wrong-seat and stale-state/discovery requests rejected without mutation. Python/TS validate and transport the same recording; the backend reference reducer proves reconnect before/after revocation yields the same final state and current bootstrap audience. |
| Actual Monty match | Two independent agents, separate seats/sessions, identical creator-backed L5 clerics, mirrored positions and normal resources. Give both the same explicit encounter-only Conjure Animals grant, plus existing Spiritual Weapon; use the same legal animal/cast level. Both must discover current membership, receive summon input turns and submit successful summon commands. Agents choose tactics from their own authorized observations; no canned driver presented as an agent match. Retain authorized streams and operator transcript, report outcome and any incomplete coverage. |
| Gameplay boundaries | Placement, concentration, duration, initiative, action/bonus/reaction economy, dropped real items, summon zero-HP departure and companion-only eligibility remain unchanged. |

Start with focused summon, encounter, player, worker and SDK suites; then run the
engine/AI/player/server suites, SDK tests and existing import-DAG/type checks for
the changed owners. Broaden to shared event/game replay consumers when the native
fact/codec changes touch them. Record pre-existing failures separately; do not
silently weaken tests or start unrelated repairs. Reviews and timings are not
substitutes for these behavioral checks.

## 8. Performance and client handoff

The Monty consumer must read ordered current membership and accept both human
and Codex external waiting states, instead of relying on bootstrap membership.
Keep that change a finite membership consumer, not a new game-state reducer.
Refresh its installed SDK before the actual match. Agent reasoning/wait time is
separate from measured backend command latency.

Compare before/after using the same checkout location, Linux uv environment,
authored builds, map/seed and warm-up. Run timings serially with reviewers/tests
quiet. Record cold startup separately from warm operation time, sample counts,
median/spread, native/capture/encoding time where existing tooling exposes it,
event counts, packet bytes and post-reply collection time. Reuse the existing
`devtools/player_server_acceptance` harnesses.

Measure unchanged ordinary movement, action discovery and the existing crowded
Fireball scenario; then summon cast/first external turn, repeated summon movement
and discovery/preview, native AI summon decisions, Fey revocation and retirement
with one/multiple observers, and a crowded multi-summon seat. Separate
the legitimate cost of an additional observer's evidence from steady-state cost
on encounters without summons. Retain cached lookup/mask paths; membership work
runs on actual transitions. Do not add world scans, per-query body construction,
per-action schema builds or a full sensory rebuild to support ownership.
Investigate repeatable regressions beyond the run's observed noise before calling
the implementation complete; this plan invents no new arbitrary millisecond SLA.

The backend handoff must state the schema version, input-boundary behavior,
ordered membership fact, observer-bit ordering rule, revocation behavior and
current bootstrap membership. Include a backend-generated cast → command → loss
or dismissal recording, SDK/replay evidence and timing comparison. NDClientGodot
integration is owned by the client thread; this plan changes no client repository
and sends no message to another chat.

## 9. Plan review receipt

Both independent reviews passed on 2026-10-22, with no remaining blocking
findings:

- **Anti-OOP/ECS — `healing_plan_review`: passed.** Tightened borrowed/owned
  controller cleanup, prepared Fey handover and committed-failure revocation,
  active HUD pruning, causal authority facts and sensory-table encoding across
  one→two→one observers within one group.
- **Anti-slop/scope — `plan_adherence`: passed.** Verified the complete eight-family
  scope, authorization/replay/retirement coverage and timing requirements.
  Corrected an initial draft assumption about SDK reducers: the existing SDKs
  remain transport-only, with no new game-state folding layer.

At planning review, the customized-seat observation policy in §1 was explicitly
proposed rather than asserted to be an existing rule; the human subsequently
authorized this plan. Implementation must still prove all stated acceptance
cases. No gameplay tests or benchmarks were run during planning; planning review
does not claim implementation or performance have passed.


## 10. Implementation receipt

Pre-change baseline is saved in `../audits/SUMMON_CONTROL_TIMINGS_2026-10-22_BASELINE.json`.
The native ownership, live session authority, ordered player audience, schema-17
transport and Monty consumer are implemented. The final combined engine, AI and
player/server run, including the conscious-combatant completion amendment below
and preceding the later color simplification in §12 and neutral-condition
correction in §11,
passed **5,497 tests with 20 expected failures and one warning in 469.93 seconds**.
The earlier rebind/sensory supplement passed 52. Python SDK
passed 110 tests and TypeScript SDK passed 83. Monty passed 22 tests, with a
separate real-creator symmetry check. Three capture child-link regressions were
repaired and nine old autonomous-summon player scenarios now issue explicit
external commands while retaining their behavioral coverage.

The independent reviews found and addressed same-occurrence ordering (apply
AudienceFact before private BodyRecords at that occurrence), fresh recorded
initial senses for a surviving body entering a new encounter, and later private
field-duration disclosure after authority is lost. The field-clock regression
now preserves historical knowledge while refusing subsequent private ticks.
Standalone combat logs use their original native cursor for membership instead
of the operation's final roster. Removing observers reindexes caches once and
recomposes their affected cells, with repeated/empty-observer churn coverage.

The real two-seat HTTP/SDK recording and detached reference state are in
`../audits/SUMMON_CONTROL_RECORDING_2026-10-22/`. Both SDKs validated all 28 records.
The actual Monty match used independent Sol agents, separate sessions and the
symmetric creator-backed fixture. The first incomplete duel is preserved separately.
The [fresh duel](../audits/MONTY_SUMMONERS_2026-10-22_VERIFIED/README.md) completed
naturally with Blue winning: both SDKs decoded 192 records, both seats completed
detached reference replay, and all 66 committed commands matched their public
packets and current control membership. One invalid agent selection was rejected
and corrected. Amber's weapon continued acting after its caster fell; combat
ended when that last conscious summon was defeated. The [timing report](../audits/SUMMON_CONTROL_TIMINGS_2026-10-22.md)
retains the original baseline, both nine-case runs and the matched A/B/B/A check.
The requested implementation and acceptance work are complete. The timing report
retains the busy-host uncertainty; no blanket zero-overhead claim is made.

Validation logs are retained in
`../audits/SUMMON_CONTROL_VALIDATION_2026-10-22/`. The final private field-clock
fix passed a focused 16-test audience/replay/duration batch and the final combined
run. Final logs and JUnit are also retained in the first duel audit's `validation/`
directory. Scoped Pyright still reports five diagnostics on unchanged lines in
`facts.py` and `projection.py`; full static typing is not claimed clean.

## 11. Live-match findings and human-authorized completion rule

The first independent summoner duel verified both sides commanding Wolves and
Spiritual Weapons, ordered control loss, and continued weapon commands after its
caster fell. It did **not** complete naturally: Blue stabilized at zero HP, its
summons were gone, and Amber had no legal opponent, but the existing encounter
predicate counted every non-dead combatant as a surviving faction. The exact
blocked run must be preserved without an encounter-completion claim.

The human explicitly selected **"End as soon as a side has no conscious
combatants"**. This authorizes a narrow amendment to the existing faction-end
check: conscious summons count for their side; unconscious, dying, stable and
dead combatants cannot keep a side in combat. Do not use inability to act as a
substitute for unconsciousness: a conscious stunned or paralyzed actor is still
conscious. Do not kill, stabilize, heal or remove a body to end combat. Existing
death-save behavior continues while a conscious ally keeps the side fighting.
No new scheduler, victory service or parallel roster is needed.

Acceptance adds native scenarios for downed/stable last combatants, a conscious
surviving summon, positive-HP unconsciousness and conscious incapacitation. The
incompatible old expectation that a lone downed side must finish death saves
before combat ends must be migrated to the chosen rule. Repeat the actual
symmetric Monty duel after the fix. The adherence agent implements the bounded
native change; the parent performs the antislop and antiOOP review and owns the
quiet performance comparison before relaunching the match.

The first run also reached Monty's existing 128-execution session cap. A fresh
session previously refused even a deliberately resumed attachment. Monty now
accepts an explicit matching `expected_attachment_epoch` through the existing
server attachment compare-and-swap; default takeover refusal remains. Seven new
checks passed, and Amber reattached to the same live game, roster and command
counter. Natural encounter completion is `outside_encounter` plus the recorded
`encounter_end` fact; whole-game `terminal` is a separate boundary. Monty now
returns immediately at `outside_encounter`.

Final architecture checks caught two mistakes in the first implementation: the
encounter predicate interpreted four concrete condition names, and its two code
comments violated the encounter source-hygiene rule (**41 passed, 2 failed**).
Both are corrected. `BaseCondition.denies_consciousness` now follows the existing
neutral condition-data pattern, with authored values on Unconscious, Sleep,
Eyebite Asleep and Glyph Sleep. The existing faction pass reads that flag and
`contributions_active()`; no new registry, sensory work or life-state writer was
added. The authored/renamed matrix proves display names do not determine the rule.
Final encounter, transform, life-state, architecture, catalog and protocol checks
passed **111 tests in 40.78 seconds**. The adherence/antislop/antiOOP re-review
passed. Contribution gating reuses the existing owner method; no separate
end-to-end retained-Sleep suppression scenario is claimed.

## 12. Human-requested single dragon color choice

The human then explicitly requested simplifying Summon Dragon to one color
choice, with matching caster resistance, and instructed us not to pursue roughly
one-millisecond differences on a busy machine. Performance qualification above
is closed with its stated limits; no further tiny-difference benchmark loop.

Use the existing summon form selector for black/acid, blue/lightning,
green/poison, red/fire and white/cold. These five choices instantiate the same
canonical Draconic Spirit body, not five new creature implementations. One
passive color-to-damage mapping determines both Breath and the caster's linked
resistance. Remove the independent Breath/resistance selections. Record the
color in native recipe parameters and the public creature name. Keep current
HP/AC scaling, Rend count, free Breath cadence, five innate body resistances,
concentration, placement, ownership and retirement unchanged.

Migrate the existing slot-5-to-9, elemental resistance, two-seat condition
publication and player transport tests without dropping their coverage. Verify
exactly five one-facet choices, matching published Breath/resistance, color-bearing
births and exact resistance cleanup. Update authored description, benchmark
selector and client handoff. No new artwork, registry, controller system or
protocol field is needed. The completed Wolf/Spiritual Weapon duel remains valid
control acceptance; it does not claim to exercise this dragon-only amendment.
The adherence subagent supplies antislop and antiOOP review of this amendment.

Implemented with five normal `form` rows and one existing body factory. The
adherence/antislop/antiOOP review passed with no blocker. The focused six-file
native/player batch passed **276 tests and one expected failure in 42.01 seconds**;
scaling, all five body resistances, matching caster lease, cleanup, public names
and actual free Breath state transitions remain covered. Obsolete independent
constructor/template inputs are rejected only at Summon Dragon, without changing
global action validation. Final architecture/protocol checks passed as part of
the 111-test corrected batch above. Logs for these batches and the initial
architecture failures are retained in `../audits/MONTY_SUMMONERS_2026-10-22/validation/`.
