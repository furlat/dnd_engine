# Gameplay resumption: environment interaction and shared delivery

The user approved returning to shared action delivery and added environment
interaction: lootable boxes/chests, doors and other props with meaningful state
and animation. This study and the asset scan establish the next bounded gameplay
unit. Startup optimization is stopped; the active checkout remains on C:.

**User correction, September 18:** the first study narrowed "other interactions"
to familiar doors and chests. The requested scope goes beyond that: levers,
extinguishing placed lights and environmental changes that affect play. The
lights/lever unit below supersedes the door/loot-first ordering later in this
document. Doors and loot remain part of the room, not the whole feature set.

**Backend scope clarification:** the user explicitly confirmed that environment
items may require new authored backend behavior. Existing mechanics are useful
starting points, not the boundary of the requested game. Add missing item state,
actions and their emitted facts at native owners; keep presentation consuming
those facts. Do not reduce an interaction to selecting an asset or stop because
the old item happened to lack the requested behavior.

## Current implementation: light control and a linked lever

Use real discovered actions and current rules to show that interacting with the
environment changes visibility and traversable risk. Reuse the original symbolic
lever drawing where a dedicated pixel sprite is absent; label that art limit.

1. Connect both placed wall and standing torches through passive prop bindings
   and the existing painter. Their base art and optional flame layer depend on
   received `is_lit`, placement and camera pose. Replace the current exact
   standing-torch-only draw restriction with this shared presentation path.
2. Capture extinguish/relight sequences from operator and witness. Test ordinary
   vision versus darkvision and a second independently owned light. Contact and
   target changes come from native sensory events, not a renderer darkness rule.
   Confirm fixture after-values survive native/public serialization; repair only
   an actually reproduced missing after-value at its existing owner.
3. Capture a discovered lever action deactivating its exact linked SpikeTrap,
   followed by real movement through its former area. Retain a control hazard
   or pre-pull walk so the gameplay consequence is observable. Keep the linked
   trap's existing perception rules. The lever currently spends a charge; this
   is not evidence of a mechanical handle pose or a general on/off switch.
4. Preserve complete causal roots and both observers' recorded public views.
   Use the existing gallery for synchronized four-corner clips and saved-input
   replay. Keep latest state independent of paused presentation. Do not add a
   second queue, per-prop action executor or new generic interaction framework.

Anti-slop review: `environment_native_review` verifies actual light/trap state,
discovery and paired facts. Anti-OOP review: `environment_timeline_review` checks
the shared prop binding/drawing and original recipe meaning. Asset exploration
by `environment_asset_scan` now includes original lever drawings, UI icons and
other relevant archives instead of stopping at the chest contact sheet.

### Completed light/lever checkpoint — September 18

The first unit is implemented. `battlefield.environment_workshop` creates actual
placed lights, a lever and two independent spike networks. The room builder
settles its traps through the existing post-initialization lifecycle, so the
lever also works outside the test producer.

- `WallTorch.light/put_out` now publish the existing item-location after-value
  under the causal action. The old implementation changed native light but left
  replay's fixture state stale. Both wall and standing regression cases failed
  before this repair. Initialization's old compensating publication was removed;
  repeated same-state calls emit nothing.
- One shared prop draw path consumes passive camera/body/optional-lit-loop
  bindings. It uses recorded visibility, placement, elevation and `is_lit`.
  Standing torch behavior is preserved; two actual wall-torch images and the
  original neutral lever marker add 60,048 bytes of media. There is no new action
  executor, event queue, per-prop renderer branch or runtime asset audit.
- Four light experiments cover standing/wall fixtures, a darkvision witness and
  an independent second light. The operator has darkvision; the ordinary witness
  loses/reacquires it. Both participants make two real steps during the off
  interval. The witness walks on authored dim footing, so its own recording has
  meaningful movement while the operator's movement is hidden.
- The lever experiment crosses the live linked spikes, retreats, pulls the
  lever, crosses safely and then enters the unrelated active trap. Saved player
  packets show HP changes `-4, 0, 0, -4`; only the linked hazard is removed. A
  paused variant exercises historical presentation with latest state ahead.

**Verification:** 49 asset/map/prop checks and 48 native/public/world checks pass
(97 distinct checks). Changed production modules, gallery wiring and new scenario
and test modules pass Pyright. Existing diagnostics in older renderer test files
outside the edits were not treated as new defects. Anti-slop and anti-OOP reviews
approved the source and actual scenario meaning.

Six experiments produce **12 paired four-corner clips**, all passing with no
presentation gaps. A fresh process re-rendered all twelve saved public inputs
with no native content installed, no scenario producers imported and an empty
event queue. Initial gameplay facts, causal lineages, bound timelines, final
states and every frame trace match; saved input bytes are unchanged. The initial
diagnostic comparison excludes the existing process-local `sense_modes_hash`
cache value; actual sense-mode values and all gameplay fields match. No hashing
or new runtime validation was added for this comparison.

- [Capture gallery](http://127.0.0.1:8767/runs/20260918T140227Z-342b3b/index.html)
- [Saved-input replay gallery](http://127.0.0.1:8767/runs/20260918T140548Z-b32e98/index.html)
- Saved inputs: `.runtime/animation-review/inputs/environment-*`.
- Local check output: `.runtime/environment-study-20260918/`.

These are immediate state interactions using the original Studio recipes.
The lever still has one neutral marker pose; wall torches have two actual source
views reused across four cameras. General lever-to-door/light behavior and
container opening are the next backend unit below, not claimed complete here.

```bash
export UV_PROJECT_ENVIRONMENT=/home/tommaso/.cache/dnd-engine/venv
# Explicit native generation, followed by rendering saved public bytes:
/home/tommaso/.local/bin/uv run --no-sync python -m devtools.animation_review.capture --tag environment
# Subsequent runs consume those same saved inputs without native generation:
/home/tommaso/.local/bin/uv run --no-sync python -m devtools.animation_review --tag environment
```

## Wider environmental gameplay to connect and author

| Interaction | Existing native meaning | Follow-through after the first unit |
| --- | --- | --- |
| Placed lights | Light/extinguish, anchored light, sensory/target changes | First unit above; preserve independent lights and special senses |
| Linked lever | Deactivate one exact SpikeTrap and consume its authored charge | First unit above; next author a reusable control for a door or placed light, with real target-state events |
| Breakable containers | Attack Object, object HP/destruction, contents spilling onto the floor | Draw intact/removal or authored break media from a recorded destructive cause; pickup is not destruction |
| Oil barrels and exposed flame | Barrel destruction creates OilSurface; fire damage can ignite it through existing spatial interactions | Connect surface/condition lifetime and actual actors entering affected cells through shared area presentation |
| Campfire | Existing Rest heals; Cook grants temporary HP | Connect the real effects; current campfire is not already a switchable light or a complete resting/crafting system |
| Skill-gated devices | Arcana-gated healing device; finite/unlimited spell-granting fixtures | Exercise existing discovery, charges and shared action/spell delivery |
| Containers, pickup, drop and equipment | Existing item transfer and ownership | Keep the previous loot repair; author container open/closed state and discovered actions, then connect lid art and subsequent item use |
| Doors and gates | Existing directional boundary state changes sight and movement | Use available gate variants through the same boundary owner |

Moving crates, pressure plates, locks and crafting are further design candidates,
not capabilities established by this study. Backend additions are authorized
where the selected interaction needs them. A general circuit language is not a
prerequisite for authoring an ordinary lever/door/light link.

### Next backend unit: authored controls and containers

The native review recommends a reusable two-position lever controlling one
placed light first, then a directional door through the same narrow link data.
This differs from the existing finite-use trap lever; do not redefine that item
merely to give every control the same class name.

1. Separate the three facts: the lever's persistent `is_engaged`, the target's
   actual `is_lit`/`is_open`, and an authored backend link identifying the target
   and requested state when engaged. A manual change to the target does not move
   the handle. A charge count is not handle state.
2. Compose the target's normal action under the lever event using the existing
   `BaseAction.apply(parent_event=...)` surface. `execute_use_action` currently
   has no parent argument; extending the functional entry point is unnecessary.
   Door use-actions are templates while torch use-actions are already executable;
   use the existing template instantiation path when needed, without copying the
   discovery/target-selection machinery into a second dispatcher.
   Preserve the target action's existing identity, light/sensory changes and
   directional-door validation, including refusal to close an occupied doorway.
   If already in the requested state, the target needs no mutation. A refused
   close leaves the lever unchanged; this follows an existing concrete rule,
   not a new rollback framework.
3. Publish the lever's accepted state through `ItemLocationStateEvent` and the
   existing item/public floor-state values. Target consequences continue to come
   from their native owners. The remote link is backend configuration, not
   automatically disclosed player state: seeing the lever must not reveal a
   hidden target's identity or location.
4. Resolve handle/chest appearances through passive state variants in the same
   prop binding. Keep the original action timeline and existing independent
   presentation clock. **The user's subsequent review corrects the immediate
   interaction assumption:** play a physical arm reach and commit the recorded
   effect at its contact frame, as with attacks. One local recipe in the original
   NeuroStudio ContentActionRecipe schema reuses the existing Attack5 clip;
   explicit action aliases share it. Source-item placement supplies facing.
   The outer lever owns the reach; its linked target action must not produce a
   second remote reach. Timed received world/sensory/inventory values use the
   existing reducer and compositor, with no delay in native event execution.
   Preserve established spell/condition fade timing outside object interactions.
   Use closed/open chest sprites and an explicitly authored mirrored lever
   handle variant. Exact pixel hand contact for every prop height/reach remains
   an alignment question; a clip contact anchor is not per-frame hand tracking.
5. Exercise pull → light change → subjective contact loss/reacquisition, manual
   target change without moving the lever, then another lever operation. Add
   the door target with its occupied-close rule and a second independent control.
   Record both viewpoints and replay saved public packets with native state
   unavailable. Test what the participants can observe, not a private call order.

For containers, define open/close and access behavior at the native item before
binding the supplied closed/open art. Empty/full and closed/open are independent
facts. The proposed ordinary chest offers Open/Close and allows Loot All when
open and nonempty. Opening does not transfer items; an empty chest still opens
and closes. Set initial lid state explicitly in authored scenes; transfer-only
fixtures can start open. Preserve the repaired transfer owner, private inventory
rules and existing destruction/spill behavior.

Authored gameplay determines the required native state and actions. Extend the
existing owners where behavior is missing and record committed consequences
through the established event contracts. No circuit simulator, prop controller
hierarchy or new interaction manager is needed for this unit. Anti-slop review
is `environment_native_review`; anti-OOP review is `environment_timeline_review`.

### Current contact acceptance boundary

Input is each observer's serialized complete lineage and retained prior state.
Before the authored contact frame, playback retains the previous object state;
at contact, the received change and its received sight consequence appear.
Retraction continues afterward. Seeking backward restores the earlier state,
and latest reduction may already be ahead. Test original standing/wall lights,
the new remote light/door control, chest lid/loot, and both subjective views.
Capture four corners per view and replay the saved bytes in a fresh process.
No synthetic interaction delay, second queue, native query during replay,
per-item renderer logic, or new source/asset auditing is part of this work.

### Completed controls and contact unit

The authorized next unit is implemented on `codex/recovery-design`:

- Native `ControlLever` holds independent `is_engaged` and a private typed link.
  Its action composes the normal placed-light or directional-door action under
  the existing causal root. Manual target changes leave the handle alone;
  already-satisfied targets need no mutation; occupied-door refusal leaves the
  handle unchanged. This does not redefine the finite-use trap lever.
- `StorageChest.is_open` controls Open/Close/Loot All discovery and validation.
  Opening leaves inventory untouched; Loot All uses the repaired transfer owner;
  the empty chest still opens/closes. Existing transfer-only fixtures now
  explicitly start open. Destruction/spill behavior is retained.
- `battlefield.environment_controls` provides a bright workbench, dark light
  area, a remote light behind a real opaque wall, a directional doorway, an
  independent control and a potion chest. Five native programs plus a paused
  chest variant add twelve paired-view clips to the twelve previous clips.
- One local `object-interaction-recipe.json` uses the original
  ContentActionRecipe structure with Attack5 and contact/effect frame 3.
  Explicit aliases cover torch, lever, door and chest interactions. The original
  imported disabled recipes remain intact as provenance. The public action
  carries its source-item UUID only when granted through this observer's
  recorded object perception; the binding faces that placement and hides held
  gear for the gesture. A same-actor linked child does not reach again.
- The compositor precomputes received world/sensory/inventory state at its
  existing interaction anchors using the existing player reducer. Sampling
  selects retained state, with no native execution or per-frame event fold.
  Other condition/attack/equipment primitives retain their established timing,
  including invisibility fading before contact loss. Exported review traces
  now include compact prop states and controlled inventory identities.
- The shared prop painter reads passive `is_open`/`is_engaged` variants. Eight
  unchanged original chest PNGs supply two states in four directions. The
  second lever SVG pose is newly authored by mirroring its handle, explicitly
  distinguished from supplied art. New media totals **288,082 bytes**.

**Validation:** the integrated gameplay selection passes **233 checks**, with
the two already marked forced-movement stair-occlusion cases remaining expected
failures. Native controls/loot and paired projection checks pass again after the
authored actor-health adjustment (**16 checks**, overlapping the earlier lanes).
The native implementation sweep passed **55** checks and exposed one unchanged
catalog census assertion expecting 150 instead of the existing 151 direct item
builders. That unrelated count assertion was left alone. Changed presentation,
projection, scenario and gallery modules pass Pyright; the native review
reproduced its five preexisting annotation diagnostics against HEAD, with no new
diagnostic. Anti-slop and anti-OOP reviews found no blockers.

The smallest regression first failed because the flame stayed lit at the contact
frame. It now passes from both viewpoints: previous object/sight state before
contact, received state at contact, then retraction. Additional saved-byte checks
prove a single physical lever reach, door/chest changes at that reach, no hidden
remote UUID in the operator payload, owner-only acquired inventory, and seeking
without mutations. The paused chest has a closed historical lid for all 18 held
frames while latest already has it open.

**All 24 clips pass with no presentation gaps.** A fresh receiving process has
no installed native content, no imported scenario producers and no native queue
events before or after replay. All saved inputs and MP4 bytes match their captures
exactly, using direct byte comparisons. Recorded trace fields also match; the
first twelve capture traces predate the additional prop/inventory diagnostic
fields. As in the prior checkpoint, only the initial process-local
`sense_modes_hash` diagnostic is excluded from initial-state comparison; actual
sense modes and gameplay values match. No hashing or audit system was added.

- [Combined saved-input gallery](http://127.0.0.1:8767/runs/20260918T144144Z-c728cc/index.html)
- Original interaction capture: `20260918T143702Z-8ca778`.
- Final controls/chest capture: `20260918T144016Z-59f6a3`.
- Saved input: `.runtime/animation-review/inputs/environment-*`.
- Comparison record and inspected contact frames:
  `.runtime/environment-study-20260918/`.

**Remaining limits:** Attack5 supplies an authored semantic reach/contact frame,
not a per-frame hand socket or automatic geometric reach solution for every
prop height. Fixed creature rigs lacking Attack5 do not gain a fabricated
gesture. Wall torches still reuse their two supplied views. The lever art is a
symbolic handle and chest lids switch between supplied states; no vendor lid
animation strip is claimed. Breakable containers, oil/fire surfaces, campfire
actions and broader shared delivery remain subsequent planned work.
Both have reviewed this next-unit design; its implementation remains ahead.

The [asset study](ENVIRONMENT_ASSET_STUDY_2026-09-18.md) records exact archive
entries, alignment references and inspection sheets. It confirms three chest
closed/open pairs, ordinary crates/barrels and the already imported door pair.
Fire and barrel destruction have real frame sequences; chest/door state pairs
do not constitute an opening strip.

## What the source already provides

- `game/session.py` submits discovered actions to existing native owners.
  `game/controls.py` already supports menu selection of their disclosed targets;
  it does not need a second interaction executor. Map selection currently uses
  the action target position, which can be the user for self-targeted item use.
  Physical prop selection therefore needs checking against actual discovery
  rows, rather than assuming the action's target entity is the door or chest.
  Native discovery limits nearby object actions by current sensory contacts and
  five-foot distance. The application should submit those discovered choices;
  raw item-use methods are not being claimed as a new network authority boundary.
- Native directional doors own their open state, boundary obstruction and
  sensory consequences. Recorded world after-values and public world updates
  already supply the renderer's open/closed choice. `game/app.py` draws the
  existing door frame/leaf from those values in all four orientations.
- `StorageChest` owns a nested Inventory and an existing `LootAllAction`.
  It has no native lid-open state. The direct builder can opt into the action;
  not every existing authored chest does. Native item transfer, player-owned
  inventory after-values and complete action ancestry need exercising together
  before declaring this path connected.
- Imported NeuroStudio rows exist for door open/close, chest looting, pickup,
  lever and campfire actions. The environment rows inspected so far disable the
  actor body, use Idle and place their effect at frame zero. Original NeuroClient
  likewise reduces door state without a dedicated door clip. These are authored
  immediate interactions, not missing references to an opening gesture.
- `game/body_action.py` already binds that recipe shape inside the shared causal
  compositor. Reuse it unchanged where the imported recipe is sufficient.
  `PlayerState.objects` already holds disclosed/remembered object placement and
  public item appearance/state. Ordinary chest/box drawing is missing; current
  world drawing handles boundary structures and the standing torch.

## Supporting room connection: doors and loot

The observable result is a small playable scene: approach an actual door, select
its discovered action, open it, see the resulting room/actor visibility, move
through it and interact with a real lootable container. The same histories feed
the paired review clips. This connects gameplay, world state and presentation.

1. Reuse the existing directional door and supplied four-orientation closed/open
   sprites. Confirm current menu selection and map picking can identify the
   intended nearby object when there is more than one. Keep action availability,
   reach, costs, obstruction and sensory changes under their native owners.
2. Add selected ordinary prop art as passive bindings in the existing
   `world_bindings.json`/asset catalog. Resolve the object's existing appearance
   identity, camera pose and recorded state to existing asset IDs. Use existing
   placement, height, disclosure and painter ordering. One ordinary-prop drawing
   path should handle these rows; doors retain their actual boundary geometry.
3. Exercise the existing chest transfer through discovery/execution and saved
   player input. Repair a demonstrated transfer/parenting omission at its native
   owner if it blocks this sequence. Owned item after-values explain what was
   acquired; spectators do not receive chest contents or another actor's private
   inventory just because the prop is visible.
4. Keep visible lid position distinct from whether a container has contents.
   A chest may be closed and empty or open and nonempty. Selecting an open asset
   requires an actual recorded open state; `loot_all`, a guessed inventory count
   or a renderer flag is not that state. Source study must settle this small
   native interaction extension before adding a lid transition. Static variants
   are usable first; actual authored frame sequences are a separate capability.
5. Record both participants' subjective histories from the same native run, then
   replay saved bytes with native production unavailable. Review four corners
   per observer, including opening-induced discovery, closing/loss of view,
   subsequent world memory and a pause while authoritative state advances.
   Include real item ownership before/after looting and capacity rejection if
   the current inventory limit is reached. Use simple flat arrangements first.

A future timed prop animation should use the existing event identity/causal
effect anchor and independent presentation clock. It must not delay the native
door's legal change, create another state machine/queue or make the renderer
recompute visibility. Do not implement this extension solely because a sprite
file has numbered variants; the asset scan distinguishes state variants from
actual animation frames.

## Shared action delivery remains the parent gameplay lane

The environment slice adds to the existing objective rather than replacing it.
After its connection, extend the missing original Studio delivery primitives
using a few representative real actions: self/touch/direct, an area with multiple
actual recipients, and persistent effects with native application/removal.
Self/touch body timing already exists for the concealment unit; imported data
and exercised semantics determine the remaining work. Do not restart it from
scratch or implement one renderer per spell.

Both action effects and object changes must retain source ordering, complete
lineages, independent latest/historical reduction and the existing subjectivity
rules. Python/Pygame remains the runtime; new authoring data stays portable to
TypeScript. Use actual available art. Existing trap deactivation is included in
the current lights/lever unit; broad new trap rules, locking, VFX authoring and a
large inventory/editor UI are not prerequisites for connecting it.

## Review and current boundary

- Asset study: `environment_asset_scan` inspects available packs and exact states
  without bulk importing or modifying source art.
- Anti-slop reviewer: `environment_native_review` traces real discovered actions,
  transfer semantics, sensory effects and causal events. A concrete native probe
  distinguishes demonstrated blockers from imagined concerns.
- Anti-OOP reviewer: `environment_timeline_review` checks original Studio/client
  intent, current passive object values and existing composition/drawing owners.

Both reviewers approved the concrete plan. Native review reproduced the Loot All
blocker below; timeline review confirmed that immediate door state reduction was
also the original client's behavior, and that the current shared body-action
path already loads the relevant imported recipes.

The previous checkpoint covered the asset/native/presentation study and the
reproduced native transfer repair below. The current implementation unit is
placed lights and the linked lever at the top of this document; a complete loot
room and timed prop animation remain separate work.
Read `HOW_TO_TEST.md` before adding behavioral coverage. Validate real commands,
resulting ownership/world facts and saved subjective replay; do not add source
fingerprints, asset audits or exact file-census tests to ordinary play.

### Reproduced blocker selected for repair

The native reviewer exercised actual discovery and `execute_use_action` with a
composed chest containing one item. With capacity available, the transfer's
`ItemLocationStateEvent` has no causal parent; with inventory `max_slots=0`,
Loot All removes the item from the chest but cannot insert it into the actor's
inventory. The item is absent from both. Probe/output are preserved in ignored
`.runtime/environment-study-20260918/loot_probe.py` and `loot_probe.json`.

`LootAllAction` currently pre-removes items and omits the parent argument.
`Entity.loot_item` and `Inventory.add_item_with_result` already own accepted
transfer from the old container. The bounded repair passes each still-contained
item and `parent_event=execution_event` to that existing owner. Verify through
the public action: accepted items arrive once with correct parented after-values;
capacity refusal leaves items in the chest. Do not add a transfer manager,
transaction layer or substitute event. The native reviewer implements/tests this
small correction; root and the timeline reviewer review its actual ownership.

**Completed repair:** Loot All now calls the existing transfer owner without
pre-removal and supplies its execution event. Three regression cases failed on
the original source, then passed: all items accepted, a full one-slot inventory,
and partial acceptance with one free slot for two items. Checks assert remaining
chest/actor holdings, exact owner/container after-values and accepted item facts
parented to the actual action lineage. Existing inventory and chest behavior
also pass: **26 checks in 2.93s**, with zero Pyright errors/warnings for the changed
source/test files. Anti-slop and anti-OOP reviews approved the actual correction.
The production change is two added lines and three removed lines.

```bash
export UV_PROJECT_ENVIRONMENT=/home/tommaso/.cache/dnd-engine/venv
/home/tommaso/.local/bin/uv run --no-sync python -m pytest -q \
  tests/engine/test_environment_loot.py \
  tests/engine/test_items_inventory_equipment.py \
  tests/manual/test_134_stackable_usable_item_legacy_contract.py::test_chest_discovery_loot_and_empty_state_are_one_contract
```

Before/after test and type-check output is retained alongside the probe in
`.runtime/environment-study-20260918/`. No new scene, art import, chest-lid
mechanic, world-prop drawer or area-delivery implementation was added in this
study/repair checkpoint. The later user correction selected placed lights and
the linked lever before the supporting door/loot room connection.

## Source pointers for implementation

| Responsibility | Current source |
| --- | --- |
| Door actions, open state and boundary update | `dnd/items/environment.py`, `dnd/core/gridmap.py` |
| Nearby usable-object discovery and inventory acceptance | `dnd/entity.py:_collect_use_actions`, `Entity.loot_item`, `dnd/blocks/inventory.py:add_item_with_result` |
| Chest builder/action/storage | `dnd/content/items/environment_item_builders.py:build_storage_chest`, `dnd/items/environment_interactables.py:LootAllAction/StorageChest` |
| Existing public object state and world memory | `game/player_facts.py:FloorItem/PlayerObject/WorldUpdate`, `game/player_projection.py:_world_update`, `game/player_reduction.py` |
| Current disclosed action menu and submission | `game/controls.py`, `game/session.py:execute_player_action` |
| Static world art, ordering and disclosure | `game/data/world_bindings.json`, `game/assets.py`, `game/app.py` |
| Imported interaction recipes and existing effect anchor | `game/data/neuroclient/source/src/render/data/animation/contentActionPresentationRecipes.json`, `game/body_action.py`, `game/choreography.py` |
| Original door state-only handling | `/home/tommaso/Dev/NeuroClient/app/src/render/subjectivePresentationMapper.ts`, `subjectivePresentationSemantics.ts` |
| Original area/self/touch semantics for the subsequent delivery slice | `/home/tommaso/Dev/NeuroClient/app/src/render/spellAuthoring/phaseGraph.ts`, `clips/CastClip.ts` |

The latter original paths share the stated NeuroClient render directory. Its
old chest drawer used a generic drawn box; there is no authored chest-opening
timeline to retrieve. Area fields are present in the imported Studio types, but
the Python area compiler connection and authoritative geometry in public spell
facts remain concrete work for the subsequent shared-delivery slice.
