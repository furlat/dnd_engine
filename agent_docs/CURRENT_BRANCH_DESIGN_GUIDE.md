# Working in the D&D engine recovery branch

Current branch: `codex/recovery-design`, based on `codex/july-reconstruction`
at `16a6bfe`. Start with [RECOVERY_PLAN.md](../RECOVERY_PLAN.md) for the objective,
NeuroStudio/async/height framing, ordered work and design gates. Historical
analysis is separate in [HISTORY_BEFORE_ME.md](../HISTORY_BEFORE_ME.md).
This guide is an owner and evidence map, not permission to expand a task.
For the detailed 2026-09-08 reread, use [CURRENT_CODEBASE_STUDY.md](CURRENT_CODEBASE_STUDY.md).
It records interception, condition/handler ownership, complete lineages, spatial
consequences and NeuroStudio playback, with exact coverage and validation limits.
Before proposing another implementation cut, follow its [next-change guard](CURRENT_CODEBASE_STUDY.md#cross-owner-conclusions-and-the-next-change-guard).
Its original study was made on 2026-09-07 at `24f293d` plus the working candidate;
that candidate was subsequently committed in the `16a6bfe` baseline.

## 1. Read the right authority

Start with [AGENTS.md](../AGENTS.md), the bounded plan for the requested work,
its applicable amendments, and the current owner code. Read
[HOW_TO_TEST.MD](../HOW_TO_TEST.MD) before writing tests. Keep AGENTS.md small.

The earlier study's modified files and untracked Pygame candidate are now
part of the committed baseline. The overnight experiment is preserved separately
on `astra_gogogo`; its combat playback is not present on this branch. Historical
verification records describe their own candidates, not fresh acceptance of
future changes. Consult Git and the recovery plan for current work status.

Historical precedence, adapted from the accepted recovery audit:

| Evidence | Legitimate use |
| --- | --- |
| Current branch code and applicable accepted plans | Current owners, contracts, scope and implementation direction |
| Current candidate and its verification records | What is implemented locally; distinguish this from fresh acceptance |
| `513dd97` (`pygame_again` / `zaczac`) | Accepted gameplay capabilities and authored values; not whole-file architecture |
| `4ebe523` | July ownership and original behavior/data where later evidence is absent |
| `1f2e525` (`broken`) | Forensics only; no implementation authority |

The recovery audit's counts and starting-state statements describe `205fd67`,
not today's tree. The Steps 11–12 plan describes its own pre-implementation
starting point. The minimum V-1 plan still says implementation has not begun,
although the local application exists. Read subsequent records and code.
README.md contains mixed-age examples: its generic advice to implement
conditions through subconditions and its cleanup description must not override
the current direct condition ownership and prepared removal graph.

## 2. Historical context

[HISTORY_BEFORE_ME.md](../HISTORY_BEFORE_ME.md) contains the broader source-backed
study of the original engine, hosting/content/reduction failures, NeuroClient,
July reconstruction, height work and the overnight experiment. Its reference
map distinguishes accepted capabilities from rejected machinery. The current
forward decisions and stages are in [RECOVERY_PLAN.md](../RECOVERY_PLAN.md).

## 3. Mechanics ownership

| Concern | Current owner and contribution rule |
| --- | --- |
| Entity | `dnd/entity.py`: data aggregate and system composer; compose existing blocks, do not add a parallel actor/controller model |
| Component state and values | `dnd/blocks/`, `dnd/core/base_block.py`, values/modifiers: mutate through the owning component and preserve source ownership |
| Actions/reactions | Existing authored lifecycle, validation, targets, cost and consequences; input and scripts choose, owners execute |
| Conditions | BaseBlock indexes and traverses the condition graph; each condition cleans its own modifiers, handlers and owned artifacts |
| Spatial conditions | `dnd/spatial/`: independent footprint/lifecycle owners; do not force them through ordinary Entity-condition cleanup |
| Creature life state | `Health.life_state` stores truth; Entity coordinates its production transitions and capability effects; no parallel DYING/STABLE/DEAD conditions |
| World | GridMap owns Tiles, placement, occupancy, traversal, support elevation, optics, light and spatial invalidation |
| Deployment | `dnd/game.py`: one passed Game owns deployed Entities and their removal |
| Combat | `dnd/encounter.py`: initiative, turns, action orchestration and authoritative combat-log sequence |
| Events | `dnd/core/events.py`: concrete phase facts; EventQueue stores/routes/records lineage and invokes existing dependency-inverted seams |
| Observer semantics | `dnd/blocks/sensory.py`, `dnd/subjective_combat_log.py`: engine-owned senses and pure event-time information reduction |
| Presentation | `game/`: detached scene values, assets, projection, drawing, clocks, input and diagnostics |

Rules applying across those owners:

- Follow the import DAG. No `dnd -> game`, Pygame, server or SDK dependency.
  Generic owners must not import concrete authored content back. Neutral
  types belong at existing dependency leaves. Count local imports in checks.
- No late imports, `getattr` dispatch or type-checking tricks to evade an
  ownership problem. Finite exact-class admission at a proven Event boundary
  is not permission for a generic runtime type dispatcher.
- Preserve component methods and actual authored hooks. Do not manufacture a
  manager/service/controller hierarchy, a second ECS or a free-function rewrite.
- Conditions implement their own rule capabilities. Use subconditions only
  for genuinely distinct named conditions, not synthetic inheritance of effects.
- Cleanup follows recorded ownership. Current BaseBlock removal prepares the
  graph before mutation and commits descendants before their owners. Preserve
  cancellation/non-mutation behavior and avoid registry scans as cleanup policy.
- Preserve source-specific modifier channels, handler registrations and their
  exact removal handles. Register Entity-owned handlers once through the owner.
- Distinguish a rejected mutation from a committed mutation whose publication
  fails. Follow the owning API's error contract; do not apply a blind rollback.
- Existing registries and EventQueue have process-wide state. The in-process
  milestone uses one serialized mechanics path and the existing runtime reset;
  a new Game object is not a separate engine universe.

## 4. Causality, cold construction and reduction

Normal construction order is cold world, `WorldInitializedEvent`, ordinary
dynamic hazard/light activation, Entity composition/birth, then Game deployment.
`Entity.create()` is provisional; `compose_entity()` validates and publishes
one birth fact. Failed provisional construction cleans up through
`discard_uncommitted()`. Do not deploy through throwaway Games or publish
partial worlds. Keep dynamic activation out of the cold snapshot lifecycle.

Events are typed phase records. Phase versions have distinct UUIDs within a
lineage; causal parents are not simply previous phases. Store and inspect the
authoritative order. Do not reconstruct it from timestamps or collapse all
versions to a guessed terminal. Existing pre-completion systems settle the
causal mechanics before the owning terminal. COMPLETION is not another
cancelable handler-driven mutation stage.

Existing typed Event payload hooks, participant/affected-position accessors,
log generation and phase/lineage methods remain lawful. They describe or
publish the Event through its established contract; they must not take over
world, sensory or condition mechanics.

`WorldModifiedEvent` groups completed structural authoring edits with cold
before/after facts. Ordinary opening, ignition, damage, movement and sensory
changes keep their concrete Event paths. A structural completion must not
produce a second mechanics cascade or duplicate a door/torch state event.

The current presentation path is:

```text
public engine operation, synchronously completed
  -> inspect the closed EventQueue interval in storage order
  -> primitive objective diagnostics + same-model subjective text
  -> detach only explicitly admitted passive concrete Events
  -> reduce cold target values and observer sensory values
  -> draw and settle the corresponding presentation interval
```

“Closed interval” means the mechanics operation has returned. The current
cursor API uses the half-open range `[start_cursor, end_cursor)`.
Capture/reduction must be generation-qualified and reject stale or partial
ranges. Finished detached values must remain usable after engine reset.

One Event type space does **not** mean every Event is safe to copy. Admit a
family only after proving its entire payload passive, including inherited
fields. Current capture also excludes any non-None context (including `{}`), combat logs and
effective-handler presentation payloads from detachable Events. No production
reflection walker or generic serializer substitutes for a family-specific proof.
An unsupported Event stays in the objective queue and has explicit coverage;
do not silently consume it or guess its animation.

Observer reduction uses event-time evidence, not later live visibility.
Identity, exact location and explicit coordinate grants are separate. Hidden
UUIDs, names, coordinates and nested summaries must not leak through text or
geometry. A visible child can retain a sanitized hidden parent in the same
`CombatLogEntry` model. Hidden log slots remain `None`, preserving source
indexes. Encounter range projection includes standalone logs and nested trees
without inventing duplicate top-level slots.

Each observer has its own sensory history. Party union does not mean replaying
one observer's deltas into another's state. Replay and the live Senses owner
share the current pure `reduce_senses_snapshot` calculation. The drawing code
uses disclosed visible/seen/contact/effective-light facts; it does not compute
FOV, darkvision, invisibility, stealth or magical darkness.

## 5. What the local Pygame application actually does

Launch from the repository root with `.venv/bin/python -m game`.
The current application is a map/door/light visual proof, not the full
two-character combat encounter. `game/app.py` builds
`battlefield.visual_vertical_seam`, composes one visual observer, deploys it
through Game, then performs real open and close door actions. The producer
yields startup/open/close intervals incrementally. It does not need a server,
SDK or character catalog to run this proof.

`game/presentation.py` currently admits four exact Event classes, restricted
to this observer and selected fixtures: `WorldInitializedEvent`, standing-torch
`ItemLocationStateEvent`, door-object `SpatialChangeEvent`, and
`SensoryUpdateEvent`. It does not currently admit `WorldModifiedEvent`, actor
animation or arbitrary combat Events. Objective cold world facts in this local
debug application are privileged data, not a ready-to-export player protocol.

The module split is concrete:

- `presentation.py`: synchronous capture, detached reduction and dispositions;
- `projection.py`: forward/inverse isometric projection, camera and support picking;
- `assets.py` and `game/data/*.json`: explicit finite bindings and derived surfaces;
- `water.py`: bounded procedural water raster work;
- `app.py`: composition, frame pump, drawing, diagnostics and interval settlement.

Preserve `E >= R >= D`: engine committed cursor, inspected/reduced cursor,
and visibly settled cursor. Ambient water/flame time is separate from Event
progress. Engine execution does not sleep for animation. Future human commands
wait for the relevant presentation boundary; autonomous mechanics may advance.
The two ordinary queues are in-process handoffs, not a protocol framework.
Queue emptiness does not establish success: required draw evidence and semantic
parity must close pending obligations. Failure/cancellation and reset must not
permit stale display work to settle a new generation.

### Current debug disclosure exceptions

The full-map amendment intentionally exposes all 4,096 static terrain supports
and static structural geometry from detached cold facts. Never-seen structure
is marked `authored`. This is an objective debug exception, not general player
knowledge. Door leaf/open state still needs current object contact. Static
geometry must not settle an undisclosed dynamic state obligation.

Composite wall/frame sprites use neutral treatment when current or authored;
they cannot independently shade inner and outer faces. Terrain/water use
engine-provided effective light when visible. The later doorway follow-up makes
memory RGB equal to authored RGB in this debug view while retaining distinct
memory provenance, absent current light and frozen remembered water. Equal
color does not mean equal knowledge. Do not restore older face-light rules or
darker memory treatment from superseded prose.

### Geometry and asset laws

- XY remains the engine coordinate; support elevation is in five-foot steps.
  Current projection uses a 128x64 diamond and 64-pixel lift per elevation step.
  Pixel lift does not create adjacency, 3-D FOV, physics or stacked floors.
- Walls and doors belong to an explicit side of a particular Tile. Opposite
  incident owners remain distinct. Sprite composition may combine compatible
  sides for drawing while retaining their exact identities and evidence.
- Forward/inverse projection has one owner. Camera turns preserve the engine
  center anchor; zoom preserves the cursor anchor. Pick actual detached
  supports at their elevations, not an imagined screen-grid coordinate.
- Pivots, contacts, Z offsets, painter order and composition role are distinct.
  Objects use `WorldObjectPlacement.base_height_steps` for their blit contact,
  not the owner Tile elevation or object top height. Painter order uses the
  composition phase and unlifted camera-rotated ground contact, not lifted
  screen Y or elevation as a sorting shortcut.
  Art uses explicit four-pose tables; do not rotate PNGs or infer gameplay
  material/blocking from names or editor metadata.
- Current cliffs/stairs retain one support per XY. The supported stair raster
  spans three actual supports with separate light/knowledge facts. Unsupported
  runs fail visibly. The debug grid is an X-ray overlay; support picking is
  not pixel-accurate cliff-face selection or multi-floor topology.
- Concrete files, frames, pivots and VFX choices belong to client data. Engine
  semantic IDs describe meaning. Missing/contradictory bindings fail visibly;
  no filename guess, nearest match, renderer registry or backend fallback.
- NeuroMapEditor/MapEditor/NeuroClient are evidence for selected art, projection
  and rigs, not architectures to port. Local copied assets make the runtime
  independent of those external checkouts.
- Optimize measured work through existing owners. Preserve pixels, painter
  order, disclosure and Event evidence. Do not turn a frame-time regression
  into a scene-graph, spatial-index or scheduler rewrite.

## 6. Recovery sequence and unfinished work

The [architecture roadmap](../DND_IN_PROCESS_PYGAME_SYSTEM_ARCHITECTURE_ROADMAP_2026-09-02.md)
defines incremental gates, not authorization for the whole program at once:

| Stage | Outcome |
| --- | --- |
| V-0 + minimum V-1 | Prove Event/information boundary through a real map, observer, assets and display terminal |
| V-1 expansion | Incremental world/ordinary state changes, camera, visibility and presentation evidence |
| V-2 | Scripted two-character/enemy encounter using public mechanics and explicit placeholder coverage |
| V-3 | Selected layered actor rigs and animation, with readiness and semantic parity |
| V-4 | Actual action/spell/spatial/light VFX required by the encounter |
| V-5 | Two-character input using existing discovery/typed targets and display pacing |
| V-6 | Authoring/editor bridge after the game seam is stable |

The content track is separate. CR-1–CR-3 direct items and CR-4–CR-5 direct
origins/characters are retained foundations. Builders use cold domain
definitions, semantic IDs and current component owners; character progression
records exact owned grants for removal. Do not revive a generic materializer
to assemble something that already has a direct builder.

CR-6 monsters, CR-7 scenarios/deployments, CR-8 static visual bindings, CR-9
remaining behavior families/bindings and CR-10 generic-runtime deletion remain
the roadmap's outstanding cuts. Some primitive behavior recovery was moved
earlier because direct items needed it; that does not complete all CR-9.

Runtime behavior attribution uses primitive `behavior_id`, `provided_by_id`
and optional `origin_root_id`: executable meaning, installing semantic owner
and originating root. Runtime UUIDs identify concrete instances; semantic IDs
identify authored meaning. Do not substitute a pack/version/hash identity for
either. Legacy admission metadata may still exist for deferred families, but
it must not reintroduce `ContentRef` into the recovered behavior fact shape.

`dnd/content_system`, `dnd/core/content`, backend visual metadata, server/AI/SDK
files and deferred persistence types still exist. Presence does not make them
the target architecture, and future deletion goals do not authorize deleting
their current consumers now. Freeze capabilities, recover exact values,
replace through current owners, prove behavior, then remove the bounded old
closure. Historical catalog counts are preservation evidence, not a demand to
keep a universal runtime registry. The roadmap allows V-2 to consume selected
existing legacy-backed public builders temporarily, with no new adapter and no
claim that CR-6/CR-7 are complete.

Current limitations requiring honest handoff:

- The general observer-safe ordinary-Event animation seam remains future work.
  The finite world/door/torch/sensory bridge is not its universal solution.
- The doorway/masonry join remains a recorded visual concern; correct source
  pivots alone do not establish visual acceptance.
- The latest cliff/stair record reports a grid-off overview median of
  **18.597 ms** at zoom 0.15, missing the **16.67 ms** gate. Zoom 0.5 measured
  13.825 ms. A concurrent application was observed, but that is not proof of
  cause or permission to mark the gate passed. These are recorded results,
  not measurements performed for this guide.
- The benchmark must include normal mouse picking: 1280x720, 60 warm frames,
  300 measured frames, prescribed pan/turn sequence, zooms 0.15 and 0.50,
  grid off for the gate and on for diagnostics. Omitting picking previously
  produced misleading performance evidence.

## 7. How to make the next change

First locate the current stage and apply the design gate in
[RECOVERY_PLAN.md](../RECOVERY_PLAN.md). Observed implementation is not itself
an accepted behavior contract, especially when reading the overnight branch.

Stay inside the user request and existing bounded plan. Identify the current
owner, observable input/output, allowed files, relevant amendment and stop gate
before editing. Ask for guidance when a real scope/architecture decision is
missing; do not add neighboring work because it seems beneficial.

Every implementation plan includes correctness, **anti-slop reviewer** and
**anti-OOP/ECS/import-DAG reviewer** gates. Reviews apply to the actual candidate;
material repairs invalidate affected approval and require rerunning its proof.
Anti-slop asks whether every abstraction/state/cache has a demonstrated need.
Anti-OOP asks whether ownership and dependency direction remain intact, rather
than counting classes or banning legitimate component methods.

Testing follows HOW_TO_TEST.MD: behavior as data, public input, observable
state/Events/output, and important non-mutation on rejection. Prefer a small
shared check helper over private-method mocks. Architecture tests enforce
explicit dependency policy; they do not prove gameplay. Select affected lanes
and required plan gates; do not restore historical server tests by resurrecting
their infrastructure. Visual requirements need actual rendered evidence and
inspection, and performance claims need the specified measured interaction.

Useful current entry points:

| Question | Code/proof to read |
| --- | --- |
| World and birth chronology | `dnd/entity.py`, `dnd/game.py`, `dnd/scenarios/battlefield_catalog.py`; `tests/engine/test_world_entity_initialization.py` |
| Structural versus ordinary changes | `dnd/core/gridmap.py`, `dnd/core/events.py`; `tests/engine/test_world_modification.py` |
| Subjective privacy and replay | `dnd/subjective_combat_log.py`, `dnd/blocks/sensory.py`; `tests/engine/test_subjective_combat_log_replay.py` |
| Conditions and cleanup | `dnd/core/base_block.py`, `dnd/core/base_conditions.py`; `tests/engine/test_condition_lifecycle.py`, `test_condition_transform_ownership.py` |
| Direct content | `dnd/content/items/`, `dnd/content/characters/builds.py`, `progression.py`, `premades.py`; corresponding CR architecture/engine tests |
| Actual presentation boundary | `game/presentation.py`; `tests/game/test_presentation_boundary.py`, `test_app_smoke.py` |
| Projection and visual composition | `game/projection.py`, `game/app.py`; projection, boundary, elevation, assets and water tests under `tests/game/` |
| Dependency ownership | `tests/architecture/test_dependency_boundaries.py` and current direct-content architecture tests |

## 8. Governing document map

- [Steps 11–12](../DND_JULY_RECONSTRUCTION_STEPS_11_12_IMPLEMENTATION_PLAN_2026-08-30.md): cold world, committed birth, same-model logs and sensory replay.
- [Content recovery audit](../DND_JULY_RECONSTRUCTION_CONTENT_RECOVERY_AUDIT_AND_MIGRATION_PLAN_2026-08-30.md): historical precedence, retained capabilities, rejected architecture and CR cuts.
- [Primitive behavior amendment](../DND_CONTENT_RECOVERY_PRIMITIVE_BEHAVIOR_FACT_SEQUENCE_AMENDMENT_2026-08-31.md): prerequisite behavior work moved ahead of item recovery.
- [Direct-item ledger](../DND_CONTENT_RECOVERY_DIRECT_ITEM_CR1_CR3_IMPLEMENTATION_LEDGER_2026-08-31.md) and [character ledger](../DND_CONTENT_RECOVERY_CR4_CR5_CHARACTER_IMPLEMENTATION_LEDGER_2026-09-01.md): implemented scope and recorded proofs.
- [World modification plan](../DND_WORLD_MODIFIED_EVENT_IMPLEMENTATION_PLAN_2026-09-02.md): structural completion ownership.
- [Minimum visual seam](../DND_PYGAME_V0_MINIMUM_V1_VERTICAL_SEAM_IMPLEMENTATION_PLAN_2026-09-03.md): finite admission, async/display obligations and first visual consumer; apply later amendments.
- [Corrective V2](../DND_PYGAME_V0_VERTICAL_SEAM_CORRECTIVE_IMPLEMENTATION_PLAN_V2_2026-09-03.md): incremental producer and removal of unnecessary cold bootstrap; later asset selections supersede its D8 proposal.
- [Boundary geometry/depth correction](../DND_PYGAME_V0_BOUNDARY_GEOMETRY_DEPTH_CORRECTION_PLAN_2026-09-03.md): placement-base contacts, unlifted depth and replacement of rejected A-wall proposals; current stone families are D1/D2/D6, with Door A1/A2 leaves. The full-map extension adds C1/C2 wood walls.
- [Full-map debug plan](../DND_PYGAME_V0_FULL_MAP_CAMERA_STRUCTURE_DEBUG_PLAN_2026-09-03.md): objective structural exception and camera/full-map proofs.
- [Neutral boundaries](../DND_PYGAME_V0_BOUNDARY_NEUTRAL_TREATMENT_AMENDMENT_2026-09-03.md) and [doorway follow-up](../DND_PYGAME_V0_DOORWAY_PRESENTATION_FOLLOWUP_2026-09-03.md): current composite-sprite treatment and debug memory override.
- [Actual-interaction performance](../DND_PYGAME_V0_ACTUAL_INTERACTION_PERFORMANCE_AMENDMENT_2026-09-03.md): mouse-enabled measurement contract.
- [Cliff/stair implementation and September 4 follow-ups](../DND_PYGAME_CLIFF_STAIR_IMPLEMENTATION_PLAN_2026-09-03.md): current support geometry, hover limits and latest recorded performance miss.

## 9. Study validation

This documentation pass inspected current owner code, local presentation code,
the cited recovery records and selected broken-branch sources without switching
branches. The focused command below passed **40 tests in 6.59 seconds**:

```bash
.venv/bin/python -m pytest -q tests/game/test_presentation_boundary.py tests/engine/test_subjective_combat_log_replay.py
```

Document links resolve and whitespace checks passed. The full gameplay,
architecture, visual and performance gates were not rerun for this documentation
change. Reported historical measurements above remain explicitly attributed
to their implementation records.

This guide records branch intent and observed implementation, not blanket
certification of all existing source. Update the affected statement when its
own implementation gate changes; do not accumulate abandoned plans here.
