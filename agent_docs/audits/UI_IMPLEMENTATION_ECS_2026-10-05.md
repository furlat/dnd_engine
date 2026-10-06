# Player UI implementation: independent ECS/import-DAG review

2026-10-05. Scope: approved PLAYER_UI_PLAN_2026-10-05.md. Reviewer: schema_fit_antislop. This receipt tracks actual implementation checkpoints separately from the previously approved design. No production edits by reviewer.

## Status

**Baseline source review complete; implementation approval pending.** No new implementation checkpoint or tests have been certified here. The intended exit is a playable native encounter with selected Fighter/Sorcerer builds and the complete approved UI, not a screenshot-only HUD. Whole-map persistence and separate narrative remain out of scope.

## Baseline hazards and required invariants

| Native/application owner inspected | Concrete hazard | Required implementation boundary / proof |
| --- | --- | --- |
| `game/session.py:_current_player` | Inspection selection could accidentally become command control | Preserve ACTIVE encounter, IN_PROGRESS turn, session human membership, exact current actor and HumanController checks for commands, equip/unequip and toggles. Two player members may be inspected without submitting for the noncurrent actor. |
| `discover_player_actions`, AvailableActionInfo private execution_template | Detached UI copy loses executable configured template; executing it can fall back to token resolution | Keep original result in Session/application-owned discovery snapshot. Detached generation+row/target handles resolve only against that retained original. Reject stale generation/actor/discovery revision before invocation. No live template reaches widget state/serialization. |
| `dnd/actions_functional.py:execute_available_action` | Reimplementing executor could break item-source adaptation or selected extras | Preserve current native dispatch and explicit source UUID. Non-item rows use retained template; native item-use path currently performs its own source-owned lookup. Do not claim UI detachment changes that path or replace it with a new spell factory. |
| `_validated_extra_target_uuids` | Sets used for UI badges could erase A/B/A order; flattened target indexing loses secondary options | Native sequence order remains authoritative. Primary-dependent secondary pool and `None` versus empty pool differ. Confirmation preview uses pure shared native selection predicates; no effect/cost validators during hover. |
| `get_extra_position_options` | Entity destination and wall/path inputs bind differently | Pass exact retained row, selected primary and ordered extra positions. Do not derive from display labels or apply arbitrary template-name parsing in UI. |
| `game/encounter_play.py` current ready/receive loop | Current Space pauses before selector; current Escape quits; duplicated input handlers can run two commands | Replace, do not layer, the legacy menu input. One event consumed once; Space neutral End Turn, Enter confirmation. Preserve independent native intake and retained historical presentation; user commands wait for the displayed settled human boundary. |
| `Session._operation` | Post-action death checks or independent roots can be omitted by UI wrappers | Native wrapper captures start before execution and end after required postchecks. Return all actual terminal roots, including cancellations; no synthetic parent event or visual-duration scheduling in Session. |
| standalone combat-log listener | Unregistered immunity entry absent from queue; naive new listener duplicates normal logs | Capture only existing standalone marker, project at original observer boundary, preserve encounter-log index. Carry optional appends on existing packet/operation owners with conservative completion gate. Remove listener on close and reset generation-owned buffer. |
| `game/player_projection.py:_public_actor` | Party inspection could expose enemy holdings or merge party fog | Current controlled_items policy is observer-specific. Add bounded authorized sheet/resource snapshots with explicit member check. Keep map/log observer and historical snapshots independent from inspected actor. Initiative excludes hidden slots/counts. |
| `dnd/core/gridmap.py:manual_object_contact/attack_object_contact` | UI “adjacent” approximation ignores footprint/boundary/elevation/access | Forward optional hypothetical origin through existing native contact; filter exact native Move candidates. Contact geometry is explicitly not disclosure authorization. Remote operation descriptor remains non-executable until fresh admission at arrival. |
| `create_session` | Existing function resets runtime and creates two hardcoded premades; creator preview can destroy live encounter | Keep all draft/resolver work outside live composition. Selected build tuple composes only at intentional start; no reset on hover/appearance choice. Preserve existing births, native controllers, deployment and summoning binding. |
| `DrawCommand`/existing boundary, fixture, terrain/depth transforms | Parallel hit-testing could pick hidden actors or aura/shadow pixels | Carry physical selection coverage through same actual cuts/painter order. Raster coverage is Pygame-local. Empty window aperture traversal is a separate affordance, not enlarged attack hitbox. Noneligible opaque foreground still blocks ordinary hit. |
| character creation/progression | UI grant duplication or invented progression policy | Expand starting package to explicit item_loadout once; current class choice does not independently install gear. Use existing pure resolvers and sole native birth. Pre-encounter chosen level is supported; no invented earned XP/free respec/save format. |

## Import and ownership gate for every checkpoint

- Native dnd owners import passive native contracts only, never game/UI.
- Session/application holds live objects and exact command templates; view modules take passive permitted data and return intents.
- Existing `controls.py` remains one selection reducer, not a second backend state machine.
- Shared geometry is downstream of actual rendering transforms; no independent world visibility/pathfinding in widgets.
- Resources/abilities are evaluated by native owners and captured as data. Existing HP/item facts are reused, not duplicated in a new sheet truth.
- Exact descriptor/direct presentation records provide icons; no display-name/fuzzy fallback registry or fabricated ContentRefs.
- No generic event bus/service locator, reflection/import cycles, global widget callbacks or per-spell UI executors.

## Evidence required before checkpoint approval

Review actual source diff plus reported command/results; independently inspect consequential tests where relevant. Initial gates include detached payload round-trip with no private templates, stale handle rejection, exact variant/source item execution, two-member control/disclosure separation, native prefix preview purity and registration of connector traversal. Later gates include post-cut picking, native approach interruption, historical resource/log timing, standalone append replay, and final real Pygame interaction screenshots/recordings. A passing narrow test does not certify unimplemented plan lanes.

## Checkpoints

- Baseline: reviewed source; no approval of implementation yet.

## Native contract checkpoint — active source reviewed

**Not yet approved for dependent UI.** Reviewed current changes to native discovery/selection, Session, HUD value records, reduction and replay. No tests run by this reviewer; parent reports prior Session passes and ongoing focused run. Remote approach, loop HUD attachment and append packet tests are acknowledged unfinished work, not unexpected regressions.

### Findings requiring correction

1. **Preview exposes mutable retained target objects.** `preview_available_selection` returns `next_targets` directly from original `valid_targets`/`secondary_targets`; `preview_player_selection` caches and returns it without detaching. Frozen AvailableSelectionPreview only freezes its fields, not mutable AvailableTarget descendants. A view can therefore mutate the native retained discovery through its preview. Normalize the preview at the application boundary and test mutation of preview target/path cannot alter original discovery.
2. **Execution trusts mutable detached target payload.** `execute_player_action` resolves original action but checks target membership against the detached action and forwards that detached target. Editing its position/path changes a target that still passes that membership check. Resolve the selected exact target handle/index against retained original targets and use that original target for command binding. Apply the same mapping to positional/selection queries; cached prefixes must not hide invalid changed payloads. Ordered secondary UUID membership still belongs to native validation.
3. **HUD identity/revision guards are incomplete.** `reduce_initialization` assigns hud_snapshot without generation/observer validation. `reduce_lineage` validates identity but accepts a snapshot revision after lineage.end_cursor (or earlier than an already installed HUD revision). Reject incompatible identity/future revision before mutating reduction state; prevent regressing HUD revision. This matters because snapshots are operation-end facts and may postdate individual captured roots. Attach only at the actual completed operation boundary, not the first root.
4. **No-event preference mutation leaves discovery cache admissible.** `toggle_player_handler` changes enabled state through a method that emits no EventQueue event. It neither checks original discovery cursor/generation nor invalidates cached discovery/previews. The existing `_retained_row` cursor comparison therefore still accepts the pre-toggle epoch. Centralize invalidation on application mutation even when no mechanical event is produced; preserve native no-event semantics rather than inventing an event. Verify old row rejected and fresh handler state exposed.

### Bounded gaps to close before their consumers

- `snapshot_player_hud` uses base action maximum (`get_base_value`) but evaluated current actions. Capacity-changing effects such as Action Surge can yield current greater than displayed maximum. Spell slots similarly combine evaluated current with normal-only capacity, ignoring temporary slot capacity. Publish correctly named/evaluated native pool values, with normal/temporary/restricted ownership explicit where needed; do not display a guessed fraction. Existing named resources already preserve restricted pools as separate keys, but limitations/allowed kinds are not yet in this snapshot.
- HUD is presently Operation data and optional PlayerLineage/Initialization data, but native RecordedSequence has no corresponding retained HUD route and project_lineage does not attach it. The announced loop/packet work must preserve exact operation revision and observer. Empty-operation updates, e.g. preference toggle, need an explicit settled display path without inventing a lineage.
- Observer is currently fixed to `session.player_uuids[0]` in HUD and standalone capture. This matches the existing single-observer encounter presentation; retain that deliberate policy. Inspecting the second human may show its authorized own sheet without replacing observer identity or combining fog/log history.
- Registered traversal and variant/count hooks need native execute tests beyond discovery presence. Temporary slot availability and item-sourced variant identity need source-owned execution coverage; a six-mode menu alone proves neither exact costs nor chosen effects.

### Accepted source direction

Passive ActionAffordance/ActionVariantFacet and selection-result values remain in native contracts; no dnd→game import introduced by inspected files. Generic preview avoids arbitrary `_validate` and uses shallow bound copies plus concrete read-only wall/telekinesis/DimensionDoor/pair predicates. Acid Splash reuses the same pair predicate in final validation. Native template and item-source dispatch remain the command owners. Custom builds are validated before runtime reset and composed through existing create_character. Standalone log capture uses existing listener, detaches projected entries and unregisters on close; no synthetic mechanical event added. These good boundaries do not clear the findings above.

### Native checkpoint recheck

Source recheck confirms findings1/2/4 repaired: original rows resolve by discovery generation/index; targets resolve from original index pool; cached previews are normalized and freshly detached on return; handler toggles check current discovery cursor and invalidate it after no-event mutation. The added target-tampering test verifies native movement follows original admitted position rather than edited detached path. Pure preview tests cover repeats, over-allocation and compound selection without cursor/RNG/resource mutation. Approach→fresh traversal test uses actual native Move and exact connector UUID.

HUD observer/generation/future-boundary validation now exists on initialization and lineage, and branch extraction explicitly removes operation-wide HUD. Optional native/player packet HUD collections preserve operation snapshots without forcing them into a fabricated lineage. Capacity now evaluates the existing native value channel excluding its existing cost modifiers; movement includes Dash. Item source uses retained variant with source-item/source-actor validation and the shared existing bound executor. Standalone capture now receives native event-time evidence. These corrections preserve the approved DAG/ECS boundary.

Two bounded source follow-ups sent to root before closing this checkpoint:

- Later lineage currently accepts HUD revision older than the HUD already installed. Reject decreasing revision (equal is legitimate for no-event operations), to prevent historical resource regression.
- `player_position_options` still checks detached `action.position_selection` for its early return; use original retained row metadata consistently. This does not let the client execute new geometry, but edited detached metadata can wrongly suppress valid options.

Remaining loop operation-completion gates, HUD packet application, widget integration and final runtime acceptance are still pending by design. This review is not approval of those unimplemented consumers. Reviewer inspected tests/source; parent owns current test execution and exact result recording.

### Native checkpoint source approval

Confirmed final corrections in settled source: reduce_lineage rejects a decreasing HUD revision and permits equal revisions; player_position_options reads original retained position metadata. Branch extraction keeps exact selected node/version/observation/world-update filtering and clears operation-wide HUD, preserving its ownership outside a partial branch. Reviewed added two-recipient Beacon of Hope/Divine Word tests asserting native recipient events and one action/bonus-action plus one slot cost.

**Native contract checkpoint approved from ECS/import-DAG and ownership source review.** Parent's61-case run was still completing when this receipt was written; this does not assert its result. HUD loop attachment, operation-level display timing, interactive UI and whole-plan playable/visual acceptance remain separate pending steps. No production edits or independent test execution by this reviewer.

## Stage2 compositor/media review — 2026-10-06

Native follow-up: runtime-generation and actor-UUID handles are checked alongside discovery epoch/index; Stone width is a typed facet of its existing selected variant. Approved as bounded ownership metadata. Parent reports66 native tests passed in24.82s; reviewer inspected source, did not rerun them.

Stage2 source inspection accepts the dependency direction: interaction_types contains passive frame-local data; DrawCommand references those values; interaction_frame performs Pygame/NumPy raster operations and never imports native entities/commands. WorldHit carries semantic identity/support only. SceneFrameResult separates evidence from interaction output. Boundary/fixture partition helpers carry mask cuts/crops, rather than rerunning rule visibility. Actor physical-only sampling preserves pose transforms/registration and excludes overlays/markers/shadow. Object selection reuses registered geometry and separates aperture from attack mask. Native command admission is not moved into renderer.

**One compositor blocker:** `fixture_depth.partition_world_depth` now includes selection-only coverage in `extent`, but its non-ordered branch still computes `depth[selected].mean()`. A depth band containing only a transparent aperture/selection region can have nonempty extent and zero visual `selected` pixels, yielding NaN painter key. Give selection-only bands a finite deterministic position within the already chosen depth band; preserve current visual-pixel ordering. Add the exact transparent selection-only partition case alongside real-camera tests.

Remaining acceptance (not alleged source defects): actual four-camera actor/window/overlap selection; final .evidence call-site compatibility; opacity/clipping and registered aperture identity; UI opt-in frame integration and performance. No whole-stage visual acceptance yet. No production edits by reviewer.

### Stage2 final source recheck / approval

**Stage2 compositor/media checkpoint approved for ECS/import-DAG and source ownership.** The transparent selection-only band now uses finite extent depth when visual selected pixels are absent, closing the reported blocker. Actual visual bands retain their existing pixel-mean ordering.

Inspected latest ground/support coverage, final volume/area mask cuts, merged construction section selection and UI media resolver. Ground regions originate in drawn terrain/stairs/water support pixels; pick_world prioritizes visible body/object, then an admitted aperture, then actual ground. No alternate live-map pathfinding or unrestricted pick_support fallback is introduced. Merged generic walls retain per-component regions; merged force surfaces derive each original identity from genuine shared volume XYZ, rather than assigning the whole merged image to one native object. Extracted volume_world_coordinates preserves the existing projection arithmetic; selection introduces no new effect timing/visibility rule.

`game/ui/media.py` receives passive ContentPresentation mappings and existing AssetSpec/ImageResourceSource registrations. Explicit reference kinds select one authored/descriptor owner; no live runtime registry or new mechanical feature registry is imported. Image cache is bounded192 entries. Authored direct item/feature/portrait records are presentation data only. DrawCommand imports passive interaction types, while the compositor consumes DrawCommand; no circular dependency or late-import workaround found in inspected files.

Parent reports11 interaction tests passed in26.33s. Reviewer read the real native window-crawl4camera test (interaction enabled/disabled pixel equality), transparent aperture sorting test, physical overlay/shadow and fully faded body cases, generic merged-corner and Force section cases. Reviewer did not independently rerun them. SceneFrameResult `.evidence` migration is explicit in changed call sites; broader downstream suite remains part of integration acceptance.

This approval is limited to current stage2 source and reported focused evidence. HUD input/selection integration, all gallery acceptance cases, performance and final playable encounter remain pending. No production edits by reviewer.

## Stages3–5 source checkpoint: input/views/projected log

Reviewed current game/ui records, action families/variant/library/inventory views, world interaction helpers, encounter_play Session dispatch and current combat_log/rich_text implementation. Root reports22 native input tests passing; this reviewer did not execute them. Canonical log implementation/tests are still actively being completed, so this is not final stage approval.

### Concrete blocker before world-input acceptance

`game/ui/world_interaction.py:approach_action` filters `target.is_path_hazardous` and ranks `path_cost`, while native movement execution prefers an affordable `safe_path` and its cost. Thus a target with hazardous shortest path and legal safe alternative is incorrectly rejected; route/cost selection can disagree with the route executed. The helper also combines every `action.move` row, so walking/flying can silently substitute. `move_to` likewise returns the first matching movement row. The reviewed contract requires exact locomotion choice and native route preference. Reuse/project the native route choice for the exact selected row; no client pathfinding or duplicated route policy.

### Boundaries accepted in inspected source

- UIHit, UIFocus, pending intent, variant and family records contain passive values; actual live ownership remains Session. Inventory/equipment/reaction clicks emit typed intents; encounter_play dispatches native gated functions. No widget imports live Entity/Encounter or changes item slots/rules.
- Families retain native indices and source-item/configuration/weapon slot. Variant selectors choose an exact existing row instead of reconstructing spell instances. Library excludes world-surface rows. Costs/reasons are formatted native data rather than recalculated affordability.
- Pending use stores actor/object/exact operation metadata and rediscovery matches template/configured ref/facets/connector before submitting. Existing current-human gate remains authoritative. This is one pending intent, not an engine macro scheduler.
- HUD operation snapshots are withheld until playback queue settles; no live HP refresh inside draw functions. Still require final tests for several queued operations/no-visible-group updates and second-human inspection to establish intended conservative timing in the integrated loop.
- Combat-log rows reuse PlayerNode.combat_log and exact generation/observer/event identity. No recursive sub_entries duplication or newly generated outcome text. Native turn_execution_id is copied, and lifecycle timings are direct existing cue start exports. Standalone appends retain their separate identity and conservative operation-completion gate.
- Log reveal indexing consumes shared milestones/dependencies and offsets; it does not modify native timelines. Exact logged-ancestor grouping, bounded10k rows/512 layouts, projected UUID chips and literal unknown markup preserve intended ownership. A log panel is not a second mechanical scheduler.

### Pending evidence, not new scope

Canonical log acceptance needs real multi-hit/multi-target/cancel/reaction/standalone replay timing cases, hidden/same-name participant tests, scroll/resize/filter/copy behavior and actual readable capture. Reaction grouping and parent aggregate floors should be checked against these producers, not certified solely by source inspection. Current UI stage does not certify creation/progression or final playable encounter. No production edits by reviewer.

### Stages3–5 bounded movement/log recheck

The reported movement-source blocker is closed. `base_actions.prefers_safe_movement_path` is a leaf function over the existing detached AvailableTarget and movement budget. Native `_disclosed_movement_path` and UI approach selection use that same affordable-safe-route predicate. Approach hazard admission and cost ranking now follow the selected disclosed route; no UI pathfinding was added. `approach_action` and `move_to` both select the exact authored movement facet, defaulting to WALKING; they cannot silently substitute the flying variant. Explicit flight remains a separate native variant choice. This is shared existing policy, not a second movement system.

Canonical log source preserves projected wording and exact event identity, consumes existing bound milestones/dependencies, and leaves native clocks untouched. Repeated equal text with distinct event UUIDs remains distinct. Standalone append identity and its conservative operation-end gate remain separate from lineage event identity. Parent/child grouping, independently early reactions, and eviction promotion operate on display rows rather than producing another combat event or inferring gameplay.

Verified the recorded focused result at `.runtime/ui-study-20261005/ui-log-tests2.log`: **9 passed in 8.81s**. Reviewed tests include native repeated Magic Missile, Counterspell outcomes, condition and opportunity-movement packets, exact native row counts/wording, repeated-packet idempotence, parent/reaction visibility, 10k retention, rich-text handling, scroll anchoring and resize. These tests support the bounded implementation; they do not individually prove every possible reaction timing or hidden-identity presentation case. This reviewer did not rerun the suite.

**Reviewed movement repair and current canonical-log ownership approved from ECS/import-DAG source inspection.** No blocker remains in these bounded changes. Neutral-hover/path visualization is still being implemented and is not covered by this approval. Integrated operation-queue HUD timing, full creation/progression, final visual captures and complete playable acceptance remain later evidence obligations; this receipt does not approve the entire player-UI plan prematurely. No production edits by reviewer.

## Creator boundary source review — 2026-10-06

**One startup blocker:** `game.__main__.main` invokes the creator for a normal `--encounter encounter.storehouse_demo` or `encounter.residue_workshop` launch, then passes the selected builds together with that encounter ID. `create_session` explicitly rejects this combination before reset (`Custom party deployment requires the skirmish encounter`). Thus pressing Start on this supported launch path crashes. Preserve authored encounter ownership by bypassing the custom-party creator for these launches, or explain the limitation before editing; no new party-deployment mechanism is required for this fix.

Cold draft boundaries otherwise pass this bounded source inspection. CharacterDraft/ChoiceEdit are frozen passive records; edits use dataclass replacement of the existing CharacterBuild. Resolver calls validate without creating Entity or clearing the runtime. Cancel abandons the draft and leaves the party tuple untouched. Deployment performs native resolution before reset and invokes existing create_character only after confirmation. Appearance preview uses appearance configuration and existing modular composition, not a temporary live combatant.

Class and origin choice requirements were factored into their existing cold definition owners and are consumed by native resolvers as well as the view. Optional spell replacement is now explicit metadata; native order/cardinality/spell legality still governs acceptance. `next_class_level` constructs an uncommitted supported-class row and cannot bypass the resolver. No dnd-to-game edge, late import or new rules registry found in these changes.

Starting gear expansion replaces the draft item_loadout with the exact selected native package plus background package only on relevant authoring edits. Neither paint nor deployment expands it again; existing prepare_character constructs each explicit loadout entry once and installs that tuple. Premade edits retain their explicit existing loadout until the user changes a package/background. No character-only save format was introduced.

Minor usability follow-up: the Sorcerer replacement picker exposes an ordered pair as a generic 'choose 2' list. The native rule assigns different roles to the first and second values; label the remove/learn order (and preferably selected order) so the player need not diagnose repeated resolver rejection by guessing. This is presentation guidance, not a request for duplicated spell eligibility rules.

Verified recorded creator run: `.runtime/ui-study-20261005/ui-creator.log` contains **6 passed in 11.36s**. Read those tests (three native-valid cold level-one drafts, package/point-buy edits, all page composition/appearance, physical Cancel→Start). Parent reports 201 progression checks passing; reviewer did not independently run these suites. Final creator approval awaits the startup correction; full playable/visual acceptance remains separate.

### Creator bounded recheck / source approval

Confirmed `use_creator` now excludes authored `--encounter` launches; those pass no custom builds and retain native authored roster composition. Cancel only exits when the creator was actually invoked. The startup blocker is closed without expanding deployment rules.

Existing ClassChoiceDefinition now supplies passive selection_labels for the ordered replacement pair. ChoiceEdit copies that metadata and the picker displays each role with its current selected value. Native validation/order remains unchanged, resolving the reported guidance issue without a UI spell-rule table.

**Creator boundary approved from bounded ECS/import-DAG source review.** This approval covers the two corrections and previously reviewed cold composition; it does not cover adjacent path-preview/inventory-scroll additions or assert final stage6 physical deployment, captures, progression interaction and whole-player-UI acceptance. No production edits or additional test execution by reviewer.

## Portrait intake and disclosed preview bounded review

Portrait source path is a developer-only import boundary. It preserves the complete delivery archive, rejects replacement of the preserved archive with different bytes, preserves/extracts originals, checks supplied image hashes and actual RGBA dimensions, and checks existing original-source hash before binding. Runtime selection is restricted to collection `existing-cie`, matched by the exact old resource file address. Original registrations are retained; role registrations are additive. Current public ui_media data contains exactly 168 role registrations plus 56 original portrait registrations, with native sizes36×48,48×64,96×128. Existing private production/local installation manifests are updated; no recipe, gameplay property or abandoned HUD repaint is selected. No new runtime registry/DAG reversal found.

The UI media consumer selects explicit initiative/hud/sheet roles through the existing catalog and uses integer nearest-neighbor scaling for those native sizes. Cache keys remain actual registered asset identity plus effective size. This preserves the requested pixels rather than regenerating/tinting portraits. Source approval is limited to this intake/consumer boundary; actual pixels and layout require the planned physical review.

Small layout risk to verify in that review: resource_image intentionally floors its multiplier at1, so at supported UI scale0.75 an initiative slot's requested31×36 interior receives the native36×48 portrait. The current initiative slot is about38×48 and places the image below a3px inset, extending past its bottom. Preserve native pixels but give the frame/hit geometry enough room (or explicitly clip to an authored viewport); do not hide this by smooth resizing. Sheet layout already advances by actual portrait width.

Disclosed movement preview source uses the same native safe-route predicate, path/cost and opportunity-exposure fields as execution. It draws only stretches with received visible terrain support; no route solving, threat eligibility or hidden elevation lookup is introduced. Neutral ground hover resolves the exact walking selection; object approach uses the existing admitted operation helper. Confirmed this remains passive rendering over discovery, not a second path authority.

Legacy controls removal is not yet present in the inspected source: old draw_menu/handle_menu_event and related menu helpers still exist in game/controls.py. Their planned deletion has no receipt here yet. No production edits or independent test run performed.

### Legacy controls / preview / layout recheck

Confirmed legacy menu drawing and event-handler implementation has been removed from game/controls.py. Remaining functions are passive intent records, target-value lookup, prefix append/undo and confirm against native AvailableSelectionPreview. No legacy execution adapter or replacement rule engine remains; repository search found no remaining old menu-function callers in game/tests/game.

Generic preview uses native effective_target_uuids for allocation counts and explicit selected ordered points for the connective graphic. Movement stays on the previously reviewed disclosed path/cost/exposure consumer. Selection paint neither validates geometry nor changes native allocation.

Portrait frame now derives dimensions from integer native36×48 pixels plus scaled margins. Its draw and hit rectangle share that frame; the previously noted0.75scale underallocation is closed. Sheet text rectangle now reduces width as its left edge advances by actual portrait width, avoiding right-side overflow.

UIFrame.detail_scroll_max is optional measured layout feedback from inventory wrapping/control count. The main loop clamps only UIFocus.item_detail_scroll; no live entity, command, native cost, historical event or discovery state is modified. This is ordinary layout ownership, not a domain event channel. Reviewed changed source boundaries approved; parent’s affected test run remains in progress, and this receipt makes no whole-plan physical acceptance claim. No production edits by reviewer.

### Final bounded source/receipt pass (acceptance still running)

Rechecked current portrait role intake, passive selection-only controls and log input validity additions. Log wheel/filter/detail/follow/expansion changes invalidate the painted hit map; pointer operations requiring old log text/row geometry are rejected until a new draw establishes valid hits. This is presentation input freshness, separate from Session’s native command generation gate. It introduces neither gameplay state nor another timeline. `capture_every` is validated positive by the public run entry and affects screenshot output cadence only, preserving simulation/frame progression.

Parent reports117 affected checks passed and scoped views/creator/importer typing clean; broader boundary/engine/game checks and physical SDL batching acceptance were still running at this receipt. No additional source blocker found in the bounded additions. No final whole-plan acceptance claim is made before those results/captures.

Inspected encounter_play’s changed loop for an identifiable cause of the reported Pyright stall. It has a large branch-heavy async function with nested closures and many reassigned narrowed optional presentation records, but source inspection alone does not establish which expression causes the checker’s CPU stall. No concrete typing defect or runtime error can responsibly be inferred from the stall. Keep the unresolved single-file typing result explicit; do not describe all game typing as passed or introduce an unrequested broad loop refactor solely on this speculation. No production edits or independent checker execution by reviewer.

### Quiet UI / human labels / default dice review

Two concrete mismatches reported to root: (1) LogView.detailed=True does not by itself expose native detailed text: row_text still chooses it only for expanded row keys, while default expanded is empty. Initial dice/modifier visibility therefore needs correction independent of child-tree expansion. (2) sheet label formatting titlecases namespaced enum values, producing Species.Human / Class.Fighter / Background.Adventurer rather than human names. Use native enum names or authored labels for those known values. These are bounded presentation defects, not requests to generate alternate combat prose or rules.

Other inspected updates preserve boundaries: targeting has concise selected action/allocation and confirmation controls rather than permanent instructions; inventory effects display their passive display_name instead of behavior_id; reference labels resolve exact registered metadata; creature portraits bind explicit projected content identity or player choice, not names or live Entity queries. Developer intake validates content/rig/body source identities/hashes before installing immutable role images. No runtime rule dispatch added by media lookup.

Typing diagnostics used temporary AST copies only. Explicit isolated Pyright config was necessary because repo config excludes .runtime. Renaming the UI tail hit variable alone caused an internal RangeError ('Maximum call stack size exceeded', assignFromUnionType→assignType→validateArgType/validateCallArgsForSubtype), not a meaningful source diagnostic. A second copy removing only generic dataclasses.replace calls in the event block still exceeded a25-second bounded run. Neither experiment isolates a precise production expression; no fix should be claimed from them. Results are in .runtime/ui-study-20261005/review_hit_alias.log and review_no_replace.log. No production edits or broad refactor proposed. Full acceptance remains pending correction/test evidence.

### Latest quiet-UI repairs recheck

Confirmed the two prior style defects are closed: log children are open by default via an empty collapsed set, and row_text chooses native detailed wording whenever detailed mode is on, independent of tree expansion. Sheet uses species/background/class enum names instead of namespaced values. No duplicate dice calculation or alternate combat wording was introduced.

Creature portraits now use the existing ContentDescriptor.presentation through exact ContentRef identity indexing; the former separate UI creature presentation table is gone. The import command validates delivered content/rig/body hashes and selects the descriptor’s portrait key. Runtime consumes passive descriptor data and projected birth identity. Player-selected portrait still takes precedence. Native font rendering changes do not modify selection or mechanical ownership.

Inventory detail_scroll_rect is precise passive layout feedback, but one concrete overlap issue remains: encounter_play’s MOUSEWHEEL dispatch checks log_open and geometry.log containment before inventory detail containment, even while a panel hides the log. With the inventory open over that area, the invisible log captures the wheel. Add the same visible-log condition used by draw (`panel is None`) before scrolling it. Reported to root; no production edits.

Parent reports physical Fighter and Sorcerer native action routes execute without presentation gaps; final recordings/full game suite remain pending. This receipt approves the repaired data/wording boundaries, not final physical acceptance or unresolved root Pyright recursion.

### Final regression-repair bounded recheck

Confirmed the hidden-log wheel capture is fixed by requiring panel is None. apply_ui_hit is a nested function in the existing frame owner, consuming the same UIHit after capture/focus/rectangle/enabled/generation checks and returning the existing native intent union. It adds no state registry, scheduler or alternative rule execution. Existing Session dispatch still executes the result. Body/head creator choices now require actual Idle sheet membership as well as permitted appearance category.

The volume ray correction properly transforms a direction as inverse(endpoint) minus inverse(origin), removing the inverse transform's translation; an absolute inverse point was not a valid ray direction. This is a renderer regression repair, not geometry-rule expansion. Parent reports136 area/scene occlusion checks passing. Floating feedback now rasterizes antialiased text at the provided display font dimensions, while world anchors/rise alone receive world/camera scale. This follows the explicit updated font policy and does not alter feedback event timing.

Selection-mask arrays make Python dataclass tuple equality unsuitable for render-command comparison. Tests comparing destination/blend/evidence and actual RGBA output retain observable render verification; independent mask/picking tests remain needed, rather than claiming ordinary RGBA comparison proves interaction masks.

Read physical proof JSONs: Fighter records3commands and zero gaps, with ordinary main-hand Attack plus native Extra Attack roots; Sorcerer records2commands and zero gaps, with Magic Missile recipients A/B/A/A (native repeat-fill); environment records2commands and zero gaps. These are execution proofs, not this reviewer's visual inspection of refreshed recordings. Final font-adjusted recordings and broader suite partitions remain pending. Root encounter_play Pyright recursion remains explicitly unresolved; no all-files typing approval. No new source blocker found in reviewed repairs, no production edits by reviewer.

### Bounded final source/visual verdict

Verified ui-types-final.log records0errors/0warnings/0information, superseding the earlier unresolved typing receipt for the scoped root/UI/composition/interaction/volume run. Do not extrapolate this to every repository file. Inspected actual refreshed physical screenshots: fighter frame00600 and sorcerer frame00400. Human portrait/name/action HUD is compact; log displays native dice/modifier breakdown by default, Unicode arrows render, and movement cost punctuation is no longer malformed. No technical UUID/descriptor keys appear in these inspected UI surfaces. Sorcerer still displays inherited anonymous native 'Unknown gains Bloodied' log rows, the previously documented packet wording issue; this is not evidence that the renderer resolved those source identities.

**Bounded ECS/import/source and inspected visual checkpoint approved.** This does not certify every frame of the refreshed videos, chest→loot→drop→pickup (being added), nor completion of the still-running full-game remainder. Existing gameplay identity, exact native command dispatch and presentation ownership remain intact in reviewed changes. No production edits by reviewer.

### Fly intake / final evidence scope update

Inspected Fly omission repair: importer retains manifest sourceIconKey only when that exact resource address is absent, through the existing checksum/dimension-validated select function. Existing owned condition address is retained; the ordinary spell reference receives an explicit alias to the same delivered PNG. No display-name guessing, new mechanical condition or runtime fallback registry was added. The native-reference media test reads spell.fly through action_reference/presentation and compares loaded RGBA bytes with the selected source image.

Verified ui-types-all-game.log records0errors/0warnings/0information and ui-movement-temp-fixed.log records41passed in38.25s. This supersedes prior game-typing uncertainty; it is not evidence that the still-running full test remainder has finished. Source review found no blocker in the intake repair. Inspected refreshed1280×720 frame00012 for the current HUD; broader refreshed packet/storage recordings remain pending and are not certified here. No production edits.

### Native SELF correction and five-case packet/capture review

Source recheck confirms explicit caster target binding now applies only to SELF actions with source_item_uuid. Ordinary SELF actions use their original source-only bound declaration; the action’s native resolver remains authoritative. Item source ownership checks and existing item execution path remain in place. This closes the overbroad binding regression without adding action-specific exceptions or another dispatcher.

All five physical sequence files exist and contain schema_version2 with initialization, lineages, combat_log_appends and hud_snapshots. Read corresponding summaries: fighter3commands, sorcerer2, environment2, storage5, completion2, each with empty gap list; completion records encounter_ended=True. Parent reports independent round-trip/reduction comparisons against captured state. This reviewer inspected packet envelopes/summaries, not independently repeated that validator.

Viewed actual final completion frame01199 and storage frame00899. Completion visibly shows two defeated enemies and encounter-complete state with surviving fighter. Storage visibly shows the open chest and native log sequence Open Chest→Loot All→Drop(Handaxe)→Pick Up→turn end. These sampled frames substantiate the delivered paths but do not replace whole-clip scrutiny or full regression results. No new bounded ECS/DAG/source blocker identified; final regression approval remains reserved until running partitions and follow-up fixes are reconciled. No production edits.

## Final local ECS/import-DAG/scope acceptance — 2026-10-06

**Accepted for the approved player-UI lane, with the report's explicit product limits retained.** Reviewed PLAYER_UI_IMPLEMENTATION_2026-10-06.md against source checkpoints, saved physical evidence and actual regression logs. All concrete defects raised in this receipt are closed. Native rules/command ownership, cold creation, observer-authorized passive facts, historical presentation, shared painted picking and native log wording remain separate and coherent. No new event executor, widget domain model, persistence format or parallel creature presentation registry remains.

Verified collection identity reconciliation directly: original collection3694, remainder2086, current3695. First1610 original identities union remainder yields exactly3694 with two overlaps and no extra identities; the sole additional current case is test_floating_text_keeps_display_glyphs_when_the_world_is_zoomed, covered by the final feedback/input rerun. Verified broad log totals and failing-file identities: prefix96 failures are90area +2equipment +4forced movement; remainder36 are5movement +1pending fact +5placement +15condition fact +6condition rendering +1support media +2support replay +1UI media. The report's complete affected-file rerun groups have recorded green totals136/29/41/36/117/5; the intermediate support run's five failures are explicitly superseded by the full36-case rendering run. Native broad seven failures are six roster-ability and one spellcasting, covered by recorded125 and final117 affected runs. Verified final32-case input/native/media/feedback pass and final scoped typing0errors/0warnings/0information. git diff --check exits successfully (line-ending advisories only).

This is completed partitioned coverage with failure closure after repairs, **not an uninterrupted all-green frozen run**. Overlapping subset totals must not be summed into a larger test count. Parent maintains the execution provenance of complete-file commands; this reviewer inspected their logs and collection identity lists without rerunning the broad suites.

Completion wording is now accurate: player clicked Move and main Attack; a native automatic opportunity attack killed the other Goblin. Prior shorthand about two ordinary player attacks must not be repeated. Sampled storage/completion/Fighter/Sorcerer/resolution images and five schema2 packet summaries support delivered paths; they are not exhaustive per-frame visual validation.

Remaining explicit limits are retained: anonymous repeated native Bloodied log wording, absent ground consumable artwork/clickable sprites, declared icon binding gaps/approximations, deferred whole-world save/load and earned in-session progression. These are not silently fixed or disguised by UI approval. No claim of Windows physical fullscreen/4K validation. No production changes made by this reviewer.
