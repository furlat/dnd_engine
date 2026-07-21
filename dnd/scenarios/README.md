# Scenario Package

`dnd.scenarios` contains reusable scene builders for tests, manual examples, and
developer-facing demonstrations. A scenario should assemble engine objects and
return a small typed bundle that callers can use directly.

Scenarios are not core rules. They should avoid adding hidden mechanics, global
state policy, or alternate rulesets. If a scenario needs custom behavior, that
behavior should be explicit in the scene objects it creates.

Current scenario modules:

- `gatehouse.py`: playable encounter package.
- `controller_catalogue.py`: built-in controller examples.
- `ai_validation_arenas.py`: deterministic arenas used by the shared agent
  policy validation harness.

This package is the natural place to add future map-editor-backed encounter
fixtures: the map editor can export geometry, lights, terrain, props, and spawn
points; scenario builders can translate that content into engine entities,
tiles, and encounter bundles.
