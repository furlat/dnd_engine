# D&D in-process Pygame system architecture roadmap

Date: 2026-09-02  
Status: **accepted high-level architecture; implementation requires bounded practical plans**

For current branch ordering and the subsequent NeuroStudio/timeline framing,
start with [RECOVERY_PLAN.md](RECOVERY_PLAN.md). The broader retrospective is
[HISTORY_BEFORE_ME.md](HISTORY_BEFORE_ME.md). Checkpoint descriptions below retain
their historical context; the ownership laws remain the foundation.

## 1. Purpose

This document reconnects the current D&D reconstruction and content-recovery
program with the new in-process `pygame-ce` client. It defines system
authority, dependency direction, information flow, temporal behavior, and the
ordered product roadmap.

It is intentionally above implementation-plan level. It does not authorize
production code, prescribe a large class hierarchy, or settle every function
and file. Each implementation stage still requires one bounded practical plan
with proportional tests and independent correctness, anti-slop, and
anti-OOP/ECS review.

The target is a small but truthful game executable:

- one authored isometric encounter;
- two user-controlled characters from the direct character pipeline;
- a small enemy group;
- real movement, attacks, reactions, opportunity attacks, spells, light,
  visibility, walls, doors, water, and support elevation;
- objective and observer-subjective diagnostic rails;
- an engine that may advance independently of human-speed presentation; and
- a renderer whose pixels and animations are reductions of committed engine
  Events, never a second mechanics authority.

## 2. Current checkpoint

### 2.1 Accepted foundation

The current branch already contains the foundation needed to begin the visual
vertical slice:

- direct behavior-free and behavior-bearing item recovery through CR-1/CR-3;
- direct origins, three class/subclass progressions, custom character
  construction, and four premades through CR-4/CR-5;
- current ECS Entity composition and one committed birth boundary;
- in-process `Game`, `Encounter`, `GridMap`, actions, reactions, conditions,
  spatial conditions, visibility, lighting, and sensory settlement;
- directional Tile-owned walls and doors, world-item lifecycle, support
  elevation, and traversal connectors;
- renderer-neutral `WorldInitializedEvent` cold world state;
- renderer-neutral `EntityCreatedEvent` aggregate state;
- observer-owned `SensoryUpdateEvent` deltas and same-model subjective combat
  log projection; and
- an ordered `EventQueue` with generation and cursor boundaries suitable for
  inspecting closed intervals and detaching specifically admitted passive
  Event families.

The direct item and direct character cuts are accepted. The historical Tile /
world-item refactor work from the discarded branch is not authority for this
roadmap; the current July-reconstruction branch and its current proofs are.

### 2.2 Current worktree seam

The current worktree additionally contains the reviewed design and candidate
implementation for one structural-authoring root:

- `WorldModifiedEvent` groups one completed Tile, placed-world-item, or
  connector edit;
- its cold `before`/`after` values can update a detached structural scene;
- existing detailed spatial/object/connector Events remain the mechanics and
  sensory causes; and
- the world-level completion is passive materialization data, not a second
  cascade.

This seam is relevant to structurally placing, removing, moving, or orienting
doors, torches, and other world items, plus map editing and future GM
authoring. Ordinary door opening, torch ignition/extinguishing, damage,
destruction, movement, and spatial effects retain their existing concrete
Event paths. The implementation state must be certified or repaired by its own
plan; this roadmap does not silently promote an uncommitted worktree to an
accepted release.

### 2.3 Remaining content recovery

The original recovery program is not complete:

- CR-6: direct monsters;
- CR-7: direct scenarios, deployments, and encounters;
- CR-8: move static item/entity/map visual bindings into the Pygame/client
  domain and remove backend visual authority after coverage exists;
- CR-9: complete the remaining action/reaction/condition/spell/trait/feature
  behavior families and their presentation bindings; and
- CR-10: delete the generic content runtime, `ContentRef`, recipes,
  materializers, pack bootstrap, and obsolete tests.

Those cuts remain governed by the approved content-recovery plan. The visual
MVP does not falsely claim they are complete, but it also does not need to wait
for the entire catalog before drawing one exact encounter.

### 2.4 External presentation evidence

Three live WSL repositories have deliberately separate roles:

| Source | Reused authority |
|---|---|
| `NeuroMapEditor` | map lattice, explicit Z-grid projection offsets, asset occurrence presentation, visual composition, painter order, and alpha picking |
| `MapEditor` | original authoring ergonomics and fantasy asset evidence/catalog |
| `NeuroClient` | layered entity rigs, animations, VFX evidence, async presentation failures, and runtime diagnostics |

None is copied wholesale. Pygame is implemented in Python from the governing
laws and selected assets.

## 3. Target architecture

The final in-process program has one mechanics world and one presentation
projection:

```text
direct authored content
        |
        v
Game / GridMap / Encounter / ECS systems
        |
        | committed concrete Events in storage order
        v
synchronous closed-interval inspection
        |
        +----------------------> objective diagnostics / coverage
        |
        | only admitted recursively-passive concrete Events and cold facts
        v
observer-safe reduction inside the D&D information boundary
        |
        | same Event model space + authoritative sensory facts
        v
renderer target state
        |
        v
human-time presentation queue
        |
        v
pygame scene, animation, text, camera, and input

client asset-binding data ----------------------^ presentation only
```

The renderer may lag. It may never lead, repair, or reinterpret mechanics.

## 4. Non-negotiable system laws

### 4.1 One mechanics authority

- `Entity` remains a data aggregate and system composer.
- Blocks/components own their state and mutations.
- Actions and reactions own validation, cost, execution, and causal children.
- Conditions own condition and subcondition lifecycle.
- `GridMap` owns topology, Tiles, occupancy, world-item placement, elevation,
  connectors, optics, propagation, and spatial invalidation.
- `Game` owns deployed Entities.
- `Encounter` owns initiative, turns, action orchestration, and combat logs.
- Events report committed facts from those owners.
- Pygame owns no movement, targeting, damage, visibility, lighting, AI, or turn
  legality.

### 4.2 Event-first information flow

- Normal renderer change is traceable to stored engine Events.
- `WorldInitializedEvent` is the cold structural bootstrap.
- `WorldModifiedEvent` is the cold structural edit root when a structural
  authoring operation occurs.
- ordinary movement, action, condition, damage, lifecycle, and turn Events
  remain their own facts.
- `SensoryUpdateEvent` is the observer-specific spatial/light/contact fact.
- snapshots are bootstrap/recovery values, not a parallel live state bus.
- the renderer does not poll live mutable Entities or GridMap during drawing;
  and
- when an Event family lacks a passive after-value required by presentation,
  its existing mechanics owner adds that renderer-neutral fact to the same
  concrete Event family before the family is admitted asynchronously.

### 4.3 One Event type space

Objective and subjective consumers operate on the existing concrete Event
hierarchy. The observer-safe form must not become a second presentation Event
union such as cues, canonical views, visual transactions, or SDK envelopes.

This does **not** make every current Event detachable. Several lawful
synchronous Events carry live mechanics objects, including conditions. Generic
model copying, serialization, masking, or archival of arbitrary Events would
clone component graphs and create a shadow ECS. V-0 therefore inventories and
admits passive Event families one family at a time. Unsafe Events remain in the
authoritative objective queue and contribute synchronous diagnostic/coverage
evidence, but do not cross the asynchronous presentation queue.

The complete mechanism for withholding inaccessible fields on ordinary Events
is a named unresolved design seam. Before player-facing action animation uses
ordinary Events, it receives one surgical implementation plan. That plan must
preserve concrete Event identity, event ordering, causality, and existing
sensory/combat-log projection; it may not revive the rejected server/SDK
subjective runtime.

### 4.4 Presentation state is not game state

The client may own:

- a cold reduced target scene;
- displayed Sprite nodes and animation clocks;
- camera, zoom, camera quadrant, hover, and selection;
- asset textures and alpha masks;
- presentation queue progress and generation;
- objective/subjective text rails; and
- event coverage and semantic parity diagnostics.

It may not answer mechanics questions.

### 4.5 No network architecture in the in-process milestone

The first game has no server, SSE, SDK, replication journal, session lease,
transport schema, TypeScript conversion, cross-language identity, or database
in its execution path. The event boundary remains detachable and explicit so a
future process/network boundary can be added after the in-process behavior is
correct.

### 4.6 No speculative architecture

This program does not introduce a generic manager, service, controller,
command bus, presentation-event hierarchy, asset compiler, renderer binding
registry, callback chain, transaction framework, scene ECS, or content
materializer.

Small state values, pure projection/reduction functions, explicit queues, and
ordinary domain functions are preferred. A new abstraction is admitted only
when at least two real consumers demonstrate the same ownership law.

## 5. Dependency boundaries

### 5.1 Engine and content

```text
dnd/types
   |
   v
dnd/core + blocks + Entity + rules + spatial
   |
   v
dnd/content/<domain>/definitions and explicit builders
   |
   v
dnd/scenarios + in-process game composition
```

Mechanics packages never import Pygame or concrete asset paths. Cold content
metadata may contain semantic IDs, names, descriptions, and gameplay tags; it
does not contain renderer execution logic.

### 5.2 Observer reduction

Knowledge, perceivability, effective light, hidden/invisible state, and event-
time identity authorization are D&D information semantics. Their reduction
belongs with the engine/application information boundary, not inside Sprite
code.

The Pygame side receives already authorized values and applies display policy
such as visible, remembered, dimmed, or absent. It does not recompute FOV,
darkvision, truesight, magical darkness, invisibility, or hidden detection.

### 5.3 In-process application composition

The future top-level `/game` package is the Python application and presentation
domain. It may import public D&D builders, `Game`, `Encounter`, Events, and
client asset bindings. `dnd` never imports `/game`.

`/game` is not a second engine. Its responsibilities are limited to:

- construct the selected battlefield, two player characters, enemies, Game,
  and Encounter;
- run the engine on one serialized execution path;
- inspect closed Event intervals and detach only admitted passive Events/cold
  facts;
- feed objective diagnostics and observer-authorized presentation;
- own Pygame display/input/animation state; and
- close/reset both sides without stale presentation work.

### 5.4 Asset-binding data

Concrete PNG, sheet, frame, pivot, orientation, animation, and VFX choices are
client data keyed by engine semantic IDs and renderer roles. Three related but
distinct client-owned inputs are allowed:

1. an asset catalog containing concrete files and presentation metadata;
2. semantic bindings from engine facts/IDs to asset families; and
3. an optional battlefield presentation companion containing exact authored
   asset occurrences for a specifically decorated map.

The exact occurrence companion takes precedence over generic semantic
materialization for the occurrence it addresses. It never changes engine
topology or mechanics. Missing or contradictory catalog, binding, or
occurrence data produces a visible marker and diagnostic; there is no filename
guess, nearest match, or backend fallback.

The data should be JSON-compatible so a future TypeScript client can consume
the same authored mapping, but Python loads and validates it directly.

The engine owns meaning such as Tile material, wall/door identity, open state,
torch state, character body, equipment, action/spell identity, and status.
The client binding selects art for that meaning.

## 6. Temporal and async boundary

### 6.1 Three clocks

The application explicitly distinguishes:

```text
E = last mechanically committed engine cursor
R = last source cursor inspected/classified, with all admitted facts reduced
D = source cursor of the last presentation boundary visibly settled

E >= R >= D is legal
```

An unsafe Event may be classified for coverage at `R` without being copied into
renderer state. No conversion changes Event semantics between these clocks.

### 6.2 Closed interval capture

After an engine operation or causal batch, the application synchronously:

1. record generation and cursor bounds;
2. inspect the closed Event interval in storage order;
3. update the privileged objective text/coverage rail from the authoritative
   Events without retaining live mechanics objects;
4. deep-copy only concrete Event families whose complete payload has already
   been proven recursively passive and admitted by the practical plan;
5. mark unsafe/unadmitted families visibly unsupported until their owners
   publish sufficient passive facts;
6. revalidate generation;
7. enqueue the admitted detached values under one interval boundary; and
8. return immediately to the engine/application scheduler.

The capture boundary performs no rendering, awaits no animation, registers no
presentation callback in `EventQueue`, and never copies a live condition,
block, Entity, item, handler, modifier, or other mechanics owner.
Passivity is a per-family design/test gate, not a production reflection walker,
generic serializer, `getattr` scan, or runtime type-inspection framework.

### 6.3 Player and enemy pacing

- Engine execution never sleeps for animation.
- The two player-controlled characters share one human input side.
- A player command is submitted only when the relevant prior player-facing
  presentation boundary has settled.
- Once submitted, its complete mechanics and reactions execute immediately.
- Enemy turns may continue mechanically while their visual work accumulates.
- The next player command waits until presentation reaches the declared player
  boundary, so the user never chooses from a visually stale situation.

This is an application scheduling policy, not an Encounter mechanics rewrite.

### 6.4 Presentation terminals

Queue emptiness is not success. One required interval/root has one presentation
terminal and a plain `event_uuid -> disposition` coverage map. The interval
settles only when:

- every disclosed Event has one closed coverage outcome;
- every required animation completed, failed, or was explicitly cancelled;
- assets required by that interval loaded;
- displayed semantic state matches reduced target state for the owned fields;
  and
- the presentation generation is still current.

This does not create terminal objects for each Event, asset, or animation.

Reset retires the old generation so stale work cannot mutate the new scene.

## 7. World, projection, and map rendering

### 7.1 World authority

The engine position remains `(x,y)`. Tile support elevation remains an engine
fact in five-foot steps. Pygame applies an authored Z-grid pixel offset to the
support contact; it does not create 3D mechanics or change engine coordinates.

Walls and doors remain concrete world items on an explicit side of one Tile.
Both incident Tiles may own adjacent structures. The renderer must not merge
them into a canonical between-cell edge.

### 7.2 NeuroMapEditor laws retained

- macro128 is the first lattice: one 128x64 diamond per engine Tile;
- fine64 remains deferred until a real selected asset/map requires it;
- Z-grid identity, pixel projection offset, and painter order are independent;
- a Sprite occurrence has an explicit world anchor and presentation pivot;
- occurrence offsets do not change world ownership;
- visual composition roles do not imply gameplay height or walkability;
- planar and spatial composition are explicit;
- painter ties are deterministic; and
- support-cell picking is the first seam; transformed bounds plus source-alpha
  narrow phase is admitted only when the first overlapping selectable object
  actually requires Sprite picking.

### 7.3 Camera

The first renderer supports:

- WASD pan;
- cursor-centered zoom;
- four camera quadrants;
- one forward/inverse projection owner;
- direction-to-camera asset-family selection without raster rotation; and
- exact mouse diagnostics including screen/world pixel, engine `(x,y)`, Tile
  UUID, support height, Z-grid offset, candidate contacts, and chosen contact.

Camera state is renderer-local.

### 7.4 First asset subset

The first map deliberately uses only enough assets to prove boundaries:

- one ground family;
- water;
- one wall family;
- the matching door frame and open/closed leaf;
- one lit/unlit torch or fire object; and
- one elevated support/transition family after the flat seam is proven.

Additional asset coverage is incremental, data-driven work rather than a
runtime inference problem.

Open/closed door and lit/unlit emitter art becomes renderer-owned only after
V-1 has characterized and admitted the existing ordinary state-bearing Event
families. Door blocking/open state currently belongs to its ordinary spatial
object-change path; flame and resolved-light changes belong to their existing
flame/light/sensory paths. If one of those Events lacks the complete passive
after-value needed by the renderer, the responsible item/GridMap/light owner
adds that value before the dynamic visual is enabled. `WorldModifiedEvent` is
not used as a redundant substitute.

## 8. Entities and animation

### 8.1 Entity target state

The renderer reduces entity creation, placement, movement, health/life,
equipment/appearance, conditions, perception contacts, and removal into cold
display facts. Stable Entity UUID remains the display identity. A Sprite rig
never becomes an Entity authority.

### 8.2 NeuroClient evidence retained

The actor phase recovers, from first principles in Python:

- semantic engine-to-rig bindings;
- body and equipment layers;
- exact layer order;
- one shared animation clock across a rig;
- directional rows and clip/frame metadata;
- ground, body, shadow, and effect anchors;
- atomic rig readiness;
- generation-fenced asset loads only if loading actually becomes asynchronous;
- movement, attack, reaction, cast, hit, downed, and death transitions; and
- visual status overlays whose state derives from Events.

The NeuroClient class/controller/store hierarchy is not ported.

The small MVP asset set should be synchronously preloaded before play. It does
not justify an asynchronous loader subsystem. Later actor rigs may add bounded
asynchronous loading when measured need exists, while retaining the same
generation and atomic-readiness laws.

### 8.3 Placeholder policy

Before the full rig phase, a semantic badge/marker may represent an Entity if
and only if coverage records the intentional placeholder. Missing actor art
must never make an Entity disappear silently.

## 9. VFX, light, and visibility

VFX is a later presentation layer on the same event seam:

- weapon swings and impacts;
- projectiles and spell travel;
- persistent areas and spatial-condition visuals;
- light-emitter appearance;
- condition/status feedback; and
- event-specific camera/audio decoration if later desired.

Mechanical light and observer-effective light are engine facts. Pygame may
tint/overlay disclosed cells and display an emitter Sprite, but the Sprite does
not create illumination. Magical darkness, darkvision, truesight,
invisibility, and hidden state are already reduced by engine senses.

Initial item presentation state is not enough for a live visual. Every dynamic
door, emitter, health, charge, condition, and similar field admitted by the
renderer needs an ordinary committed after-value reducer or remains an explicit
unsupported placeholder. The first practical plan inventories only the fields
used by its selected assets.

Decorative VFX may fail locally without corrupting mechanics. A required
state-bearing visual must fail visibly and prevent a false presentation
acknowledgement.

## 10. Scripted encounter as the integration oracle

The first executable product is a self-playing, authored encounter rather than
a complete UI.

### 10.1 Authored setup

- one small capability map using the selected asset subset;
- two user-side direct characters;
- a small enemy side;
- deterministic initial deployment and action script;
- live dice rolls unless a focused test injects deterministic results; and
- no server, persistence, character creator, menus, or campaign shell.

### 10.2 Script coverage

The script should exercise, in a readable sequence:

- world initialization and deployment;
- camera/map projection and visibility initialization;
- both user characters taking turns;
- movement across ordinary/water/elevated support;
- attacks, damage, downing/death as appropriate;
- opportunity attack/reaction ordering;
- one spell with projectile or impact evidence;
- one persistent/spatial effect;
- a door state change;
- a torch/light or darkness change;
- subjective visibility/contact change; and
- encounter completion or an explicit scripted stop.

The script names actions and targets in advance but uses the public action and
Encounter paths. It does not directly mutate combat state to obtain visuals.
The script is only a decision source: it chooses among the same discovered
actions/typed targets that later player input or enemy AI will choose. Engine
owners still validate and execute every choice. No new controller base class
or command model is introduced for the script.

### 10.3 Debug product

The executable shows text even before all art exists:

- objective Event rail;
- active-observer subjective Event/log rail;
- current engine/reducer/display cursors;
- presentation queue and active generation;
- mouse/grid/Z diagnostics;
- unsupported/failed visual badges; and
- target-versus-displayed semantic parity failures.

This makes visual feedback and automated evidence complementary.

## 11. Event coverage and parity

Every consumed Event receives exactly one terminal presentation disposition:

- `represented`;
- `state_only`;
- `diagnostic_only`;
- `not_disclosed`;
- `unsupported`; or
- `failed`.

Coverage is diagnostic data keyed by existing Event UUID/lineage. It is not a
second event hierarchy and does not mutate the Event.

The objective rail is populated synchronously from primitive Event identity,
kind, phase, lineage, and already-generated `CombatLogEntry` values. It does
not retain an unsafe Event or later call its live mechanics payload from the
renderer task. The first implementation may use plain mappings/rows; no
diagnostic record hierarchy is required.

At declared acknowledgement boundaries, semantic facts owned by the renderer
are compared between target and displayed state. The comparison concerns
identity, contact, pose/state, disclosed visibility, door/torch state, and
other admitted render facts—not raw pixel equality.

## 12. Content-recovery and Pygame coordination

The visual and recovery tracks join at explicit points:

| Recovery cut | Relationship to the visual track |
|---|---|
| CR-6 direct monsters | expands exact enemy construction and behavior coverage; does not block the first map/projection seam |
| CR-7 direct scenarios | replaces remaining generic encounter construction; the scripted MVP becomes one public in-process consumer and proof |
| CR-8 static bindings | expands the Pygame binding data established by the MVP, then removes backend item/entity/map asset authority only after coverage |
| CR-9 behavior bindings | maps remaining action/spell/condition/trait semantic IDs to actor/VFX presentation while completing their mechanical hard cuts |
| CR-10 generic deletion | certifies the final direct in-process game with no generic content runtime or backend renderer authority |

No temporary backend visual system is introduced while waiting for CR-8.
Bindings selected for the MVP begin in their final client-owned domain.

CR-6 and CR-7 may proceed alongside map-renderer work when they do not touch
the same ownership seams. CR-8 and CR-9 require the client binding format to be
proven first. CR-10 remains last.

The scripted MVP does not wait for the complete CR-6/CR-7 catalogs. It may use
the current public battlefield and selected monster builders already present in
the checkout and compose one application encounter explicitly. If one selected
public builder is still backed by the legacy generic runtime, V-2 may consume
that existing path temporarily; it adds no adapter, facade, alternate monster/
scenario materializer, or new legacy dependency. Such a demo is downstream
product evidence only and never counts as CR-6 or CR-7 direct-content
acceptance. Those cuts later migrate the same public capability under their own
complete inventory and deletion gates.

## 13. Ordered roadmap

The names below use `V` for the visual/in-process track and retain `CR` for the
existing content-recovery track.

### V-0 — event and information-boundary closure

- Characterize closed Event interval inspection from the current queue.
- Inventory the first consumer's Event families and admit asynchronous copying
  only when every payload is recursively passive.
- Name that bounded admitted family set explicitly; add no generic runtime
  passivity scanner or event registry.
- Keep unsafe live-mechanics Events in the synchronous objective diagnostic /
  coverage path; do not serialize, clone, mask, or archive them.
- Add missing renderer-neutral after-values through the existing owning Event
  family before admitting that family.
- Design and implement the smallest observer-safe reduction for ordinary
  concrete Events without a parallel event ontology.
- Reuse current sensory deltas and combat-log projection.
- Define renderer target-state ownership and terminal coverage dispositions.
- Prove the async observer/renderer consumers never consult live mutable state
  after an admitted value crosses the boundary.

Gate: one closed causal interval can feed synchronous objective diagnostics and
one observer-authorized async reducer using only admitted passive concrete
Events, with preserved ordering/lineage and no shadow component graph or
server/SDK type.

### V-1 — Pygame map and async presentation seam

- Create the minimal `/game` package and pygame-ce frame pump.
- Compose one current battlefield in-process.
- Load the selected NeuroMapEditor-derived asset subset.
- Load its asset catalog, semantic bindings, and optional exact battlefield
  occurrence companion with explicit precedence.
- Render macro128 terrain, water, walls, door, torch/light, and one elevation
  case.
- Implement pan, zoom, four quadrants, grid overlay, and Z-aware picking.
- Reduce `WorldInitializedEvent`, admitted `WorldModifiedEvent`, sensory
  changes, and the minimum ordinary object/flame/light after-value Events into
  target/display state.
- Characterize and repair any passive fact gap before open/closed or lit/unlit
  art is treated as state-bearing.
- Establish async engine/reducer/display clocks, generation reset, text rails,
  coverage, and parity.

Gate: structural world changes and observer knowledge update incrementally
without a board rebuild, live-engine polling, or mechanics duplication.

### V-2 — scripted encounter and placeholder actors

- Build the two-character plus enemy encounter through current public
  battlefield/character/monster builders plus `Game`/`Encounter`, under the
  temporary CR-6/CR-7 rule in Section 12.
- Add no demo-only content construction path and claim no CR-6/CR-7 completion.
- Execute the complete authored action script with live rolls.
- Represent every Entity and action at least by semantic markers/text.
- Exercise the player-boundary wait and enemy-ahead scheduling policy.
- Close every Event with a coverage outcome.

Gate: the encounter runs end to end while the engine can advance ahead of
human-time presentation and no event disappears silently.

### V-3 — complete entity Sprite and animation recovery

- Port selected actor assets and then the complete admitted layered-rig system
  from NeuroClient evidence.
- Bind creation, deployment, movement, action, reaction, damage, condition,
  downed, death, and removal state.
- Replace semantic markers only when the real rig has atomic readiness and
  parity proof.

Gate: the scripted encounter is readable entirely through real actor rigs and
animation, with placeholders remaining only for explicitly deferred catalog
rows.

### V-4 — action, spell, spatial, and light VFX

- Add data-driven bindings for the encounter's actual action/spell/condition
  families.
- Add projectile, impact, persistent-area, status, emitter, and visibility
  presentation.
- Expand only from actual unsupported coverage records.

Gate: all mechanically important Events in the scripted encounter are
represented or intentionally state/diagnostic-only; decorative failures do not
block mechanics.

### V-5 — two-character interactive input

- Replace the user-side fixed script with a minimal turn/action/target input
  surface for both characters.
- Use existing action discovery and typed targets.
- Keep enemy execution autonomous and renderer-independent.
- Preserve the same presentation boundary before accepting each new player
  command.

Gate: switching between two user-controlled characters requires no new game
authority and produces the same Event/presentation path as the script.

### V-6 — authoring/editor bridge after the game seam is stable

- Use the existing world-authoring operations and `WorldModifiedEvent` to edit
  the running structural world.
- Optionally expose a small live GM/map-authoring surface.
- Persist authored world history only as cold initialization plus completed
  structural edits if a real save/use case is approved.

Gate: authoring uses the same world owners and renderer reduction as gameplay;
it does not add a second map model or replay framework.

### Recovery closure — CR-6 through CR-10

Complete the remaining approved content cuts at their governed gates, using
the proven `/game` binding domain and scripted encounter as downstream
consumers. The final result removes the generic content runtime and retains
the Pygame application as an ordinary client of direct in-process D&D content.

## 14. The first practical plan after this roadmap

The next document should cover **V-0 and the minimum V-1 vertical seam needed
to prove it**. They should not be implemented as unrelated foundations:

- one real `WorldInitializedEvent` interval enters the bridge;
- one observer-authorized reduction feeds a renderer target scene;
- pygame draws the macro grid and first asset family;
- the objective and subjective rails show the same interval at their lawful
  information levels;
- pan/zoom/quadrant/picking diagnostics operate on that displayed scene; and
- presentation returns an exact terminal.

The practical plan should stop before full actor rigs, spells/VFX, interactive
commands, full asset migration, CR-6, or generic content deletion.

## 15. Explicitly rejected directions

- Porting NeuroClient's server/SSE/SDK/journal/cue/transaction pipeline.
- Recomputing visibility, light, or mechanics in Pygame.
- Polling live engine objects each frame.
- Treating renderer target state as an authoritative world.
- Canonicalizing two Tile-owned walls into one shared edge.
- Encoding support height into engine pixel positions or general 3D physics.
- Runtime filename inference, asset matching, reconstruction, or fallbacks.
- Copying NeuroMapEditor's Unity import, causal-height, or enclosure-repair
  machinery into the game.
- Copying NeuroClient's store/controller/class hierarchy.
- Creating a generic animation/VFX recipe language before real repeated
  bindings require shared data.
- Moving visual asset paths back into engine/content mechanics.
- Blocking the engine thread on animation time.
- Treating queue idle as successful presentation.
- Building networking, persistence, campaign UI, character creation UI, or a
  general map editor before the scripted encounter works.
- Reintroducing generic content/runtime aliases to accelerate the demo.

## 16. Program-level acceptance

The roadmap is complete when:

- one fresh Python process builds direct content, Game, world, and Encounter;
- the two-character encounter runs without server, SDK, or TypeScript;
- objective mechanics and observer-subjective presentation are both derived
  from the same ordered engine Event history;
- map, actors, animations, light/visibility, and admitted VFX converge through
  explicit target/display state;
- the engine can advance ahead of presentation without causal corruption;
- player input never acts on a visually stale acknowledged boundary;
- every delivered Event has a closed presentation disposition;
- concrete assets are client-owned bindings over semantic engine facts;
- CR-6 through CR-10 ultimately remove the remaining generic content closure;
- mechanics packages import no Pygame/assets/server/SDK code;
- no compatibility facade, dual authority, manager/service/controller layer,
  callback chain, reflection, late import, or circular dependency was added;
  and
- the final executable and each implementation cut receive correctness,
  anti-slop, and anti-OOP/ECS approval.

## 17. Review record

The first independent round produced:

- anti-slop: **APPROVE**, with three narrow tightenings;
- anti-OOP/ECS/dependency-DAG: **APPROVE**; and
- correctness/completeness: **REJECT**, identifying four substantive gaps.

The candidate was corrected before acceptance:

1. arbitrary Event-interval cloning was replaced by synchronous objective
   inspection plus explicit per-family admission of recursively passive Events;
2. client data was split into asset catalog, semantic bindings, and an optional
   exact battlefield occurrence companion;
3. ordinary door/flame/light after-value reducers became a V-1 gate rather
   than being misattributed to `WorldModifiedEvent`; and
4. V-2's temporary relationship to unfinished CR-6/CR-7 was made explicit,
   with no adapter, alternate materializer, or acceptance claim.

The anti-slop tightenings also established one interval terminal plus a plain
coverage map, support-cell picking before alpha-mask object picking, and
synchronous preload for the small MVP asset set.

All three reviewers then re-read the corrected candidate:

- correctness/completeness: **APPROVE** — current code, accepted content
  recovery, world-authoring boundaries, passive Event limits, and sequencing
  are consistent;
- anti-slop: **APPROVE** — no speculative loader, registry, event ontology,
  diagnostic hierarchy, or presentation framework is authorized; and
- anti-OOP/ECS/dependency-DAG: **APPROVE** — existing mechanics owners remain
  authoritative, `/game` is a strict downstream leaf, and the async boundary
  adds no callback/reflection/type-inspection/circularity pressure.

No reviewer edited the checkout. This approval covers the high-level roadmap,
not any future implementation candidate.
