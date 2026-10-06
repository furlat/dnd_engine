# Player UI implementation — independent anti-slop review

Date: 2026-10-05. Reviewer: independent implementation subagent.

**Status: native, bounded compositor/media, shell, canonical-log and cold-creator source checkpoints approved; complete UI integration pending.** The user approved implementation of
the complete [player UI plan](../PLAYER_UI_PLAN_2026-10-05.md). Its earlier design
approval is not implementation approval. This receipt begins with inspected
baseline hazards and concrete exit evidence; each code checkpoint and the final
integration must receive a separate verdict below. No production edits or test
runs were made for this initial source pass.

The outcome is a playable native encounter with a selected fighter or sorcerer,
including the approved shared UI, creation/inventory and world interaction
flows. A single spell demonstration, scripted command callback, attractive
static HUD or passing parser tests alone cannot establish that outcome. Gameplay
persistence remains deferred; no character-only save or new narrative subsystem
belongs to this implementation.

## Inspected baseline hazards

These describe the source before the implementation checkpoints. They are
specific contracts to repair or preserve, not a claim that proposed code has
failed them.

| Owner and baseline source | Observed hazard | Required externally observable result |
|---|---|---|
| `game/encounter_play.py:_run` input loop, baseline lines 211–238 | Escape exits and Space toggles pause before `handle_menu_event`. `ready` is computed outside the event loop. | Modal/target cancellation consumes Escape/right-click first. Live Space ends exactly one eligible neutral human turn; it does nothing during targeting/modal/AI/history. One input batch cannot submit two actions. Panel/copy modifiers cannot also affect the world. |
| `tests/game/test_encounter_play.py:test_full_round_moves_conditions_and_enemy_actions_while_history_paused` | Existing application test explicitly asserts live Space pause. Helper-only control tests do not expose interception. | Replace this superseded live-input expectation with real Pygame-event coverage for the approved contract. Preserve independent engine intake/history behavior and review-only pause coverage at their actual boundaries. |
| `game/controls.py:_choose_target`, `handle_menu_event` | Reaching the target cap or exhausting a secondary pool immediately commits. Backspace clears all entity selections; Enter ordinarily selects the cursor target. | Ordered A/B/A and native repeats survive; Backspace undoes one recipient/point; complete and partial allocations show effective native preview and await explicit confirmation. One selected target must not silently become all projectiles. |
| `game/controls.py:selection_target_pool`, `_target_options` | Chain-style secondary targets belong to the selected primary; they are not necessarily in the flat initial target list. | Primary-dependent next choices and final ordered selection use the original native row and its admitted pool. UI does not reject legal branches or accept arbitrary creatures by position/name. |
| `game/session.py:discover_player_actions`, `execute_player_action`, `player_position_options` | `_current_player` correctly owns turn admission, but discovery has no retained generation/row association; execution only checks target value membership in the supplied row. | An exact row/target from a previous discovery, reset, actor or operation is rejected without native expenditure. Current detached UI payloads contain no private execution template. Final execution still uses native admission. |
| `game/environment_draw.py:pick_environment_target` versus `game/app.py:draw_frame` | Existing object picking independently sorts pre-cut authored masks; drawing subsequently clips boundaries, splits fixtures/terrain and splits world depth. Actor/tile fallback is a different path. | Hover, targeting and Alt consume shared regions after the actual renderer cuts. Fully occluded bodies/items cannot be clicked. Frame/insert pixels, a visible actor through a hole, and empty traversal aperture resolve as the approved window rule specifies. |
| `game/encounter_play.py:_log_lines`, baseline lines 81–85 | `dict.fromkeys` identifies rows by text, removes distinct equal hits, strips only simple tags and drops verbose/detailed text. | Canonical key is generation + observer + projected node UUID; equal text with distinct identities remains. Same-key replay is idempotent, conflicting data is rejected. Existing full detail remains available. |
| `game/encounter_play.py:_run`, baseline lines 162, 379–398 | History is a 20-string deque; three lines are shown and whole roots are appended at group completion. | Replace this display/storage path with the canonical bounded panel, exact existing release boundaries, grouping, scrolling and details. Do not leave an additional text stream or earlier old panel consuming the same logs. |
| `dnd/core/events.py:Event.phase_to`, `_collect_child_combat_logs`; `game/player_projection.py:_project_nodes`, `_action_log` | Native parent logs embed descendants already represented by projected nodes. Foreign Font of Magic text has additional projection redaction. The encounter callback occurs before the posted completion UUID is allocated. | PlayerNode logs are canonical; embedded `sub_entries`/`per_target_logs` are details, never second row streams. Never replace projected text with objective callback/native text or use callback UUID as terminal node identity. |
| `game/presentation_timing.py:presentation_milestones`, `presentation_dependencies`; `game/presentation_group.py:presentation_groups` | Existing clocks and reaction grouping are already authoritative. Native completion can precede visible impacts. | Damage/save/summary rows use exact causal result identities, state commits and group offsets; parent totals wait for relevant descendants. Reaction rows appear at their own effect. Missing precise timing uses existing group completion, not zero or an invented scheduler. |
| `dnd/core/events.py:EventQueue.push_combat_log`; `game/session.py:_operation`; `game/replay.py:RecordedSequence`, `capture_history`, `decode_sequence` | Standalone immunity is an unregistered carrier with `combat_log_origin=standalone`; EventQueue-root capture misses it. `decode_sequence` returns only baseline and lineages. | Capture only this marked path via the existing encounter listener, immediately subjectively project/detach, retain encounter-log index identity and operation-end timing, and preserve it in existing sequence/Operation fields. Round-trip and replay consumption must retain it; ordinary callbacks must not duplicate node rows. |
| `game/player_facts.py:PlayerActor`, `PlayerState`; `game/player_projection.py:_public_actor` | Current projected state is not a full controlled sheet/resource/initiative view; undisclosed inventory is `None`. | Add the bounded authorized passive snapshots. Do not query live actors from widgets, treat undisclosed as empty, expose hidden initiative counts/gaps, or overwrite delayed/historical panels with current native resources. |

## Evidence required at each slice

All checks follow [HOW_TO_TEST.MD](../../HOW_TO_TEST.MD). Use native observable
outcomes and stable application boundaries; architecture assertions prove only
their dependency policy. Record exact commands, changed source scope, failures,
repairs and complete affected-file reruns. Do not change an old expectation to
green unless the approved contract actually supersedes it.

| Slice | Required source and behavior evidence before dependent work |
|---|---|
| 1. Native exposure | `selected_only` versus `fill_primary` derives from native owners; actual cap and repeat rules remain native. Repeated valid/invalid full-prefix preview leaves events, RNG, economy, actor state and retained templates unchanged. Show exhausted known slot ranks, all existing named modes/facets and exact item/provider identity without invented choices. Prove named Beacon of Hope/Divine Word cap repairs through native outcomes. Discover/execute the real window connector. Test stale row rejection, active-human command gates, auto-only reaction toggles, own/unknown passive snapshots and standalone immunity capture/round-trip. |
| 2. Media and interaction geometry | Exact ContentRef descriptors keep their authority; direct feature/item IDs use only validated presentation records with the same asset index. No retired class factories, fake hashes or runtime name fallback. Demonstrate post-cut region identity through all four cameras, wall/window openings, overlapping loot, prone/flying/large actors, cliffs and open/destroyed/hidden objects. Prove bounded cache/region memory; no full-screen buffer per entity. |
| 3. Shell and world clicks | Real Pygame input proves focus precedence, cancel/undo/confirm and Space behavior, including multiple input events in one frame. Door/lever/chest/window operations stay off the hotbar; Ctrl attacks use the actual native attack option. Remote affordance inspection does not admit use before contact. Approach chooses existing native Move targets, rediscovering final use after movement; interrupted/dead actor, removed target, changed turn and cancellation prevent follow-up. |
| 4. Combat log | Distinct identical hits, A/B/A, mixed saves/damage, immunity, reaction interruption, concentration and state-only absence retain exact native text and identities. Confirm parent/child grouping without duplicates and no future totals/hidden names. Replay/skip reaches the same final rows. Unknown/malformed/nested markup remains literal. Exercise filters, actor identity chips, copy, resize/expand anchors and 10,000-row eviction with at most 512 layout/surface entries; inspect actual expanded rolls at supported widths/scales. |
| 5. Action bar and initiative | Real UI confirms full/partial repeated target allocations and native secondary pools, source-item/class spell variants, rank/mode/form facets, walls and entity destinations. One summon cast creates exactly one selected creature. Retained hotbar preferences never restore stale authority. Initiative keeps native disclosed relative order and summon changes; selected portrait does not transfer turn ownership. HP/resources appear only at admitted presentation dates. |
| 6. Creation, sheet and inventory | Actual UI creates supported fighter/sorcerer and representative other supported choices using native point-buy/choice validation, chosen level and loadout once. Cancel leaves no live entity/event mutation. Deploy selected party; equip/drop/pickup/use and partial chest loot show actual ownership/effects/capacity. Ground-fallback unequip is disclosed before confirmation. A noncurrent party member can be inspected but cannot mutate combat state. No unsupported Save/Continue button. |
| 7. Integrated acceptance | Play ordinary encounters through visible controls as selected fighter and sorcerer, including movement, native enemy decisions, spell/attack selection, resources/log synchronization and settlement. Remove superseded handlers/log rendering. Run affected game/progression/architecture checks and inspect actual 1280×720, 1920×1080 and high-DPI imagery plus the plan's named world/target/log/character/inventory lanes. Keep recorded passive inputs so the same native run replays without rerunning rules. |

### Final acceptance is not inferred from isolated proofs

The integrated record needs the exact player-visible scenario and which input
route it exercises. A `player_input` callback is useful native integration
coverage but does not prove clicking, keyboard focus, tooltips or modal
precedence. Mask metadata tests do not prove post-occlusion click pixels. A
serialized packet alone does not prove the running UI consumes all its fields.
A render capture alone does not prove the corresponding control executes the
native command. These evidence types complement one another.

No acceptance case requires new narration for missing producers. In every log
family, `combat_log is None` stays no row, including silent cancellations and
state-only destruction/transfer/summon outcomes. Existing native details and
projection disclosure are the only wording source.

## Checkpoint verdicts

| Checkpoint | Verdict | Evidence |
|---|---|---|
| Baseline inspection | No implementation verdict | Encounter/input/log/session/projection/timing/picking source inspected; no production change reviewed yet. |
| Slice 1 | Native source approved; integration pending | The settled-source recheck below supersedes the first review's findings; playback consumption and visible control acceptance remain later gates. |
| Slice 2 | Bounded compositor/media source approved; integration acceptance pending | Final recheck below closes the reproduced floor cut and earlier source findings. Wider geometry lanes, shell consumption and visible UI acceptance remain required. |
| Slice 3 | Bounded shell source approved; broader world/input acceptance pending | Settled recheck below closes the reproduced focus/selection findings. Actual SDL focus/Space cases and native variant checks pass; downstream panel flows, broader world gestures and final gameplay remain separate gates. |
| Slice 4 | Bounded canonical-log source approved; full interaction/replay/visual acceptance pending | Settled recheck closes exact operation/life/turn timing, eligibility-count and reading-anchor defects. Broad hidden/state-only/replay/visual lanes remain required. |
| Slice 5 | Pending | Await action/initiative integration evidence. |
| Slice 6 | Bounded cold-creator source approved; full deploy/inventory integration pending | Settled creator recheck closes the reproduced stale roster/draft hit defects with actual SDL regressions. Full creation/deploy/inventory and visual lanes remain required. |
| Final integration | Pending | Requires current source, reconciled tests, record-once replay and inspected gameplay captures. |

## Native contract checkpoint — first implementation review

Scope: the notified action/discovery/spell/connector edits, Session adapters,
passive HUD/log packet fields and `test_player_selection_contract.py`. No widgets
or later interaction geometry were reviewed. Production was being edited during
the review; this is not a frozen-source final approval. The reviewer made no
production edits. Remote approach, attachment to the HUD playback loop, and
packet-append acceptance were explicitly declared unfinished by the implementer.

### Changes required in implemented code

1. **P1 — Visible immunity results still disappear.**
   `Entity._declare_entity_condition` creates the original immunity entry with
   no perceiver/identified/located evidence. `EventQueue.push_combat_log` sends
   that unregistered carrier directly; it does not run normal completion log
   enrichment. `Session._bind_log_capture` correctly calls the original pure
   projector, which consequently drops every such entry whose participant is
   not its controlled observer. A native probe made the visible second party
   member immune to Poisoned and applied Poisoned: recipient was in the first
   observer's senses, the native encounter received one immunity entry, and
   capture received zero appends. Both native evidence collections were empty.
   Copy the existing declaration's event-time observation evidence into this
   original producer entry before publishing it. Do not repair this by granting
   all party/enemy identities, reading live state during replay, or adding a
   second immunity formatter. Acceptance needs own, visibly observed other and
   hidden-other cases, plus recorded append round-trip.

2. **P2 — HUD maxima describe base values, not the current native capacity.**
   `snapshot_player_hud` uses `get_base_value` for actions/bonus/reactions and
   `current_speed` for movement maximum. A native Dash probe produced
   `PlayerResource(key='movement', current=60, maximum=30)`. Action Surge adds a
   native action modifier and likewise can produce current above this base
   maximum. Derive evaluated capacity/spent values from the native economy,
   preserving Dash grants, Action Surge, Slow and restricted Haste channels;
   do not clamp the current value in the widget or call a base value a maximum.
   Test after grant, expenditure and turn reset.

### Corrections observed during this review

- The initial new spell discovery called `has_spell_slot_capacity`, whose
  implementation only inspected the base modifier. Direct-character slot
  capacity is installed as aggregate contributions: the premade sorcerer had
  capacity `{1: 4, 2: 3, 3: 2}`, positive remaining slots, base modifiers zero and
  `has_spell_slot_capacity=False`; all leveled spell rows vanished. The updated
  helper reads the existing installed aggregate first and retains the original
  fallback for other supported configurations. The focused checks now pass and
  the depleted-rank test actually spends its slots.
- Session previews now resolve target indices back to the retained original row
  and detach the result through its passive model. A runtime probe confirmed
  returned `next_targets` are no longer original authoritative target objects.
  Execution also resolves its primary back to the original row. Thus mutation
  of detached target fields does not acquire native authority.
- Handler toggling changes no EventQueue cursor; cursor checks alone therefore
  left old choices usable. The updated command invalidates its discovery cursor
  and preview cache. A runtime probe confirmed the old row now raises the stale
  selection error after toggling.
- `execute_available_action` now supplies the retained item template to
  `execute_use_action`; the latter skips fresh `get_use_actions` selection and
  checks source item/entity identity. This repairs the previously observed
  exact-template bypass. A real adaptive/configured item outcome regression is
  still required; source inspection alone does not prove all item modes.
- Initialization and lineage reduction now reject wrong-observer/generation or
  future-revision HUD snapshots. Correct operation-end attachment and recorded
  reproduction remain unfinished, so this check alone is not timing acceptance.

### Remaining planned work and missing acceptance evidence

These are not relabelled as working behavior, nor counted as regressions merely
because the checkpoint was explicitly partial:

- Complete the declared remote-world descriptor/approach adapter and native
  window execution checks. Newly arriving remote-approach edits during this
  review are outside this checkpoint's verdict.
- Carry HUD snapshots into the existing recording path and consume them at
  conservative operation boundaries. Current `RecordedSequence` has log
  appends but no HUD values; `project_sequence(native)` cannot yet recreate the
  new live HUD snapshots. Show old-packet compatibility, paused/history behavior,
  own/unknown disclosure and round-trip without live engine access. Party sheet
  authorization must not merge map observers.
- Complete optional log-append packet capture/round-trip/consumption checks and
  ordinary-callback nonduplication. No transcript, synthetic event or second
  wording source is introduced by the reviewed append field itself.
- Finish typed facet coverage for existing choices, notably Fire Shield's
  warm/chill and Spirit Guardians' radiant/necrotic variants. They currently
  produce differently named rows but no `get_variant_facets`; the new
  `damage_type` facet key has no producer in these owners. Do not parse their
  display labels in future widgets.
- Prove invalid as well as valid complete-prefix previews for Acid Splash,
  dependent Chain selections, wall paths and creature/destination actions.
  The new purity test covers valid Magic Missile prefixes and compares slot
  capacities; capacity does not establish unchanged remaining slots/actions or
  named resources. Check actual current values, event/RNG state and unchanged
  actor/template values. Reject an invalid extra target index cleanly: Session's
  retained-pool lookup currently uses an unguarded `next(...)`.
- Exercise Beacon of Hope and Divine Word through discovery and native execution
  with multi-recipient outcomes and one native cost. The current Beacon test
  asserts the same count hook that was just implemented; it is not the approved
  behavioral proof of the corrected cap.
- Cover exact item source/configuration/variant execution, one summon creature,
  stale resets/operations, controlled snapshots and absence of executable
  references beyond the existing detached-row example. Use the native owners;
  no broad validator or targeting rewrite is requested by these cases.

### Independent verification performed

Environment: WSL source under `/mnt/c/users/tommaso/documents/dev/dnd_engine`,
prepared Linux environment `/home/tommaso/.cache/dnd-engine/venv`. Commands use
`UV_PROJECT_ENVIRONMENT=/home/tommaso/.cache/dnd-engine/venv uv run --no-sync`.

| Command after that prefix | Result | Scope |
|---|---|---|
| `python -m pytest -q tests/game/test_player_selection_contract.py --tb=short` | Initially 2 failed, 2 passed in 5.30s; following repairs 4 passed in 3.54s | Initial failures preserved above; source/test repair included installed slot capacity and correct spell registration. |
| `python -m pytest -q tests/game/test_player_selection_contract.py tests/game/test_session.py tests/engine/test_action_discovery.py tests/engine/test_chain_lightning_selection.py --tb=short` | 28 passed in 15.60s | Current affected discovery, gated Session and native Chain compatibility; does not establish unfinished HUD/log/UI cases. |
| Small native diagnostic processes using public Session/native condition operations | Reproduced Dash 60/30 and visible immunity 1 native/0 captured; confirmed target detachment and stale rejection after toggle | Concrete findings and bounded repair checks, not new committed tests or visual evidence. |

This first checkpoint was not approved. Its findings and evidence are retained
as review history; the settled-source recheck below gives the current verdict.
No later UI or final gameplay acceptance is implied.

## Native contract checkpoint — settled-source recheck

Verdict recorded 2026-10-06 (Europe/Rome): **approved for the bounded native
source checkpoint**. No remaining production-code blocker was found in this
scope. This authorizes dependent implementation; it is not approval of the
complete UI slice or playable encounter.

Scope: the same native discovery/action/spell owners, `dnd/blocks/action_economy.py`,
`dnd/core/events.py`, `game/session.py`, passive player facts/projection/reduction,
existing replay models, and the two new native contract test files. No widget,
renderer-mask, live input, or history-playback implementation is covered. The
reviewer changed only this receipt.

### Resolved source findings

- **Capacity comes from native evaluation.**
  `ActionEconomy.channel_capacity` delegates to the existing
  `normalized_score_excluding_static_modifiers`, excluding the existing native
  cost modifiers while retaining grants and constraints. Movement uses native
  current speed and Dash count. The Dash/spend test observes 60/60, then reduced
  remaining movement with maximum 60 and an unchanged earlier snapshot. There
  is no widget clamp or duplicated capacity evaluator.
- **Standalone immunity uses original event evidence and wording.**
  `Entity._declare_entity_condition` copies declaration-time identified/located
  grants into the original immunity entry and calls
  `EventQueue.perceivers_for_event`, which delegates to the already installed
  observation policy. `Session._bind_log_capture` remains restricted to the
  native standalone marker and calls the original subjective projector before
  detaching. A visible other-party immunity now produces one original projected
  append, retained by encounter index and operation-end cursor. The packet
  round-trip preserves that entry. Normal event callbacks are excluded by the
  marker gate; no second formatter or narrative stream was introduced.
- **Action authority survives neither rediscovery nor restart.**
  Recheck reproduced an old Session's row being accepted against a new Session
  because both ordinal epochs began at one. `AvailableActionInfo` now carries
  the existing EventQueue runtime UUID, actor UUID, discovery epoch and row
  index; `Session._retained_row` checks the current runtime/actor/epoch/cursor
  before resolving the original authoritative row. The restart regression
  rejects both preview and execution without events or expenditure. Primary
  and secondary targets resolve by native indices; each returned preview is
  detached anew. Mutation tests exercise target position/path tampering and
  preview-child mutation without changing the executed target.
- **Item use shares the original executor.**
  `execute_available_action` passes its exact retained item template to
  `execute_use_action`, which checks source item/entity and delegates binding
  to `_execute_bound_action`. The former duplicated item binding branches are
  removed. The real configured chill Fire Shield device produces the chill
  native condition and spends one device charge. This is a configured-item
  outcome proof, not a claim that every adaptive item combination was tested.
- **Remote world choices preserve operation identity.**
  Observed device descriptors now retain the existing discovery template name,
  configured ContentRef and typed facets in addition to subject and behavior.
  Thus two configured operations on one device need not be resolved by label
  or first matching behavior after approach. Contact cells come only from the
  current cell and already admitted Move targets, filtered by native contact
  or connector admission. Apertures carry their actual connector UUID. The
  native window test moves to an admitted endpoint, rediscovers and executes
  the real connector with movement cost. The automatic approach/follow-up UI
  is still pending.
- **Named modes and count repairs have native owners.**
  Fire Shield and Spirit Guardians expose their existing choices as facets;
  Stone wall variants now expose panel width alongside form and side. Spell
  ranks remain the existing typed rank field. Beacon of Hope and Divine Word
  tests execute two chosen recipients, observe their native spell events, and
  charge one action/bonus action and one slot. No new general spell catalog or
  widget-specific rules were added.
- **HUD recording uses existing packet boundaries.**
  Optional `hud_snapshots` live on `RecordedSequence` and `PlayerSequence`.
  `project_sequence` installs a matching initial-boundary snapshot and retains
  later operation snapshots for conservative settlement. Reduction rejects
  mismatched or future facts; branch extraction clears an operation-level HUD
  snapshot instead of attaching it to an earlier child. Old packets default
  to no HUD/append values. This proves storage and admission, not the future
  playback loop's correct release date.

### Recheck evidence and limits

The initial recheck's single Acid Splash/Dimension Door test failure came from
replacing installed slot capacity with the same contribution owner. The fixture
was corrected to use native supported replacement by a new owner, preserving
existing expenditure. This was not repaired by changing the rules.

Independent command with the environment prefix above:

`python -m pytest -q tests/game/test_player_selection_contract.py tests/game/test_player_hud_boundary.py tests/game/test_session.py tests/engine/test_action_discovery.py tests/engine/test_chain_lightning_selection.py tests/game/test_consumable_replay.py tests/engine/test_true_seeing_potion.py --tb=short`

Result before the final disclosure-fixture repair: **45 passed, 1 failed in
27.65s**. The failure was the new test's assumption that invisible-target
redaction must use `None`; native anonymous UUID fields may be empty strings,
and nonvisual identification must follow existing senses policy. The revised
test then compared with the last encounter log after ending the turn, which
was a `TURN_END` row rather than the immunity entry: **15 passed, 1 failed in
12.67s** across the two changed contract files. Neither failure justified a
new disclosure rule. The fixture must compare the actual original immunity
entry with the same original subjective projector.

After retaining that original entry before `end_player_turn`, the complete two
changed contract files were rerun independently:

`python -m pytest -q tests/game/test_player_selection_contract.py tests/game/test_player_hud_boundary.py --tb=short`

**16 passed in 11.07s.** No production change was made to force either disclosure
fixture green. The earlier affected-file run's other 45 cases passed, including
the existing Session, discovery, Chain Lightning, consumable-replay and True
Seeing potion paths.

`git diff --check` reports no whitespace errors; Git emits only the repository's
LF/CRLF conversion notices. The implementer separately reported 61 affected
checks passing and scoped Pyright with zero errors; these are attributed
reports, not substituted for the independent results above.

### Remaining integration gates

The reviewed native source introduces passive exposure and Session adapters,
not a parallel rules, event, log or targeting system. The following remain
required work under the approved plan, rather than defects in absent widgets:

- Attach and consume operation-end HUD snapshots and standalone appends in the
  live and recorded playback loops. Prove paused/history/skip equivalence,
  future-fact exclusion, canonical row deduplication, and parent/reaction timing.
- Exercise complete allocations, wall/destination previews, typed modes and
  one-creature summons through the eventual visible controls; source and
  native partial-allocation tests do not prove those input routes.
- Implement the approved approach/follow-up, cancellation and stale-target
  handling using rediscovered native choices and the retained exact world
  operation identity. Verify window frame/actor/aperture pixel priority after
  renderer cuts.
- Complete all later media, shell, log, character/inventory and integrated
  Fighter/Sorcerer encounter gates in the matrix above. No full-slice or final
  playable-game approval is inferred from this native checkpoint.

## Compositor interaction checkpoint — review history

Scope: `game/interaction_types.py`, `interaction_frame.py`, `DrawCommand`
metadata, actor/environment/item/construction coverage, existing boundary,
fixture/world-depth and volume/area cuts, `SceneFrameResult`, and explicit
`.evidence` callers. The following findings record the intermediate review;
the final settled-source verdict below supersedes their open status. HUD and
control integration are outside this bounded checkpoint.

### Boundary and memory assessment

The implementation follows the intended shared compositor boundary: passive
semantic `WorldHit` values, local raster coverage on real draw commands,
`cut_selection` applied alongside actual cuts, and one final reverse-painter
occlusion pass. It introduces no engine target rule or alternative world-depth
solver. `pick_world` gives actual surviving actor/object coverage precedence
over a transparent aperture fallback. Highlights consume those same regions.

`compose_interaction_frame` allocates one viewport-sized boolean occlusion mask
and cropped local region masks. It does not allocate one full-screen mask per
entity. Latest source caches untransformed physical actor poses in the existing
32 MiB bounded palette-image cache, with media/rig/clip/facing/frame/layers in
the key; local transformed frame masks are discarded with the frame. Existing
environment and ground-item image caches remain bounded. Source inspection
supports those bounds; it is not a measured long-session memory receipt.

### Findings repaired during the intermediate review

- `partition_world_depth` initially included transparent selection/aperture
  extent in the visual depth mean. Latest source preserves the original
  selected-visual-pixel mean whenever any exist, using selection extent only
  for a transparent metadata-only piece. This avoids metadata changing real
  visual sort keys and avoids an empty mean for a transparent aperture band.
- Real construction media initially did not obstruct picking. Stone/Ice body
  commands and the original procedural shell/membrane surfaces now explicitly
  carry physical coverage; decorative motes and retired dust do not. Selection
  masks also follow the existing volume/area cuts. The original opaque Thorns
  shell now obstructs picking too, while remaining a nonselectable spatial
  effect; no object UUID is invented for it. This does not make every VFX
  command an occluder.
- Per-surface opacity is separate from `surfarray.array_alpha`. The final
  composition now skips `get_alpha() == 0`, so a completely faded body cannot
  retain a clickable or blocking silhouette.
- Generic merged wall corners initially assigned their entire displayed
  surface to each component UUID. Latest source supplies each member's existing
  straight-wall coverage, aligns it with the merged command, and intersects it
  with displayed pixels. Distinct native walls must retain distinct hit areas.
- Registered object masks initially extended beyond the actually displayed
  object's alpha. Latest source intersects them with its displayed surface;
  transparent aperture coverage remains separate. The initial renderer test
  exposed an object hit taking precedence at a retained actor-region sample.

### Findings tracked at the intermediate checkpoint

1. **Exact identity of merged Force wall sections.**
   `construction_media_draw_commands` merges adjacent native force-membrane
   objects into one rendered surface owned by the first UUID. Binding that
   whole command's alpha as the first object's hitbox assigns later sections
   the wrong native target. Latest source repairs this with retained native
   members and `_construction_selection`, using existing
   `volume_world_coordinates` and each member's original segment/height to
   partition genuine source coverage. This preserves the existing merged
   drawing and avoids a replacement engine object. The new real Force-wall
   recording test now confirms that every merged native member retains
   nonempty, distinct coverage in all four cameras. Source and this producer
   boundary test close the incorrect-whole-wall-UUID finding; visible control
   integration remains separate.
2. **Non-vacuous public renderer evidence.**
   An intermediate four-camera test permitted zero actor regions in every view after
   removing its failed `assert actor_regions`. That cannot establish a visible
   actor is selectable through the aperture. Retain a verified actual visible
   pose/pixel case, plus a truly occluded case, and assert the corresponding hit
   identities. A completely hidden actor may correctly produce no region; the
   test needs rendered visibility evidence to distinguish that from dropping
   all actors. This is now repaired: the test uses the real recorded
   `CrawlThroughWindow` midpoint with its authored sill height and tucked pose,
   requires nonempty actor regions, and checks actor hits in all four cameras.
   A real two-component corner identity case remains required for the repair
   above. Its first fixture used `environment.wall.fantasy_g1`, which is a
   registered environment prop and never reaches the generic merged-corner
   branch. Use the actual generic structural-wall path and assert its one
   `wall_corner` draw plus both component hits. Remaining plan lanes
   (overlapping loot, varied body poses/scales,
   cliffs, unknown/open/destroyed objects) need their named acceptance evidence
   before full Slice 2 approval.
3. **Ground fallback must preserve blocking information at shell integration.**
   Current `pick_world` returns `None` for both empty ground and an ineligible
   opaque foreground surface with no selectable identity. A caller must not
   treat every `None` as permission to run geometric `pick_support` or recover
   a concealed actor by tile equality. The approved last-priority support hit
   needs visible terrain coverage in the frame, or an equivalent bounded
   blocked/miss distinction. Do not invent an unknown object's UUID. This is
   an explicit shell/frame integration requirement; the absent shell is not
   claimed to be working by the present object/actor/aperture tests.

### Independent initial renderer run

With the same prepared Linux environment:

`python -m pytest -q tests/game/test_interaction_frame.py tests/game/test_window_presentation.py tests/game/test_boundary_rendering.py tests/game/test_jump_terrain_occlusion.py tests/game/test_elevation_rendering.py --tb=short`

**168 passed, 5 failed in 104.10s.** All five failures were in the newly added
interaction file: two views produced no actor region, two sampled actor-region
pixels picked an object, and the effect-exclusion fixture requested `Effect4`
in the unsupported `effect` slot. The latest fixture uses the actual `aura`
slot and a recorded destroyed window insert. Existing window, boundary, jump
and elevation renderer files passed. These results predate the source repairs
listed above and do not establish that current four-camera behavior passes.

After those source/fixture repairs, the complete changed interaction file was
rerun independently with `python -m pytest -q tests/game/test_interaction_frame.py
--tb=short -x`: **9 passed in 12.61s**. The four-camera test currently allows
zero actor regions in every view, so this passing result does not close the
explicit visible-body-through-aperture requirement above. No additional
production change was made by the reviewer.

The strengthened version of that same complete interaction file then passed
**9 tests in 13.11s**, independently. It now exercises a real visible body
through the window in all four cameras without relaxing the nonempty-region
assertion. Collection enabled/disabled produces byte-identical scene pixels in
each camera. Existing world-depth, field-volume, construction and Thorns
regressions are being checked for the later helper/cut changes.

With the Force and initial corner cases added, another complete interaction
file run passed **11 tests in 25.56s**. This closes the merged Force producer
case. It does not close the generic corner fixture mismatch described above.

### Latest compositor and media recheck — 2026-10-06

The corrected generic corner fixture now uses the actual structural-wall path,
requires `wall_corner` in public renderer evidence, and requires independent
nonempty coverage for both native component identities in all four cameras.
This closes the earlier fixture mismatch. The real crawl midpoint still
requires surviving actor pixels and exact actor hits in all four cameras, and
interaction collection still leaves the corresponding scene bytes unchanged.

`support_selection` now attaches only disclosed terrain/stair/water support
tops to their existing draw commands. `pick_world` resolves a visible actor or
object before the empty aperture, and the aperture before the supporting ground.
No hidden object's identity is invented. Water retains its original draw role,
so adding interaction metadata does not enlist it in a different visual floor
composition path. The eventual shell must consume these final regions and must
not revive a geometric ground fallback on every `None` result.

One additional source blocker was found after support coverage was added:
`game/floor_composition.py:compose_floor_coverings` transfers terrain pixels
beneath a rug/other covering and removes them from the terrain's visual surface,
but currently retains the terrain's original selection coverage. That transfer
exists specifically because the terrain's old painter depth can otherwise
cover its own floor object. Keeping those removed ground hit pixels can make
the picker select ground over the displayed covering. Apply the same existing
removed-pixel mask to selection/blocker metadata at this operation, without a
new depth calculation, and prove the resulting floor-object/ground distinction.
This is a blocker in implemented source, separate from absent control widgets.
An independent in-memory reproduction exercised `compose_floor_coverings`,
the real painter sort, `compose_interaction_frame` and `pick_world`: after the
terrain transferred all its pixels to the visible rug, remaining ground alpha
pixels were **0**, but the shared pixel still returned `WorldHit(kind='ground',
identity='tile')`. No test or production file was edited for that reproduction.

The independently run existing depth/volume/construction/Thorns files passed:

`python -m pytest -q tests/game/test_world_depth_commands.py tests/game/test_field_volume_ownership.py tests/game/test_construction_presentation.py tests/game/test_thorns_contact_presentation.py --tb=short`

**64 passed in 174.68s.** This followed the volume-coordinate extraction,
construction coverage and opaque Thorns-shell repairs. It does not substitute
for the later ground/floor fix.

The revised interaction/media and affected liquid/app boundary files also passed:

`python -m pytest -q tests/game/test_interaction_frame.py tests/game/test_ui_media.py tests/game/test_liquid_surface_media.py tests/game/test_app_smoke.py --tb=short`

**36 passed in 52.39s.** This includes the genuine corner, exact merged Force
member, crawl, per-surface alpha, physical-body-only and media dispatch cases.
It precedes repair/proof of the floor-composition selection gap above. Commands
use the prepared Linux uv environment specified earlier; repository/media reads
remain on the WSL-mounted Windows checkout.

### Bounded media-source assessment

`game/ui/media.py` uses existing `ContentPresentation`, `ImageResourceSource`
loading through `image_resources`, and existing `AssetSpec` paths. It does not
introduce another rule/feature catalog. Registered `ContentRef` values retain
their exact descriptor authority; direct native feature/item IDs and portrait
choices have explicit separate presentation references. Configured action refs
are resolved exactly. An unknown identifier returns no image; no display-name,
class-name or spell-name fallback is present.

`game/ui_composition.py` supplies current native feature IDs from the already
defined cold class levels/choices and item IDs from the existing direct-item
builder keys. It does not instantiate retired class factories or gameplay
objects to discover UI data. The loader requires each direct-ID set to equal
the corresponding current native set minus registered descriptor owners.
An initial duplicate `feat.lucky` direct row was removed: its existing registered
descriptor remains the owner, including its other presentation fields.

The reviewed data registers 515 indexed recovered icons and 56 portraits.
Independent file/hash inspection found every selected resource present and
**zero payload mismatches** against the existing authenticated icon index.
The current direct feature rows cover 48 unregistered IDs; registered Lucky is
the 49th native feature owner. All 374 direct-item rows correspond to native
IDs, with 246 icon bindings and 128 explicit missing images. Provisional reuse
such as Pistol's Light Crossbow icon is declared in `approximation`; it is not
a fabricated native content alias. Missing registered artwork is an explicit
handoff and later labelled-placeholder requirement, not an excuse to infer a
different content descriptor. The small image cache is capped at 192 entries.

No media-source blocker remains in this bounded inspection. Actual portraits,
tooltips, placeholders, action/inventory buttons and their input semantics are
later UI gates. The media resolver's success does not establish that the UI is
already playable or that every subject has exact artwork.

## Settled compositor/media source verdict — 2026-10-06

**Approved within the reviewed source boundary. No source blocker remains from
this checkpoint.** This verdict supersedes the intermediate open findings above.
It does not approve the complete UI, gameplay input, or all planned visual lanes.

`game/floor_composition.py:compose_floor_coverings` now passes the exact
already-computed transferred region through `cut_selection` for both selection
and physical blocker metadata. It preserves cuts from earlier coverings and
uses the same local coordinates as the removed visual pixels. Existing surface
composition and painter-depth arithmetic are unchanged; no second depth or
visibility calculation was introduced.

The new observable picker cases cover the original failure and adjacent
contract: a visible rug wins over transferred terrain; exposed terrain still
picks its ground identity; an opaque foreground wall without a selectable
identity blocks the underlying support; and an empty admitted aperture wins
over ground. Earlier meaningful four-camera crawl/corner and native merged
Force-section checks remain present.

Independent complete affected-file recheck, with the prepared uv environment:

`python -m pytest -q tests/game/test_interaction_frame.py tests/game/test_ui_media.py tests/game/test_world_depth_commands.py --tb=short`

**38 passed in 29.58s.** This final run follows the floor fix. The implementer's
separate 16-case interaction/media result was not used in place of this run.
The existing world-depth file verifies unchanged composition for translucent
and sparse overlapping floor coverings, support shadows, additive/alpha media
and cropped world-depth coordinates. `git diff --check` also reports no
whitespace errors, only the repository's LF/CRLF conversion notices. The
reviewer made no production edits.

Remaining acceptance is explicit: the shell must consume the final hit regions
without a geometric fallback, and wider planned body/loot/cliff/object lanes
need their actual control and visual evidence. UI media requires visible
labelled placeholders, tooltips and portrait/action/inventory integration.
The user's newly chosen Blender-rendered pixelated chrome with sharp live text
belongs to the next UI step; no generated chrome or finished-widget claim is
covered by this source verdict. Later HUD/log timing, focus/selection, native
commands and playable Fighter/Sorcerer encounters remain separate gates.

## Stage 3 shell/world interaction — first source review, 2026-10-06

**Not approved yet.** This is an active implementation checkpoint: the
implementer began repairing findings during this review. Earlier native and
bounded compositor/media approvals remain scoped to their recorded boundaries.
The reviewer made no production edits, read no other chat, and contacted only
the parent implementation agent through the current task's collaboration tools.

Reviewed `game/ui/action_bar.py`, `world_interaction.py`, `variants.py`, `hud.py`,
`layout.py`, `types.py`, `media.py`, `targeting.py`, `game/controls.py`, the actual
`game/encounter_play.py` SDL input/command path, relevant Session/native discovery
owners, and `devtools/import_ui_icons.py`. The current user direction is a
minimal chosen-shortcut row with unchanged CIE28 icons, maximum acceptance
resolution 2560×1440, and directed straight Wall of Fire whose ordered endpoints
determine its hot side. The superseded Blender-heavy default HUD is not an
accepted visual target. Library, inventory, creation, complete log and final
encounter flows are declared unfinished; their absence is not reported as a
false completion claim.

### Source findings requiring repair and focused recheck

1. **Native Sorcerer alternatives disappear in the facet picker.**
   `action_families` correctly retains the real indices, but `variant_choices`
   only renders rank/facet dimensions. Current native discovery for both
   `action.class.sorcerer.convert_sorcery_points_to_slot` and
   `action.class.sorcerer.convert_slot_to_sorcery_points` has three distinct
   alternatives and no such dimensions. The popup consequently renders zero
   choices and defaults to one row. An independent scan of both default native
   player characters found the real `2SP→Slot L1`, `3SP→Slot L2`, `5SP→Slot L3`
   and inverse L1/L2/L3 rows colliding under empty `variant_values`. Expose the
   remaining exact rows in a fallback selector, or publish their rank from the
   native owner as a typed facet. Do not parse display strings or manufacture
   conversion actions. Prove that every native conversion remains selectable
   and uses its original cost/effect.
2. **A captured shortcut executes after a modal opens.**
   The running frame pump was independently exercised with pointer-down on
   Dodge, then Escape (opening the encounter menu), then pointer-up at the
   captured shortcut. It executed one player command. `pointer_capture`
   survives the focus change, and the family release path does not require
   the original widget to remain in the active focus surface. Invalidate or
   revalidate capture across modal/selection/layout transitions; release over
   a disappeared or obscured widget must not execute it. This proof used real
   SDL events and the existing `run` entry, not a mocked handler.
3. **Ctrl mode needs a complete discovery lifecycle.**
   Initial source allowed Ctrl release to replace `choices` after a command's
   indices had already been queued in the same input batch. Independent native
   discovery proved the consequence: forced melee target index 0 was Shield
   Fighter, while the same normal-discovery index was Goblin 2; index 1 changed
   Goblin 2 to Goblin 1, and index 2 disappeared. The initial queued-command bug
   now has a `command is None` guard at Ctrl release. A second transition still
   needs recheck: releasing Ctrl during active targeting clears the flag but
   retains all-target discovery; canceling back to neutral must rediscover
   normal targets before an ordinary click can attack an ally. Command indices
   must always belong to the exact retained discovery at dispatch.
4. **Ctrl and aperture routing must stay distinct.**
   Initial source passed an aperture's frame UUID to `main_attack`, turning a
   transparent opening into an enlarged attack hitbox. The first narrowing to
   `elif force_attack and hit.kind == 'object'` left aperture clicks falling
   into the normal world-action branch, potentially traversing while Ctrl was
   held. Ctrl plus empty aperture must do neither. Explicit object-target
   selection must also exclude aperture UUID matching. Frame pixels, visible
   actor pixels and neutral empty-aperture traversal retain their separate
   compositor meanings.
5. **Pending approach can outlive replacement user intent.**
   `select_row` and panel opening retained `focus_ui.pending`; the automatic
   follow-up block did not require neutral selection/focus. After a move, a
   new target choice or inventory opening could therefore still trigger the
   earlier world use. Retire the pending intent when replaced/canceled and
   permit follow-up only at the correct neutral ready boundary, after matching
   actor and exact current native descriptor/admission. Neither a different
   action nor a modal may coexist with automatic follow-up authority.
6. **Exact world descriptor matching drops its template identity.**
   The native owner supplies `AvailableWorldInteraction.template_name` for
   observed item uses. Both `admitted_world_actions` and post-approach descriptor
   matching initially ignored it, checking only behavior/configured ref/facets
   and subject/connector. Include the supplied exact template identity when
   matching a source-item action. Identical displayed dimensions must not
   authorize substitution of a different retained use variant.
7. **Alt can overwrite selection and its labels lack a click route.**
   Selected/hover highlights are appended before Alt entries, while
   `draw_highlights` uses the last color for each identity. Alt therefore wins
   instead of remaining lowest priority. Resolve one final color with the
   required selection > hover > Alt precedence. Drawn Alt labels currently
   have no semantic hit region. The window's label/context traversal alias is
   required when an actor occupies the hole; it must route the disclosed exact
   world identity without attacking through the aperture or bypassing native
   admission.

### Initial findings already being repaired

- Right-click initially bypassed `ui_frame.blocked` and could open world
  context through the log/bar. Latest inspected source consumes blocked points
  before that world branch. This needs a real input regression alongside
  cancel/popup precedence; source inspection alone is not full focus acceptance.
- Pause initially changed `paused` but left the precomputed `ready` usable for
  the remaining input batch. Latest source clears readiness and a queued command
  when pausing. An independent `run` scenario posted Pause and Space together at
  an established human-ready frame: **0 player commands**, frames 80–82 paused
  and not input-ready. This sampled repair does not prove every focus/mode
  transition in the larger dispatcher.

### Bounded positive evidence

The widgets consume detached native rows and passive player/HUD facts. Native
execution remains in Session calls from the application loop. Variant selection
returns actual discovery indices rather than rebuilt actions. World approach
uses existing Move targets and native contact positions, excluding hazardous
paths; no client pathfinder or invented Dash is present. Final world picking
uses the reviewed interaction frame. Unseen destination picking is restricted
to explicit native preview positions and supplies no hidden entity identity.

Straight Wall of Fire now exposes one `segment` variant with native `hot_side`
set to left and no side facet; ring inside/outside remains explicit. The popup
enumerates facets from native rows, so archived unused left/right illustration
rows do not themselves create a gameplay choice. Native description explains
endpoint reversal. Reversed-endpoint native/visible preview acceptance remains
required; this is a source finding, not a pixel/behavior completion claim.

Current media continues exact `ContentRef` lookup first, then explicit native
provider/direct-ID presentation. Choice illustrations match an exact registered
owner plus discovered facet/value requirements. Intake refreshes artist-handoff
hashes to current native descriptor owners rather than fabricating refs or
creating new mechanics. Original CIE28 images remain byte-for-byte intact;
28-pixel resources use integer nearest scaling while text is rendered live.

Independent intake inspection verified **588 selected files / 613,296 bytes**:
every installed and private production copy matches the admission hash, the
preserved original archive hash matches, and **48** subject-owner rows are
refreshed. No copy/hash failure was found. The existing three media tests pass,
including exact owner lookup and the 42-pixel request resolving to an unchanged
28-pixel integer-size icon. Choice/skin candidates still require visual approval.

Independent command, using the prepared uv environment and short tracebacks:

`python -m pytest -q tests/game/test_ui_media.py tests/game/test_controls.py tests/game/test_encounter_play.py --tb=short`

**13 passed in 36.61s.** The controls file still tests the superseded menu path,
and the encounter tests chiefly submit native callbacks. These passes do not
cover the reproduced captured-pointer defect or constitute the upcoming new
input/variant acceptance. The additional native-discovery and real-event
reproductions above were run without editing test or production files.

Layout calculations were sampled at 960×540, 1280×720, 1920×1080, 1920×1200 and
2560×1440 for 100/125/150% UI scale: the computed shortcut row fits horizontally
in each case. This is geometry-only evidence; no 4K or larger-monitor checks
were run or claimed, and it does not prove legibility or collision-free panels.

### Named remaining integration work

The ability library must preserve chosen shortcut slots when their family is
temporarily absent: `shortcut_indices` currently filters missing keys and
compacts neighbors. Retain a disabled labelled slot rather than silently
shifting bindings. The live melee/ranged preference control and visible native
unavailability reasons need their eventual routes. Remove the now-uncalled
legacy `handle_menu_event`/`draw_menu` path in final cleanup instead of keeping
two maintained selectors. The current permanent three-medallion utility row
also needs reconciliation with the user's minimal, panels-on-demand direction
before visual approval. Complete downstream panels, combat-log acceptance,
HUD commit timing and actual Fighter/Sorcerer play remain later gates.

### Repair progress observed after the first shell review

The implementer has since added capture invalidation on keyboard/resize changes
and focus matching at release; tracked the discovery's Ctrl mode separately
and invalidated mismatched choices on return to neutral; prevented ordinary
world fallback for Ctrl/aperture; cleared pending approach on replacement
selection/panel/world intent; and required neutral focus for its automatic
follow-up. These are promising bounded source repairs, pending the requested
new real-input regressions and independent settled-source recheck.

The first template-match repair was too broad: an unconditional comparison
against `option.template_name` rejects native pickup and connector descriptors,
whose template field is intentionally `None`. The exact comparison belongs only
where the descriptor supplies a template (source-item uses); UUID/connector
binding remains authoritative for the other families. This regression was
reported immediately. Do not close world interaction acceptance without real
pickup, connector and source-item variant cases.

The exact-row fallback for Sorcerer conversions, stable absent shortcut slots,
Alt precedence/label routing, and removal of the permanent utility row were
still being implemented at this inspection. No new source approval is issued
from an in-progress repair report.

## Slice 3 settled source recheck — October 6

**Bounded shell source approved.** This supersedes the open source verdict
above, not the remaining world/input/visual acceptance requirements. Reviewed
the current `game/encounter_play.py` dispatcher and `game/ui/action_bar.py`,
`world_interaction.py`, `variants.py`, `panels.py`, `hud.py` and `types.py`.
No production or test-file edits were made by this reviewer. The complete
combat-log implementation is a separate next checkpoint; creation, complete
inventory flows and the final Fighter/Sorcerer encounter are not approved by
this receipt.

### Earlier findings closed at this boundary

| Finding | Current implementation and bounded evidence |
|---|---|
| Facet-free native alternatives disappear | `variant_choices` adds a residual exact-row group when more than one original index has the same native facet values. Labels remain native `display_name`; selection retains the original index. Independent native Sorcerer conversion coverage passes. No display-string parsing or substitute conversion executor was introduced. |
| Pointer capture crosses a modal/focus change | Keyboard/resize/right-click invalidate capture; left press requires the rendered focus, and release requires the captured focus plus current discovery generation. The real SDL press–Escape–release regression passes with zero commands. The ordinary click still issues exactly one native Dodge. |
| Ctrl discovery is rebound or survives cancellation | The loop records the discovery's force mode, protects already queued commands from Ctrl-release rediscovery, and refreshes normal choices on neutral return/cancellation. Indices remain attached to the retained native result. |
| Ctrl aperture falls through to attack/traversal | Forced attacks accept actual actor/object regions; `target_at` does not UUID-match an aperture as an object. Normal world routing is explicitly guarded by `not force_attack`, preventing Ctrl aperture/ground fallback. |
| Pending approach outlives replacement input | Selection, panel opening and replacement world intent retire the pending intent. Follow-up requires neutral ready focus, a later generation, the original actor, and a matching newly discovered descriptor before finding a current native action. |
| Exact use identity is incomplete | Direct admission checks a supplied `template_name`, configured ref, facets and native subject/connector binding. The template comparison is conditional because pickup/connector descriptors intentionally omit that field. Pending matching also retains the descriptor identity. An independent real workshop discovery admitted its lever exactly once and found safe native Move approaches for remote torches. This is not a substitute for the remaining execute/pickup/window gesture lane. |
| Alt competes with selection or has a separate executor | Alt outlines are added at lowest priority. Label `UIHit` carries the actual passive region `WorldHit`; its press enters the existing world/active-target/context route. There is no label-specific executor or implicit choice of the first world option. |

The label implementation briefly stored a preselected world option. That bypassed
active target selection and the normal tied-default context behavior. It was
replaced during recheck with the shared `WorldHit` route above. This source fix
is approved; dense-label placement and actual occupied-window label clicks
still require their integration evidence.

The ability search now consumes keyboard input before Q/E/G/T world controls;
continuous camera panning is gated while a panel is open. Drawing and keyboard
selection share `shortcut_page`, so an out-of-range saved page cannot display
one slot while its key selects another. Missing pinned families retain `None`
slots and their exact `ActionFamilyKey`; a neutral right-click can remove even
an absent family without native execution. The permanent utility medallions
are removed in favor of keyboard/on-demand menu navigation.

Two additional concrete source defects were found and repaired in this
recheck:

- Right-click initially removed a bar shortcut before canceling an active
  target/pending intent, and blocked UI regions could suppress cancellation.
  Cancellation now comes first and consumes the gesture before shortcut,
  blocked-region or world-context handling. Context/unpin needs a later click.
- A rejected native command's `MenuState.status` was cleared by next-frame
  discovery, leaving its reason visible for one frame. Rediscovery now retains
  inactive status; replacement selection or a successful command clears it.
  This uses the existing status display rather than a second notification
  subsystem.

### Passive panel and command boundary

`panels.py` receives only `AvailableActionsResult`, `PlayerState` and the
authorized `PlayerHUDSnapshot`. Ability filters group current native rows;
item powers preserve source UUID and row index. Inventory visibility explicitly
distinguishes undisclosed data from an empty inventory. Equip slot choices come
from the projected native-compatible slots, and `own_turn` gates mutation hits.
The application submits ordinary Session commands; widgets do not query live
entities, construct actions, grant resources or implement equip/use rules.

The sheet reads the presented actor and conservative HUD snapshot. The playback
sampler has already replaced the displayed actor's HP with its sampled value;
there is no newly introduced future-HP lookup in the sheet. This source result
does not establish all future panel timing or inventory-flow acceptance.

### Test evidence and limits

Independent recheck command in the prepared uv environment, short tracebacks:

`python -m pytest -q tests/game/test_ui_input_acceptance.py tests/game/test_ui_native_choices.py tests/game/test_ui_media.py tests/game/test_controls.py tests/game/test_encounter_play.py --tb=short`

**20 passed, 2 failed in 100.70s.** All five actual SDL gestures passed: ordinary
click, captured press–Escape–release, Pause+Space, menu+Space and neutral Space.
The two failures were invalid test setup in the new native-choice cases: the
Wall of Fire caster lacked a discoverable rank, and the attack target setup did
not admit the expected follow-up. The implementer corrected these fixtures;
the tests now use a native rank-four spell actor and admitted Fighter attack
targets with fixed rolls. The expectations were not weakened.

Independent complete affected-file rerun:

`python -m pytest -q tests/game/test_ui_native_choices.py --tb=short`

**4 passed in 5.78s.** This covers residual native conversion choices, directed
straight/ring Wall of Fire facets, stable missing pin positions and native
Extra Attack after the ordinary main attack without a bonus expenditure.
The implementer's current combined native-choice/wall-selection/SDL run is
recorded in `.runtime/ui-study-20261005/ui-input-current.log`: **22 passed in
67.57s**. This log was inspected; it is not represented as an independent run.

The five physical SDL cases do not yet prove every Ctrl/Alt/pending approach,
occupied-window, source-item variant, dense-label or search/page gesture. The
final cancellation/status changes received source verification, without a new
dedicated physical regression from this reviewer. Those limits remain explicit
integration requirements, alongside full inventory operations, multi-target
confirmation/undo, visual acceptance up to 2560×1440, and the final playable
Fighter/Sorcerer encounter. Remove the superseded uncalled menu handlers during
final integration rather than maintaining a parallel selector.

## Slice 4 canonical combat log — October 6 source review

**Not approved yet.** The new log retains the correct native authority, but the
uncovered timing and scroll-state defects below need repair and focused recheck.
Reviewed `game/ui/combat_log.py`, `rich_text.py`, the encounter's intake/render/
input use, optional `PlayerNode.turn_execution_id`, `presentation_timing.py`,
the existing Session standalone capture and sequence/projection fields. No
production or test-file edits were made.

### Positive boundary findings

- Canonical rows are exactly the projected `PlayerNode.combat_log` entries,
  keyed by generation, observer and terminal event UUID. Equal text does not
  deduplicate distinct events; equal keys reject conflicting payloads. Embedded
  `sub_entries` are not traversed as a second row stream. Empty native producers
  do not gain generated narration.
- Nearest logged native ancestry owns row nesting. Separately retained reaction
  roots use the existing presentation group relationship; their own gates can
  precede an unrevealed trigger. Parent summary gates include their logged
  native descendants, preventing early final totals. No new mechanical or
  animation clock is present.
- Timing reads the existing normalized milestone/dependency exports and exact
  resolution ownership. The lifecycle export copies existing cue UUID/start
  values. `turn_execution_id` is an optional copy of the native identity and
  traverses the ordinary player serialization path.
- Standalone immunity remains the previously reviewed original producer and
  immediate observer projector, detached in `CombatLogAppend`. Ordinary event
  callbacks do not duplicate canonical rows. The optional sequence fields
  preserve those values without introducing a transcript schema.
- Rendering, filtering and copy receive projected entries only. The parser
  recognizes the documented fixed vocabulary; unknown/nested/unclosed markup
  remains literal. Measured wrapping preserves long text, newlines and spaces.
  Category/actor filtering keeps native totals and muted ancestor context.
- History caps canonical rows at 10,000 and evicts received groups; missing
  parents promote remaining rows in the view. Layout has bounded height records
  and at most 512 span layouts, without permanent surfaces per event. Only
  displayed rows are rasterized. The old three-line log is replaced.

### Concrete repairs required

1. **Standalone appends wait for unrelated later operations.**
   `encounter_play.receive` records each append's `operation_end_cursor`, but
   the display path releases the entire pending list only when `active is None`
   and the complete presentation queue is empty. An earlier immunity therefore
   waits through subsequently received operations; the cursor is unused.
   Associate appends with their containing operation's already queued last
   disclosed head, and release on that head's historical settlement. With no
   disclosed head, use the next already established settled boundary. Preserve
   the recorded end cursor for passive replay. Prove two consecutive operations
   with an earlier append and a later nonzero-duration group: the first append
   appears once after its operation, before the later operation completes.

2. **Death-save and turn-start timing ignores available native dates.**
   Independent `lifecycle_history(save_seeds=(5,))` binding shows the natural-20
   `SAVING_THROW` log at **1250 ms / group_completion**, while its exact exported
   `life/start` milestone is **0 ms**. The generic log-family branch excludes
   `life/start`. The same history has a turn-start marker at 1250 ms although
   its bound turn start is 0 ms. Use the exact lifecycle cue for death saves,
   and the existing turn-start boundary for the marker, retaining exact event
   ownership. Do not synthesize a new timing policy or select by actor/name.
   Keep result-bearing parent summaries gated on their descendants; turn
   headings follow the study's explicit turn-marker rule.

3. **The new-entry badge counts rows that cannot yet be shown.**
   `visible_log_rows` checks native ancestor gates, but the footer counts only
   each row's `reveal_ms`. An independent render with parent=100 ms, child=10 ms
   and now=50 ms produced **zero visible rows and `New entries (1)`**. Factor one
   ancestor-admitted eligibility view for hierarchy and the counter; collapsing
   or filtering must not redefine admission. A separate reaction association
   must still permit an earlier reaction. This is a visibility/count defect,
   not permission to change any native or presentation time.

4. **Filtering discards a valid reading anchor.**
   The `log_filter` and `log_actor` input handlers reset `scroll=0, anchor=None`
   even when the anchored entry remains in the filtered view. Preserve the
   existing key and intra-row offset, then let layout clamp or choose a fallback
   only if that entry disappears. Prove category and actor changes while reading
   an entry that survives the filter, in addition to the existing resize test.

The view also retains expanded/selected identities after history eviction.
Prune these UI-only keys against retained rows during ordinary view
reconciliation, so the fixed history limit does not leave a growing expansion
set across a long encounter.

### Independent evidence

`python -m pytest -q tests/game/test_ui_combat_log.py --tb=short`

**9 passed in 8.78s.** Real observer packets cover repeated identical Magic
Missile damage, successful/failed Counterspell, condition and opportunity
movement histories. Other cases cover literal markup/wrapping, the 10,000-row
cap and promotion, parent-versus-reaction eligibility, and resize/read anchoring.
The implementer's corresponding 9-case log records 8.81s. The general reaction
cases assert preserved entries and dates within group bounds; they do not assert
every exact family boundary, which is why the death-save probe above matters.

Additional read-only native binding reproduced the death-save timing above;
the footer reproduction used original native entries with only their passive
test dates/parent link replaced. Its first diagnostic run lacked the standard
content-system bootstrap and stopped before assertions; rerunning with the
documented test startup produced the stated result. No engine behavior was
changed to obtain it.

### Remaining interaction and acceptance scope

Current scrolling is wheel plus Follow/new-entry control, with whole-row copy;
there is no character-range selection or scrollbar/keyboard page navigation.
The category control cycles individual native enums rather than the planned
grouped categories. Historical participant chips check `actor.present`, which
is not current perception; camera centering still uses permitted scene actors,
but historical inspection needs a visible historical/current distinction.
These limitations must be reconciled before claiming the complete log UI.

The live standalone operation test, passive replay/seek/skip consumption,
hidden/same-name participant cases, explicit state-only absence, concentration,
destruction/loot/summon and actual long-detail/high-DPI captures remain acceptance
work. Optional packet fields round-tripping does not prove a replay UI retains
them: `decode_player_sequence` intentionally remains a baseline/lineage
convenience API, so the UI must also retain the decoded sequence model.

### First repair recheck

The generic gate now accepts exact life starts: the native natural-20 death
save itself moves from 1250 ms/fallback to **0 ms/presentation**. A common
`admitted_log_rows` now owns ancestor admission for the tree and footer. Filter
handlers retain the reading anchor, and drawing prunes evicted expansion and
selection keys. These inspected source changes address their named defects.

Three timing/count details remained open in that first repair snapshot:

- The turn-start ancestor still has no event-owned exported boundary, so its
  fallback remains 1250 ms and continues to hide the now-correct save. Removing
  descendant delay alone does not supply the existing 0 ms turn boundary.
- Real projectile death (`projectile_life_history(LifeState.DYING)`, caster
  packet) has a DEATH log at **1371.23 ms/fallback**, but an exact unlogged
  native LifeFact descendant has **761.23 ms life/start**. The death gate must
  use that exact native descendant evidence, with relevant HP ownership,
  rather than dropping it because the LifeFact has no log of its own.
- Appends are now paired with the operation's last received group and released
  when that group completes. An operation with no disclosed group still gets
  `owner=None` and is released immediately, even while prior history is playing
  or paused. Such appends need the last already queued/active head at receipt as
  their settlement boundary; later operations must not extend that wait.

The footer must also keep truncation count distinct from admission: adding all
`history.dropped` can count a never-revealed prefix of an oversized active group
as new. Ordinary completed-group eviction does not expose this edge.

Additional independent complete-file checks:

`python -m pytest -q tests/game/test_player_hud_boundary.py tests/game/test_presentation_commit_evidence.py --tb=short`

**16 passed in 34.27s.** This preserves prior HUD/append disclosure/packet
contracts and existing commit-evidence behavior. It does not close the timing
and counter issues just reproduced, or establish a working replay UI.

### Settled log recheck — bounded source approval

All four source blockers above are now closed at the inspected boundary:

- `BoundChoreography.turn_starts` retains each exact TurnFact event UUID
  alongside its already computed time and actor. `presentation_milestones`
  exports that value as `turn/start`; the log consumes it directly. The existing
  condition-lifetime consumer was explicitly updated for the added tuple value.
  Natural-20 save/turn rows now use their 0 ms boundary and are visible then;
  the 1250 ms body recovery no longer delays the marker.
- Death gates traverse only the logged Death node's native `children_lineages`
  and read the existing life-start milestones of those exact descendants.
  Unlogged LifeFact evidence is retained without creating an extra log row or
  matching unrelated actors. The real projectile death case now uses its
  761.23 ms life boundary instead of 1371.23 ms group completion.
- Standalone appends bind to their containing operation's final received group.
  With no such group, they bind to the last already pending or active head at
  receipt, or the next settled display when no head exists. Later operations
  cannot postpone them, and older paused/playing history cannot be bypassed.
  Their original operation-end cursor remains on the passive recorded value.
- Admission is shared by rows and unread bookkeeping. `LogView.seen` contains
  only retained admitted keys; truncation count is separate. Evicted expansion,
  selection and seen keys are pruned. Actor/category handlers preserve existing
  anchors and offsets for ordinary layout reconciliation.

Independent settled-source command:

`python -m pytest -q tests/game/test_ui_combat_log.py tests/game/test_ui_character_creation.py --tb=short`

**18 passed in 19.63s:** 12 log cases and 6 creator cases. New native log tests
cover the natural-20 turn/save and projectile-death dates, and unrevealed
eviction not generating a new-entry badge. Earlier 16 HUD/append/commit checks
also passed as recorded above. No fresh physical two-operation append/replay
test was run by this reviewer; settlement is a bounded source approval, with
that integrated evidence still required.

The canonical log has no remaining blocker in this source checkpoint. This
does not approve the remaining grouped filters, selection/navigation, historical
chip distinction, passive replay consumption or actual expanded/high-DPI
recordings named above. The player encounter remains the final acceptance gate.

## Cold creator and startup source checkpoint — October 6

**Creator input source not approved yet.** The cold-data/native-validation
boundary is sound, but a physical stale-roster click can crash the creator.
Reviewed `game/character_select.py`, `game/ui/character.py`, `game/__main__.py`,
selected-build Session composition, and the extracted origin/class requirement
helpers in the existing native definitions. No production/test edits.

The creator keeps immutable `CharacterBuild` drafts, reads the same ordered
origin/class requirements as the resolvers, and uses `resolve_character_build`
for whole-candidate admission. `origin_choices` and `class_level_choices` are
shared extractions from existing native definitions; widgets do not create a
second class table. Sorcerer replacement's optional flag and ordered labels
describe the existing old-spell/new-spell contract. A preview uses passive
appearance input and the existing modular renderer, without live Entity
creation or global reset. Starting packages expand when chosen, not during
paint or repeated deployment. Back/cancel drops only the draft.

Startup runs the creator before ordinary skirmish composition, returns a
validated one/two-build tuple, and creates each selected native character once
at the existing Session boundary. `--encounter` deliberately keeps its fixed
authored roster, and headless/quick-start keeps premades. There is no new save,
XP award, live respec or hydration subsystem. Prepared/feature defaults and
all actual grants remain in the native build path.

### Blocking physical input reproduction

`choose_characters` resolves press events against the previous frame's `hits`
even after a prior event changes `party` or opens/closes a draft. A read-only
independent run posted two real left-click gestures in one frame: **Remove the
first roster member, then Edit the formerly second member**. The first gesture
shrinks the tuple; the stale second hit still carries index 1 and raises
**`IndexError: tuple index out of range`**. Stale roster Start can similarly
remain reachable after opening an editor before repaint.

Revalidate the pressed/released hit against the rendered party/draft/layout
surface, matching the bounded focus/capture policy already used by the
encounter shell. A changed surface must consume stale gestures until its new
controls have been drawn; checking only the numeric index would prevent the
crash while still choosing a different character. Prove both same-frame roster
mutation and modal/draft capture transitions with the real creator entry.

The independent 18-case run recorded above includes six creator cases: all
three level-one drafts validate without EventQueue mutation, point-buy/package
edits use native admission, every page/modular appearance draws, and a physical
edit-cancel-start sequence preserves the original party. Those existing cases
use separate frames for transitions and do not cover the reproduced crash.

Complete creation acceptance still requires chosen Fighter/Sorcerer deployment,
required origin/class/ASI/metamagic/replacement choices and multiclass/cap
rejection, representative supported origins, before/after/automatic-grant
review, and actual supported-size captures. Full in-encounter inventory remains
a separate unfinished lane.

Independent complete affected native-definition files:

`python -m pytest -q tests/progression/test_direct_character_builds.py tests/progression/test_direct_character_origins.py tests/progression/test_direct_fighter_progression.py tests/progression/test_direct_barbarian_progression.py tests/progression/test_direct_sorcerer_progression.py --tb=short`

**137 passed in 5.14s.** The shared cold-choice extraction preserves tested build,
origin and all three class progression contracts. It does not cover the stale
creator hit surface.

A repository-wide compatibility search after the bounded log approval also
found `devtools/animation_review/trace.py:group_trace` still unpacking two values
from the now-three-value `turn_starts`. This trace consumer must be updated and
a native turn/lifecycle trace rechecked before the overall integration can
close. The canonical log's exact-date logic itself remains approved.

The trace compatibility repair is now verified: `group_trace` unpacks the
three values and preserves `event_uuid` in its existing trace row. A fresh
natural-20 native history successfully serialized its turn trace, and the
exported identity matched a real node in that captured group. No replacement
trace schema or timing computation was introduced.

The creator now clears the rendered hit surface after each accepted gesture
and keyboard/text/scroll/resize transition. This prevents stale-index reuse,
including a roster Start click after opening the editor. The first complete
8-case rerun reported 6 passed and 2 setup failures (`font not initialized`):
the earlier physical creator case calls `pygame.quit`, so the two new cases
needed the normal Pygame initialization before drawing their fixture controls.
The implementation was not changed to accommodate this test-lifecycle issue;
the complete-file rerun after fixture correction follows below.

### Settled creator recheck — bounded source approval

Independent complete-file rerun after the setup correction:

`python -m pytest -q tests/game/test_ui_character_creation.py --tb=short`

**8 passed in 19.31s.** Both new actual SDL regressions pass in the full file:
removing the first roster member followed by a stale Edit click preserves the
remaining original member and starts it only on the later redrawn Start; opening
an editor followed by the old Start click does not deploy. The existing cold
edit/cancel/start and no-event-mutation checks also pass. The native 137-case
build/origin/class suite and 18-case log/creator run are recorded separately
above, without adding overlapping tests into a misleading unique total.

**Bounded cold-creator source approved.** No identified creator/startup source
blocker remains after this recheck. This covers draft ownership, native choice
and validation reuse, one/two-build startup composition and repaired hit-surface
admission. It does not claim completion of all creator/appearance choices,
deployment/inventory gameplay, portrait-art visual approval, or the final
Fighter/Sorcerer encounter. Those remain the named integration acceptance lanes.

## Log text selection and scrollbar extension — October 6 review

**Checkpoint open: one stale-layout input blocker.** Reviewed
`game/ui/combat_log.py` and the corresponding capture/dispatch paths in
`game/encounter_play.py`; no production or test edits. The parent shell run is
complete: `.runtime/ui-study-20261005/ui-shell-acceptance.log` reports
**117 passed in 244.15s**. Independent complete-file verification reports
**13 passed in 9.25s** for `tests/game/test_ui_combat_log.py --tb=short`.
These overlapping runs are separate evidence, not a combined unique count.

The extension preserves the approved ownership boundary. `LogTextRegion`
contains current measured character advances and canonical row identity;
`copy_log_selection` slices `plain_log(row_text(...))` from the original native
entry. It adds neither narrative wording nor a second log-entry store.
Expansion has its own `log_expand` hit, while text selection stays within one
entry. The scrollbar's measured track/thumb map through `drag_log_scroll` into
the existing `scroll_log` anchor and offset. The new test covers canonical
character slices and both scrollbar endpoints. Root capture consumes these
gestures before world command dispatch, and keyboard/resize/focus transitions
cancel or reject captures as previously reviewed.

### Required repair: invalidate character coordinates when log mode changes

`log_expand` and `log_detail` change `log_view`, but do not change `focus_ui`.
The subsequent press guard compares only `focus_ui` with `rendered_focus`.
Consequently, two queued gestures in one frame can expand an entry and then
select its old compact text using the previous frame's `LogTextRegion`. Copy
resolves the same indices against the newly selected native verbose/detailed
string. The selected characters no longer match the text the user pressed.

The mismatch was checked with an actual captured opportunity-attack entry from
`attack_history('weapon.longsword', 5, opportunity=True, whole_movement=True)`.
Its compact string is `Goblin CRITS Hero for 8 damage!`; its verbose string
begins `Goblin → Hero (Handaxe)`. Reusing the compact character range for
`in CRITS Hero for 8 ` after expansion copies `in → Hero (Handaxe)\n`.
This independent check reproduces the canonical/layout state mismatch; the
current physical SDL suite does not post this particular batched gesture.

Admit text and scrollbar gestures against the rendered log layout as well as
the existing shell focus. A log layout-changing gesture must consume stale
log hits until repaint, or an explicit layout version must reject them and
cancel affected captures. Keep this as passive input/layout state; do not
retain a competing selected-text transcript. Prove expansion/detail followed
by an old text drag/copy within one event batch cannot reinterpret character
indices. Filter/actor layout transitions should use the same admission path.

After that repair, recheck the focused log and physical-input cases. No further
source blocker was found in this small extension. This review does not close
the broader replay, historical-disclosure, visual or complete encounter gates.

### Repair source recheck — physical evidence pending

The bounded repair adds `log_hits_valid` to the existing encounter input loop.
It begins false and becomes true only after `draw_combat_log` builds the actual
hit surface. Expansion, detail, category/actor filters, follow and wheel scroll
invalidate that surface. Subsequent stale log presses/releases are consumed,
and text-selection motion requires valid rendered positions. Keyboard/resize
still cancel capture through the established shell path. A captured scrollbar
drag can continue against its existing measured track while invalidating new
log hits; this does not reinterpret canonical character indices.

The identified source defect is repaired without a new log, timing or gameplay
owner. Final approval of this extension remains pending the promised physical
SDL batched gesture/copy regression. The earlier 117-case shell run predates
this admission repair and is not evidence for that new regression.

## Strict UI, native labels, portrait ownership and SELF binding — October 6

**Bounded source approval after repairs; complete encounter/visual acceptance
remains open.** Read the latest Recovery Plan and player UI constraints, then
reviewed the live UI views, log defaults/capture, all item-effect presentation
producers, exact portrait resolution/intake and the shared action binder.
No production or test edits were made by this reviewer.

The current views use flat quiet panel backgrounds, content-sized live panels,
the accepted single shortcut row and readable live text. Target selection shows
the native action name, current allocation count and confirmation/cancellation;
the persistent instructional prose was removed. Item effects now carry
`display_name`/`description` on `ItemEffectPresentationState`; weapon additional
damage, weapon coats and Continual Flame supply their existing native labels.
Inventory reads these passive facts instead of exposing behavior keys. Existing
snapshot/projection ownership remains unchanged. Creator portrait choices use
their authored labels and spell/feature choices use descriptors; visible
appearance controls no longer print `NakedBody`/`Head17` implementation values.
This is source review, not a claim that every supported-size visual has been
inspected or approved.

### Findings repaired during this checkpoint

1. **Recorded dice hidden by default.** Switching wording to native detailed
   text alone did not satisfy the new default-visibility rule: an independent
   real repeated-Magic-Missile capture had seven canonical rows but one visible
   parent summary and no visible recorded rolls. `LogView` now starts with no
   collapsed keys; causal rows are open by default and explicit collapse is a
   bounded retained-key preference. Native detailed text is the default, with
   the existing verbosity control choosing native verbose text. The original
   ancestor/outcome admission dates still govern every row. No child wording is
   copied into a parent and no rolls or modifiers are recalculated.

2. **A second creature presentation owner.** The first intake added a
   `CreaturePortraitRecord`/`creature_portraits` table and bypassed native
   descriptor portrait fields. That table and its resolver kind have now been
   removed. Existing beasts/fiends/goblins descriptors carry `portrait_key`;
   the SRD descriptor key already supplied the matching identity. The UI's
   exact content-reference index resolves the actor's native identity and uses
   that descriptor through the ordinary `content_ref` path. Explicit player
   portrait choices keep their existing precedence. No old-creature/name alias
   or reconstructed ContentRef hash is introduced. Current media checks retain
   the 41-body association to native rig references and all three role sizes.

3. **Stale log character coordinates.** The preceding `log_hits_valid` repair
   now has physical SDL evidence: changing the visible hierarchy followed by
   an old text drag/copy within one batch cannot reinterpret character indices;
   a subsequent gesture against freshly drawn text copies the displayed native
   characters. This closes the earlier text-selection extension blocker. The
   source still owns only canonical entry keys and measured layout, with the
   original scroll anchor/clock and no parallel transcript.

The native SELF fix is also sound at its shared owner:
`dnd/actions_functional.py:_execute_bound_action` binds
`target_entity_uuid=entity.uuid` for `TargetType.SELF`, restoring the target that
the former item-use branch supplied before consolidation. The retained item
variant still executes through the same binder; no widget rule or second
item-use implementation was added. Full affected engine files cover the six
pack-use regressions, including activation, charge use and rejected replacement
preserving the existing condition owner.

### Completed independent evidence

- Complete `tests/engine/test_roster_ability_batch.py`,
  `tests/engine/test_spellcasting.py` and the then-current
  `tests/game/test_ui_media.py`: **99 passed in 22.35s**. This verifies the SELF
  repair and completed item-effect schema, including Ember Quiver/weapon-coat
  snapshots. The portrait-owner repair subsequently received the next rerun.
- Complete current `tests/game/test_ui_combat_log.py`,
  `tests/game/test_ui_media.py` and the physical batched log selection/copy case
  from `tests/game/test_ui_input_acceptance.py`: **20 passed in 35.24s**.
  This includes default-visible native child rolls, descriptor-owned creature
  portraits, measured selection/scrollbar behavior and the repaired real SDL
  interaction. These overlapping commands are not a combined unique total.
- All **123 installed creature portrait PNGs** were independently compared by
  SHA-256 with the delivered `creature-portraits-runtime.zip`; every file is
  byte-identical. All **41 delivered content identities** also match their exact
  manifest-named native rig and each selected role resource path. This verifies
  unchanged intake and associations, not human aesthetic approval.

No remaining source blocker was found within this checkpoint. At review time,
documentation still needs two exact reconciliations: the main plan's
"While selecting: persistent prompt" paragraph conflicts with the strict ban
on targeting instructions, and the log study's default-collapsed Magic Missile
text/acceptance row conflicts with the now-required default-open rows. These
obsolete instructions must not govern later work. Overall encounter, replay,
historical-disclosure and visual completion are not approved by this receipt.

## Final bounded input/font follow-up — October 6

**Approved within this follow-up's scope.** The main plan's targeting paragraph
now specifies a small native action title/allocation count, with explanations
in descriptions/tooltips. The log study now specifies default-open canonical
children, retaining exact ancestor/outcome timing. Both documentation follow-ups
above are closed.

`draw_panels` now exports the actual painted inventory detail rectangle through
`UIFrame`; `draw_hud` carries it unchanged and wheel input tests that rectangle.
It no longer estimates this region from the creator/modal centre or unrelated
blocked HUD rectangles. The scroll maximum remains the existing measured
content maximum and the current selected item's offset remains passive UI
state. No item ownership or mechanical operation occurs during scrolling.

One source defect found in this follow-up was repaired immediately: a log left
open before entering inventory remained eligible for wheel input while hidden.
At 1280×720 and 150% UI scale, an independent geometry check measured a
205×195-pixel overlap between visible inventory details and the hidden log's
rectangle. The log branch consumed wheel events there before the precise detail
region could handle them. Its condition now additionally requires
`focus_ui.panel is None`, matching actual log draw visibility. The visible
inventory region therefore receives these gestures. The source repair is
bounded to that condition; it adds no new input router.

The font change preserves live antialiased text and the same measured wrapping,
selection regions and canonical native text slicing. The family list resolves
to the available system face (FreeSans on this review host); no bundled artwork,
text-to-image copy or log formatting authority was added. Independent glyph
metrics confirmed `→`, `−`, `×`, `✓` and `…` in normal/bold UI faces at effective
scales 0.75, 1, 1.25, 1.5, 2 and 3. This checks glyph availability, not complete
visual acceptance at every resolution.

Independent current-font verification:

`python -m pytest -q tests/game/test_ui_combat_log.py tests/game/test_ui_input_acceptance.py::test_batched_log_expansion_rejects_old_text_coordinates_and_new_drag_copies_displayed_text --tb=short`

**15 passed in 25.48s.** Native recorded dice/modifiers, default-visible causal
rows, reveal gates, rich text, copy/scroll measurement and the real SDL stale-hit
regression continue to pass with the new font. The completed parent run in
`.runtime/ui-study-20261005/ui-final-input-font.log` reports **33 passed in
110.63s**; this is separately attributed evidence, not an additional independent
or unique test total.

The inspected physical-play logs contain an actual Sorcerer `SpellFact`, the
Fighter's two attack roots and accepted command counts, with zero presentation
gaps in the sampled runs. The parent additionally reports rank-two ordered
repeat-fill A/B/A verification; the printed log itself does not include rank or
recipient allocation, so this reviewer does not present those specifics as an
independently reproduced proof. The bounded changes introduce no remaining
source blocker. Full encounter breadth and subjective visual approval remain
outside this follow-up's completion claim.

## Final local source/proof follow-up — October 6

**Bounded source approval; remaining-suite, refreshed visual and typing gates
are open.** No production edits or broad test suites were performed. Reviewed
the current dispatcher extraction, appearance admission, cloud direction,
floating glyphs, movement-log wording and the supplied physical native proofs.

`encounter_play._run.apply_ui_hit` is a local extraction inside the existing
frame/session owner. Press/release focus, drawn-log validity, enabled state and
discovery-generation checks remain at the caller; command dispatch retains the
ready/current-choices/no-existing-command guard. No new controller or widget
mechanics were introduced. Hidden inventory/log wheel routing remains repaired.
Appearance cycling now intersects the existing permitted categories with actual
Idle sheets, using that same admitted list during paint and editing. It does
not introduce new appearance assets or mutable character construction.

The cloud repair in `game/volume_media.py` correctly converts an inverse-rotated
endpoint into a direction by subtracting the inverse-rotated origin. The
projection rotates positions about the map centre, so an endpoint alone is not
a direction. An independent four-camera check produced `(1,1)`, `(1,-1)`,
`(-1,-1)`, `(-1,1)`, exactly matching the former sum of basis vectors. Existing
volume XYZ, ownership, painter depth and clipping remain the inputs. The
completed parent area-scene rerun reports **136 passed in 46.66s** in
`ui-area-scene-repair.log`; this reviewer did not rerun that broad set.

The changed playback assertions no longer compare new NumPy selection fields
using Python tuple equality. The inspected equipment/forced-movement cases
still check destination/blend/evidence, actor/settled state and actual RGBA
equality. They retain their visible playback contract instead of deleting the
pixel comparison to make the suite pass. Selection coverage remains the
separate previously reviewed compositor contract.

`animation_draw._number_blit` now renders fill/stroke with antialiasing at the
selected display font size and performs no bitmap enlargement. Only the anchor
and rise use world projection scale. A bounded independent check through
`number_draw_commands` found identical glyph dimensions and RGBA at all five
supported camera zooms, distinct projected anchors, and unchanged native value
and application identity. No feedback value, outcome or event time is
recomputed by this change.

`StepMovementEvent.generate_combat_log` changes only the separator between
native path count and movement cost from comma to semicolon. This prevents the
existing coordinate recognizer from interpreting those two numbers as a map
location. The projector/sanitizer's permissions remain unchanged. Independent
controlled, fully disclosed and undisclosed-endpoint checks preserve
`step 1/3; 5.0ft` where admitted and continue hiding unseen coordinates.
Complete focused `tests/engine/test_subjective_combat_log_replay.py --tb=short`:
**36 passed in 1.83s**.

### Physical evidence now inspected

The JSON files under `.runtime/player-ui-20261006/physical/` materially improve
the earlier abbreviated console evidence:

- Fighter: exact native `action.attack` and `action.feature.extra_attack` roots
  against the same retained recipient, three accepted commands including the
  reported End Turn, native detailed attack dice/modifier text, no gaps and
  matching latest/historical cursor 326.
- Sorcerer: the captured gestures choose rank two and allocate A/B/A after an
  undo; the actual native spell root retains **A/B/A/A**, proving the remainder
  went to the primary. Four distinct native damage rows retain `1d4+1: 1+1`,
  including repeated A rows, followed by the original observed-total summary.
  Two accepted commands, no gaps and matching latest/historical cursor 528.
- Environment: the captured Alt/world-click sequence has two accepted commands,
  the original Pull Lever action and trap-state log, detailed subsequent native
  attack logs and no gaps. This file has no separate `player_roots` array;
  its typed-root proof is therefore narrower than the other two captures.

These are inspected saved runtime proofs, not a claim that this reviewer
independently repeated those complete physical encounters. Fighter and
environment JSON still contain respectively 12 and 20 old
`Unknown position.0ft` step strings at this review point. They establish the
recorded command behavior but must be refreshed alongside the gallery before
being presented as current movement-log/floating-text visuals.

No remaining source blocker was identified in these bounded repairs. The
remaining game run had not completed, final floating-text gallery refresh was
pending, and root Pyright had no successful current completion (the inspected
latest log ends in an internal analyzer stack). **Typing is not approved** and
no full-suite/visual completion follows from this source receipt.

## Final refreshed evidence and personal visual review — October 6

**Bounded approval of the reviewed UI source and sampled refreshed encounter
visuals. Full regression acceptance remains open.** This follow-up supersedes
the preceding pending-typing and stale encounter-recording notes; it does not
turn sampled visual inspection into exhaustive encounter or resolution coverage.
No production edits, test edits or broad suites were performed.

The completed `.runtime/ui-study-20261005/ui-types-final.log` reports **0 errors,
0 warnings, 0 informations**. The former failed analyzer run is no longer the
typing evidence. The refreshed `physical/fighter.json`, `sorcerer.json` and
`environment.json` each contain **zero** `Unknown position.0ft` strings and zero
presentation gaps. Fighter retains its two exact attack roots and cursor
326/326; Sorcerer retains ordered A/B/A/A recipients and cursor 528/528. Recorded
native movement now retains `step 1/6; 5.0ft` / `step 1/2; 5.0ft` / `step 1/3;
5.0ft` in the corresponding captures. These remain saved runtime proofs, not
independent re-execution of the complete gestures by this reviewer.

Personally opened and inspected these actual image files under
`.runtime/player-ui-20261006/`:

- The three refreshed standard-gallery `cases/{fighter,sorcerer,environment}/poster.png`
  images in `runs/20261006-player-ui-acceptance/`.
- `physical/sorcerer/frame-00180.png`, `00230`, `00260`, `00290`, `00330`, and
  `00470`; `physical/fighter/frame-00180.png`; and
  `physical/environment/frame-00380.png` (each numbered shorthand denotes the
  same `frame-NNNNN.png` naming).
- `screens/sorcerer-classes-2560x1440.png`,
  `resolution/inventory-1920x1080/frame-00001.png`, and
  `resolution/sheet-960x540/frame-00001.png`.

The refreshed encounter samples show one compact touching shortcut row,
unboxed vitals, flat on-demand panels, readable native labels, and targeting
limited to the ability title, count and confirmation controls. The Sorcerer
frame 00290 visibly retains four separate `2 Force` feedback values, including
three at the repeated recipient; their display glyphs are readable. The
inspected source still renders these supplied native values directly with
antialiasing and no bitmap enlargement. Source/anchor ownership is unchanged.
The log samples visibly retain original dice, modifier breakdowns and arrows,
including `1d4+1: 1+1`, attack totals versus AC, and the repaired movement cost.
No replacement narrative, UUID, hash or engine key was visible in these
refreshed encounter samples. The sampled inventory and creator text fits its
quiet background; this is not approval of unseen long descriptions or every
resolution/frame.

One **stale evidence artifact** remains: the 960×540 sheet image visibly shows
`second_wind` and `action_surge`. Its saved modification time precedes the
current `snapshot_player_hud` label repair in `game/session.py`, which emits
`Second Wind` and `Action Surge` through the existing passive resource label.
`_sheet_lines` displays that label directly. This is not an unresolved current
source defect, but that image must be refreshed before representing the complete
resolution set as current or visually approved.

At review time `ui-game-remaining.log` was still incomplete and already contained
**11 failure markers**, without final failure diagnostics or a passing rerun.
It must be completed and its failures reconciled before full regression
approval. The separate `ui-storage-physical.log` showed native Open/Close Chest
and Loot All discovery transitions through stage 8, but no completed
drop/pickup result; the entire storage gesture sequence is therefore still
unapproved by this receipt. These are explicit remaining evidence gates, not
claims of additional source defects without diagnostics.

## Final ownership and storage follow-up — October 6

**No remaining blocker found in the bounded source and evidence reviewed here.**
The full game partition is still running, so this is not final regression or
whole-video approval. This follow-up closes the stale sheet-image finding and
the previously incomplete native storage gesture proof.

The refreshed `resolution/sheet-960x540/frame-00012.png` and
`sheet-2560x1440/frame-00012.png` were personally opened: both show **Second
Wind**, **Action Surge** and **Extra Attacks**. The former underscored labels
are absent. Also inspected the current `inventory-960x540` and `hud-2560x1440`
frame 00012 images. The sampled text is readable, the sheet and inventory use
the existing small flat panels, and the HUD remains one shortcut row with
unboxed vitals. All 15 expected refreshed resolution image files exist; this
receipt personally inspects the four named here and does not claim to have
viewed the other eleven or an entire video.

Rechecked current `encounter_play._run.apply_ui_hit`, command submission and
`receive`, `ui.panels`, `ui.world_interaction`, `ui.media`, `ui_composition`, and
the corresponding Session entry points. Views still consume detached player
facts/discovery, not live actors. Painted hits retain capture/focus/discovery
checks; execution resolves the retained native row and target through Session.
Chest context and ground pickup take the same world-selection path. A pending
approach still requires the exact subject, native template, connector,
ContentRef and variant facets after rediscovery. Neither storage nor the label
repair adds a widget mechanic, synthetic inventory transfer, outcome formatter,
or presentation clock.

Registered content continues to resolve its own `ContentPresentation`; direct
feature/item presentation rows must exactly match current native IDs lacking a
registered descriptor. Creature portraits use the exact descriptor unless the
player explicitly chose a portrait. No second creature catalog or display-name
resolver has returned. The existing canonical log remains the sole wording
source, and standalone appends remain attached to their operation boundary.

The completed saved `physical/storage.json` and `storage-lineages.json` now
contain **900 frames, 5 accepted commands, zero gaps**, and exact native roots
for Open Chest, Loot All, Drop (Handaxe), Pick Up and the turn transition. The
captured inventory gains one distinct Potion of Healing after Loot All; the
same Handaxe UUID disappears after Drop and returns after Pick Up. The driver
posts SDL events and returns no direct action command. Its observation wrapper
reads the actual painted HUD; it does not replace the native transfer. This
review inspects these recorded results rather than claiming an independent
re-execution. Personally inspected storage frames **00080, 00180, 00360 and
00500**; the final sample visibly shows the original native interaction log and
no invented transfer narration. The complete `storage-sequence.json` capture
was not yet present at inspection, so its serialization/portable replay is not
approved by this follow-up.

The inspected `ui-types-all-game.log` and `ui-importer-types-final.log` each
finish with **0 errors, 0 warnings, 0 informations**. The completed affected-file
rerun `ui-movement-temp-fixed.log` reports **41 passed in 38.25s**, closing the
parent-identified eleven failures seen so far in the broad partition. The
reviewed test repairs preserve RGBA/destination/blend/evidence comparisons while
excluding new ndarray mask fields from Python tuple equality, and select the
actual Constitution variant for the temporary-HP fixture. They do not weaken
native HP ownership or movement pixel assertions. The broad partition still
has no final completion summary; any additional failure and the final suite
denominator must be reconciled in the forthcoming feature trace/report.

## SELF binding, complete packets and encounter completion — October 6

**Bounded approval; no new source blocker found.** Final full-regression
approval remains reserved until the running partition and its affected reruns
are reconciled. No production or test edits were made by this reviewer.

`dnd.actions_functional._execute_bound_action` now binds the actor as the
explicit SELF recipient only when `template.source_item_uuid` is present.
This preserves the item-use convention lost during consolidation, while
ordinary SELF declarations keep their original source-only binding and native
resolver. In particular, Thaumaturgy again records no target/application rather
than acquiring an artificial self-target. This is a narrow repair of the shared
binding path; it introduces no spell-name branch or UI executor.

The Shield of Faith test expectation now matches the existing authored source:
`git show HEAD:game/data/support_spells/spell-studio-drafts.json` already has
83.33333333333326 ms contact delay and both halves use the contact clock. The
test still checks registration, duration, scale, depth, attachment and absence
of damage/projectile/area. No artwork was changed to make this check pass.
Independent focused pytest selection across `test_support_replay.py`,
`test_support_media_import.py` and `test_player_selection_contract.py`:
**6 passed, 29 deselected in 15.59s**, covering both Thaumaturgy observers, both
Shield of Faith observers, authored media registration and exact source-item
variant execution. The separately inspected parent `ui-self-source-final2.log`
reports **117 passed in 31.09s**; these are overlapping evidence, not additive
coverage totals.

All five `physical/{fighter,sorcerer,environment,storage,completion}-sequence.json`
files are now present as **schema-2 `PlayerSequence` packets**, retaining native
projected facts and wording. An independent value check encoded each packet,
validated equality after decoding, reduced every lineage, and checked the HUD
snapshot generation/observer ownership. Final reducer cursors were respectively
**326, 528, 543, 308 and 459**; HUD snapshot counts were **13, 11, 15, 17 and 8**.
All five physical captures have zero standalone appends, so these particular
files do not add coverage to the separately reviewed immunity-append tests.
The capture observer's own completed save checks compare reduced final HP and
position against the live captured result; this reviewer independently also
compared completion HP/life state with `completion.json`. This closes the
previously absent storage packet gate. It does not claim a whole-world resume
format or a new replay UI.

The completion recording uses ordinary `random.seed(0)` with the normal native
encounter and contains no fixed-dice context or HP edits. Its **two accepted
player commands are walking and a main-hand attack**. The Fighter's other kill
is an automatic native opportunity attack within the enemy movement lineage;
the final report must not describe two player attack clicks. Reduction gives
Fighter **41 HP/alive**, Goblin 1 **−4 HP/dead**, Goblin 2 **−5 HP/dead**, matching
the captured final result. `encounter_ended` is true and gaps are empty.

Personally inspected the standard gallery's current completion/storage posters
and completion frames **00330** and **00383**. The latter show the settled
"Encounter complete · You survived" state, both enemy bodies, one compact
shortcut row and readable vitals; the storage poster shows the canonical native
Open Chest/Loot All/Drop/Pick Up wording. The standard gallery now has five
cases. These remain sampled images: no claim is made to have watched all five
videos or all 1,200 completion frames. At this receipt the broad game log still
had no completed pytest summary; that final acceptance gate remains open.

## Final implementation and regression acceptance — October 6

**Approved for the documented player-UI scope. No unresolved anti-slop blocker
remains.** The completed
[implementation report](PLAYER_UI_IMPLEMENTATION_2026-10-06.md) now reconciles
the regression evidence and states the native/content limits without presenting
them as delivered features. This closes the earlier pending full-partition gate.
This reviewer made no production edits and did not rerun the broad suites.

Independently reconstructed the game denominator from the actual collected
node-ID logs, rather than adding successful rerun totals:

- Original collection: **3,694 distinct identities**.
- Completed original prefix: **1,610** cases, with **1,514 passed / 96 failed**.
- Completed remainder: **2,086** cases, with **2,050 passed / 36 failed**.
- Prefix and remainder intersect in **two** identities. Their union is exactly
  the original 3,694, with no missing original identity.
- Current collection is **3,695**; its only addition is
  `test_floating_text_keeps_display_glyphs_when_the_world_is_zoomed`, covered by
  the final feedback/input evidence. No original test identity was removed.

The 96 prefix and 36 remainder failed-ID sets are disjoint. Their exact union
matches all **132** rows in the private `ui-acceptance-evidence.json` closure
map, with no missing or surplus identity. Reviewed the designated rerun logs:
90 area/scene cases map to the 136-pass rerun; six draw-command comparisons to
the 29-pass rerun; eleven movement/placement/temporary-HP cases to the 41-pass
rerun; fifteen condition-fact variants to the passing facts file in the
60-pass/five-failure intermediate run; six condition-rendering cases to its
completed 36-pass rerun; three support/SELF cases to the 117-pass rerun; and the
UI resource assertion to its five-pass rerun. All five intermediate remaining
failures were in condition rendering and are closed by the later complete-file
run. No mapped identity remains failed in its designated closing run.

The separate native broad log finishes **3,031 passed / seven failed**. Its seven
failures are confined to six roster/item-owner cases and the known-depleted-slot
expectation in spellcasting, matching the complete affected-file 125-pass run
and final 117-pass SELF refinement. Earlier source reviews and the independent
six-case follow-up establish why these repairs preserve native ownership. The
report does not treat an intermediate failure as a final pass or discard it as
unrelated.

Verified final `ui-last-input-recheck.log`: **32 passed in 97.97s**. Verified
`ui-types-last.log`: **0 errors, 0 warnings, 0 informations** for the reported
game/action-adapter/importer scope. An independent `git diff --check` returned
success (only the repository's CRLF conversion notices). The report correctly
calls this partitioned coverage with failure closure, **not** one uninterrupted
all-green run against frozen source. Overlapping subsets are not added into an
inflated total.

The implementation/acceptance matrix remains consistent with the source,
five independently checked packets and personally sampled images documented
above: native Session execution, passive UI facts, exact media ownership,
shared physical picking, original recorded log wording, and no duplicate rule
or narrative system. Completion correctly distinguishes the clicked Move and
Attack from the native automatic opportunity-attack kill. The report explicitly
does not claim exhaustive visual inspection, physical Windows fullscreen tests,
ground-consumable appearances, flawless anonymous Bloodied wording, or live
save/load. Those disclosed limits remain real; this acceptance does not erase
them or authorize a separate implementation task.

Reviewed report SHA-256:
`d71c9d8db6528f816dafb483ca5d965a15665c0dda4e33c2813500bd9da69266`.
