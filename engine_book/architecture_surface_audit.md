# Architecture Surface Audit

Last updated: 2026-06-30.

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
- `dnd/scenarios/agent_tactical_training.py`
- `dnd/scenarios/agent_decision_training.py`
- `server/event_stream.py`
- `server/live_replication.py`
- `server/arena_mode.py`
- `server/mapeditor_support.py`
- `server/api_models.py`
- `server/event_server.py`
- `ai/models.py`
- `ai/interface.py`
- `ai/primitives/behavior_tree.py`
- `ai/primitives/utility.py`
- `ai/agents/base.py`
- `ai/agents/examples.py`
- `/home/tommaso/Dev/MapEditor/README.md`
- `/home/tommaso/Dev/MapEditor/docs/PROJECT_INVENTORY.md`
- `/home/tommaso/Dev/MapEditor/app/src/types.ts`
- `/home/tommaso/Dev/MapEditor/app/src/exporter.ts`
- `/home/tommaso/Dev/MapEditor/app/src/localMapIndex.ts`

## Surface Classification Matrix

| Surface | Classification | Current decision | Evidence | Required follow-up |
| --- | --- | --- | --- | --- |
| `dnd.controller.Controller`, `TurnContext`, `PassController`, `HumanController`, `CodexController`, `ExternalAIController`, `AIAgentController` | core engine architecture | Keep in `dnd`. Controllers are the engine turn-ownership abstraction for encounters. | `dnd/controller.py` defines controller registry, lifecycle callbacks, turn contexts, human/Codex/pass/external-AI variants, and an agent delegation controller. | Review docstrings and field descriptions during the controller hygiene pass. Keep controller policy out of action legality; action legality stays in engine actions. |
| `dnd.maps.arena_layout` | product/game-mode architecture | Keep as a shared arena environment builder, not as core grid law. | `build_standard_arena_environment()` creates the reusable arena floor, directional wall strip, door, light, objects, and loot used by arena and MapEditor support. | Decide whether stable map packs need a formal `MapPackage`/`EnvironmentPackage` contract. |
| `dnd.scenarios.gatehouse` | public tutorial support | Keep as a documented playable scenario package for Chapter 22. Treat it as the prototype for scenario packaging, not as proof that every scenario API is final. | `create_gatehouse_scenario()` builds map state, actors, controllers, active encounter, deterministic initiative, and scenario result helpers. | If scenario packaging becomes product architecture, promote an explicit scenario protocol and separate tutorial reset utilities from scenario runtime. |
| `dnd.scenarios.controller_catalogue` | public tutorial support | Keep as the Chapter 24 teaching scene for controller behavior. | The module creates controller actors, deterministic encounters, turn contexts, and controller-specific fixtures for examples. | Consider moving to a `dnd.tutorials` or `dnd.examples` namespace if it remains teaching-only. |
| `dnd.scenarios.agent_tactical_training` | public tutorial support | Keep as the Chapter 26 training scene for the tactical agent interface. | The module creates an agent actor, target, active encounter, first-attack agent, and deterministic attack helpers. | Keep it documented as a tutorial scene. If product agents need training arenas, design a separate stable arena/training package. |
| `dnd.scenarios.agent_decision_training` | public tutorial support | Keep as the Chapter 27 training scene for decision patterns. | The module builds one-target and two-target decision scenes and melee-only actors for behavior-tree and utility examples. | Same namespace concern as other teaching scenes; do not present it as production encounter content without approval. |
| `server.event_stream.DndEventStream` and stream payload models | product/game-mode architecture | Keep as first-class client/replication architecture. | `server/event_stream.py` bridges `EventQueue` and `Encounter` combat logs to resumable SSE payloads with event/log cursors and bounded subscriptions. | Add focused stream contract tests around overflow, replay ordering, and completion/log pairing before marking complete. |
| `server.live_replication` | public tutorial support | Keep as the Chapter 25 local scene surface. It demonstrates replication behavior but should not be the stream service boundary. | The module creates one active stream scene, attaches `event_stream`, executes a real attack, parses SSE frames, and drains subscriptions. | Split scene factories from production replication service if this becomes runtime code. |
| `server.event_server` arena and simulation routes | product/game-mode architecture | Keep as the current API host for arena, simulation, sessions, state, events, and streams. | Routes include arena start endpoints, state/action/session surfaces, SSE stream endpoint, and MapEditor endpoints. | The file is a large monolith. Extract routers by domain before calling the API architecture polished. |
| `server.arena_mode` | public tutorial support | Keep as an in-process manual/local-client wrapper over existing FastAPI routes. | `ArenaApiClient` uses HTTPX ASGI transport; `start_joined_human_arena()` starts human arena mode, creates a session, and joins the hero. | Do not document this as the production client. If standard arena becomes product architecture, expose a cleaner app/client package. |
| `server.mapeditor_support` | product/game-mode architecture | Keep as the D&D backend adapter for the external MapEditor, with an explicit entity-free boundary. | The module rejects `include_entities`, resets editor world state, serializes `MapEditorMapSnapshot`, saves/loads map documents, patches tiles, places/deletes catalog objects, and exposes walkability/visibility/light layers. | Replace catalog dependencies on `dnd.items.test_items` before productizing. Keep scenario-owned actors, factions, controllers, and victory rules out of this module. |
| `server.api_models` MapEditor models | product/game-mode architecture | Keep as the API schema contract for MapEditor integration. | `MapEditorMapSnapshot`, saved map documents, tile patches, catalog entries, walkability, visibility, and light responses use Pydantic `Field(description=...)`. | Continue the Pydantic metadata audit for non-MapEditor API models; decide whether schemas should be generated for the external MapEditor client. |
| `/home/tommaso/Dev/MapEditor` | product/game-mode architecture | Keep external. Integrate through backend APIs and durable map documents, not by merging projects. | The README calls it a standalone generative isometric map editor; the D&D backend is optional through `VITE_MAPEDITOR_BACKEND_BASE`. TypeScript `MapDocument` owns grid bounds, tiles, floor objects, asset placements, generation settings, and saved map metadata. | Define the stable document/API handoff between MapEditor-owned entity-free spaces and scenario-owned actors/controllers/objectives. |
| `ai.models` tactical data models and scoring helpers | product/game-mode architecture | Keep as the agent-facing decision contract, separate from D&D engine objects. | `TacticalState`, `ActionOption`, `TargetOption`, `AttackData`, `SpellData`, `ActionResult`, and EV helpers model the subjective tactical surface. All public Pydantic fields now have `Field(description=...)`, and Chapter 26 guards that contract. | Expected-value approximations must stay documented as agent scoring heuristics, not engine rules. Continue broader AI primitive and agent hygiene. |
| `ai.primitives` and `ai.agents` | product/game-mode architecture | Keep as reusable AI decision patterns over `GameInterface`. | Behavior trees, utility scorers, composites, `BaseAgent`, `BehaviorTreeAgent`, `UtilityAgent`, and example fighter/archer agents choose through tactical state and interface calls. Chapter 27 guards the no-comment-scaffolding contract for behavior trees, state machines, utility scoring, composites, and agent runners; `CompositeResult` and `ScoredOption` now expose `Field(description=...)` metadata. | Continue behavior-quality tests as new agent patterns are added. Expected-value scoring still remains tactical ranking, not engine combat truth. |
| `ai.interface.LocalGameInterface` | product/game-mode architecture | Keep as the local in-process adapter between live engine objects and agent-facing tactical models. | `LocalGameInterface` imports engine dependencies at module scope, translates live `Entity` state into `TacticalState`, and executes selected rows through `execute_by_index`. `tests/manual/test_26_agent_tactical_interface.py` guards against function-local imports. | Continue adapter tests as tactical models evolve. If remote agents become primary, add a separate HTTP-backed `GameInterface` implementation. |
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
6. The AI package is product/game-mode architecture above the engine.
   `LocalGameInterface` is the local D&D adapter and imports engine
   dependencies at module scope. Future remote agents should use a separate
   `GameInterface` implementation rather than weakening this boundary.

## Known Risks To Carry Forward

- `server/mapeditor_support.py` currently builds parts of the MapEditor catalog
  from `dnd.items.test_items`, which is too demo-flavored for a product
  authoring contract.
- `dnd.scenarios.*_training` modules are legitimate public tutorial surfaces,
  but their namespace makes them look more final than they are.
- `server/event_server.py` combines simulation, sessions, events, MapEditor,
  streams, and arena routes in one large API module.
- `data/mapeditor/maps/*.json` appears to be local saved output. It should not
  become source truth without curation.
- Expected-value helpers in `ai.models` are agent scoring heuristics. They must
  stay documented as tactical estimates rather than engine combat rules.
