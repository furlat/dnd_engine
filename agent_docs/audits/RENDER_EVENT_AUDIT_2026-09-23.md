# Render event purity and causality audit — 2026-09-23

Read-only review by the event/causality reviewer. This document is the only repository edit made for this audit. Read `RECOVERY_PLAN.md`, the global `bug-fix` skill, and `HOW_TO_TEST.MD` first. Authoring/importers and XYZ compositing have separate reviewers; their findings are not claimed as independently verified here.

## Result

The intended boundary still exists. Native execution produces recorded initialization and complete lineages; projection emits an observer's passive facts; latest reduction advances independently of historical playback; the frame sampler and drawer read retained player state. I found no live `Entity`, `GridMap`, action execution, or `EventQueue` query in the current frame-sampling path. Damage, saves, death, conditions, equipment, destruction, and surface membership are not computed by the renderer.

There is nevertheless a **current, reproduced public replay failure**: newly generated object-destruction facts cannot decode from their own JSON. The recently added spell compatibility hook wraps the entire public fact union and changes strict nested placement validation. This blocks the actual clip/server-style byte boundary, even though direct in-memory execution can appear healthy. Fix it before claiming the present build supports cold destruction replay.

There is also a reproduced **coverage-report omission**: a real bound portal animation is reported merely as a received fact. Separate from those defects, historical spell compatibility assumes a propagation policy from spell identity without proving the archive epoch; and live play/review recording duplicate the admission bookkeeping around an otherwise shared binder and sampler. Those are bounded cleanup concerns, not evidence that the event architecture must be replaced.

## Confirmed findings

### E1 — Public destruction JSON fails at the fact-union compatibility hook

**Active, high impact, high confidence.** Relevant locations:

- `game/player_facts.py:386`: `ObjectDestroyedFact.placement` is the native passive `WorldObjectPlacement` value.
- `game/player_facts.py:404`: `BeforeValidator(upgrade_player_fact)` wraps **every** member of `PlayerFact`.
- `game/recording_compat.py:16`: the hook changes only spell dictionaries, but receives every fact first.
- `dnd/types/world_placement.py:47`: placement has strict tuple-valued coordinates/supports.
- `game/player_reduction.py:240`: the real public decode uses `PlayerSequence.model_validate_json`.

Fresh `prop_destruction_history` inputs failed, including wardrobe, bookshelf, storage shelving, ingredient shelves, pottery cluster, crates, chests, and statues. They are generated during the test, not stale archives. The error is:

```text
lineages.…events.…fact.object_destroyed.placement.position
  Input should be a valid array [type=tuple_type, input_value=[5, 4], input_type=list]
lineages.…events.…fact.object_destroyed.placement.covered_supports
  Input should be a valid array [type=tuple_type, input_value=[…], input_type=list]
```

Isolation in the current Python 3.13.12 / Pydantic 2.13 runtime:

| Identical native placement/fact JSON decoded through | Result |
| --- | --- |
| `TypeAdapter(WorldObjectPlacement)` | Pass |
| `TypeAdapter(ObjectDestroyedFact)` | Pass |
| Same discriminated `PlayerFact` union, without the outer before-validator | Pass |
| Current `PlayerFact` union, with its outer before-validator | Fails on the two tuple fields |

The outer hook materializes the fact into Python values before nested validation. Returning an unchanged dictionary is therefore not semantically neutral for strict JSON-native models. The native private codec does not share this exact failure: it explicitly validates each concrete event as JSON in passive mode at `game/event_record.py:122`.

**Smallest correction:** keep the legacy spell upgrade at the spell/archive admission boundary, without intercepting unrelated fact decoding. Preserve JSON validation for strict nested values. Do not loosen `WorldObjectPlacement`, replace tuples with arbitrary containers, suppress the error, or synthesize missing placement data. Verify direct public encode/decode of a real destruction history, then rerun destruction and liquid replay tests. Also retain a representative non-spell nested-value round trip alongside the spell compatibility test; the existing spell-only test did not cover this effect on the union.

### E2 — Actual portal cues are omitted from observed coverage

**Active diagnostic defect, low gameplay impact, high confidence.** At `game/presentation_coverage.py:119`, `visit_group` records attacks, conditions, equipment, shoves, forced movement, damage, body actions, hops, movement, healing and lifecycle. It does not record `value.portals`. The declared registry knows `portal_transfer` at `game/choreography.py:1299`; the actual cue is also typed and has an `event_uuid` at `game/portal_animation.py:12`.

Reproduced with the existing real native `portal_history(program="bare-walk")`, public JSON replay after producer reset, `bind_motion`, and `lineage_coverage`:

```text
portal cues 1
coverage [('portal_animation', 'received', [])]
```

This is **not** a missing portal animation. The inventory underreports evidence that it already has. It makes a missing-animation review less useful because an authored and bound behavior looks unbound.

**Smallest correction:** register the existing portal cue owner in the same coverage traversal. Check the adjacent stationary/contact/reaction cue lists for comparable accounting omissions while touching that traversal, without introducing a new registration or dispatch system. Do not turn every `received` fact into a failure: undisclosed participants, linked applications and canceled parents can legitimately have no independent cue.

### E3 — Retained native destruction archives reject later event fields

**Active compatibility defect, high confidence; distinct from E1.** The completed core run has **three failures and two setup errors** in `tests/game/test_device_destruction.py` while reading `legacy-device-destruction.json.gz`, `legacy-door-destruction.json.gz` and `legacy-web-destruction.json.gz`. They stop at native `RecordedSequence.model_validate_json`, before public projection or drawing. `game/event_record.py:113–120` requires current event fields not retained by those actual archives: `action_economy_spent` on Action/Movement events, and that field plus `harmful`, `harmful_target_entity_uuids` and `target_type` on Spell events. The five outcomes are the unknown-replacement case, late-wreck-sight case, device/door settled-pixel cases, and hidden-before-removal legacy case.

**Smallest correction:** inspect these retained source generations and restore supported archive admission explicitly, preserving available recorded evidence. Missing modern facts must not be recovered from live entities, treated as known false/payment outcomes without evidence, or silently replaced by newly executed histories. If a newer presentation distinction was genuinely absent from the archive, retain that limitation rather than inventing gameplay facts. Keep the actual old recordings as the compatibility test inputs.

## Design concerns with bounded recommendations

### R1 — Legacy area policy is an inference, not a recorded fact

**Active only for input missing `area_propagation`; high confidence about the implementation, historical exactness unverified.** `game/recording_compat.py:6–13` chooses `connected` for `spell.fireball`, otherwise `line_of_effect`. Existing explicit values win. The native decoder uses this at `game/event_record.py:111`; the public decoder uses the problematic union hook above. Current projected casts carry the explicit native field, so this is not a current per-spell rendering branch.

The test at `tests/game/test_aoe_surfaces.py:135` builds a modern dictionary with the field absent. It proves the chosen compatibility policy and explicit-value precedence; it does **not** prove what every historical Fireball producer or renderer did. Native schema version 2 and public schema version 1 span other changes and do not by themselves identify an epoch with this geometry behavior. This review has not established a supported source epoch for that inference.

Keep existing approved replay behavior during the immediate decoder repair. Subsequently document which retained archive generation the default actually represents and verify an existing saved example from that generation. If older archives differ, migrate those known recordings explicitly at intake. Do not infer new mechanics in the drawer, add a hash audit, or claim pixel-exact historical compatibility from the synthetic missing-field test.

### R2 — Shared execution is surrounded by duplicated head admission

**Active maintenance risk; no actual parity drift reproduced in this audit.** Compare `game/encounter_play.py:251–299` with `devtools/animation_review/record.py:323–404`. Both independently:

1. Reduce/stage a presentation group and prepare contacts/media.
2. Choose motion versus choreography and load its media.
3. Register condition lifetimes, spatial lifetimes and deposit start times.
4. Retain motion media, body history, feedback and gaps.

They call the same existing functions, and both ultimately use `sample_playback_frame`; the gallery is not running a separate invented combat renderer. However, adding the next persistent effect requires remembering both orchestration blocks. There is also repeated traversal of nested group/motion states in condition lifetimes, spatial lifetimes and body trails. These traversals describe different outputs and are not automatically interchangeable.

**Smallest useful consolidation:** one ordinary head-admission function returning a passive bound-head record and the existing updated presentation accumulators. Keep native production, live input, video encoding, camera framing and review checks in their current callers. Preserve the absolute clock and the existing motion/choreography types. No second timeline language, generic scheduler framework, ECS rewrite or inheritance hierarchy is needed. First prove one saved sequence has the same sampled state/contact/phase results through both callers, then move the bookkeeping mechanically.

`game/play.py:107` is the older finite cast/equipment demonstration and `game/demo.py` is the door/light demonstration. They intentionally exercise narrower paths and do not register the current maintained-media accumulators. Treat them as scoped demos/regressions, not proof that the full encounter/gallery behavior has parity. They are not a reason to maintain three complete gameplay executors.

### R3 — A passing gallery case is not a complete-binding or artistic approval

**Active report semantics; no new gameplay defect inferred.** `devtools/animation_review/record.py:498` sets `status="passed"` from recorded checks and separately returns `gaps`/`coverage`. The checks include terminal lineages, final state equality, four-camera state parity, pause determinism, framing, placement and encoded frame counts. A pass does not assert zero binding gaps, nor that every authored effect is attractive or spatially correct.

Preserve this distinction in summaries. If a single overall label is needed, add a small separate binding-completeness indicator to the existing report; do not conflate it with check success or claim user approval from captured pixels. The requested large visual-regression framework remains deferred.

## Authority and data path

| Boundary | Current implementation and what it owns | Audit conclusion |
| --- | --- | --- |
| Native production | `game/session.py:158` collects real terminal operation roots; scenario producers issue actual commands, damage, condition and world operations | Live engine access belongs here. Choosing setup data/dice does not fabricate downstream outcomes. |
| Initialization | `game/replay.py:45` captures the actual event interval from generation start to the recorded baseline; `CapturedHistory.before` is a derived reference, not the wire authority | The starting world, actors and sensory state come from events. No extra live-world snapshot is required by public replay. |
| Complete lineage capture | `game/presentation.py:770` indexes native history; `:793` traverses the terminal root and required descendants, preserving version and lineage identities | A completed leaf or batch flush is not treated as an entire completed action. Missing required terminal children fail capture. |
| Detachment | `game/presentation.py:579` removes executable modifier graphs, retains committed values, and projects combat logs; `game/event_record.py:102` decodes known concrete families in passive mode | Native queries here are capture-time, not render-time. Detached after-values/dice results are legitimate facts. |
| Observer projection | `game/player_projection.py:554` folds recorded private values and recorded observer grants, then emits facts, causal headers, observations and world updates | Projection can read the recorded objective packet; a player drawer cannot. Blank causal nodes retain parent/child identity without filling in forbidden details. |
| Public state | `game/player_reduction.py:160` applies received values; `:198` reduces initialization; `:207` folds a complete public lineage | Latest state and timed historical states use the same public reducer. No rerolls, rule handlers or pathfinding. |
| Linked reaction roots | `game/presentation_group.py:20` joins explicit triggered reaction lineages with their target root while retaining original roots | Causal presentation grouping, not an invented engine event or independent per-event queue. |
| Binding | `game/choreography.py:165` binds one head; `:991` joins descendant recovery; `:1042` compiles its state anchors; `:1553` binds motion | Presentation time can differ from native completion order while the facts and final state remain native. |
| Sampling/drawing | `game/playback_frame.py:65`, `game/body_presentation.py:33`, `game/choreography.py:1141`, `:1797`, `game/app.py:345` | Retained values, authored media and the explicit clock only. Camera rotation does not execute native logic. |
| Review production/replay | `devtools/animation_review/capture.py:16` runs a native experiment once; `cli.py:177` reloads persisted public bytes before recording | The authoritative clip input is saved public JSON. Current E1 genuinely blocks that boundary for destruction. |

The exact native wire-family registry in `game/event_record.py:42` is appropriate for passive decoding; it is not a per-spell behavior registry. Unknown concrete event payloads are detached to causal headers with an explicit unsupported disposition at `game/presentation.py:544` and `:837`. Their unknown state is not reconstructed by guessing. The finite public fact union, state-only set and `FACT_PRESENTATION` describe the supported surface without asset hashing.

## Privacy and observation handling

The important distinctions are maintained in the inspected active path:

- `game/player_projection.py:77` publishes an observed actor's appearance/loadout and retained public values; `controlled_items` is populated only for the observer's own actor. Foreign sensory updates are rejected before `SensoryFact` creation (`:153`); the observer's existing native deltas are copied (`:92`).
- Movement projection only discloses authorized edges/endpoints. A partially seen walk does not gain a complete private path. Portal departure and arrival are independently disclosed, including an arrival-only observer without the hidden portal identity (`:272`).
- An unseen damage source can remain absent while the known recipient receives genuine applied damage. That preserves the native subjectivity rules rather than replacing them with a shorter invented narrative.
- `_capture_actor_admissions` (`game/presentation.py:686`) reconstructs observations from the recorded history. Reacquisition gives the newly observed after-state without replaying hidden damage/equipment as visible actions. `_project_nodes` (`game/player_projection.py:572`) retains per-delivery entry sight where the action itself removes its visibility.
- World updates disclose currently observed tile/object changes and retain prior memory (`game/player_projection.py:526`). Boundary residue faces are filtered through their observed faces (`:493`). A later view of an existing pool/field receives its state without replaying its creation.
- Actor admission and individual condition projection take different code paths. I explicitly probed the existing hidden-damage/reacquisition and both discovery scenarios for internal-marker leakage; they did not emit internal conditions. A superficial reading of the actor-value copy is not sufficient evidence of a privacy defect, and no new filtering obligation is claimed here.

`devtools/animation_review/capture.py:36` also retains `native.json` locally; `cli.py:168` copies it alongside local case diagnostics. `serve.py:71` serves that review workspace on loopback. That directory is a developer diagnostic artifact, not the public player transport package. The actual renderer input excludes native objective diagnostics, foreign sensory data and private inventories. A future server/client transport should send the existing public packet, not the whole local review directory; this is a boundary description, not a request to add security machinery to the local review tool.

## Inventory of presentation policies and special cases

These are the active exceptions and compatibility paths relevant to this audit. A derived visual policy is not automatically an invented mechanic.

| Area / exact source | Active behavior | Assessment |
| --- | --- | --- |
| Action actor admission — `game/choreography.py:195` | Newly after-visible referenced actors may be staged at action entry, using the actual received observation; arrival-only relocation waits for release | Explicit inherited presentation policy. Do not replace the observation with current live actor state. Destruction-owned admissions are excluded. |
| Damage — `game/player_reduction.py:111`, `game/choreography.py:777` | Applied HP is an after-value; child damage is timed to parent contact | Correct ownership. TakeDamage intent, missing damage and death do not manufacture a damage amount. |
| Blood/materials — `game/choreography.py:777`, `game/residue_media.py:70` | Release uses native `body_release` regions/pattern; world contributions are received facts; landing templates choose repeatable particle positions | Decorative trajectories/variation interpolate a native release. They do not apply bleed damage or enlarge mechanical floor membership. Unknown attack direction has a deterministic visual fallback, not a native hit-direction claim. |
| Death and waking — `game/choreography.py:835`, `game/condition_animation.py:183` | Native life state and condition membership own downed/rest poses; authored transitions may play the death strip forward/reverse; actual dead actors override sleep pose | Legitimate reuse of body media. No resurrection/heal/save result inferred from the strip. |
| Held corpse / stopped motion — `game/visual_position.py:11`, `game/body_presentation.py:63` | Preserve the rendered subcell position while the same legal tile remains authoritative | Required separation of legal origin and rendered body. A later legal relocation supersedes the overlay. |
| Corpse memory — `game/scene.py:28` | Witnessed dead bodies can remain at their last visual position; stale living positions do not render | Existing retained-memory display policy. No live corpse query. Do not silently redefine native visibility during cleanup. |
| Sleep hit pose — `game/condition_animation.py:183–212` | Rest pose can replace idle/damage body; finite fall/wake gesture follows actual aggregate membership change | Explicit condition presentation, no condition application/removal invented by the renderer. |
| Movement speed — `game/choreography.py:1687` | Received resolved speed scales travel/body cadence, preserving continuous walk phase across steps | Uses evaluated native values. No renderer Haste/Dash rule table. |
| Opportunity reactions — `game/choreography.py:1702` | Walk lead-in holds the body while actual child attacks resolve; committed step determines continuation | Generic reaction composition, not a separate fake attack sequence. The clamped visual lead-in is code policy; changing it changes approved timing. |
| Jump — `game/choreography.py:1383` | Direct-arc movement resolves reactions before one flight; authored duration determines one full jump cycle; actual ground/air facts own contact state | Intentional presentation reordering requested by the user. Native trap/surface activation remains outside rendering. No hovering/flight system introduced here. |
| Partially disclosed motion — `game/choreography.py:1553` | Hidden steps contribute no invented distance; one authored dwell separates isolated observations | Visual timing fallback for absent public geometry, not reconstruction of the private path. |
| Missing movement clip — `game/body_presentation.py:43` | Unsupported rig movement falls back to Idle while still moving its received contact | Active generic capability fallback. Keep visible as a limitation; it is not a mechanical movement failure. No instance proving a newly missing rig clip was established in this audit. |
| Forced movement / trap dodge — `game/body_hop.py`, `game/choreography.py:1275` | A successful save hop additionally requires the recorded ForcedMovement result; start/landing are native endpoints | Correct: the hop is not proof that a mechanical escape happened. Reuse requires authored effect binding plus factual displacement. |
| Portals — `game/choreography.py:368`, `game/portal_animation.py:30` | Recorded crossing owns the transfer; authored fall/transit/emerge fills the presentation time; legacy missing content identity selects a default portal recipe | Current endpoint behavior is event-driven. Default recipe is legacy art compatibility, not a reconstructed portal rule; coverage currently misses the actual cue (E2). |
| Interrupted actions — `game/interruption.py:21`, `game/choreography.py:287` | Typed cancellation phase/outcome/economy selects an authored prefix; actual surviving children remain; contact/hit media are suppressed when canceled | No rollback or “absence of damage means miss” inference. Protection contact geometry only chooses the visual cutoff; native suppression decides who was protected. |
| Equipment — `game/player_reduction.py:107`, `game/choreography.py:1183` | Attack's recorded weapon slot selects the active set; equipment after-values settle at authored commit/completion | Derived stance mirrors native attack semantics; inventory remains observer-owned. There is no live weapon lookup in playback. |
| Condition visuals — `game/condition_animation.py:215`, `game/condition_media_lifetime.py:118` | Actual owner UUID membership selects layers; witnessed application/removal gets finite media; cold/reacquired membership enters quiet sustain | No gameplay duration tick, expired-save inference, or invented condition. Activation uses actual received turn starts, not video wall time. |
| Destruction clearance — `game/choreography.py:181`, `:1042` | Only nonzero authored bank markers own delayed sensory/spatial/technical state and actor admissions | Correct bounded policy in source: sibling damage, conditions and spills keep their own anchors. Cold JSON tests currently stop before sampling because of E1, so this audit does not claim fresh visual verification of those frames. |
| Remnant identity — `game/player_projection.py:656` | Current explicit ItemDestruction result yields one same-object remnant; old removal/replacement recordings have a separate compatibility path | Keep current fact ownership. Do not turn the legacy fallback into a second destruction implementation. |
| Liquid release — `game/deposit_media.py:47` | Actual destruction and authored release frame date the already recorded deposit UUID/geometry; cold acquisition is settled | Liquid extent and effects come from native surface state. The timing is deliberately independent of obstruction-clearance markers. |
| Maintained spatial fields — `game/spatial_media_lifetime.py:67` | Actual CREATED/REMOVED facts distinguish intro/dissipation from simple acquisition/loss of sight | Correct separation of state changes and observer visibility. Removal media are not triggered solely by absence from sight. |
| Spatial contact media — `game/spatial_contact_media.py:71` | Visible recorded grounded entry or positive applied damage in a known field triggers a finite decorative contact | Does not cause damage, trigger a trap, or re-evaluate airborne occupancy. |
| Moving fields — `game/world_animation.py:98` | Same observed owner with old/new geometry interpolates its field | Legitimate visual motion between disclosed values; no map query or rule execution. |
| Body trails — `game/body_history.py:57` | Short retained input window samples prior authored body poses; sight/relocation cuts prevent a trail crossing an undisclosed gap | Presentation memory, not another event history or native motion simulation. |
| Unsupported recipes — `game/condition_animation.py:245`, `game/presentation_coverage.py:42` | Missing condition/media authoring retains state, reports limitations, does not invent a visual | Correct fallback policy. Explicitly accepted potion-source strip omissions remain accepted; dormant empty fields are not present gameplay failures. |

## Cost, purity and what not to “clean up” blindly

There are no SHA/hash checks in the inspected `game` Python modules. Stable coordinate arithmetic used to vary residue texture is not an integrity audit or native random outcome. Offline git provenance in `devtools/animation_review/cli.py:33` is review metadata, not per-frame validation.

`game/player_reduction.py:24` copies mutable state indexes to preserve historical ownership and shares immutable values. `sample_choreography` then samples retained states; it does not serialize/deserialise a whole event stream each frame. These copies have a purpose. Their cost should be measured if a concrete size/frame-time problem emerges, not removed on the premise that all copying is waste.

There are identifiable scaling boundaries: `capture_lineages` rebuilds an index over recorded history, live `receive` currently calls single-root capture for each operation root, `_before_event` folds prior facts for binding, and the binder stores timed state snapshots. They are intake/bind costs, not renderer mechanics. This audit did not measure a performance regression in them and does not prescribe caches, event hashes or a new incremental-history subsystem. Batching the already available capture operation is a possible measured follow-up, not part of the immediate correctness repair.

The drawer has typed generic branches because movement, damage, conditions, equipment, world objects and portals have different visual semantics. “Data driven” does not mean zero executable branches. The problematic growth is duplicated ownership or spell-identity-specific execution, not a finite interpreter for distinct primitives. Current event audit did not identify a new per-spell mechanics implementation in the frame path.

## Fresh validation and limits

A fresh selected causality/privacy run was started independently of previous reported counts, under dummy SDL, the WSL uv environment, Python 3.13.12 and pygame-ce 2.5.8. It selected 23 relevant files. After reaching the repeated fresh destruction decode failures, I interrupted **my own** duplicate run because the root reviewer was already running all `tests/game`. Final partial result: **126 passed, 37 failed in 339.47 seconds; exit 130 from the intentional interrupt**. All 37 reported failures were object-destruction public JSON validation failures. This is not the complete suite result.

The completed part included passive event decoding, player projection, recorded history, capture headers, actor discovery, paired visibility/concealment/environment, cancellation replay, counterspell grouping, condition lifecycle and healing replay. The destruction block then failed before its renderer assertions. Later selected files—including liquid replay, several motion/death/wake cases and portal replay—were **not completed by that run**, so this report does not reuse old pass counts for them.

Additional focused read-only probes performed:

1. Exact JSON validator isolation for E1, including the same union with/without its outer hook.
2. Real `portal_history(program="bare-walk")` → encoded/decoded public packet → motion binding → coverage. A real portal cue exists; coverage says `received`.
3. Existing native visibility history with hidden damage/equipment and reacquisition, plus both discovery modes, checking public foreign inventory/internal condition exposure. No leak was reproduced; the ordinary projection assertions passed in the selected run too.
4. Static source tracing for live backend accesses from sampling/drawing and private/public schemas. Only composition/capture owns the identified live accesses.

No new gallery was generated for this audit, and no pixel/art approval is claimed. The root review's complete test result belongs alongside this partial run when consolidating the final report. The body/field/geometry policies above were traced in source; a source review is not a substitute for a saved visual case when changing their timing.

### Completed core suite and exact failure classification

The parent subsequently completed the non-gallery core run, recorded in `/tmp/render-audit-core-suite-20260923.txt`: **2,052 passed, 206 failed, 7 setup errors, 15 deselected in 1,914.93 seconds**. I independently split and classified all 213 failed/error traceback blocks; the earlier interrupted selection is not added to these counts.

| Actual stopping point | Failed | Setup errors | Interpretation |
| --- | ---: | ---: | --- |
| Fresh public `ObjectDestroyedFact` strict placement JSON | 112 | 5 | E1; downstream rendering assertions do not execute |
| Retained native archives missing later event fields | 3 | 2 | E3; separate archive admission failure |
| Area-scene geometry assertions | 89 | 0 | Owned by the separate geometry audit |
| Wall-memory native setup expects only one scorched face | 1 | 0 | Obsolete scenario premise after connected Fireball spread; detailed below |
| Fireball retained full-canvas size expectation | 1 | 0 | Separate media contract expectation; actual 650×324 layers versus old 1536×1536 assertion |
| **Total** | **206** | **7** | **Every failed/error outcome accounted for** |

The 117 E1 outcomes are distributed across prop destruction (39), deposits (22), liquid barrel replay (14), device destruction (12), liquid surface media (8), sustained tethers (6), environment presentation (4), Web condition layers (4), device replay (3), spatial deployment (2), Web replay (2), and multicell replay (1).

In particular, `test_native_trap_hardware_owns_one_body_during_actual_plate_activation` stops decoding the later destruction in the same saved history at `test_environment_presentation.py:338`. `test_object_action_projection_does_not_grant_an_unknown_target_uuid` also stops decoding destruction at `test_sustained_tether.py:247`. Neither trace demonstrates an independent trap-body error or private target leak. Repair admission and then run their still-required behavioral assertions; do not mark those contracts verified from a failed decode.

The wall-memory case is genuinely distinct. At `tests/game/test_area_spell_projection.py:201`, native setup expects a wall residue with only `WEST`; native Fireball now produces `EAST` and `WEST`. The failure happens before replay. A read-only map/AoE probe verified the in-radius route `(5,6) → (6,6) → (6,7) → (7,7) → (7,6)` has open propagation edges throughout. Connected spread therefore reaches both sides of the wall at `(7,6)`; the old line-of-effect policy reaches only the western adjacent cell. This matches the approved connected propagation and `deposit_area_residue`'s reached-face ownership. The smallest correction is a native scenario that again establishes one-sided contact while preserving the test's independent-face memory and hidden-removal assertions. Merely accepting both faces throughout would erase the intended privacy coverage; reverting Fireball propagation would change authorized mechanics.

## Behavior-preserving cleanup order

1. Repair E1 at public JSON admission and E3 at the separate retained-native archive admission. Prove fresh destruction and liquid bytes work, retain passive native registry behavior, and preserve explicit/current spell propagation values. Keep actual old fixtures and their evidentiary limits. No presentation tuning in this change. Re-establish the wall-memory test's one-sided native setup without weakening its privacy assertions or changing authorized propagation.
2. Correct E2 in the existing observed coverage traversal. Keep pass checks, binding gaps, missing authoring and user approval separate.
3. Pin the actual supported legacy area-policy inference to verified recorded examples/documentation. Preserve already approved output during migration; do not guess historical rules from modern spell identity.
4. Consolidate only the duplicated live/review head-admission bookkeeping, using the current passive records and functions. Compare the same saved interruption, condition lifetime, movement, destruction and liquid histories before/after. Keep source scenario execution outside the replay path.
5. If later cleanup moves staging or joins, do it one primitive at a time against existing native scenarios: windowed sight/reacquisition; preflight jump OA; stopped/dead subcell pose; sleep fall/wake/lethal hit; equipment commit; witnessed versus cold destruction; liquid release versus obstruction clearance; field creation/removal versus sight loss. Do not invent a universal cancellation rollback, generic spell physics engine, or new visibility policy to simplify the test surface.

The anti-slop conclusion is therefore bounded: preserve the working authority/causality structure, repair the demonstrated byte-boundary regression, improve evidence accounting, and reduce orchestration duplication without rewriting the timeline model.
