# Directional Arena Hotswap Plan

Status: implementation plan for the final backend hotswap pass.

This document covers the last large backend migration step for the standard
arena fixtures. The directional wall/door item classes already exist and are
tested in isolation. This pass replaces the old scalar wall tiles and scalar
`TestDoorA` arena door in the shared arena layouts with tile-owned directional
items, then runs the broad test/debug loop around movement, senses, light,
AoE, actions, event serialization, SSE, and server endpoints.

The scope here is the standard arena and its copied fixtures. The
`dnd.utils.setup_combat_arena()` helper is not a map builder; it only updates
senses and creates an encounter, so its many users are regression tests rather
than direct wall/door hotswap sites.

## Current Arena Builders

### Live Combat Arena

`server/event_server.py`

- `setup_arena_combat(...)` builds the live 15x15 combat arena.
- It creates open floor with `grid.create_rectangle(...)`.
- It adds a vertical scalar wall at `x=7`, `y=3..11`, excluding `y=7`:
  `grid.set_tile(7, y, walkable=False, visible=False, name="Wall")`.
- It places a scalar closed `TestDoorA` at `(7, 7)`.
- It also adds:
  - water island at the upper-left;
  - spike zone at the lower-left;
  - difficult terrain near both ends of the wall;
  - darkness on all tiles;
  - wall torches at `(14, 1)` and `(14, 13)`;
  - potions, trap lever, scrolls for sorcerer setup;
  - player and skeleton entities;
  - opportunity attack handlers and initial senses.
- It is reached directly by server startup endpoints such as human and pvp
  simulation setup.

### Mapeditor Crypt Preset

`server/mapeditor_support.py`

- `build_forgotten_crypt_arena_map(...)` mirrors the same terrain/object
  layout for the map editor preset.
- It currently uses the same scalar wall strip and scalar `TestDoorA`.
- `create_editor_map(...)` dispatches to this preset for
  `preset_id="forgotten_crypt_arena"`.
- `build_scratch_map(...)` is separate and creates uniform scalar floor/wall
  maps from the requested default tile type.
- `build_catalog(...)` still exposes scalar tile wall and scalar door catalog
  entries. The preset hotswap does not require changing generic catalog
  placement yet, because orientation for user-placed directional doors/walls
  is a separate editor/frontend workflow.

### Copied Arena Fixtures

These examples copy the standard wall/door layout and should be migrated in
the same pass so failures are found early:

- `examples/test_available_actions_perf.py`
  - `setup_sorcerer_arena(...)` is effectively a local copy of
    `setup_arena_combat(character_class="sorcerer")`.
  - It exercises door open/close, hidden/visible enemies, torch state,
    movement to the door, LOS/visibility, and action profiling.
- `examples/test_door_interaction.py`
  - Local setup recreates the vertical wall plus closed door.
  - It asserts movement and visibility are blocked by the closed door and
    restored by opening it.
- `examples/test_light_propagation.py`
  - `create_dark_arena_with_wall_and_door(...)` recreates the dark wall/door
    layout.
  - It asserts wall/door light blocking, light propagation after door state
    changes, wall torch behavior, and senses visibility through the opened lit
    doorway.

## Directional Representation For The Hotswap

The hotswap must use ordinary tile-resident items. No edge object layer is
introduced.

For compatibility with the old arena, use this mapping first:

- Former scalar wall cells:
  - Tile remains ordinary floor: `walkable=True`, `visible=True`.
  - Place one `DirectionalWall` on the same tile.
  - Configure directions `north`, `south`, `east`, and `west`.
  - Configure channels `movement`, `vision`, `light`, and `propagation`.
  - This preserves old behavior because the former wall cell remains
    unreachable from every adjacent side, while the blocking fact now comes
    from tile-owned directional item state rather than scalar tile
    walkability/visibility.
- Door gap `(7, 7)`:
  - Place one `DirectionalDoor` on `(7, 7)`.
  - Configure directions `east` and `west`.
  - Configure channels `movement`, `vision`, `light`, and `propagation`.
  - Closed state blocks crossing the doorway; open state clears only the
    door's own directional contributions.
  - Existing intrinsic or unrelated item directional blockers on the tile must
    survive open/close.

This is the compatibility hotswap. A later map-design pass can choose thinner
east/west-only wall segments if we want the former wall column to become
occupiable space. That behavior change should not be mixed into the test
stabilization pass.

## Implementation Steps

### 1. Add A Shared Arena Terrain Helper

Create a small helper module that can be imported by both `server/event_server`
and `server/mapeditor_support` without importing server code back into `dnd`.

Recommended location:

- `dnd/maps/arena_layout.py`

Recommended responsibilities:

- Provide constants for the standard arena size and fixed feature positions.
- Provide a helper to apply the shared environment layout to an existing
  `GridMap`.
- Place directional walls and the directional door in the compatibility mapping
  described above.
- Preserve water, spike zone, difficult terrain, darkness, wall torches, and
  floor-object placement behavior.
- Return useful object handles or UUIDs when callers need to keep references.

Dependency direction:

- The helper may import `GridMap`, `Tile`, terrain/tile conditions, light
  enums, and item classes.
- It must not import `server.*`, `Encounter`, controllers, sessions, API
  models, or entity setup code.
- Entity placement and encounter/controller setup stays in
  `server/event_server.py`.

### 2. Replace The Live Arena Terrain Construction

In `server/event_server.py::setup_arena_combat(...)`:

- Keep combat/session reset logic in place.
- Keep player, skeleton, item inventory, controller, and encounter setup in
  place.
- Replace the direct scalar wall loop and `TestDoorA` placement with the shared
  directional arena helper.
- Preserve the current initial door state: closed.
- Preserve current initial lighting: all dark, wall torches lit.
- Preserve current visible object/action behavior:
  - directional wall should not appear in `senses.objects`;
  - directional door should appear when visible/perceivable;
  - open/close use actions should still be available only when valid.

Also replace any direct tile dictionary writes in this setup with public grid
APIs where possible, so tile recomputation and spatial subscriptions stay on
the normal path.

### 3. Replace The Mapeditor Crypt Preset

In `server/mapeditor_support.py::build_forgotten_crypt_arena_map(...)`:

- Use the same shared directional arena helper for the common environment.
- Preserve the preset's state-only behavior: no combat entities are created.
- Preserve map snapshot expectations for:
  - size;
  - terrain layers;
  - darkness;
  - torches;
  - potions and trap lever;
  - door presence.
- Update tests that currently assert wall tiles are scalar non-walkable /
  non-visible. After hotswap, the former wall positions are floor tiles with
  directional blocking maps and directional wall objects.

Do not change generic mapeditor catalog placement in this pass unless a test or
caller already supplies orientation/directional placement data. The crypt
preset can contain directional objects without making every catalog wall/door
placement directional immediately.

### 4. Replace Copied Example Fixtures

Migrate the copied arena layouts in:

- `examples/test_available_actions_perf.py`
- `examples/test_door_interaction.py`
- `examples/test_light_propagation.py`

The clean target is to reuse the same helper rather than keep three more local
copies of wall/door placement logic. If a test needs tiny local control, keep
that setup local but use `DirectionalWall` and `DirectionalDoor` with the same
compatibility directions.

### 5. Clean Up Duplicated Arena Helpers

After the shared helper exists, remove avoidable local copies of standard
arena construction. The next person reading the tests should be able to answer
"what is the standard arena?" from one helper, not from four subtly different
snippets.

Cleanup targets:

- Move shared constants into the helper:
  - arena size;
  - wall column;
  - wall y-range;
  - door position;
  - torch positions;
  - water island positions;
  - spike zone positions;
  - difficult terrain positions.
- Replace copied wall/door loops with helper calls.
- Keep only test-specific entity/action setup local to each example.
- If a test intentionally needs a non-standard wall/door arrangement, name the
  helper clearly, for example `build_custom_dark_wall_door_fixture(...)`, so it
  is not confused with the standard arena.
- Avoid hidden duplication between live server and mapeditor preset:
  - common terrain/object placement should live in the shared helper;
  - server-only entity/controller/session work remains in `event_server`;
  - editor-only snapshot/catalog/save-load work remains in
    `mapeditor_support`.
- Add a quick static guard test or grep-style assertion in the hotswap example
  if practical:
  - standard arena code should not contain the old scalar wall loop;
  - standard arena code should not instantiate `TestDoorA`.

Do not turn this into a broad map-builder refactor. The cleanup is successful
when standard arena terrain/object placement has one source of truth and tests
that need custom layouts make that customness obvious.

### 6. Update Assertions From Scalar Cells To Transitions

Old assertions often say:

- wall tile is not walkable;
- wall tile is not visible;
- door object blocks the whole cell.

New assertions should say:

- the tile exists and remains floor-like;
- transition through the blocked side is denied for movement;
- FOV/LOS through the blocked side is denied;
- light through the blocked side is denied;
- AoE/line-of-effect through the blocked side is denied;
- unrelated transitions still behave as expected;
- door open/close updates directional maps and events.

Use `GridMap.can_transition(...)`, `can_see_transition(...)`,
`can_light_transition(...)`, and `can_propagate_transition(...)` in backend
tests instead of checking only `Tile.walkable` or `Tile.visible`.

### 7. Verify Events And Streams

No new event type is needed.

The hotswap must keep using:

- `SPATIAL_OBJECT_PLACED`
- `SPATIAL_OBJECT_REMOVED`
- `SPATIAL_OBJECT_CHANGED`
- `SPATIAL_TILE_CHANGED`
- `SPATIAL_LIGHT_CHANGED`
- `SENSORY_UPDATE`
- existing movement/collision events

Door open/close must emit `SPATIAL_OBJECT_CHANGED` with directional metadata
that is JSON-safe under `model_dump(mode="json")`.

Senses updates must still be driven by the existing spatial callback:

- path dirtiness when movement blocking changes;
- FOV dirtiness when vision/light/propagation relevant blocking changes;
- visible object deltas when the door becomes visible or changes state;
- no wall spam in `senses.objects`;
- no new event family in SSE or websocket payloads.

### 8. Import Hygiene Check

After the hotswap:

- Static import graph over `dnd/` and `server/` must report zero cycles.
- New helper module must not import server code.
- No late imports should be added.
- No `TYPE_CHECKING` import escape hatch should be added.
- No constructed `getattr` / `setattr` for directional fields should be added.
- No duck-typed checks for door/wall state should be added where a real class
  or explicit API exists.

## Direct Hotswap Test Inventory

Run these after the first hotswap slice, one file at a time.

### Standard Layout Direct Users

- `python examples/test_available_actions_perf.py`
- `python examples/test_door_interaction.py`
- `python examples/test_light_propagation.py`
- `python examples/test_visibility_contract_payloads.py`
- `python examples/server_tests/test_event_serialization.py`
- `python examples/test_mapeditor_api.py`

Expected update pressure:

- Mapeditor tests currently expect scalar wall tile fields.
- Door/light tests currently expect scalar `TestDoorA` semantics.
- Visibility/action tests may need assertion updates around visible objects and
  door object names/classes.

### Server/API Indirect Users

These reach the standard arena through `/simulation/start-human` or direct
`setup_arena_combat(...)`. Run them with a live uvicorn server when required by
the test file.

- `python examples/server_tests/test_jump_api.py`
- `python examples/server_tests/test_equipment_api.py`
- `python examples/server_tests/test_handler_toggle_api.py`
- `python examples/server_tests/test_server_api.py`
- `python examples/server_tests/test_toggle_cli_debug.py`
- `python server/test_human_control.py`

Also keep the open AoE server arena as a control:

- `python examples/server_tests/test_aoe_api.py`

### Directional Foundation Regressions

These should stay green because the hotswap relies on the already-built
directional backend.

- `python examples/test_directional_environment_items.py`
- `python examples/test_tile_directional_blocking.py`
- `python examples/test_directional_event_stream.py`
- `python examples/server_tests/test_directional_event_stream_live.py`

### Movement, Senses, Light, AoE, And Action Regressions

Run these to catch downstream behavior changes that may not touch the standard
arena directly.

- `python examples/test_usable_items.py`
- `python examples/test_reactive_senses.py`
- `python examples/test_invisibility_pathfinding_leak.py`
- `python examples/test_shove.py`
- `python examples/test_jump.py`
- `python examples/test_thunderwave.py`
- `python examples/test_aoe_shapes.py`
- `python examples/test_burning_hands.py`
- `python examples/test_faction_system.py`
- `python examples/test_available_actions.py`
- `python examples/test_entity_blocking.py`

## Broader `setup_combat_arena()` Regression Pool

These tests use `dnd.utils.setup_combat_arena()`, which does not build the
standard wall/door arena. They are not direct hotswap targets, but they are a
useful second regression wave if movement/senses/action changes are touched
while debugging:

- `python examples/test_barbarian_fighter_combat.py`
- `python examples/test_faction_system.py`
- `python examples/test_invisibility_pathfinding_leak.py`
- `python examples/test_sorcerer_factory.py`
- `python examples/test_skeleton_units.py`
- `python examples/test_terrain_movement_system.py`
- `python examples/test_event_hierarchy.py`
- `python examples/test_light_source_cleanup.py`
- `python examples/test_lighting_system.py`
- `python examples/test_serialization.py`

## New Or Updated Tests To Add

Add a focused arena hotswap example instead of relying only on existing tests:

- `examples/test_directional_arena_hotswap.py`

Required assertions:

- Standard live arena wall positions are floor-like tiles but cannot be entered
  from any side because of directional wall item contribution.
- The door at `(7, 7)` is a `DirectionalDoor`, starts closed, and blocks
  movement, FOV, light, and propagation east/west.
- Opening the door restores movement, FOV, light, and propagation through the
  doorway.
- Opening the door does not clear unrelated intrinsic or item directional
  blockers.
- Directional walls do not appear in `senses.objects` or available object/use
  actions.
- Directional door appears in `senses.objects` when visible/perceivable and
  offers only state-valid open/close actions.
- Closing the door while an entity occupies the door tile fails with the same
  semantic behavior as existing doors.
- `SPATIAL_OBJECT_CHANGED` for door open/close serializes as JSON with
  directional metadata and no new event type.
- `SENSORY_UPDATE` after door open/close carries the expected visibility,
  object, and path dirtiness deltas.

Add a server roundtrip test if the existing live directional event test does
not cover the standard arena:

- `examples/server_tests/test_directional_arena_live.py`

Required assertions:

- `/simulation/start-human` produces a grid/state payload containing
  directional wall/door data for the standard arena.
- The event stream receives existing `game_event` payloads for door interaction.
- Serialized event payloads include directional metadata as JSON arrays/maps.
- No new event type name is introduced.

## Execution Order

1. Run the direct hotswap inventory before editing to record the baseline.
2. Add the shared helper and the focused hotswap test.
3. Switch `server/event_server.py::setup_arena_combat(...)`.
4. Run `examples/test_directional_arena_hotswap.py`,
   `examples/test_door_interaction.py`, and
   `examples/test_light_propagation.py`.
5. Switch `server/mapeditor_support.py::build_forgotten_crypt_arena_map(...)`.
6. Run `examples/test_mapeditor_api.py`.
7. Switch copied fixtures in perf/light/door examples to the shared helper.
8. Remove avoidable duplicated standard arena constants and wall/door loops.
9. Run the full direct hotswap inventory.
10. Start uvicorn and run the server/API indirect users individually.
11. Run directional foundation regressions.
12. Run movement/senses/light/AoE/action regressions.
13. Run the import hygiene check.
14. Document any unrelated failing test in `KNOWN_ISSUES.md` with command,
    error, and hypothesis.

## Acceptance Criteria

- Standard arena no longer uses scalar wall tiles for the vertical wall strip.
- Standard arena no longer uses `TestDoorA` for the doorway.
- Mapeditor crypt preset no longer uses scalar wall tiles or `TestDoorA` for
  its standard wall/door layout.
- Copied standard arena fixtures use the shared helper or have explicit
  non-standard fixture names.
- Standard arena constants and terrain/object placement are not duplicated
  between live server, mapeditor preset, and copied examples.
- Movement, FOV, light, propagation, senses, targeting/action discovery, events,
  SSE serialization, and server snapshots agree on the same directional facts.
- Directional walls do not create visible object/action spam.
- Directional doors remain interactable through the existing object action
  path.
- Existing scalar `TestDoorA` tests still pass where they intentionally test
  the legacy full-cell door class.
- No circular imports, late imports, `TYPE_CHECKING` escapes, constructed
  directional `getattr/setattr`, or duck-typed state checks are introduced.
