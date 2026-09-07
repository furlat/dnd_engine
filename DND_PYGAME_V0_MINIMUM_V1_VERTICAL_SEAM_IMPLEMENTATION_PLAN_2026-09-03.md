# Pygame V-0 plus minimum V-1 vertical-seam implementation plan

Date: 2026-09-03  
Status: **accepted implementation plan — implementation has not begun**

This candidate supersedes the earlier accepted narrow V-0 draft. The earlier
review remains historical evidence only; the enlarged 64 x 64, water,
structure, light, and animation contract requires a complete new review.

## 1. Requested result

Implement one truthful, scalable in-process seam from the current D&D engine
to a real pygame-ce window. One command must:

1. build a 64 x 64 dark battlefield with Earth, Water, a directional stone
   wall, one closed directional door, and one fixed standing torch;
2. compose and deploy one existing premade observer;
3. let the normal authored-world settlement ignite the torch;
4. execute the existing Open Door and Close Door actions as separate mechanics
   commands;
5. capture each completed EventQueue interval synchronously, without adding an
   EventQueue callback;
6. let mechanics enqueue all three intervals without waiting for pygame;
7. reduce only audited copies of existing concrete Events into one
   observer-authorized renderer target;
8. show the closed, open, and closed-again states at human speed while water
   and flame animate from one renderer clock; and
9. expose objective rows, subjective rows, coverage failures, E/R/D clocks,
   locality counters, camera state, and exact mouse-to-grid/support-height
   diagnostics.

The visible proof is deliberately small in content but not toy-sized in world
extent. It proves:

- exact 64 x 64 cold-world materialization without per-frame full-map work;
- four-view isometric projection, pan, stepped zoom, grid, and picking;
- Earth and source-faithful animated Unity water;
- tile-owned directional walls and a layered frame/leaf door;
- a source-faithful 16-frame torch flame;
- engine-owned light, FOV, wall occlusion, and door recomputation;
- distinct Tile disclosure and object disclosure;
- engine execution running ahead of human-time presentation; and
- fail-visible handling for every Event not yet represented.

This cut does not draw actors or play the full scripted encounter. It completes
V-0 and only the minimum V-1 needed to prove terrain, structures, light,
continuous animation, and one ordinary runtime state transition on the same
vertical seam.

## 2. Governing authority and verified starting point

This plan is subordinate to:

- AGENTS.md;
- HOW_TO_TEST.MD;
- DND_IN_PROCESS_PYGAME_SYSTEM_ARCHITECTURE_ROADMAP_2026-09-02.md;
- PYGAME_P0_NEUROCLIENT_SYSTEM_STUDY_2026-09-02.md; and
- PYGAME_WORLD_ASSET_BRIDGE_NOTES_2026-09-02.md.

The current engine already owns the rules needed here:

- EventQueue generation/cursor/ordered-history access;
- WorldInitializedEvent as a complete actor-free cold world;
- ItemLocationStateEvent as a complete post-commit item presentation fact;
- SpatialChangeEvent with SPATIAL_OBJECT_CHANGED and complete door placement,
  boundary contribution, blocked channels, and is_open after-values;
- SensoryUpdateEvent with observer-owned visible/seen cells, effective light,
  contacts, position, sense modes, and visual-access after-values;
- GridMap-owned directional transition, optical, propagation, light, FOV, and
  senses recomputation;
- DirectionalWall and DirectionalDoor as tile-owned boundary objects;
- the ordinary Open Door and Close Door actions;
- WallTorch fixed-light lifecycle and authored-world post-initialization
  settlement;
- capture_senses_snapshot() and Senses.apply_sensory_update();
- project_combat_log() for same-model subjective text; and
- current elevation facts for projection and picking proof;
- bootstrap_content_system() and SERVER_CONTENT_SYSTEM_RUNTIME as the existing
  in-process engine content installation boundary required by direct character
  and action materialization.

In particular, the existing door path already has the required causal order:
the door publishes SPATIAL_OBJECT_CHANGED, GridMap recomputes light before that
spatial cause completes, and observer SensoryUpdateEvent children carry the
result. Pygame consumes those facts; it must not add a second light or
visibility calculation.

The existing authored-world flow publishes a cold, unlit torch in
WorldInitializedEvent, then lights it through its normal fixture lifecycle and
publishes an ItemLocationStateEvent containing is_lit=true. No new torch-state
Event is needed for this demo.

## 3. Non-negotiable design laws

1. **Mechanics remains the only world authority.** Renderer state is a reduced
   copy of completed Events, never a second GridMap.
2. **Use existing Event types.** Do not introduce render Events, cues,
   transactions, receipts, journals, field masks, or a parallel event enum.
3. **No presentation callback enters EventQueue.** Capture occurs after each
   complete mechanics command returns.
4. **The async boundary carries passive values only.** It never carries a live
   Entity, component, item owner, handler, modifier, context, or registry.
5. **Subjectivity is engine-owned.** Pygame consumes SensoryUpdateEvent and
   existing combat-log projection. It does not recompute FOV, light,
   invisibility, hidden state, darkvision, truesight, or magical darkness.
6. **Tile visibility is not content visibility.** Terrain, boundary surfaces,
   doors, and later actors use their own explicit disclosure rules.
7. **Animation time is presentation state.** It never mutates mechanics,
   advances EventQueue, or claims a gameplay revision.
8. **Engine execution never waits for human animation time.** Presentation may
   lag, but it may not complete or alter an engine Event.
9. **Scale is observable.** Steady-frame work is bounded by the current
   viewport/disclosure and visible animated pixels, not 4,096 world Tiles.
10. **Assets are exact client data.** New authored content contains semantic
    material, placement, direction, state, and item identity—not pygame PNG
    paths, catalog IDs, pivots, poses, frames, or chunk metadata. The renderer
    deliberately ignores retained legacy sprite_name/visual_item_name fields;
    removing that older authority belongs to CR-8, not this plan.
11. **No guessed art.** Missing assets fail visibly; no filename inference,
    raster rotation, mirroring, procedural replacement, or auto-discovery.
12. **Keep the Python graph acyclic.** dnd never imports game or pygame; imports
    remain module-level; no TYPE_CHECKING, dynamic import, getattr, or type-test
    escape hatch may hide a cycle or ownership mistake.

## 4. Exact proving battlefield

### 4.1 Battlefield identity and geometry

Add one ordinary public battlefield through the existing battlefield catalog:

    battlefield.visual_vertical_seam

Its authored facts are exact:

- bounds: (0, 0) through (63, 63);
- 4,096 unique support Tiles at elevation_steps=0;
- base light: LightLevel.DARKNESS on every Tile;
- ordinary Earth Tiles everywhere except the Water rectangle;
- Water positions: x=29..34 and y=33..36, exactly 24 Tiles;
- Water surface: TileSurface(base_material=Material.WATER);
- Water movement: walking_cost=0, swimming_cost=1, with the existing ordinary
  flying/burrowing defaults unless current validation requires their explicit
  normal values;
- Earth surface: TileSurface(base_material=Material.EARTH), walking_cost=1;
- a continuous barrier between columns 31 and 32, owned by the Tiles at
  (31, y) on their EAST side for y=26..37;
- one closed DirectionalDoor at (31, 31), EAST boundary;
- one DirectionalWall at every other barrier position, exactly 11 walls;
- one fixed StandingTorch at center placement (29, 32), initially cold/unlit;
- no connectors; and
- no spatial conditions.

The Water patch deliberately crosses the x=31/32 16-cell chunk boundary. The
barrier deliberately uses the real tile-owned side model: it is on one Tile's
EAST boundary, not a synthetic between-cell object and not duplicated onto the
neighbor.

The battlefield is graphic-agnostic. Every authored Tile leaves its retained
legacy sprite_name field as None, and the battlefield writes no pygame catalog
ID, path, pivot, tint, animation frame, camera, chunk size, or renderer
metadata. ItemPresentationState may still carry the existing
visual_item_name field; game ignores it and binds the standing fixture only by
stable item_id. This plan neither removes nor repurposes either legacy field.

### 4.2 An honest standing-torch backend object

The selected art is a freestanding fixture, not a wall-mounted torch. Add one
narrow StandingTorch domain subtype beside WallTorch and one direct
build_standing_torch() content constructor with stable item_id
environment.standing_torch.

StandingTorch changes only truthful content identity/default presentation
semantics (name and stable item_id). It reuses the current fixed-fixture light,
exposed-flame, use-action, attached-light, authored settlement, and
ItemLocationStateEvent behavior unchanged. It adds no new component, system,
event, registry, manager, or duplicated light rule. Because it is a WallTorch
specialization, the existing authored fixture settlement remains its sole
ignition path.

Do not rename or generalize the entire torch hierarchy in this cut. Do not
pretend the portable Torch is fixed world geometry. If review shows the narrow
subtype cannot reuse settlement without special cases or dependency pressure,
stop; do not create a new fixture framework.

### 4.3 Observer and named probes

Create the current direct fighter premade at (29, 31). The factory returns an
already-composed Entity; do not compose it a second time. Before seeding or
deployment, find its exact inventory item with item_id
equipment.portable_torch and execute its existing "Extinguish Torch" use
action through execute_use_action(). The premade currently ignites this item
during creation, so leaving it lit would introduce a second, undrawn light and
make the standing-fixture proof false. Require that the action succeeds, that
the portable torch is unlit with no attached source, and that the standing
fixture is the sole active light before deployment. Then deploy the observer
through Game. The observer is not drawn yet.

The engine proof uses named positions rather than a renderer-authored sight
shape:

- near probe: (30, 31), on the torch/observer side;
- door-owner support: (31, 31);
- far probe: (32, 31), immediately beyond the door; and
- water probes on each side of the barrier.

Before pygame code is written, Slice 2 must characterize these probes through
the live engine. The accepted behavior is:

- the near side is disclosed and carries the torch's effective light;
- the closed door blocks ordinary optical and propagation transitions across
  (31, 31) -> (32, 31);
- opening the door makes the far probe visible and gives it the exact
  engine-resolved effective light category;
- closing the door removes current visibility beyond it while preserving
  already-seen terrain; and
- the door remains perceivable to the observer throughout the scripted
  transition.

Tests compare the reduced renderer snapshot to the live Senses snapshot and
assert these named facts. They do not copy a hard-coded renderer FOV mask. If
the stated positions do not yield the expected current-engine geometry, adjust
only the map's local observer/torch/barrier coordinates in this plan and rerun
all three reviews; do not patch sight or light in game.

### 4.4 Three mechanics commands and three closed intervals

The exact producer script is:

1. **Startup interval**
   - install bootstrap_content_system() into SERVER_CONTENT_SYSTEM_RUNTIME once
     through the existing dnd.content_system boundary before reset, world
     construction, character materialization, or action lookup;
   - reset through the existing runtime boundary;
   - build the battlefield;
   - allow ordinary authored fixture settlement to light StandingTorch;
   - create the already-composed fighter;
   - extinguish its exact equipment.portable_torch through the existing use
     action and verify the standing fixture is now the only active light;
   - capture the observer seed immediately before deployment without advancing
     EventQueue;
   - deploy the fighter; and
   - close/capture the interval after deployment returns.
2. **Open interval**
   - execute the existing Open Door use action through execute_use_action();
   - require successful completion and open authoritative door state; and
   - close/capture the interval after the action returns.
3. **Close interval**
   - execute the existing Close Door use action through execute_use_action();
   - require successful completion and closed authoritative door state; and
   - close/capture the interval after the action returns.

The content-runtime name is historical: SERVER_CONTENT_SYSTEM_RUNTIME lives in
dnd.content_system and is the active in-process engine content boundary. No
server/API/transport module participates. The portable-torch action Events
remain ordinary objective startup rows and, because they are outside the four
admitted presentation cases, finish visibly unsupported.

The producer may enqueue all three intervals before the renderer displays the
first. There is no Encounter, AI, turn loop, actor animation, or new command
abstraction in this cut.

## 5. Event and information boundary

### 5.1 Closed interval capture

Capture is one synchronous read of already-committed EventQueue storage. It
registers no callback or handler. Every interval validates:

    same generation before and after capture
    0 <= start_cursor <= end_cursor <= EventQueue.event_cursor()
    exact indexes start_cursor .. end_cursor - 1
    storage order preserved
    no missing or duplicate source index

The startup interval additionally requires:

    start_cursor <= observer_seed_cursor <= end_cursor

and rejects any selected-observer SensoryUpdateEvent before that seed. A reset,
generation change, invalid cursor, missing index, duplicate index, or partial
capture rejects the whole interval; no partial envelope is enqueued.

### 5.2 Exact admitted concrete Events

Only the following existing concrete completion values may cross async:

| Existing Event | Exact admission predicate | Renderer responsibility |
|---|---|---|
| WorldInitializedEvent | exact class; COMPLETION; selected battlefield | materialize the cold 64 x 64 world and exact object identities |
| ItemLocationStateEvent | exact class; COMPLETION; item_id environment.standing_torch; FLOOR; exact known fixture UUID | replace that object's complete post-ignition item presentation state |
| SpatialChangeEvent | exact class; COMPLETION; SPATIAL_OBJECT_CHANGED; exact known door UUID | apply its placement/boundary/is_open after-values |
| SensoryUpdateEvent | exact class; COMPLETION; exact selected observer UUID; source index at/after seed | reduce observer knowledge, effective light, and contacts |

Admission is one explicit finite branch, not a registry, protocol, visitor,
decorator, serializer, or extensible dispatch framework. The current declared
fields and representative produced values of every admitted case receive a
passivity test. The normal produced Event must have no arbitrary context,
combat-log object, or effective presentation handler attachment. Any violation
leaves the Event only in EventQueue and marks that source version unsupported.

The detached value is event.model_copy(deep=True). It remains the same Event
subclass with the same UUID, lineage, parentage, phase, and payload. Copying
must not register another Event. No Event is deleted or mutated.

Spatial light children are intentionally not copied. The renderer's light
authority is the selected observer's effective-light fields in
SensoryUpdateEvent. ActionEvent and ExposedFlameEvent likewise remain objective
diagnostic rows until their later visual families exist.

### 5.3 Primitive diagnostic rows and coverage

Every stored Event version receives one primitive objective row keyed by its
source queue index and Event UUID. The row retains only current common scalar
facts needed by the rail: UUID/lineage/parent identities, type, phase,
source/target identities and captured names, execution UUID, status/outcome,
canceled/modified flags, and already-produced display text when present.

It never retains an arbitrary subclass payload, context, Entity, item,
component, handler, modifier, or condition. Unadmitted source versions start
and finish as unsupported; their badge remains visible.

The selected subjective text rail uses project_combat_log() during synchronous
capture and retains only its resulting text. This does not create a subjective
Event class or general projector.

Final dispositions are:

- represented: an admitted world/item/door fact affected a matching displayed
  frame;
- state_only: a selected sensory fact correctly changed or reaffirmed the
  target without requiring its own animation;
- not_disclosed: an otherwise relevant state change was not authorized for the
  selected observer;
- unsupported: no admitted visual rule exists;
- failed: admitted reduction/drawing/parity was impossible.

No Event is silently dropped and no false represented result is allowed.
An unadmitted SensoryUpdateEvent for any observer other than the selected UUID
is unsupported, just like every other unadmitted source version, and cannot
mutate the target. not_disclosed is reserved for an admitted objective
world/item/door fact whose current selected-observer disclosure forbids a
draw; it is not a synonym for rejected admission.

### 5.4 One small interval envelope

One frozen plain Python value carries only:

- generation, start cursor, and exclusive end cursor;
- selected observer UUID and, for startup, the seed cursor/snapshot;
- exact scenario door/standing-torch UUIDs needed by the finite admission
  predicates;
- ordered primitive objective rows;
- ordered already-projected subjective text rows;
- source-index dispositions; and
- ordered pairs of source index plus detached admitted Event.

The objective rows are the one source identity/order list; do not duplicate it
as a second manifest. The envelope has no gameplay kind enum, mutation method,
handler, callback, acknowledgement object, or replacement Event identity.

## 6. One sensory calculation

Extract the current value calculation inside Senses.apply_sensory_update() into
one pure function beside SensesSnapshot in dnd/blocks/sensory.py:

    reduce_senses_snapshot(expected_observer_uuid, previous, event)
        -> next_snapshot

It preserves the current rules exactly:

- validate selected observer identity;
- visible removals before additions;
- monotonic seen additions;
- entity/object contact removals before changed after-values;
- remove effective-light entries for cells no longer visible;
- apply exact effective-light after-values;
- apply position, perception, sense modes, and visual access only when their
  changed flags say so;
- derive the sense-mode hash from the reduced modes using the current formula;
- preserve already-dirty paths and let the Event only assert dirtiness;
- return fresh collections/deep-copied SenseMode values; and
- perform no GridMap, Entity, registry, FOV, light, hidden, or condition query.

The pure function does not own sense_mode_sources or the source visual-access
ModifiableValue. The live Senses wrapper keeps its existing component-owned
commit law: equal effective modes preserve sources; changed modes replace the
direct after-value and clear sources; reduced visual access commits only to
_last_visual_access. The recursive replay validator remains in the live
wrapper, not in game as a generic payload scanner.

Both live Senses and the pygame target call the same pure calculation. Pygame
never creates a Senses component and never reads the live observer after the
startup seed.

## 7. Target state and subjective drawing laws

### 7.1 Minimal target

The renderer target holds existing detached values, not duplicate Pydantic
world models:

- latest WorldInitializedEvent;
- Tiles indexed by engine position for lookup only;
- world objects indexed by UUID and placement for lookup only;
- the exact current detached item state for StandingTorch;
- the exact current door placement/boundary/is_open after-value;
- selected observer UUID and detached SensesSnapshot;
- objective/subjective rail rows, coverage, generation, and reducer cursor R.

Those dictionaries are read-optimized indexes over existing frozen values.
They are not authoritative mechanics, a scene ECS, or a second schema.

### 7.2 Terrain disclosure

| Observer fact | Terrain display |
|---|---|
| currently visible position | draw exact Earth or animated Water with the engine-delivered effective LightLevel treatment |
| seen but not visible | draw a fixed dim memory treatment; remembered Water is non-animated |
| unseen | draw neither terrain nor grid and disclose no Tile identity/elevation |

Missing effective light on a currently visible cell is an error, not a client
default to Darkness.

The finite LightLevel-to-appearance mapping is client data in
world_bindings.json and has exactly these treatment IDs and RGB multipliers:

| Delivered value | Treatment ID | RGB multiplier |
|---|---|---|
| LightLevel.VERY_BRIGHT | light.very_bright | (1.08, 1.08, 1.04) |
| LightLevel.BRIGHT_LIGHT | light.bright | (1.00, 1.00, 1.00) |
| LightLevel.DIM_LIGHT | light.dim | (0.65, 0.68, 0.78) |
| LightLevel.DARKNESS | light.darkness | (0.34, 0.38, 0.50) |
| LightLevel.MAGICAL_DARKNESS | light.magical_darkness | (0.22, 0.15, 0.32) |

The fixed memory treatment is memory.seen with RGB multiplier
(0.38, 0.40, 0.46); it never consults a current LightLevel. For Earth, apply
the selected multiplier to canonical/scaled asset RGB immediately before the
final blit and preserve alpha. For currently visible Water, evaluate the Water
material at current T first, apply the selected multiplier to its RGB, preserve
its material alpha, then perform the final blend. Remembered Water uses one
cached material evaluation at T=0 followed by memory.seen, so it is
deterministic and non-animated. Clamp multiplied RGB to the 8-bit range. No
other tint, ambient value, or inferred client light exists.

### 7.3 Wall and door disclosure

DirectionalWall is intentionally not an ordinary object contact. Treat a
boundary surface as:

- current/full when either incident support Tile is currently visible;
- remembered/dim when neither is visible but either is seen; and
- hidden when neither incident Tile is disclosed.

This is a finite renderer disclosure rule over engine-owned incident cells. It
lets the wall itself remain visible while blocking the Tile behind it. It does
not make the hidden Tile, or any object in it, visible.

The DirectionalDoor frame follows the same boundary-surface rule. The leaf and
its open/closed state require the door UUID in current observer object
contacts. The reducer may update the detached objective door after-value while
offscreen, but it must not draw that state until contact authorizes it. When
contact is newly gained, the current detached after-value supplies the state
the observer can now see. No generic subjective object projector is added.

This exact script requires contact before, during, and after the transition.
Failure to satisfy it is a scenario/test failure.

### 7.4 Standing torch and light

The torch body and flame require the StandingTorch UUID in current observer
object contacts. Body selection uses its stable item_id. Flame is drawn only
when the latest admitted ItemLocationStateEvent says is_lit=true.

The Sprite never illuminates pixels by rule. Tile and structure treatments use
only effective LightLevel values already delivered by SensoryUpdateEvent. A
current wall/frame/door leaf chooses the brightest delivered value—maximum
LightLevel.value—among its currently visible incident support cells. A
currently contacted standing-torch body uses the delivered value at its
visible placement support. If the relevant supports are only remembered, the
structure/body uses memory.seen; if none is disclosed, it is hidden. Apply the
selected multiplier after static asset scaling and before the final blit,
preserving alpha. The flame itself is emissive presentation art: it keeps its
asset RGB/alpha, but is drawn only when the contacted body is drawable and the
engine state says is_lit=true. None of these rules traces or propagates light.

Door opening must visibly reveal/re-light the far side from the sensory delta;
closing must remove current far-side disclosure while retaining seen memory.
The corresponding SPATIAL_LIGHT_CHANGED Events remain visibly unsupported in
the objective rail because their subjective result is represented by the
SensoryUpdateEvent, not re-read directly.

## 8. Exact client asset subset

### 8.1 Repository-owned copies only

Copy only the following reviewed source families into game/assets. Record
source path and SHA-256 in assets.json; runtime never reads WSL repositories.

From /home/tommaso/Dev/NeuroMapEditor/public/assets/fantasy/environment:

- ground-a1-e.png;
- wall-d2-{e,n,s,w}.png;
- wall-d6-{e,n,s,w}.png;
- door-a1-{e,n,s,w}.png, closed leaf candidates; and
- door-a2-{e,n,s,w}.png, open leaf candidates.

From /home/tommaso/Dev/MapEditor/app/public/assets/unity-reference:

- sprites/6ccb6893c0aa9974091d5318779c1e76.png, Water alpha mask;
- effects/waterImage.png, repeating ripple texture;
- effects/waterNormal.png, repeating normal texture;
- sprites/fa27919a4e81577468f97c3b668cffa2.png, standing-torch body; and
- the exact 16 flame Sprite PNGs listed below.

The four wall and doorway-frame poses are accepted source families. The door
leaf set has weaker active-occurrence evidence for some views even though the
catalog files exist. Slice 0 must visually verify that every copied A1/A2 pose
is truly the same closed/open leaf family. A failed pose remains a visible
missing-asset diagnostic for that camera view. It must never be synthesized by
rotation or mirroring. The default R0 view uses the already high-evidence .s
frame and leaves.

### 8.2 Two direct JSON files

Add only:

1. game/data/assets.json — exact image resources, native dimensions, pivot,
   scale, material/animation metadata, ordered flame frames/fps, and exact
   Water constants/blend rule; and
2. game/data/world_bindings.json — finite direct maps from Material.EARTH,
   Material.WATER, the stone DirectionalWall boundary family, the
   DirectionalDoor frame plus is_open leaf family, and item_id
   environment.standing_torch to those catalog IDs, plus the six direct
   current/memory treatment rows in Section 7.2.

They contain no Python class names, engine objects, predicates, tags,
priorities, inheritance, regexes, filename rules, fallback chains, or asset
inference. Engine objects never contain client asset IDs.

### 8.3 Direction-to-pose law

The artist-space pose for an engine boundary depends on camera quadrant. At R0:

| Engine boundary | Asset pose |
|---|---|
| NORTH | w |
| EAST | s |
| SOUTH | e |
| WEST | n |

Each quarter camera rotation rotates this mapping coherently. Local PNG pixels
and pivots are never raster-rotated. Door painter order is frame, then leaf.
Torch painter order is body, then flame.

### 8.4 Loading and failure

After pygame.display.set_mode():

- validate relative-path containment, existence, SHA, native dimensions,
  frame order, and direct bindings;
- load synchronously and call convert_alpha() once;
- keep immutable canonical Surfaces;
- use nearest-neighbor scaling at the finite zoom levels;
- cache scaled static images and flame frames;
- configure Water ripple/normal sampling as repeat plus nearest in the software
  sampler; and
- surface any missing/malformed/unknown resource as a failed interval plus
  readable diagnostic.

No procedural ground, wall, door, Water, or torch fallback is permitted.

## 9. One presentation clock and two continuous animations

### 9.1 Clock ownership

The renderer owns one monotonic presentation_time_seconds. Runtime advances it
from the one pygame Clock delta; tests inject exact deltas. The same time drives
Water and flame.

Camera pan, zoom, rotation, culling, remounting, sensory changes, and interval
boundaries do not reset it. Continuous animation alone does not advance E, R,
or D and does not create an Event or terminal.

### 9.2 Flame

Use this exact 16-frame order at 10 fps:

1. f52dea0b72342b246a1216e289dc5168
2. d0ad60029a0000444a7857492c6a6c8f
3. 40f6c77eb5fc22a469128a41099f5290
4. 2276e4f9d5b5375498378d15537db6bb
5. 48ecf78b49001774082006e4def7022a
6. 23ca28e336270bc458c4e3b626186ca6
7. 284115ada2975f1409611751ae8743a7
8. d5227bc3bac87004d8aae57741cc00ce
9. 3ceb33c008cf91545b06eb6a6763b90d
10. 3a911e83eaeb1714ea0a08180ec0c614
11. 1dca70b6deec00a4ab47b04675c4d55f
12. 730718fd0c474f54194c2fe0184ca24a
13. e8b3e4d342784df4792e9d60d505de82
14. d4eccfde5037d4d40986d61754bb33d4
15. f09e44a4b6d53e9409a13272d4198c54
16. 77c165966e3947c40a3d08440e7f9bf2

The selected frame is:

    floor(max(0, presentation_time_seconds) * 10) % 16

Body and flame use pivot (128, 209.92), scale 128/127, and the same projected
contact. The orientation-neutral fixture is valid in all four views.

### 9.3 Source-faithful Unity Water

Implement the existing Unity/TS material as one vectorized NumPy/pygame
software kernel in game/water.py. Do not approximate it with a blue tint,
per-Tile frame swap, Python pixel loop, GPU wrapper, ModernGL dependency, or
new shader abstraction.

The immutable material values are:

| Field | Value |
|---|---|
| shallowColor | [0.06878672, 0.40544975, 0.59119487, 0.6666667] |
| deepColor | [0.07058824, 0.4039216, 0.5921569, 0.5529412] |
| tint | [1, 1, 1, 1] |
| depthBlendStrength | 1.554 |
| uvScale | 1.37 |
| detailPan | [0.005, 0.004] |
| detailInfluence | 0.648 |
| ripplePan | [0.1, 0.1] |
| rippleTilingMultiplier | 1 |
| rippleAmount | 0.2 |
| uvWobbleAmount | 0.1 |
| normalPanA | [0.1, 0.1] |
| normalPanB | [1, -0.1] |
| normalTilingMultiplier | 1 |
| normalScale | 2 |
| sheenStrength | 0.158 |
| sheenSharpness | 3.46 |
| overallAlpha | 0.812 |
| alphaDepthStrength | 0.222 |
| alphaCutoff | 0.493 |
| premultiplyOutput | false |

For each visible Water owner-chunk batch, reproduce the TS shader sequence
exactly:

1. sample the composed Water mask alpha and discard below alphaCutoff;
2. map input pixels into worldPosition;
3. derive worldUv;
4. sample ripple red, calculate wobble;
5. sample both normal pans, combine, safe-normalize, and scale;
6. evaluate the unassigned detail texture as white, matching the Unity sample;
7. compute world-y depth interpolation and shallow/deep mix;
8. add ripple color and screen-edge sheen;
9. compute depth-adjusted alpha and overall alpha; and
10. blit straight shader RGB using pygame.BLEND_PREMULTIPLIED without first
    calling premul_alpha(), reproducing Unity's unusual One / OneMinusSrcAlpha
    declaration with straight shader output.

World-space mapping follows the current TS reference:

    origin = (source_origin_px.x / tile_width,
              -source_origin_px.y / tile_width)
    pixel_axis_x = (1 / (tile_width * render_scale), 0)
    pixel_axis_y = (0, -1 / (tile_width * render_scale))

Translation does not affect UVs. Support-height pixel lift does not affect
UVs. Ripple and normal textures use repeat/nearest sampling. Default flow is
(1, 1) at speed 1; any future flow rotation must rotate every pan vector
coherently, but this cut adds no runtime flow control.

### 9.4 Water chunking and fidelity oracle

Use fixed 16 x 16 engine-coordinate owner chunks. A Water Tile belongs to one
owner chunk. For each visible owner chunk, cache one stable painter-ordered
packed batch of per-support alpha/sample-local geometry and stable projected
offsets. Rebuild that geometry only when disclosed support membership, camera
quadrant, or zoom changes. Each frame, intersect it with the current viewport
clip and add the current pan/viewport origin to derive exact global framebuffer
coordinates for the raw invocation. A pan therefore changes screen-edge sheen
without rebuilding cached local geometry or changing world-space UV phase. A
LightLevel change updates only its direct per-support treatment selection; it
does not rebuild the raw material geometry.

Invoke the vectorized raw Water kernel exactly once per visible clipped owner
chunk per frame over that packed sample batch—never once per Tile and never
once per treatment. Scatter its raw results back to the existing per-support
slots, apply each support's own delivered LightLevel multiplier, and blit those
support outputs at their ordinary painter positions. Overlapping support
Sprites remain separate packed layers, so their order and alpha semantics are
not flattened. This permits Water supports and boundary art to interleave under
the same painter law without a whole-chunk Sprite, a second material
evaluation, or a scene object. Clip packed vector work to the viewport plus
exact Sprite overhang.

Before implementing the Python kernel, capture a tiny immutable fixed-time
oracle from the existing unityWaterFilter.ts/Pixi reference using the exact
ripple, normal, and synthetic mask inputs. The fixture freezes its source and
output dimensions, complete material constants, source_origin_px, tile_width,
render_scale, exact sample-local coordinates, exact global framebuffer origin,
framebuffer dimensions, and a nonzero known destination RGBA. It records both
raw shader RGBA and the expected final composited RGBA at t=0, 0.1, and 1.25
seconds. Store only those small samples plus provenance/source and input-image
SHAs in tests; production has no TS/Node runtime dependency.

Compare the Python raw output within at most one 8-bit channel step where
GPU/CPU rounding differs. Separately blit the straight shader output over the
fixture's known nonzero destination with the real pygame
BLEND_PREMULTIPLIED path—without premul_alpha()—and compare final composited
RGBA to the recorded reference. The chunk split/unsplit proof must render and
compare identical global framebuffer coordinates with the same framebuffer
size, destination pixels, source origin, tile width, scale, and T; changing a
chunk-local origin is not an admissible equivalence proof.

Additional mathematical tests must prove:

- fixed global coordinate/time output does not change when one pool is split
  across the x=31/32 chunk boundary;
- pan preserves world-space material phase while updating screen-edge sheen
  from the new global framebuffer coordinates; camera remount and elevation
  offset likewise do not shift world-space phase;
- zoom changes sampling scale without resetting time;
- two different times change visible Water pixels; and
- remembered/not-visible Water does not continue animating.

A real mixed-light proof must simultaneously render the current engine facts
in owner chunk (1, 2), including Water supports (29, 33), (30, 33), and
(31, 33), and show their distinct delivered treatments in one raw material
invocation. The test groups the ordered support draw evidence by the owner
chunk derived from each engine position; the raw chunk evidence carries no
duplicated LightLevel/treatment field.

The oracle is a narrow material test, not a full-scene screenshot golden.

Official pygame-ce contracts used by this implementation are the display,
Surface, transform, time, mouse, surfarray, special blend flag, and
premultiplied-alpha references. Slice 0 resolves and locks the current stable
pygame-ce 2.5.x release supported by Python 3.12; it must not guess a future
version. NumPy is already a direct project dependency.

## 10. Projection, painter order, camera, and picking

### 10.1 One pure projection owner

game/projection.py owns the forward/inverse relationship. For one macro128
support after camera-quarter rotation:

    world_x = (camera_x - camera_y) * 64
    world_y = (camera_x + camera_y) * 32 - elevation_steps * 64

The -64-pixel lift per five-foot engine support step is presentation geometry
only. Engine position remains (x, y); no visual Z coordinate is written into
Tile or Entity.

### 10.2 Four camera quadrants and controls

Rotate around the fixed map-center pivot (31.5, 31.5):

| View | Rotated coordinates |
|---|---|
| R0 | (x, y) |
| R90 | (-y, x) |
| R180 | (-x, -y) |
| R270 | (y, -x) |

The inverse applies the opposite quarter turn. Controls are:

- W/A/S/D: screen-space pan;
- mouse wheel: cursor-centered next/previous finite zoom;
- Q/E: one quarter camera rotation, preserving the focused engine contact;
- G: disclosed-grid overlay;
- Escape/window close: clean shutdown.

The initial camera focuses the local proving scene, not the whole 64 x 64 map.
Zoom levels are a small fixed tuple supporting local inspection and overview.

### 10.3 Painter law

Build one deterministic ordered draw list from disclosed current candidates.
The key uses camera-transformed projected support contact, finite role band,
and stable engine identity. Required local role order is:

    Water/base support
    Earth/base support
    boundary wall or doorway frame
    door leaf
    standing-torch body
    standing-torch flame
    debug/grid/hover/UI overlays

Water versus Earth never overlap on the same base Tile in this map. The role
order exists to make cross-cell Sprite overlap deterministic, not to invent a
second z-index API. Pan, zoom, insertion order, and animation frame do not
change semantic painter order.

An animated Water owner chunk is only a vector-work/cache owner; it never owns
a painter key and is never blitted as one scene Sprite. Each scattered Water
support output occupies the same support draw slot that static terrain would.
Consequently the existing contact-first painter key may place wall/frame/leaf
draws between Water supports where the view requires it. A real default-R0
test uses the known Water/barrier crossing, composites actual Water and wall
Surfaces in the prescribed order, and requires the final overlapping pixels to
match that order and differ from the reversed composite. It also checks the
recorded draw sequence, so a visually coincidental opaque result cannot hide a
whole-chunk late blit.

### 10.4 Height-aware picking

Candidate supports come only from observer-visible or observer-seen positions
within the current viewport candidate window. For each distinct disclosed
support elevation:

1. remove pan/viewport and zoom;
2. remove that support's -64 * elevation_steps pixel lift;
3. invert macro128 projection;
4. inverse-rotate around the map pivot;
5. require an exact disclosed Tile at the candidate coordinate/elevation;
6. test the projected 128 x 64 support diamond; and
7. select the visually foremost valid support by the same painter law.

Hover diagnostics report screen/world pixels, quadrant, zoom, raw plane
estimate, every tested elevation, chosen engine (x,y), Tile UUID, material,
height steps/feet, Z-grid pixel offset, projected contact, painter key, and
diamond result. When no disclosed support matches, no objective Tile identity,
material, height, or map membership may leak.

This cut picks supports only. It does not implement wall/door/torch alpha-mask
selection.

## 11. 64 x 64 locality and caching contract

The cold event necessarily contains 4,096 Tiles once. Startup may validate and
index them once. No steady frame may scan all 4,096.

For each frame:

- derive an engine-coordinate candidate rectangle by inverse-projecting the
  viewport and adding the exact maximum catalog overhang;
- intersect that rectangle with observer disclosed positions, using set/dict
  membership;
- look up only candidate Tiles and world objects;
- group only visible Water candidates into fixed owner-chunk vector batches
  while retaining their individual painter slots;
- draw only current candidates and visible animated chunks/objects; and
- reuse canonical/scaled static Surfaces and cached Water masks.

Sensory deltas update disclosed membership directly. Door/item after-values
invalidate only their owner placement and incident boundary cells. Camera
rotation or zoom may rebuild finite presentation caches; pan changes the
candidate window/blit positions and the per-frame global framebuffer
coordinates supplied to Water sheen, but does not rebuild local Water geometry
or alter its world UVs. No full-board string signature or rebuild is allowed.

The diagnostics expose at least:

- total world Tiles (4,096);
- visible and seen support counts;
- viewport candidate coordinates tested;
- static candidates drawn;
- Water chunks and Water pixels evaluated;
- visible animated fixtures;
- cache rebuild/hit counts;
- presentation time and flame frame; and
- E/R/D per interval.

An automated locality proof renders the same local disclosed viewport in a 16
x 16 and the 64 x 64 world and requires equal steady-frame candidate and
animated-work counts. A real 64 x 64 SDL-dummy multi-frame smoke must also run.
Manual profiling at 1280 x 720 with Water and flame visible records median and
p95 frame time after warm-up; the automated correctness gate is the work-count
invariant, not a machine-dependent millisecond threshold.

## 12. Async execution, revisions, pacing, and terminals

### 12.1 One thread and one event loop

Use one asyncio.run() composition. Pygame initialization, input pumping,
drawing, display update, and Clock remain on the main thread. Mechanics
commands are synchronous and each completes before its interval is captured.
No worker, networking, server, or second event loop is introduced.

### 12.2 Two ordinary bounded queues

Use:

- asyncio.Queue(maxsize=3) for exactly the startup/open/close envelopes; and
- asyncio.Queue(maxsize=3) for their terminal values.

The producer uses put_nowait() after valid capture and can finish all mechanics
before pygame catches up. Overflow is a visible fatal presentation failure,
not backpressure into Event completion and not a silent drop. These queues are
not buses: nothing subscribes and no future/callback map is created.

### 12.3 E, R, D, and ambient time

- E: authoritative exclusive EventQueue end cursor captured for an interval;
- R: end cursor after every source version was either given a final
  non-display disposition or reduced into an exact pending display obligation;
- D: end cursor after a frame with exact target/display semantic parity was
  published; and
- T: renderer-local continuous presentation_time_seconds.

Within one generation, E >= R >= D. T is not comparable to those revisions.
Water/flame animation can advance T for any number of frames without changing
E/R/D. represented does not become final at R: a world/item/door source with a
pending display obligation becomes represented only after its matching
successful parity frame advances D. This makes E=R>D both valid and directly
observable without claiming that scheduled work was already displayed.

### 12.4 Human-visible interval pacing

The renderer consumes one interval at a time. After reducing it, it must
publish at least one exact matching frame and keep that discrete state on
screen for one small explicit display duration before consuming the next
interval. Use one application constant (initially 0.75 seconds) driven by the
same injected presentation clock; do not sleep in tests.

Continuous Water/flame motion continues during the hold. The hold belongs only
to this scripted demonstration and is not encoded in Events or gameplay. It
exists so an already-enqueued open state is not coalesced immediately into the
later close state.

### 12.5 One terminal per source interval

One terminal contains generation, cursor range, settled/failed/cancelled, and
failure text. It settles only after:

- every source index has one final disposition;
- admitted values reduced in source order;
- required assets/material output succeeded;
- exact expected display evidence equals evidence appended only after each
  corresponding real blit succeeded;
- the matching frame was displayed;
- the interval's visible hold elapsed; and
- generation still matches.

No per-Event, per-Tile, per-asset, per-animation, or per-frame terminal exists.
Queue emptiness is not completion proof. Ambient animations never finish and
therefore are not terminal obligations; one correct displayed frame at that
interval's T proves their current materialization.

Expected calculation evidence is an ordinary set of primitive tuples, and
expected draw evidence is one ordinary ordered sequence of primitive tuples in
the already-required painter order. Actual draw entries are appended only after
their real blits succeed. These are fields of the existing per-interval
presentation state, not new objects or a second rendering model. Their finite
tuple forms are:

- support: (Tile UUID, engine position, asset ID, current_or_memory, delivered
  LightLevel or None, treatment ID);
- wall/frame: (object UUID, owned side, asset ID, current_or_memory, selected
  LightLevel or None, treatment ID);
- door leaf: (door UUID, is_open, pose asset ID, current_or_memory, selected
  LightLevel or None, treatment ID);
- standing fixture: (fixture UUID, is_lit, body asset ID, current_or_memory,
  body LightLevel or None, body treatment ID, exact flame asset ID or None,
  exact flame frame index or None); and
- raw animated Water batch: (owner chunk coordinates, clipped global
  destination bounds, evaluated packed-sample count, exact T,
  water.unity-material ID).

The expected calculation set and draw sequence are derived from the reduced
target, disclosure, and painter list at the captured frame T. The actual raw
Water tuple is recorded only after its one chunk kernel invocation succeeds;
each treated Water support row enters the actual draw sequence only after that
support's scattered result is blitted in its painter slot. Grouping Water
support rows by owner chunk and their engine position reconstructs the exact
ordered mixed-treatment membership without duplicating LightLevel/treatment
inside the raw-batch tuple. Door/torch/flame rows likewise cannot pass on target
state alone. Equal calculation evidence and exact draw-sequence equality are
checked before D advances or represented becomes final. The dedicated
asset/Water tests own pixel fidelity; this frame evidence owns semantic
materialization, treatment, ordering, and successful blit coverage without
hashing the framebuffer each frame.

A generation reset cancels all stale envelopes/targets and prevents them from
changing the new generation's scene, coverage, R, or D. Shutdown stops new
input, closes pending terminals once, quits pygame once, and uses the existing
engine reset boundary rather than deleting authoritative Events.

## 13. Minimal visible product

The pygame window shows:

- observer-authorized Earth and animated Water;
- the disclosed stone barrier and layered door;
- the perceived standing-torch body and animated flame;
- engine-resolved light treatments and seen-memory treatment;
- optional disclosed grid and hover diamond;
- objective Event rows and subjective log rows;
- unsupported/failed/not-disclosed counts;
- E/R/D/T, interval, queue depth, and generation;
- locality/cache/animation counters;
- camera quadrant, zoom, and pan; and
- full mouse-to-grid/support-height diagnostics.

The exact UI colors, font sizes, rail geometry, and line wrapping are not stable
contracts. The semantic data and its live update are.

## 14. Small module shape and dependency DAG

The intended maximum shape is:

    game/__main__.py
            |
            v
    game/app.py ------------------------------> pygame
       |          |           |          |
       v          v           v          v
    presentation  projection  assets     water
       |
       v
    existing dnd Events and sensory values

Responsibilities:

- game/presentation.py: interval capture/admission, primitive rails, pure
  target reduction, coverage, E/R/D, and interval terminal;
- game/projection.py: camera rotation, macro128 forward/inverse, height offset,
  painter key, viewport bounds, and support picking;
- game/assets.py: exact two-JSON validation, Surface loading, finite static and
  flame-frame caches;
- game/water.py: the one NumPy Unity-water material calculation;
- game/app.py: direct scenario/observer/action script, two queues, one clock,
  in-process content installation, frame/input/draw loop, pacing, culling, and
  diagnostic layout; and
- game/__main__.py: tiny executable entry.

If a module remains trivial, merge it into its only caller. Do not add manager,
service, controller, store, repository, adapter, interface, scene graph, scene
ECS, command bus, event bus, scheduler, animation graph, or DI container.

Dependency rules:

- game may import public dnd values/builders, including the existing
  dnd.content_system bootstrap/runtime boundary, NumPy, and pygame;
- dnd must never import game, pygame, or client asset paths;
- game must not import server, SDK, transport, services, deprecated, AI, or
  external MapEditor/NeuroClient source;
- water imports NumPy/pygame and client data only, never Entity/GridMap;
- projection is pure and imports no mechanics owner;
- all project imports are module-level; and
- Entity remains a data aggregate/system composer, never a renderer object.

## 15. Planned file envelope

Expected existing-file changes:

- pyproject.toml — pygame-ce dependency and game type-check scope;
- uv.lock and requirements.txt — keep supported install surfaces aligned;
- dnd/blocks/sensory.py — pure sensory value extraction/live reuse;
- dnd/items/torches.py — narrow StandingTorch subtype only;
- dnd/content/items/environment_item_builders.py — direct standing-torch
  constructor/export;
- dnd/scenarios/battlefield_catalog.py — one 64 x 64 battlefield;
- nearest existing engine tests for sensory, cold world, door light cascade,
  and fixed torch facts; and
- dependency architecture tests.

Expected new files:

- game/__init__.py;
- game/__main__.py;
- game/app.py;
- game/presentation.py;
- game/projection.py;
- game/assets.py;
- game/water.py;
- game/data/assets.json;
- game/data/world_bindings.json;
- exact copied asset files under game/assets/;
- tests/game/test_presentation_boundary.py;
- tests/game/test_projection.py;
- tests/game/test_assets.py;
- tests/game/test_water.py;
- tests/game/test_app_smoke.py; and
- one tiny Water oracle fixture under tests/game/data/.

Do not touch server, SDK, transport, generated code, renderer/editor
TypeScript, external repositories, CR-6 through CR-10, or unrelated content.
No implementation ledger, manifest, or hash ritual is required.

## 16. Observable acceptance matrix

### 16.1 Engine world and causal facts

1. Public battlefield construction yields exactly 4,096 unique support Tiles,
   4,072 Earth and 24 Water, all at height zero and base Darkness.
2. Exact barrier ownership is 11 walls plus one closed door on the listed EAST
   sides, with no neighbor-side duplicate.
3. StandingTorch has stable item_id, fixed-fixture behavior, center placement,
   cold is_lit=false world state, then one complete lit floor
   ItemLocationStateEvent through ordinary authored settlement.
4. The premade's auto-lit equipment.portable_torch is extinguished through its
   existing action before deployment; it has no attached source, and the
   standing fixture owns the scenario's sole active light at its placement
   after settlement. No renderer value participates.
5. The normal Open Door action emits the expected SPATIAL_OBJECT_CHANGED,
   light recomputation, and observer sensory cascade before its complete source
   interval closes; Close Door reverses it.
6. Live named probe facts match Section 4.3 and the reduced snapshot exactly.
7. New battlefield/content authoring writes no pygame catalog ID/path/pivot/
   pose/frame/chunk value; authored Tile.sprite_name stays None. The new game
   bindings ignore rather than remove retained legacy sprite_name and
   visual_item_name fields.

### 16.2 Sensory reducer

8. Pure reduction equals live Senses for visible/seen cells, contacts,
   effective light, position, modes/hash, passive perception, access, and path
   dirtiness across startup/open/close.
9. Removals precede additions/changed after-values.
10. Wrong observer identity is rejected without mutating prior state.
11. Equal effective modes preserve live sense_mode_sources; changed modes clear
    them; visual-access replay never replaces its source ModifiableValue.
12. Pure reduction performs no live owner/registry/GridMap query and remains
    stable after runtime reset.

### 16.3 Capture, passivity, and coverage

13. Three exact contiguous intervals preserve every source (index, Event UUID)
    once and in order.
14. Only the four cases in Section 5.2 cross async, retaining exact Event class,
    identity, lineage, parentage, phase, and value payload.
15. Arbitrary context/handler/live values reject admission.
16. Action, flame, raw light, character/equipment, declaration/execution/effect,
    and all other unadmitted versions remain objective and visibly unsupported.
17. Invalid cursor/seed/generation/index rejects an entire interval without
    partial enqueue.
18. Reset after capture cannot change detached reduction.
19. No presentation callback is registered and no authoritative Event is
    deleted or modified.

### 16.4 Subjective scene

20. An objective 4,096-Tile world exists before observer disclosure, but unseen
    Tiles draw no ground/grid and leak no hover identity.
21. Visible Earth/Water use the exact delivered-LightLevel table and operation
    order in Section 7.2; remembered supports use exact fixed memory; visible
    missing-light is a failure.
22. Tile visibility does not imply object visibility.
23. A wall/frame may draw from an incident disclosed support while the blocked
    support beyond remains hidden.
24. Door leaf/state and torch layers require their exact current object contact.
25. Opening displays the open leaf and newly disclosed/lit far side; closing
    displays the closed leaf and memory beyond.
26. A different observer's sensory Event is unsupported by admission and cannot
    mutate the selected scene; admitted objective facts hidden from the selected
    observer are not_disclosed.

### 16.5 Assets, animation, and Water

27. Every copied file passes exact path/SHA/dimension/catalog validation.
28. Unknown binding, malformed JSON, escaping path, wrong SHA/dimension, missing
    pose/frame, or decode failure is visible and terminal-failing.
29. Four camera views choose explicit pose files without rotating/mirroring
    pixels; any rejected door-leaf pose remains a visible missing-asset case.
30. Flame frame selection is exact at boundary times and shares T with Water.
31. Torch body remains stable; is_lit gates flame; camera/culling does not reset
    its phase.
32. The Python Water kernel matches the fully frozen TS oracle's raw output at
    all sampled pixels/times within one 8-bit step, and its real straight-output
    BLEND_PREMULTIPLIED blit matches the frozen nonzero-destination final RGBA.
33. Chunk-split/unsplit output matches at identical global framebuffer
    coordinates and complete frozen inputs; pan preserves world-material phase
    while producing the correct new screen-edge sheen, elevation does not shift
    phase, time changes pixels, and memory Water is static.
34. Raw Water evaluates in one vector invocation per visible clipped owner
    chunk, not per Tile or treatment; packed results scatter into per-support
    painter slots with simultaneous mixed-light treatments and correct real
    Water/wall overlap order.

### 16.6 Projection, controls, and locality

35. Forward/inverse and cursor-centered zoom round-trip representative cells in
    all four views.
36. Real current elevated supports prove -64 pixels per step and height-aware
    pick recovery without changing engine coordinates.
37. Painter order is deterministic across input order, pan, zoom, and frames.
38. WASD, wheel, Q/E, G, close/Escape, rails, and hover diagnostics work in the
    real window.
39. No steady frame scans 4,096 Tiles; locality counters match between equivalent
    16 x 16 and 64 x 64 local views.
40. SDL-dummy runs multiple real 64 x 64 frames with Water/flame visible and
    reports bounded candidate/animated work.

### 16.7 Async and terminal semantics

41. Producer completes and enqueues all three mechanics intervals without
    waiting for a frame or hold duration.
42. E>R=D, E=R>D, and E=R=D are each observable at their proper boundary.
43. Startup, open, and close are each displayed for their exact semantic state,
    their finite expected/actual post-blit evidence sets match at captured T,
    and they produce exactly one terminal in order.
44. Continuous animation advances T without moving E/R/D or preventing a
    terminal.
45. Queue emptiness, scheduled drawing, or target existence alone cannot settle.
46. Overflow, missing art, reducer failure, false represented state, or parity
    mismatch fails visibly.
47. Reset cancels stale work; shutdown closes once.

### 16.8 Architecture

48. dnd imports neither game nor pygame.
49. game imports no excluded server/SDK/transport/editor/client layer.
50. The active graph has no cycle, function-local/late project import,
    TYPE_CHECKING workaround, dynamic import, getattr, or reflection-based
    passivity scanner.
51. No new Event hierarchy, renderer ECS, callback path, manager/service/
    controller, generic asset selector, or duplicated light/FOV calculation
    appears.

Tests assert stable values, causal ordering, displayed evidence, and work
counts. They do not freeze arbitrary private call order, fonts, layout pixels,
or mocked pygame draw calls.

## 17. Test lanes

### 17.1 Focused value lane

    uv run pytest -q \
      tests/game/test_presentation_boundary.py \
      tests/game/test_projection.py \
      tests/game/test_assets.py \
      tests/game/test_water.py \
      tests/engine/test_world_entity_initialization.py \
      tests/engine/test_world_geometry_contract.py \
      tests/engine/test_senses_light_stealth.py \
      tests/engine/test_subjective_combat_log_replay.py

### 17.2 Real pygame smoke

    uv run pytest -q tests/game/test_app_smoke.py

The test sets SDL dummy video/audio before importing/initializing pygame, uses
real copied assets and Surfaces, injects deterministic T deltas, waits on
semantic terminals, and never sleeps or mocks pygame.

It also launches a fresh Python subprocess that cannot inherit pytest's autouse
content installation. That subprocess imports and calls the same game.app.run()
entry used by game.__main__, with only explicit finite frame deltas and a zero
test display hold supplied as function arguments. It must install the existing
dnd.content_system runtime itself, execute the portable-torch extinguish plus
door open/close script, display all three parity frames under SDL dummy, print
one final primitive E/R/D/terminal summary, and exit zero. This is the
standalone bootstrap proof; it adds no server import, test-only event path, or
second application entry.

### 17.3 Architecture/type/compile

    uv run pytest -q tests/architecture
    uv run pyright game dnd/blocks/sensory.py dnd/items/torches.py \
      dnd/content/items/environment_item_builders.py \
      dnd/scenarios/battlefield_catalog.py
    uv run python -m compileall -q game dnd tests/game
    git diff --check

### 17.4 Broad regression and manual proof

Run the active engine/content/progression/architecture lanes owning touched
behavior, preserving governed excluded collection failures rather than adding
stubs. Then run:

    uv run python -m game

Manually verify all four views, every zoom, pan, grid, hover/Z diagnostics,
Water/flame continuity, closed-open-closed door/light behavior, rails,
unsupported badges, queue lag, E/R/D/T, locality counters, and clean close.

## 18. Ordered implementation slices and stop points

### Slice 0 — dependency, asset, and oracle preflight

- resolve/lock current stable pygame-ce 2.5.x on Python 3.12;
- initialize real and SDL-dummy displays;
- hash/dimension/visually inspect only the exact asset subset;
- validate every door leaf pose or explicitly mark it unavailable;
- capture the tiny TS Water oracle with provenance;
- add dependency entries, game shell, and DAG gate.

Stop for a real missing/incorrect required source. Do not guess or broaden the
asset search.

### Slice 1 — pure sensory reducer

- write value-equivalence/ownership proofs;
- extract one pure snapshot calculation;
- make live Senses delegate to it;
- run complete sensory/light/replay lanes.

Stop on any live behavior difference; do not compensate in pygame.

### Slice 2 — 64 x 64 world and mechanics characterization

- add StandingTorch and its direct builder;
- add exact battlefield;
- prove cold/lit fixture sequence, exact directional ownership, and that the
  premade's portable torch is extinguished before deployment so the standing
  fixture is the only active light;
- deploy observer and verify named probes;
- execute real open/close use actions and prove causal light/sensory order.

Stop and amend/re-review only if the exact local geometry needs coordinate
adjustment. Do not change mechanics rules.

### Slice 3 — interval boundary and target

- implement primitive rows and exact closed capture;
- implement only four finite admission cases;
- implement target reduction/disclosure/coverage;
- prove reset independence, negative unsafe values, and all three intervals.

Stop until every source version has one honest disposition and no unadmitted
Event crossed async.

### Slice 4 — projection, catalogs, and static scene

- implement pure four-view projection/picking/viewport bounds;
- add two direct JSON files and exact loader/cache;
- draw Earth, static Water memory, walls, door frame/leaf, torch body, grid,
  rails, and hover diagnostics;
- prove subjective disclosure and 64 x 64 locality.

Stop before animation if any asset requires inference or any frame scans the
whole world.

### Slice 5 — shared clock, exact Water, and flame

- implement vectorized oracle-matched Water;
- implement exact flame frame order;
- connect both to one injected presentation clock;
- prove chunk seam, phase continuity, memory behavior, and animated-work counts.

Stop on fidelity drift; do not replace Water with a tint or GPU dependency.

### Slice 6 — async playback and integration

- compose startup/open/close producer;
- add exactly two capacity-three queues;
- display one interval at a time with finite hold;
- prove mechanics run-ahead, E/R/D/T, exact frame parity, and terminals;
- add real multi-frame SDL-dummy, fresh-process content-bootstrap/action, and
  manual window proof.

Stop before actors, movement, combat, spells, WorldModifiedEvent consumption,
or a general animation scheduler.

### Slice 7 — final acceptance

- run every Section 17 lane;
- inspect exact diff and unrelated-work preservation;
- record manual profiling/counters and visual proof;
- obtain correctness/information-boundary review;
- obtain anti-slop review; and
- obtain anti-OOP/ECS/dependency-DAG review.

Any repair reruns affected evidence and all three final reviews.

## 19. Explicitly excluded and rejected shortcuts

Excluded from this plan:

- actor Sprites, rigs, equipment layers, movement, attacks, reactions, death;
- the two-player-character scripted encounter and enemy AI;
- spells, projectiles, impacts, persistent VFX, and audio;
- torch extinguish/reignite playback;
- runtime structural authoring or WorldModifiedEvent consumption;
- elevation art composition beyond projection/picking proof;
- foam, shores, extra materials, props, windows, and broad asset catalog;
- player command UI, action discovery UI, targeting, and Encounter controllers;
- server, SSE, SDK, transport, save/load, persistence, and replay framework.

Rejected implementation shortcuts:

- copy/serialize arbitrary Events;
- delete objective Events after reduction;
- add to_subjective(), to_render_event(), cues, or render methods to Events;
- instantiate Senses or query GridMap from the renderer;
- derive illumination from flame pixels;
- read SPATIAL_LIGHT_CHANGED instead of effective observer light;
- treat visible Tile as visible contents;
- canonicalize or duplicate the tile-owned boundary;
- model wall/door state in client-only fake classes;
- put pygame asset IDs into engine state, repurpose legacy sprite_name/
  visual_item_name for this client, or widen this cut into CR-8 cleanup;
- read external asset repositories at runtime;
- copy the whole asset library or run its generator;
- infer assets from filenames/tags/selectors;
- raster rotate/mirror missing views;
- approximate Water with a blue overlay or per-Tile filter;
- add a GPU/shader dependency for this software cut;
- scan all 4,096 Tiles each frame;
- add broad chunk/scene management abstractions;
- use callbacks, futures per Event, sleeps, or queue emptiness as completion;
- block mechanics on presentation queue consumption;
- let continuous animation prevent terminal settlement; or
- continue into actor/V-2 work because this seam passes.

## 20. Completion boundary and successor

This plan is complete when one executable and its tests prove that:

- the current engine authored a 64 x 64 semantic world and real observer;
- the ordinary torch, door, light, FOV, and sensory systems produced all state;
- exact existing Event values crossed a passive async boundary;
- the renderer stayed one observer-authorized reduction of those values;
- Earth, exact animated Water, walls, door, and torch rendered from direct data;
- Water and flame shared one continuous presentation clock;
- closed-open-closed mechanics ran ahead but displayed in human order;
- camera/picking/Z diagnostics worked in four views;
- frame work was local rather than proportional to 4,096 Tiles;
- every source Event had visible coverage; and
- no second mechanics/event system, callback chain, OOP renderer hierarchy,
  import cycle, asset inference layer, or server dependency was introduced.

The immediate successor is the V-2 actor/scripted-encounter plan: two
player-controlled preset characters plus enemies, layered actor Sprites, and
movement/attack/reaction animation driven by the same Event bridge and
terminal semantics. The remaining V-1 extensions—WorldModifiedEvent-driven
live authoring and a full elevated asset composition—stay separately bounded
unless the actor plan first proves they are required.

## 21. Validation protocol and review record

Before implementation, three independent reviewers must reread this entire
amended candidate against the current checkout and governing documents:

1. correctness/information-boundary reviewer — mechanics facts, Event
   admission/passivity, subjectivity, door/light causality, Water fidelity,
   reset, async clocks, terminal semantics, and testability;
2. anti-slop reviewer — unnecessary types/modules/indexes/queues/caches,
   premature generality, inflated asset/work scope, redundant tests, and
   simpler exact alternatives; and
3. anti-OOP/ECS/dependency-DAG reviewer — StandingTorch reuse, component/world
   ownership, renderer shadow-state pressure, import direction, callback/
   reflection pressure, and circularity.

Any rejection requires correcting this file and a complete reread by all three
reviewers. The earlier narrow-plan approvals do not authorize implementation of
this amended candidate.

Review record: **accepted**.

- Substantive candidate reviewed: SHA-256
  f10f8828ca1d85efa8e932209f519f99f3984883e04a681449de4c11d3d7569c.
- Correctness/information-boundary: APPROVE after complete reread; no remaining
  mechanics, Water/light, Event, async, or testability blocker.
- Anti-slop: APPROVE after complete reread; every retained module, cache,
  queue, evidence field, asset, and test serves the current vertical seam.
- Anti-OOP/ECS/dependency-DAG: APPROVE after complete reread; no shadow
  mechanics owner, scene hierarchy, callback chain, cycle, late import, or
  dependency inversion.
- The only post-review edit was this status/review record. All three reviewers
  must reconfirm the final file bytes before implementation begins.
