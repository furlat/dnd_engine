# Dismiss summons when their caster is defeated

Date: 2026-10-22. Status: implementation and deterministic validation complete;
independent live match completed with the explicit coverage limit below.
Source: the current `feature/rules-checking` working tree,
including the uncommitted summon ownership and single dragon color changes.

## 1. Requested correction

The human challenged the recorded Spiritual Weapon continuing to fight after its
caster fell, clarified that summons should disappear at caster zero HP regardless
of concentration, and requested this cleanup plan. Lack of concentration does not
establish an independent lifetime.

Larian's [official early-access patch notes](https://baldursgate3.game/news/community-update-14-forging-the-arcane_44)
document dismissal when a caster becomes incapacitated. Its
[Summon documentation](https://docs.baldursgate3.game/index.php?title=Functors:Summon)
separately describes the caster-death link and optional concentration extension.
These explain the distinction; this plan adopts the human's narrower **zero-HP
and death boundary**, not every BG3 incapacitating condition or a universal
tabletop D&D rule.

| Test definition | Contract |
| --- | --- |
| Requested behavior | A caster's existing summons depart when that caster actually becomes downed at zero HP or dies, irrespective of concentration. |
| Boundary | Native damage/life transition through summon retirement, then the normal worker publication and next actor input. |
| Input | A legal damaging action, committed direct life-state transition, or instant-death effect against a caster with live summons. |
| Expected output | All affected summons lose agency, control, observation and deployment through existing retirement; the next boundary contains no departed summon. The caster retains its real life state and normal death-save rules. |

This is a correction to the lifetime assumptions preserved by the
[controller ownership plan](SUMMON_CONTROLLER_OWNERSHIP_PLAN_2026-10-22.md), not
a replacement for its ownership, replay, sensory or dragon color work.

## 2. Behavior and scope

Cover the eight existing families in `SummoningSystem`: Animals, Fey, Fiend,
Elemental, Planar Ally, Dragon, Spiritual Weapon and Flaming Sphere. Use the
actual summoner UUID, not a shared controller's source actor or the whole seat.

| Situation | Planned behavior |
| --- | --- |
| Caster commits DYING at zero HP, or enters STABLE directly at zero HP | Dismiss its affected summons before the next actionable boundary. |
| Caster dies, including instant death without ordinary damage | Same cleanup, even for a non-concentration summon. |
| Caster stabilizes, takes further damage while down, or later dies | No duplicate removal, control revocation, item drop or sensory detach. |
| Caster is healed or revived afterward | Removed summons do not reappear; a new legal cast is required. |
| Damage is canceled or Death Ward prevents the caster's defeat | No dismissal from this new rule. Existing concentration consequences still apply. |
| Temporary HP are consumed while the actual caster remains alive | No dismissal merely because that pool reaches zero. |
| Caster has positive HP and is asleep, unconscious, stunned or paralyzed | Add no universal dismissal trigger. Preserve the existing concentration rules and conscious-combatant end rule. |
| One caster falls in a seat containing another caster | Only the fallen caster's summons depart; the other caster and summons retain control. |
| Damage also defeats a summon, or concentration also ends its existence | Settle one departure per body with the correct causal event. |

**Explicit authorized Fey resolution:** caster defeat ends the original summoned
body even if concentration was previously lost and it has already become hostile.
Its lifetime still has the original `SummonOrigin.summoner_uuid`. This deliberately
supersedes the earlier expectation that a released Fey survives its caster's
death. Ordinary loss of concentration while the caster remains alive continues
to release a living hostile Fey. Rebinding without the original caster present
is not itself evidence that the caster has died; that existing scenario remains
valid. The human authorized this behavior by requesting implementation of this plan.

Ordinary party companions, unrelated creatures and effects outside these eight
summon families are outside this change. Do not rewrite animate-dead behavior,
spell economy, durations, stats, AI tactics, concentration policy, the selector,
or the general encounter scheduler. No client repository changes are included.

## 3. Verified source boundaries and the missed coverage

| Existing owner | Relevant state |
| --- | --- |
| `dnd/entity.py::_transition_life_state` | Publishes the existing typed `LifeStateChangeEvent` after authoritative life state commits. Canceled death can restore 1 HP; incoming damage alone is not proof of defeat. |
| `dnd/conditions.py::Concentrating._install_concentration_handler` | Zero-HP applied damage can release concentration before `receive_damage` commits DYING/DEAD. A later life-event listener alone cannot prevent a transient Fey handover. |
| `dnd/summoning/system.py` | Owns memberships, condition-removal admission, group settlement and retirement. Its existing event filter handles damage/death but `_resolve` checks the event target as a summon, not as a caster. |
| `dnd/summoning/conditions.py` | Spiritual Weapon has a linked owner with no caster-downing handler. Elemental/Planar Ally's owner handles death but not downing. Fey concentration owns control separately from existence. |
| `dnd/types/summoning.py` | `SummonOrigin` already identifies the caster; `TerminalOwnerRelease` already supplies exact mandatory retirement authority. |
| Player audience and sensory owners | Existing schema-17 revocation removes controls/observer contributions and active private details. This cleanup must use that existing path. `SpatialFact.terminal_cause` already exposes `SummonDepartureCause`, so a new reason requires protocol regeneration. |

The suite did not merely omit this boundary. The recent
`test_encounter_conscious_end.py` explicitly expects a fallen caster's weapon to
keep fighting and preserve its death-save turn. The lifecycle suite also expects
Fey to survive source death. Those expectations encode the behavior being changed.
The recorded Monty duel then exercised the same mistake and was described as
successful lifetime behavior. Passing transport/control checks did not validate
that rules assumption.

## 4. Implementation approach

Keep the change inside the existing native composition owners. Entities remain
ordinary data with their existing life-state writer; the summoning system owns
the consequences for its bodies.

1. Reproduce the Spiritual Weapon case with a real cast and damage that commits
   caster downing. Record the current erroneous survival at native and worker
   boundaries before changing the expected result.
2. Consume the existing committed life-state event in the summon owner. Cover
   downing, direct stable entry and death; ignore healing/revival and unrelated
   actors. Do not infer defeat from condition names, action permission, intended
   damage, or a temporary HP pool. Keep imports directed toward passive life
   contracts; the entity/health layers must not import summoning or player code.
3. Resolve the affected memberships from their existing summoner provenance only
   when this lifecycle transition occurs. Start with the existing membership
   collection; do not add a second ownership registry, per-frame polling, or
   per-action/sensory scans. A retained derivable index is unnecessary without
   evidence that the bounded transition lookup is material.
4. Feed each exact existence condition through the existing prepared mandatory
   retirement and condition-graph settlement. Add `CASTER_DEFEATED =
   "caster_defeated"` to the existing departure-cause enum: this is mandatory
   cleanup, distinct from voluntary dismissal, concentration sustain loss and
   the summoned body's own defeat. The existing spatial terminal-cause field
   carries it; no additional field is needed. Do not kill the summoned creature to simulate
   dismissal, and do not let a voluntary-removal veto keep it active.
5. Coordinate this with existing concentration-removal admission and group
   settlement. If the same damage operation ends caster life and Fey control,
   whole-body retirement wins: no hostile assignment publication or AI turn for
   a body that is departing. Deferring a possible handover must still complete
   the ordinary hostile transition if the caster ultimately remains alive.
   This ordering must be proved in the first slice, not postponed to integration.
   Any necessary neutral removal hook belongs to the existing protocol; no
   spell-specific check belongs in health or generic condition mechanisms.
6. Preserve simultaneous damage semantics: later targets resolve against the
   admitted group state, then departures settle. Do not remove a caster's summon
   midway through a multi-target effect and thereby change target resolution.
   Reuse the current group settlement, retirement preparation and error handling.
7. Retire all siblings even if a committed publication fails for one. Preserve
   the existing committed-failure reporting; never restore authority after a
   committed mandatory loss. Close only summon-owned native AI controllers;
   borrowed Human/Codex controllers and unrelated summons remain usable.
8. Enclose sibling removals in the existing removal/settlement scope so an
   intermediate combatant-leave callback cannot end combat before their cleanup
   settles. Finish retirement and existing audience/sensory revocations before publishing
   the next input boundary or evaluating the final surviving sides. Keep the
   chosen encounter rule: combat ends when at most one side has conscious
   combatants. A different conscious ally can still keep a downed actor's side
   fighting and allow its death saves; its own dismissed summons cannot.

Regenerate the normal protocol artifacts and both SDK contracts through
`devtools/export_player_protocol.py`. The public finite enum changes, so increment
player schema 17 to 18 (or the next version if the baseline changes) and recompute
its identity through the exporter; protocol version stays 1. Keep ordinary
compatibility rejection. Do not add a special client dismissal command, snapshot
endpoint, schema field, SDK reducer, new controller hierarchy, or full sensory
rebuild. Birth history remains true; current control and current presence change
through ordinary recorded facts.

## 5. Behavioral acceptance and existing tests to migrate

Follow [HOW_TO_TEST.md](../../HOW_TO_TEST.md). Keep specialized creator-backed
fixtures, real spell casts and normal commands. Use table-driven scenarios with
one clear helper, rather than a new test framework or a full combinatorial cross
product. Architecture checks are separate from gameplay evidence.

| Case | Required evidence |
| --- | --- |
| Eight-family native matrix | Actual caster downing retires each body, including non-concentration Weapon/Elemental/Planar Ally; Dragon's resistance and Sphere's existing bound effects end through their owners. |
| Human, Codex and native AI | Representative cases prove the same lifetime and correct borrowed/owned-controller teardown for each mode. |
| Multiple bodies and two casters sharing a seat | The defeated caster's siblings all retire; the surviving caster's bodies and command access remain. |
| Fey control/existence ordering | A lethal hit while controlled causes one departure and no temporary hostile handoff; already released Fey also departs under the explicit proposal in §2. Nonlethal concentration loss still yields a working hostile Fey. |
| Death and prevention | Instant death/direct committed transitions work. Real Death Ward, prevented damage and temporary-HP depletion preserve summons if caster defeat never commits. |
| Simultaneous caster/summon damage | Targets retain the existing resolution semantics; overlapping defeat/concentration causes emit one cleanup per body. |
| Mandatory cleanup | A voluntary condition-removal veto cannot retain defeated-owner summons. Existing terminal cleanup/error-path coverage remains applicable. |
| Stabilization/healing | Repeated downed-state transitions do not duplicate cleanup; recovery never resurrects old summons. |
| Positive-HP status | A representative non-concentration summon is not newly dismissed just by a positive-HP incapacitating condition. Existing concentration consequences remain covered. |
| Encounter outcome | A side with only its downed caster and now-dismissed summons ends immediately after settlement. A real conscious ally still keeps combat active and permits the downed actor's death saves. |
| Real worker publication | Owner sees current membership revoked before the next boundary; stale summon commands fail without spending resources. Other seat receives only authorized departure evidence. Bootstrap/catch-up and detached replay preserve the same final membership. |

Replace the two weapon-survival scenarios in
`tests/engine/test_encounter_conscious_end.py`. Retain their death-save/remaining
ally coverage using a genuinely surviving ally, not the fallen caster's summon.
Migrate the source-death Fey expectation in `test_summoning_lifecycle.py`; preserve
its mandatory-removal-veto coverage. Keep ordinary drop/replacement, expiry,
rebind, items, single dragon color and native AI behavior tests intact.

Run the focused summon, life-state, concentration, encounter, player and relevant
architecture suites first, then the combined engine/AI/player-server regression
once the fix settles. Run both SDK suites and the protocol identity/export checks
for the new finite cause, and decode the new exact recording through both SDKs.
Record failures and
validation scope honestly; the existing unrelated typing diagnostics are not part
of this cleanup.

## 6. Performance and live acceptance

Reuse the existing timing harness and results. Before implementation, capture a
small same-host comparison for caster defeat with one and several summons, plus
an ordinary no-summon damage operation. Repeat those cases after the change,
recording whole command-to-boundary time, capture/encoding where available,
event counts and observer changes. Measure actual extra retirement work rather
than expecting dismissal to cost the same as leaving bodies alive.

No new benchmark framework, broad optimization lane or new millisecond target.
Do not chase roughly 1 ms differences on a busy host. Investigate a reproducible
stall, duplicate work or a substantial unexplained regression; retain host noise
and transport exclusions explicitly. The change must not add work to routine
movement, cached discovery or sensory calculation when no life transition occurs.

After deterministic checks pass, run one fresh independent Sol-versus-Sol Monty
match with the existing symmetric creator-backed summoner fixture and authorized
seat isolation. Both agents must cast and command summons; when a caster falls,
its surviving linked summons must depart without receiving another input turn.
Retain exact packets, receipts and outcome, decode both SDKs and run detached
reference replay. An incomplete run is reported as incomplete. This remains a
gameplay acceptance run, not a timing measurement of agent reasoning.

## 7. Documentation, review and completion

Preserve all earlier packet bytes and validation receipts. Annotate the earlier
completed duel and handoff: transport and command authorization passed, but the
weapon-survival portion exposed the missing lifetime rule and is superseded as
gameplay acceptance. The new match receives a separate audit directory.

Update the ownership plan's lifetime assumption, this plan's implementation
receipt, RECOVERY_PLAN and the backend client handoff. The client uses the same
retirement/membership message shapes with the regenerated schema version and
new departure-cause value; it must not implement a second caster-HP cleanup rule.
Do not message another chat or edit NDClientGodot.

Required reviews:

- **Anti-slop reviewer:** check that only the eight existing families and chosen
  defeat boundary change, Fey semantics are explicit, old coverage is migrated
  rather than weakened, and evidence claims match recorded behavior.
- **Anti-OOP/ECS reviewer:** check native ownership, import DAG, event/group order,
  exact mandatory retirement, controller cleanup and absence of new systems.
- **Implementation adherence subagent:** track this plan throughout implementation,
  flag drift, review the timing evidence and the completed change. Planning review
  does not substitute for this final implementation review.

Completion requires passing relevant regressions, current-roster/replay evidence,
the corrected independent duel, bounded timing results, and both final reviews.
The implementation receipt below distinguishes current results from the original
planning-only review.

### Plan review receipt

Both independent reviewers passed the concrete plan on 2026-10-22 after these
corrections were incorporated:

- **Anti-slop — `summon_cleanup_scope_review`: passed.** Kept the eight-family
  boundary, made the released-Fey override explicit, removed speculative
  temporary-form requirements, preserved actual temporary-HP/Death Ward cases,
  and bounded the validation and timing work.
- **Anti-OOP/ECS — `summon_cleanup_ecs_review`: passed.** Identified the early
  concentration-loss/late life-state ordering risk, required sibling settlement
  through existing owners, and corrected the public departure-cause assumption.
  A precise finite `caster_defeated` cause and normal schema/SDK regeneration are
  planned instead of mislabeling the summoned body as killed.

These are planning approvals only; final implementation review is recorded below.

## 8. Implementation receipt

### Bounded correction found by live acceptance

The fresh independent duel exposed a pre-existing Spiritual Weapon movement
defect: its authored flying Move has no legal destination even on a fresh turn.
The speed grant uses the entity UUID, while existing grant resolution requires an
active condition owner. Restore the already-authored 20-foot flight using the
existing `InnateFlight` condition and declare that content dependency, matching
other flying summon bodies. This adds no movement rule or resolver.

| Test definition | Contract |
| --- | --- |
| Requested behavior | A controlled Spiritual Weapon can use its existing 20-foot movement. |
| Boundary | Real cast, native movement action and worker choices/preview/command. |
| Input | A fresh weapon turn and an adjacent legal destination. |
| Expected output | Move succeeds, spends 5 feet, resets on the next turn, and caster defeat still removes the body and its owned contributions. |

The anti-OOP/adherence reviewer approved this narrow acceptance correction. The
recorded duel was left untouched and explicitly predates this correction;
fresh deterministic native and worker cases qualify movement. Original timings
predate it; a separate final-code confirmation is now retained in the timing
report. Do not expand into general flight or pathfinding work.

The final native/player/content/architecture batch passed **322 tests, 1 xfailed,
81.33 seconds**. Real Human/Codex worker movement and subsequent defeat/HTTP
replay passed **3 tests in 11.05 seconds**. The independent ECS/adherence reviewer
passed the implementation, declared dependency and retirement of the flight
contribution. Stale factory prose claiming no manual control was also corrected.

The existing `SummoningSystem` consumes committed life changes through its indexed
pre-completion route. Completion facts themselves do not execute handlers. Life
state is already authoritative at this point; retirement uses the recorded parent
event, or a root for a direct transition without a parent, never the unregistered
effect event. Memberships are selected by their real original caster UUID and
retired through existing mandatory condition ownership. There is no second summon
registry, entity-layer dependency, polling or added sensory rebuild.

Fey zero-HP concentration loss waits only for its current damage lineage to settle.
Actual defeat retires the body without starting hostile AI; prevented death at
1 HP completes the ordinary hostile handoff. Grouped damage may have completed
before concentration callbacks run, so that path hands over immediately instead
of retaining an unresolved pending entry. Ordinary nonlethal loss is unchanged.
Pending transition data is cleared on retirement, cancellation, completion and
reset. Summon-owned native AI closes; the caster's borrowed controller survives.

Independent review found a second ordering case: opposing casters defeated in one
simultaneous group. The regression reproduced encounter end between their two
departures. The existing group settlement now holds one membership scope across
all queued events, attempts remaining events after a committed failure, and ends
combat after both sides' cleanup. Empty groups still return immediately. This
final group-scope amendment followed the timing capture and arena startup; the
duel and timing cases exercise individual caster defeat. Its native regression
and related summon/encounter batch passed **176 tests in 22.47 seconds**.
An additional grouped instant-death Fey regression passed unchanged (**1 test,
4.59 seconds**): the existing group owner settles life transitions before deferred
death handlers, so no extra guard or mechanism was added for that route.

Schema **18**, protocol **1**, adds `caster_defeated` to the existing terminal
cause enum. Both SDK contracts and the normal schema/OpenAPI/field-ledger artifacts
were regenerated. Digest:
`8eb07a2f102b0549f83fc6556b65359a3f061bcb5d71b1a1aa39973ba5c8867f`.
An earlier concentration retirement can truthfully retain `sustain_lost`.

The first focused native, worker, HTTP, life/condition, architecture and protocol
batch passed **245 tests in 56.69 seconds**. Python SDK passed **110** and TypeScript
SDK **83**. The new creator-backed worker cases prove both Human and Codex control,
two casters sharing one seat, exact owner-only dismissal, unauthorized stale
commands, observer/private-sheet removal, detached decoded replay and HTTP
bootstrap/catch-up/reattachment. Existing tests that expected weapon/Fey survival
were corrected; death-save coverage now uses a real conscious ally. Native cases
cover all eight families, both grouped/ungrouped death prevention, positive-HP
conditions, temporary HP, instant/direct transitions and native-AI resource ownership.

[Timings](../audits/SUMMON_CASTER_DEFEAT_2026-10-22/timings.md) retain before/after
data, excluded warmup and three samples per case. Ordinary damage command plus
encoding stayed **9.62 → 9.62 ms** median. Weapon defeat changed **11.05 → 17.16 ms**;
Weapon+Wolf changed **18.85 → 23.74 ms**. These cases now perform the missing
retirement and combat end, adding 16 events and one sensory event. Maximum after
was **24.63 ms** for command plus encoding. No stall was observed in these bounded
cases; transport/rendering, agent reasoning and larger summon populations are
not measured. No one-millisecond noise investigation was added.

A single final-code confirmation includes both later corrections: ordinary
damage **10.15 ms**, Weapon defeat **16.52 ms**, Weapon+Wolf defeat **25.00 ms**
median, maximum **25.55 ms** command plus encoding. Flight contributes four more
native retirement events but no additional sensory events or encoded bytes.
The same expected final populations and boundaries passed. This measures defeat,
not casting or movement; no broad performance claim is inferred.

The combined engine/AI/player regression passed **5,542 tests, with 20 expected
failures and one warning in 594.29 seconds**. Its source was imported before the
final group-scope amendment, independently qualified by the focused batch above.
The warning is the existing VersionRows serialization warning in a transport
review test. The independent ECS/adherence reviewer passed the final source and
timing evidence with no blocker. Both the ECS/adherence and anti-slop reviewers
passed the final source and evidence with the live-coverage qualification below.

The independent Sol-versus-Sol match ended naturally in round 16: Amber won,
remaining at 28/38 HP; Blue became DYING at 0/38. Both seats received
`encounter_end` and `outside_encounter` at sequence 210. All 145 committed
commands matched exact public packets and current authority; one invalid potion
selection was rejected and corrected. Python and TypeScript SDKs decoded all
422 packets, and both seats passed detached reference replay. No separate live
PlayerState oracle was captured. The
[new archive](../audits/MONTY_SUMMONERS_2026-10-22_CASTER_DEFEAT/README.md)
retains exact streams, receipts, errors, reconnect evidence and lifetime facts.

**Direct live caster-defeat dismissal was not exercised:** Wolves departed
earlier and both Weapons expired at sequences 177/182. Thus this run qualifies
independent summon control, expiry, reattachment and natural completion. The
native and worker cases separately prove dismissal with living bodies. This is
a qualified implementation result, not a claim that every §6 scenario occurred
live. The unchanged arena also predates the final group-scope and weapon-flight
corrections, qualified separately above.

The adherence reviewer clarified the live evidence limit during round 10: if all
summons expire or depart before caster defeat, record direct live caster-defeat
dismissal as **not exercised**. Independent control and natural completion remain
valid evidence; the native/worker cases separately prove dismissal with living
bodies. Do not manipulate the game or automatically repeat matches until a
preferred sequence occurs. This qualification is not an assertion that the
unobserved live case passed.
