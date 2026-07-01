# Chapter 08 Plan: World Model And Movement

## Status

Drafted with real tutorial tests. Public Astro page should be published for
browser review in this work pass.

Prepared test file:

- `tests/manual/test_08_world_model_and_movement.py`

Focused test run:

- `uv run pytest tests/manual/test_08_world_model_and_movement.py`
- Result: 5 passed.

Working public file:

- `src/content/manual/08-world-model-and-movement.mdx`

## Reader Promise

By the end of the chapter, the reader should understand:

- How NeuroDragon represents the tactical map as tiles in `GridMap`.
- How D&D-style 5-foot movement maps to grid-cost units and feet.
- How tile movement costs create normal terrain and difficult terrain.
- How pathfinding uses tile cost, movement mode, and transition rules.
- How directional borders block movement between adjacent cells.
- How entity position indexes update when the grid moves an entity.
- How spatial enter/leave/tile-change events connect the map to the event
  system.
- How voluntary step movement and forced movement can parent spatial updates
  without becoming the same event type.

## Evidence Studied From Source

Current-source evidence read for this plan:

- `dnd/core/gridmap.py`
- `dnd/core/base_tiles.py`
- `dnd/actions.py`
- `dnd/entity.py`
- `dnd/core/events.py`
- `examples/test_difficult_terrain.py`
- `tests/manual/test_08_world_model_and_movement.py`

Evidence conclusions below come from source inspection and focused tests, not
old prose.

## Source Facts To Teach

### GridMap

`GridMap` owns:

- `_tiles`,
- `_tiles_by_uuid`,
- `_entities_by_position`,
- `_entity_positions`,
- object position indexes,
- cell subscribers,
- light sources,
- spatial event firing,
- pathfinding.

`create_rectangle(...)` batch-creates tiles without emitting per-tile change
events.

`set_tile(...)` stores a tile and can emit a `SPATIAL_TILE_CHANGED` lifecycle.

`register_entity(...)` and `move_entity(...)` update position indexes and emit
`SPATIAL_ENTITY_ENTERED` and `SPATIAL_ENTITY_LEFT` lifecycles.

### Tile

`Tile` is a `BaseBlock`. It stores:

- position,
- `walkable` and `visible` compatibility flags,
- movement-mode costs,
- directional borders for movement, vision, light, and propagation,
- light state,
- condition support.

`Tile.get_movement_cost(mode)` reads the matching `ModifiableValue`.

`difficult_terrain_factory(...)` creates a walkable tile whose walking cost is
2 and flying cost remains 1.

### Pathfinding

`GridMap.compute_paths(...)` uses Dijkstra. Distances are in grid cost units.
The action layer converts cost units to feet with `cost * 5`.

`ignore_difficult_terrain=True` caps terrain costs above 1 for walking paths.

### Directional Borders

`set_tile_directional_border(...)` changes a tile-owned border and emits
directional metadata through `SPATIAL_TILE_CHANGED`.

`can_transition(...)` checks:

- adjacency,
- tile existence,
- diagonal transition rules,
- directional borders,
- destination walkability for the requester.

### Movement And Spatial Events

`Move` resolves a path, then walks it cell by cell. Each transition creates a
`StepMovementEvent` at `EFFECT`; if it is not canceled, the entity position is
updated through `Entity.update_entity_position(...)`, which delegates to
`GridMap.move_entity(...)`.

Low-level map examples can call `GridMap.move_entity(...)` directly. When the
caller passes `parent_event`, the spatial enter/leave completions resolve that
event's lineage as `parent_lineage`.

`ForcedMovementEvent` uses `FORCED_MOVEMENT`. It can parent spatial updates,
but it is not `STEP_MOVEMENT`.

## Concepts Allowed In This Chapter

Allowed:

- GridMap
- Tile
- terrain cost
- movement mode
- Dijkstra path cost
- difficult terrain
- directional border
- entity position index
- spatial enter/leave/tile-change event
- voluntary step event
- forced movement event
- parent event lineage for spatial updates

Allowed only as future landmarks:

- senses subscriptions
- line of sight and light

## Concepts Forbidden In This Chapter

Do not teach:

- full perception/senses recalculation
- stealth/invisibility reveal rules
- opportunity attacks beyond the movement-surface distinction
- full combat action flow
- spell zone authoring in detail
- encounter/session APIs
- map editor APIs

Do not use hidden helpers from old tests.

Forbidden public names:

- `EB-*`
- parity
- `tests/engine_book`
- private notes
- `make_bonus`
- `make_damage_roll`
- `make_d20_roll`
- `fixed_randint`
- `completed_damage_events`
- `RegistryProbe`

## Public Page Shape

### 1. The Map As Tactical State

Start from the game:

The grid is the videogame board. It answers where things are, which cells exist,
what they cost to enter, which transitions are blocked, and what changed.

### 2. Where The Imports Come From

Import map must appear before code.

### 3. Tiles And Terrain Costs

Show rectangle, difficult tile, bounds, lookup, cost, path distance, and
ignore-difficult-terrain path.

### 4. Directional Borders

Show east movement border blocking transition and emitting tile-change metadata.

### 5. Entity Position Indexes

Show register and move entity UUIDs, position lookup, entities-at-position.

### 6. Spatial Enter/Leave Events

Show `StepMovementEvent` parent and spatial event completion parent lineage.

### 7. Forced Movement

Show `ForcedMovementEvent` as a separate event type that can still parent
spatial updates.

### 8. Batch Map Creation

Show `create_rectangle(...)` avoids noisy per-tile events, while `set_tile(...)`
emits a tile change.

## Diagram Requirement

Create:

- `world-model-movement.svg`
- `world-model-movement.excalidraw`

Caption:

> The grid owns tiles, path costs, and position indexes; movement updates the
> indexes and emits spatial events so the rest of the engine can react to map
> changes.

## Test Requirement

The test file must remain a real pytest file:

- `tests/manual/test_08_world_model_and_movement.py`

It must include:

- visible imports,
- no wrappers around examples,
- no imports from `examples`,
- no imports from `tests.engine_book`,
- no `iter_example_tests`,
- behavior names instead of EB numbers.

Required focused tests:

- `test_grid_tiles_have_bounds_lookup_and_movement_costs()`
- `test_directional_border_blocks_transition_and_emits_tile_change()`
- `test_entity_position_index_and_spatial_events_follow_grid_moves()`
- `test_forced_movement_is_a_distinct_event_that_can_parent_spatial_updates()`
- `test_batch_tile_creation_does_not_emit_tile_change_events()`

Run focused only:

```bash
uv run pytest tests/manual/test_08_world_model_and_movement.py
```

Do not run the full test suite.

## Public Acceptance Gate

Before publishing or keeping the page public:

- Chapter 08 includes the import map before code.
- Every code symbol is imported or defined before use.
- No public note/test/parity links.
- No hidden helpers in public snippets.
- No full perception, stealth, spell-zone authoring, encounter/session, or map
  editor API explanation before introduced.
- The voluntary movement versus forced movement distinction remains explicit.
- Diagram renders at desktop and narrow widths.
- Focused pytest file passes.
- Manual arc focused tests pass.
- Astro build passes.
- Route returns `200`.
- Public hygiene scan finds no `engine_book`, `tests/`, `parity`, `notes/`,
  `TODO`, `placeholder`, or old helper names.
