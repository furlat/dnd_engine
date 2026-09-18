# Gameplay resumption: environment interaction and shared delivery

The user approved returning to shared action delivery and added environment
interaction: lootable boxes/chests, doors and other props with meaningful state
and animation. This study and the asset scan establish the next bounded gameplay
unit. Startup optimization is stopped; the active checkout remains on C:.

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

## First implementation slice: a usable room with doors and loot

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
TypeScript. Use actual available art. Additional VFX authoring, destruction,
locking, trap systems and a broad inventory/editor UI are not prerequisites for
the first door/loot slice.

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

The current work is the asset/native/presentation study, this bounded plan and
the following reproduced native transfer repair. This document does not claim
that a new scene, loot presentation or timed prop animation is already working.
Read `HOW_TO_TEST.MD` before adding behavioral coverage. Validate real commands,
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
study/repair checkpoint. The next work is the room-level connection above.

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
