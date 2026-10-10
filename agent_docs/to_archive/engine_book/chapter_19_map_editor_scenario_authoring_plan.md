# Chapter 19 Plan: Map Editor And Scenario Authoring

## Reader Promise

This chapter teaches how NeuroDragon authors playable spaces before combat
starts: map-editor catalogs, entity-free scratch and preset maps, terrain
patches, placed objects, objective layers, durable saved maps, and the handoff
boundary between authoring state and running-game state.

## Concepts Introduced For The First Time

- `MapEditorCatalog`
- `MapEditorCreateMapRequest`
- `MapEditorMapSnapshot`
- `MapEditorTilePatchRequest`
- `MapEditorObjectPlaceRequest`
- `MapEditorObjectDeleteRequest`
- `MapEditorSavedMapDocument`
- `MapEditorWalkabilityResponse`
- `MapEditorVisibilityResponse`
- `MapEditorLightResponse`
- `DND_MAPEDITOR_SAVE_DIR`

## Concepts Kept Out Of This Chapter

- Live encounter setup from a saved map.
- Browser-side editor UI state.
- Asset pipeline and renderer placement handles.
- Multiplayer permissions around authoring.
- Scenario scripting beyond static map, object, and loot placement.

Those are follow-on chapters after the authoring payload contract is stable.

## Runtime Sources Studied

- `server/mapeditor_support.py`
- `server/api_models.py`
- `server/event_server.py`
- `server/session.py`
- `server/event_stream.py`
- `dnd/core/gridmap.py`
- `dnd/core/base_tiles.py`
- `dnd/items/environment.py`
- `dnd/maps/arena_layout.py`

## Game Meaning

The map editor is the workbench for spaces. It does not serialize a combat
encounter and it does not create actors. It builds the geometry and objects a
developer needs before the running game begins.

The authoring contract should make three boundaries obvious:

- A catalog defines what the editor can place.
- A snapshot defines the current entity-free map state.
- Objective layers describe walkability, visibility blocking, and light without
  depending on a particular observer.

## Visual

Use `/diagrams/map-editor-scenario-authoring.svg` and matching Excalidraw
source. The diagram should show:

- catalog entries feeding authoring operations;
- scratch and preset map creation;
- tile, object, and loot placement;
- objective map layers;
- save/load/delete round trips;
- clean replacement of running combat state when entering authoring mode.

## Public Example Contract

Use one named exact-execution group:

- `map-editor-authoring-flow`

Example blocks:

- EB-19-001: read the catalog and create an entity-free scratch map.
- EB-19-002: patch terrain, light, and directional borders.
- EB-19-003: place objects and read objective walkability, visibility, and light
  layers.
- EB-19-004: delete placed objects by UUID and by tile position.
- EB-19-005: save, inspect, load, list, and delete an authored map.
- EB-19-006: create the crypt preset and show that it replaces running combat
  state with authoring state.

Public setup routines must be visible and tutorial-facing:

- `reset_map_authoring_state`
- `tile_at`
- `layer_cell`
- `create_authoring_client`
- `create_tutorial_editor_map`
- `patch_tutorial_room`
- `place_tutorial_objects`

## Verification

Focused test:

```bash
uv run pytest tests/manual/test_19_map_editor_scenario_authoring.py tests/book_examples/test_public_mdx_snippets.py
```

The exact public snippet runner should increase by one example group and the
manual page should remain free of private source references and meta
verification language.
