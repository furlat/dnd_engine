# Scenario Package

`dnd.scenarios` owns authored battlefield builders and the sole canonical
encounter assembler.  Authored and saved content reaches runtime through
`EncounterRecipe`; there is no parallel direct-entity arena path.

Scenarios are not core rules. They should avoid adding hidden mechanics, global
state policy, or alternate rulesets. If a scenario needs custom behavior, that
behavior should be explicit in the scene objects it creates.

Current product modules:

- `battlefield_catalog.py`: nine authored battlefield definitions and their
  exact runtime builders.
- `encounter_catalog.py`: direct canonical roster, deployment, and encounter
  recipes.
- `encounter_compatibility.py`: static and built-map preflight.
- `encounter_assembler.py`: the only recipe-to-`Encounter` path.

This package is the natural place to add future map-editor-backed encounter
content: the map editor can export geometry, lights, terrain, props, and spawn
points as canonical battlefield and encounter recipes.
