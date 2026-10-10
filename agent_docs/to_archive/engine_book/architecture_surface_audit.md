# Architecture Surface Audit

Last updated: 2026-07-14.

This audit classifies newer NeuroDragon surfaces that appeared while the manual
was being built. Its purpose is to keep the public manual honest: a surface is
not final architecture merely because it exists or because a chapter imports
it.

## Classification Labels

- `core engine architecture`: belongs in the D&D engine runtime because rules,
  encounters, actions, events, or entities depend on it directly.
- `product/game-mode architecture`: belongs above the engine as a game, API,
  authoring, scenario, client, stream, or automation layer.
- `public tutorial support`: may be imported by the public manual as a
  documented teaching surface, but should not be mistaken for core runtime law.
- `temporary manual scaffolding`: exists only to make the current manual pass
  possible and should be moved or deleted when better public surfaces exist.
- `generated/cache output to remove`: generated, local, saved, or cache output
  that should not become source truth.
- `risky or accidental change needing review`: may be useful, but the current
  shape conflicts with architecture rules, ownership boundaries, naming, or
  product quality expectations.

## Evidence Inspected

- `dnd/controller.py`
- `dnd/maps/arena_layout.py`
- `dnd/scenarios/gatehouse.py`
- `dnd/scenarios/controller_catalogue.py`
- `dnd/scenarios/ai_validation_arenas.py`
- `server/event_stream.py`
- `server/live_replication.py`
- `server/arena_mode.py`
- `server/mapeditor_support.py`
- `server/api_models.py`
- `server/event_server.py`
- `ai/protocol/`
- `ai/observation/`
- `ai/subjective/`
- `ai/semantics/`
- `ai/knowledge/`
- `ai/policy/`
- `ai/codex_tools/`
- `/home/tommaso/Dev/MapEditor/README.md`
- `/home/tommaso/Dev/MapEditor/docs/PROJECT_INVENTORY.md`
- `/home/tommaso/Dev/MapEditor/app/src/types.ts`
- `/home/tommaso/Dev/MapEditor/app/src/exporter.ts`
- `/home/tommaso/Dev/MapEditor/app/src/localMapIndex.ts`

## Surface Classification Matrix

| Surface | Classification | Current decision | Evidence | Required follow-up |
| --- | --- | --- | --- | --- |
| `dnd.controller.Controller`, `TurnContext`, `PassController`, `HumanController`, `CodexController`, `ExternalAIController` | core engine architecture | Keep in `dnd`. Controllers are the engine turn-ownership abstraction for encounters. | `dnd/controller.py` defines controller registry, lifecycle callbacks, turn contexts, and human/Codex/pass/external-AI ownership variants. | Keep controller policy out of action legality; action legality stays in engine actions and decision epochs. |
| `dnd.maps.arena_layout` | product/game-mode architecture | Keep as a shared arena environment builder, not as core grid law. | `build_standard_arena_environment()` creates the reusable arena floor, directional wall strip, door, light, objects, and loot used by arena and MapEditor support. | Decide whether stable map packs need a formal `MapPackage`/`EnvironmentPackage` contract. |
| `dnd.scenarios.gatehouse` | public tutorial support | Keep as a documented playable scenario package for Chapter 22. Treat it as the prototype for scenario packaging, not as proof that every scenario API is final. | `create_gatehouse_scenario()` builds map state, actors, controllers, active encounter, deterministic initiative, and scenario result helpers. | If scenario packaging becomes product architecture, promote an explicit scenario protocol and separate tutorial reset utilities from scenario runtime. |
| `dnd.scenarios.controller_catalogue` | public tutorial support | Keep as the Chapter 24 teaching scene for controller behavior. | The module creates controller actors, deterministic encounters, turn contexts, and controller-specific fixtures for examples. | Consider moving to a `dnd.tutorials` or `dnd.examples` namespace if it remains teaching-only. |
| `dnd.scenarios.ai_validation_arenas` | product/game-mode architecture | Keep as the controlled arena catalogue for agent validation. | Arena specifications rotate doors, water, line of sight, class kits, ranged pressure, and area effects while preserving deterministic setup metadata. | Expand only when accumulated evidence identifies a missing tactical dimension; avoid one-scenario overfitting. |
| `server.event_stream.DndEventStream` and stream payload models | product/game-mode architecture | Keep as first-class client/replication architecture. | `server/event_stream.py` bridges `EventQueue` and `Encounter` combat logs to resumable SSE payloads with event/log cursors and bounded subscriptions. | Add focused stream contract tests around overflow, replay ordering, and completion/log pairing before marking complete. |
| `server.live_replication` | public tutorial support | Keep as the Chapter 25 local scene surface. It demonstrates replication behavior but should not be the stream service boundary. | The module creates one active stream scene, attaches `event_stream`, executes a real attack, parses SSE frames, and drains subscriptions. | Split scene factories from production replication service if this becomes runtime code. |
| `server.event_server` arena and simulation routes | product/game-mode architecture | Keep as the current API host for arena, simulation, sessions, state, events, and streams. | Routes include arena start endpoints, state/action/session surfaces, SSE stream endpoint, and MapEditor endpoints. | The file is a large monolith. Extract routers by domain before calling the API architecture polished. |
| `server.arena_mode` | public tutorial support | Keep as an in-process manual/local-client wrapper over existing FastAPI routes. | `ArenaApiClient` uses HTTPX ASGI transport; `start_joined_human_arena()` starts human arena mode, creates a session, and joins the hero. | Do not document this as the production client. If standard arena becomes product architecture, expose a cleaner app/client package. |
| `server.mapeditor_support` | product/game-mode architecture | Keep as the D&D backend adapter for the external MapEditor, with an explicit entity-free boundary. | The module rejects `include_entities`, resets editor world state, serializes `MapEditorMapSnapshot`, saves/loads map documents, patches tiles, places/deletes catalog objects, and exposes walkability/visibility/light layers. | Replace catalog dependencies on `dnd.items.test_items` before productizing. Keep scenario-owned actors, factions, controllers, and victory rules out of this module. |
| `server.api_models` MapEditor models | product/game-mode architecture | Keep as the API schema contract for MapEditor integration. | `MapEditorMapSnapshot`, saved map documents, tile patches, catalog entries, walkability, visibility, and light responses use Pydantic `Field(description=...)`. | Continue the Pydantic metadata audit for non-MapEditor API models; decide whether schemas should be generated for the external MapEditor client. |
| `/home/tommaso/Dev/MapEditor` | product/game-mode architecture | Keep external. Integrate through backend APIs and durable map documents, not by merging projects. | The README calls it a standalone generative isometric map editor; the D&D backend is optional through `VITE_MAPEDITOR_BACKEND_BASE`. TypeScript `MapDocument` owns grid bounds, tiles, floor objects, asset placements, generation settings, and saved map metadata. | Define the stable document/API handoff between MapEditor-owned entity-free spaces and scenario-owned actors/controllers/objectives. |
| `ai.protocol` | product/game-mode architecture | Keep as the dependency-neutral typed contract shared by server projection, traditional AI, and LLM clients. | It defines subjective decision epochs, affordances, action economy, semantics, and epoch-bound commands without importing live engine entities. | Continue extending semantics through typed contracts rather than policy name checks. |
| `ai.observation` and `ai.subjective.SubjectiveRuntime` | product/game-mode architecture | Keep as the only agent state transport and local materialization path. | Objective events and combat logs are projected by session perception, streamed with monotonic cursors, and reduced locally from one bootstrap snapshot plus deltas. | Preserve strict subjectivity and prove replay equivalence, idempotence, eviction, and resync behavior. |
| `ai.knowledge` and `ai.policy.PolicyHost` | product/game-mode architecture | Keep as the one decision architecture for traditional AI and LLM-assisted control. | Typed fact derivation feeds routines, hierarchy, utility arbitration, memory, command binding, and authoritative result reconciliation. External AI, self-play, and Codex all use this host. | Add new behavior as typed semantics, candidate families, and reusable routines; do not add parallel controller policies. |
| `ai.codex_tools` | product/game-mode architecture | Keep as the typed takeover and hot-runtime surface for Codex. | Tools expose the same subjective runtime, epochs, policy trace, and command protocol used by the normal external AI. | Improve compact local read projections without adding backend information queries. |
| `data/mapeditor/maps/*.json` | generated/cache output to remove | Treat as local saved map artifacts, not source truth. Do not delete without Tommaso's approval. | The workspace contains many timestamped saved map JSON files under `data/mapeditor/maps/`. | Decide whether any saved maps become curated fixtures. Ignore or remove the rest after explicit approval. |
| `/home/tommaso/Dev/MapEditor/app/node_modules`, `/home/tommaso/Dev/MapEditor/app/dist`, `/home/tommaso/Dev/MapEditor/app/public/generated` | generated/cache output to remove | Keep out of source history and out of the manual. | MapEditor project inventory identifies node modules, dist output, and generated job folders as non-migration/default-exclusion material. | Ensure these remain ignored; do not use generated jobs as public manual source unless deliberately curated. |

## Boundary Decisions

1. Controllers are engine architecture; controller decisions choose from legal
   engine surfaces, while action legality remains in the action system.
2. Scenario packages are currently public tutorial/product prototypes. They
   should remain visible because the manual imports them, but they still need a
   stable package contract before being called complete product architecture.
3. MapEditor owns entity-free authored spaces: grid bounds, tiles, terrain,
   directional borders, floor objects, objective light, walkability,
   visibility blockers, saved map documents, asset placements, generation
   settings, and visual-layer artifacts.
4. Scenarios own play layered onto a map: actors, monsters, factions, loadouts,
   controllers, initiative, turn handoff, action execution, objectives,
   victory or defeat, and encounter ending.
5. Live streams are product/client architecture; the current stream scene file
   is tutorial support over that architecture.
6. The AI package is product/game-mode architecture above the engine. Every
   controller consumes the session-subjective event stream and typed decision
   epochs. No AI adapter reads live engine entities as its decision surface.

## Known Risks To Carry Forward

- `server/mapeditor_support.py` currently builds parts of the MapEditor catalog
  from `dnd.items.test_items`, which is too demo-flavored for a product
  authoring contract.
- Validation arenas share a product namespace with scenario builders. Their
  namespace makes them look more final than they are, so additions need evidence
  from the rotation rather than tutorial convenience.
- `server/event_server.py` combines simulation, sessions, events, MapEditor,
  streams, and arena routes in one large API module.
- `data/mapeditor/maps/*.json` appears to be local saved output. It should not
  become source truth without curation.
- Utility components in `ai.policy` are agent scoring heuristics. They must stay
  documented as tactical estimates rather than engine combat rules.
