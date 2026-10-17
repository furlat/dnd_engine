# Single-pass change propagation — analysis and plan (v3.15)

Date: 2026-10-16. Status: **APPROVED by the human 2026-10-17 (incl. D7c, Q7 EXECUTION convention, temp-HP record-only).** **v3.5 adds available-actions discovery (§14, PD1/PD2) per the human's 2026-10-17 decisions (model approved 2026-10-17).** **v3.6 folds in the §14 antislop/antiOOP reviews and the whole-world-scan redesign. v3.7 folds in the v3.6 re-reviews, the human's answers (D14 approved; Q-W1, Q-W3, Q-W4 decided) and the first P0a measurements; open items are in §14.10.** Implementation is at P0a.

**Hard rules from the human (2026-10-17):** "do not let old path exist and fallbacks — we want one correct way for things to work, and then fix if it breaks stuff; it means we did not plan in advance well enough." Every replaced mechanism is deleted, not kept beside the new one; no compatibility shims, no fallback branches, no feature flags. A breakage is fixed in the one path, and the plan is corrected if it missed the case.

- **Worktree** (canonical copy of this plan):
  `/home/tommaso/.codex/worktrees/single-pass-propagation/dnd_engine`
- **Branch:** `codex/single-pass-propagation`, created from `d13e6ad083f` on the
  human's instruction. Agents don't commit.
- **Base:** `d13e6ad083f` (spell worktree: Antimagic removed, schema 11;
  production `229ce` is its ancestor). All refs are base-relative lines.

| Abbreviation | Path |
| --- | --- |
| BA | `dnd/core/base_actions.py` |
| ACT | `dnd/actions.py` |
| AC | `dnd/spatial/area_conditions.py` |
| EV | `dnd/core/events.py` |
| GM | `dnd/core/gridmap.py` |
| SEN | `dnd/blocks/sensory.py` |
| EVO | `dnd/spells/evocation.py` |
| CONJ | `dnd/spells/conjuration.py` |
| ABJ | `dnd/spells/abjuration.py` |

Companions in this worktree's `agent_docs/`:

- `AOE_SYSTEM_INDEX_2026-10-16.md`: patterns, ordering hazards, handlers.
- `CODEBASE_STUDY_NOTES_2026-10-16.md`
- `ENGINE_PERFORMANCE_HANDOFF_2026-10-16.md`: measured evidence.
- `ENGINE_COMPUTATION_THEORY_2026-10-16.md`

## 0. Human direction

**Problem:**

- "cut times by a lot … things trigger multiple cascade across sensory systems
  instead of happening only once and same sensory computations are repeated across
  observers"
- "invalidation and recomputations are global while often only e.g. 1 light source
  changed … pervasively across many systems that might be untracked"

**Method:**

- Stress with "big rooms with lot of people and lights and destroyable objects".
- Analysis and an analytic plan with expected recomputation counts, before any
  code, in a new worktree.
- "the main leading change will be a new event containing the accumulated changes"
  (§5.5).
- "separating objective physical changes from how a single agent perceives it …
  light interacts with subjective stuff" (§4).
- "all area of effect spells … index all of them … DO ALL THE WORK". Spell-level
  work is owned here.

**Decided:**

| # | Decision |
| --- | --- |
| D0 | Base `d13e6ad`; Antimagic stays removed ("hundreds of edge cases") |
| D7 | The per-target loop "was intended to be something that could be parallelized" |
| D7a | "we do all damages (all damage reactions happen) … nothing magical … choices on order that earlier was implicit in the loop". Reactions can't affect other targets; Counterspell "way before". |
| D6a | One damage roll per area effect |
| D6 | "if we have any other bugs they need to be fixed" |
| D11 | Worktree created on instruction |
| D12 | Available actions in scope (§14): env use within reach + move+use suggestions; no object attack rows; AoE aim points per perceived creature with hit sets; spells listed once with allowed levels; single space scan; "make it fast" |
| D13 | Movement destination list kept ("we need the path to know if reachable… important for ai") |

## 1. Stress scenario "Gallery Crowd" (GC)

Lantern Gallery (`dnd/scenarios/battlefield_catalog.py:357`):

- hall x 24–71 × y 2–37 (1,728 cells), dark;
- 26 hall wall torches lit by the fixture + 6 carried (L = 32);
- 30 creatures (party 4, enemies 26), 2 audiences;
- sight radius 80 (`encounter_assembler.py:379`), so V ≈ 30 observers per hall
  cell;
- ~100 breakable props: monuments, statues, bookshelves and crate stacks block
  optics and propagation and leave debris; plus oil barrels.

Cases (one or more per index pattern):

| Pattern | Case | Instance values |
| --- | --- | --- |
| P-a | Circle of Death into the crowd; Holy Aura on 8 allies; Blindness ×3 twinned | 12 hit, 8 die |
| P-b + P-f | **Fireball classic** | T=10, D=6, Lc=1 corpse torch, B=5 light-blocking props (each K≈3 in-range sources, f=1 debris cell), 1 oil barrel (c=9) → spill → ignite |
| P-c | Magic Missile at 3 targets incl. a Shield holder; Chain Lightning (primary + 4); Color Spray | — |
| P-d | Sleet Storm cast and drop (C≈200, obscured); Ice Storm (C≈49, 4 deaths) | — |
| P-e | Gust of Wind zone (terrain, anchored) with caster walking 6 steps; Spirit Guardians walk (membership only, no terrain); Cloudkill caster turn | — |
| P-g1 | Pressure plate → gas vent; portal with 3 occupants; Delayed Blast bead destroyed by Fireball | — |
| P-g2 | Turn Undead on 6 undead | — |
| P-h | Wall of Stone | S=10, D=4 displaced, E=1 escaper, p=3 path steps |
| P-i | Round step with 3 ROUNDS zones (Sleet, Entangle, Gust) | — |
| Light geometry | Darkness cast, then Daylight dispelling it | — |
| Ordered | Thunderwave pushing 4 creatures 10 ft into Spike Growth; Mass Heal; summon retirement | 8 ENTER entries |

Routine baselines: creature step, torch-bearer step, door toggle, turn start, AI
decision.

Discovery (Choices) baselines (§14.6):

- the party caster with the godmode grant of all ~47 area/multi-target spells at levels 1–9 (the held experiment's worst case);
- one enemy fighter (weapon attacks + env use);
- each measured as cache miss, cache hit, Preview and Command.

All counts are predictions; P0b measures them.

## 2. Cost model (hypothesis until P0b)

Sensory cost = `Σ settled facts × candidate observers × cost(path)`.

- FR = one full `recompute_observer` (SEN:708).
- Constants fitted from the saved production gallery runs (V=6):
  - ≈5.2 ms unobscured FR;
  - ≈44.6 ms under Sleet obscurement (attributed, unprofiled, to the per-cell
    supercover walk SEN:819-866);
  - ≈8 ms Ice Storm.
- The cost-only Sleet arm (1,487 ms) is not yet reconciled.
- P0b measures FR count and time, per-version cost, per-seat publication and AI
  reduction, reconciles, then scales to GC.
- The discovery cost model is §14.6 (rows × variants × candidates × per-candidate copy/validation, now vs after PD1).

## 3. Root causes

| # | Cause | Main sites |
| --- | --- | --- |
| R1 | One logical change → many facts/passes | per-cell tile events AC:1339-1427; per-source light events GM:5985-6042; manual reducer + completion AC:972, 1510; duration republish AC:964-974; death chain (`entity.py:2531-2556`, `base_block.py:572-589`); destruction chain (`blocks/base_item.py:722-782`); identity computation per version EV:2159-2172 |
| R2 | No objective→subjective delta | full recompute for perceivability/death/effect; tile hint `requires_paths=True` GM:1629 blocks the cheap path (movement doesn't touch observer revisions); light eligibility by causal parent SEN:1639, 1843-1857; `_paths_dirty` boolean |
| R3 | Global invalidation | whole-cache clears GM:584-641; three-channel area bumps AC:285, 472, 662, 742, 1572; light recompute scans all sources GM:5985; per-entity caches on global counters (`entity.py:6103-6113, 6181-6187, 6648-6699`); Fireball re-stage on any propagation bump EVO:1039; choices on any cursor change |
| R4 | Objective work repeated per observer/seat | per-observer boundary snapshot, obscurement capture + supercover walks, light descriptors (GM:4139-4219, 5383-5450, 5539-5578); per-seat capture/folds (`player/capture.py`); AI knowledge re-sorts |
| R5 | No group semantics | per-target EXECUTION re-dispatch BA:2218 (every CAST_SPELL/BASE_ACTION execution handler and every CAST_SPELL effect handler re-runs per target; Counterspell has no root guard ABJ:939-965); handlers acting on others fire mid-loop; shared mutable `self.target_entity_uuid` (BA:2201); per-target damage rolls; 4 sort keys |
| R7 | Discovery enumerates instead of solving | per-level variant rows; per-cell LOS/wall/AoE candidates with deep copies and eventful validation; object target pools; whole-world scans; caches keyed on the event cursor; discovery/execution footprint mismatch (§14) |
| R6 | Untracked or misplaced writes; channel strings | condition positions without bumps GM:1542, 1663; `Tile.edit_movement_cost`; 31 private GridMap accesses from content through `get_map()` locals; outside `_paths_dirty` writes; `Set[str]` channels + positional revision tuple |

## 4. Objective physical layer vs subjective perception

*For sensory settlement this section is superseded by §6b PV1: one settlement path over owned grids. The objective-layer rule (owners write; revisions bump at the write) stands.*

**Objective layer.** Owners are GridMap, Tile, Item and Entity fields; no observer
is involved. Revision bumps and cache invalidation happen **at the write**, so
objective reads are never stale.

| Kind | Storage / rule |
| --- | --- |
| Geometry | blockers, boundary structures (`_object_placements`, bands). FOV from an origin is a pure function of origin, radius and blockers. |
| Obscurement | `_optical_obscurements_by_position`. The push API exists; AreaCondition becomes its writer and the pull branch goes. |
| Illumination | `Tile._light` contributions, `source.affected_tiles`. A geometry change re-lights only the sources whose lit area contains the cell. |
| Movement | tile costs, occupancy, walkability |
| Subject state | position, stealth DC, invisible, life state. The life-state commit stays atomic and immediate: occupancy, light suppression and perceivability together. |

**Subjective layer.** `SpatialSensesSystem` writes each observer's `Senses`:

| Derived item | What it is |
| --- | --- |
| Sight field | FOV from origin within range |
| Perceived light/visibility | objective light × modes (darkvision, devil's sight, truesight) × obscurement along the route |
| Contacts | stealth vs passive perception; invisibility vs truesight/see invisible |
| Known hazards | the owner's `is_hazardous_for`, per observer |
| Navigation | movement data + perceived blockers + hazards |
| Memory | `seen` and contacts. Only advanced. |

**Dependency table.** An objective change at X triggers this subjective work for
each affected observer:

| Objective change | Subjective work |
| --- | --- |
| Geometry | field in X's shadow region, then light/contacts/hazards there |
| Obscurement | visibility for cells whose route crosses X |
| Illumination at Y | perceived light at Y ∩ field + contacts there |
| Movement | navigation freshness only (revision compare); occupancy also updates one contact |
| Subject | that one contact |
| Own capability | own light/contacts/hazards |
| Own move | field from the new origin |

**Data model:**

- One channel enum in the leaf `dnd/types/world.py`, keying
  `observer_spatial_revisions`.
- Writers derive the channels.
- The reducer picks work from the fact's data and per-observer revisions, never
  from causal parents.
- Geometry uses objective positions (`get_position()`), never another block's
  `senses.position`.

## 5. Groups and single settlement

### 5.1 The rule (D7/D7a/D6a)

For any area or multi-target effect:

1. **Root:** cast-level reactions once, at declaration/execution, as today.
2. **A. The effect on every target, in one fixed order:**
   - one shared damage roll, with roll-level modifiers applied once (Overchannel
     maximize, Empowered Evocation);
   - then per target: save (fixed order) → target-level modifiers inside the damage
     lifecycle (Sculpt Spells, Potent Cantrip, resistance, Shield, Death Ward,
     Relentless Rage) → HP → death state;
   - plus the same-instant effects: terrain, ignition, ash, debris, and all stages
     of one Fireball/payload blast.
   - **Pushes resolve step by step, inline, per target in the fixed order.** Each
     step fires its traps, zone/residue/portal entries and falls on that step. A
     step that kills, incapacitates or forces a retreat stops that push, exactly as
     today (`actions.py:411-430`).
3. **Settle once:** one light publication + one subjective pass per affected
   observer.
4. **B. Reactions to A's damage and deaths, same order, each its own group:**
   Hellish Rebuke, Retaliation, Fire Shield, Holy Aura blindness, concentration
   saves and releases, aura refresh, summon departures, payload explosions.
5. **The spell completes.**

**Movement is always step by step and is never a group** (human, 2026-10-16:
"opportunity attack could happen and kill before even other steps happen or traps
get hit").

- **Voluntary movement (Move):** each step commits on its own. OA, traps and zone
  entries fire on that step; a kill or incapacitation stops the move before the
  next step (`actions.py:836+`). Perception settles on that step, so the AI and the
  next OA see it. The only change is the cost of that per-step update (the §4
  delta instead of a full recompute for other observers).
- **Forced movement inside a group:** the same per-step trigger semantics. Only the
  observers' perception update is deferred to the group's single settle; no OA
  applies to forced movement.

### 5.2 Where groups open

| Entry | Covers |
| --- | --- |
| Convolution branch of `_apply_action` (BA:2514-2545), from target resolution through `_finalize_aoe` | P-a, P-b (one group per blast; stages are sub-steps), P-c, `_finalize_aoe` installs, P-f, residues |
| `SpatialCondition.activate` (AC:580-627) | zone install incl. APPEAR |
| Zone move: `relocate_anchor` / `move_zone` / `_change_footprint` | P-e |
| Wall formation (`wall_constructions.py:641-715`) | P-h |
| In-cast free loops | Ice Knife burst, Moonbeam/Glyph initial exposure, `payload_blast` |
| P-g2 nested batches (Turn Undead etc.) | — |
| Round step (`encounter.py:712-716`) | zone ticks/expiries |
| Trap/plate fire, portal transfer, material interaction | — |

**Nesting:**

- An entry reached inside an open group joins it.
- Phase-B items run after depth returns to 0, each opening a fresh group.
- `BaseAction.apply` itself does **not** open a group. Single-target actions and
  each Move step settle per fact through the §4 delta, as today but cheap.
- Move is `POSITION_PATH` (`actions.py:563`), so OA and attack validation keep
  per-step perception (`reactions.py:50`, `actions.py:261`).

**Mechanism:** a dedicated ContextVar on `EventQueue`, next to
`_event_batch_depth` (EV:1285-1292). It holds the group root event uuid, the
entry-kind stack (a leaf enum in `dnd/types/event_facts.py`) and the
deferred-dispatch list. It is **not** `batch_on_event_callbacks`, which encounter
opens around a whole controller decision (`encounter.py:1365-1375`).

### 5.3 Inside a group

1. **Fixed order.**
   - `resolution_order_key(block)` in `base_block.py` (`get_position()`, name,
     uuid) replaces the `getattr` in `target_resolution_sort_key` (BA:118-127). That
     `getattr` is an AGENTS.md violation and mis-sorts carried and unplaced items
     at (0,0).
   - Sort once at the iteration owner (`_resolve_execution_targets` /
     `_apply_target_batch`).
   - Exceptions: player-selected `get_all_targets` order (Chain Lightning primary
     at index 0, darts, Mass Heal targets) and authored physical order
     (supported-item depth composes `(depth, *key)`; material op order).
2. **Objective writes and their revision/cache invalidation are immediate.** Only
   light publication and the subjective reducer defer. Fireball stage reach and
   push destinations therefore read current objective state.
3. **Perception reads see pre-group perception.** This follows automatically: the
   reducer records instead of settling, and the group check sits inside
   `SpatialSensesSystem.recompute_observer` (SEN:708), so direct callers
   (`update_entity_senses`, `materialize_navigation` in `entity.py`, `actions.py`,
   `evocation.py`, `necromancy.py`) are covered.
4. **Handler dispatch:**
   - `BaseHandler.group_dispatch: HandlerGroupDispatch {INLINE, AFTER_GROUP}`; the
     enum lives in `dnd/types/event_facts.py`; default INLINE.
   - While a group is open, EventQueue stores AFTER_GROUP dispatches as (handler
     uuid, deep-copied event) in arrival order (precedent EV:2040-2045) and replays
     them in phase B.
   - Deferred handlers must return `None` or the unchanged event, enforced like
     `validation_only` (EV:1959-1962). They revalidate liveness themselves.
   - **Spatial ENTER/LEAVE handlers (traps, zones, residues, portals) are always
     INLINE**, whether the step is voluntary or forced. They are per-step movement
     rules, not reactions.
   - **Non-handler consequences** are split: the inline part records state on its
     owner, and an AFTER_GROUP handler executes it. Precedent:
     `SpellPayload.detonation_requested` / `defer_detonation`
     (`spell_payloads.py:227-228, 263, 274`).
   - The concentration handler (today it returns a modified event) splits into its
     save/release (AFTER_GROUP) and inline bookkeeping. Summon departure and the
     encounter-end check split the same way.
   - An architecture test asserts every O handler in index §7 declares AFTER_GROUP.
5. **Root vs per-application handlers.** P3 produces a complete table for every
   CAST_SPELL/BASE_ACTION execution and effect handler: Counterspell, Silence,
   Hidden reveal, InvisibilityEffect reveal, Greater Invisibility check, Sanctuary
   self-break, MetamagicAutoRemove, Vicious Mockery, Globe, Sculpt Spells,
   Forcecage, Wet, Divine Health, Resilient Sphere.
   - The discriminator is `application` on ActionEvents (already the convention:
     `wizard.py:233`, `cleric.py:67/121`, `paladin.py:1121`) and `resolution_ref`
     for other events.
   - Counterspell and Greater Invisibility become root-only. Greater
     Invisibility's once-per-cast check is a rules point listed for sign-off (D6).
6. **Iteration isolation:**
   - per-target state lives on the per-target event, not in a mutated
     `self.target_entity_uuid`;
   - pools stay on their owners: the per-cast action instance (ephemeral via
     `instantiate`, BA:1818-1845) for Mass Heal/Sleep/Color Spray, and Guardian of
     Faith's lifetime zone budget;
   - one shared damage roll drawn at group open; saves in the fixed order.

### 5.4 Close sequence

The settle runs in the **group root event's pre-completion**. Sensory events then
attach to an open parent, and `located_entity_observer_uuids` (EV:441-449) is
computed from settled senses.

- `PreCompletionSystem` (EV:133-138) gains `settle_group(root)`, invoked through
  the existing `_pre_completion_systems` registry.
- `SpatialSensesSystem.settle_group` calls a public
  `GridMap.settle_pending_lights()` first, then runs one subjective pass per
  affected observer. The order is explicit in code.
- Pending work stays with its owners: GridMap's pending re-light cells, the
  reducer's pending facts. None of it lives in the ContextVar.
- Then phase B: deferred dispatches in order, each in a fresh group.

### 5.5 The accumulated-changes event (D1)

- **Independent loop** (no rule callback between iterations): terrain cells at
  install/footprint change/removal, the per-source light recompute, Sleet dousing.
  - Keep the writes and publish one `SpatialChangeEvent` with `change_type` and
    `WorldTileState` rows, accumulated through `SpatialRemovalPublication`
    (AC:48-55, 835-858).
  - **EFFECT dispatch is kept.** Readers migrate from `event.position` to
    `get_affected_positions()`: residue fear (`conditions.py:1150`), pending return
    (`entity.py:1047`), `_spatial_world_after_values`, `world_facts.py`.
- **Dependent loop:** residue deposits (each vetoable, `residues.py:244-245`) keep
  one fact per iteration; inside a group they settle at close.

### 5.6 Ordered cases

| Case | Resolution |
| --- | --- |
| Voluntary movement | not a group. Step by step as today: OA, traps and zone entries per step; a kill stops the move; perception settles per step via the §4 delta. |
| Forced movement (Thunderwave, Gust, Seismic Strike, Glyph detonation, wall displacement, stone escapes) | each target's push resolves step by step, inline, in the fixed target order, against committed occupancy. Traps, zone entries, falls and paid retreats fire on their step and can stop the push (`actions.py:411-430`), unchanged. |
| Pools/budgets | sequential on their owners; refunds on cancelled applications (PB) |
| Self-interference (Banishment of self, Exhale Dragon's Breath granter, markers, Faerie Fire) | concentration release in phase B; all targets resolve under the pre-group grant |
| Perception publications per target | settled once at close |
| Fireball / `payload_blast` stages | One shared staged-loop implementation in `spell_payloads.py` or below; today it's duplicated (EVO:929-1045 and `spell_payloads.py:53-206`) with different keys. Each stage checks its own barrier set's `integrity is DESTROYED`; the item records its destruction lineage, feeding `prerequisite_destruction_lineages`. No event scan, no global propagation counter. A Delayed Blast bead destroyed mid-group detonates in phase B. |
| Material op order, barrel spills, supported depth, portal exit, plate pulses | authored order |
| Summon retirement, encounter end, aura refresh, anchors moved by pushed creatures | phase B |

### 5.7 Perception-read outcome changes (listed for sign-off)

Mid-group perception reads now see pre-group perception:

- unseen attacker/target on later rays (`conditions.py:1470/1489`);
- Frightened source visibility (`conditions.py:1120/1132`);
- Hidden reveal;
- Counterspell and OA eligibility;
- Chain Lightning secondaries;
- Color Spray/Sleep eligibility (already a pre-pass).

Geometry readers of `senses.position` switch to objective positions:
`creature_transforms.py:222/246`, `fighter.py:460`,
`barbarian.py:1095/1255/1378/1521`, `transmutation.py:807`, `conjuration.py:606`,
Thunderwave EVO:1606-1607.

### 5.8 P3 implementation record (2026-10-17)

**Mechanism.**
- `EventQueue.group(kind, root, *, shares_damage_rolls)`, holding `OpenGroup` (root uuid, entry kinds, deferred dispatches, shared dice). Entries join an open group.
- At the outermost close, each pre-completion system's `settle_group(root)` runs:
  - the reducer absorbs GridMap's one pending light fact, then gives each recorded observer one pass;
  - the summoning system resolves its recorded departures.
- Settled deltas and the light fact attach to the still-open root, because lineage capture cannot adopt children of completed facts.
- Then phase B replays the `AFTER_GROUP` dispatches in arrival order, each in a fresh REACTION group.

**Entries.**
- Convolution branch (AREA_APPLICATION).
- Zone install, move and removal: the zone's own change and the application complete after the settle.
- Round step.
- Moonbeam cast exposure.
- Wall formation (escapes, displacement, sections, appearance damage), Ice Knife burst, Glyph payload, `payload_blast` (one roll per blast).
- Nested batches: `_apply_target_batch` itself (Turn Undead, Preserve Life); inside an area it joins the area's group.
- Plate pulses (`activate_link`, the one dispatch to mechanisms), multi-target trap fire, portal occupant transfer.
- Material interactions: `resolve_interaction` (`dnd/spatial/ignition.py`) runs every declared interaction's EXECUTION/EFFECT in one group; all 8 emitters use it.

**Phase B work** is a list of callables in arrival order: deferred `AFTER_GROUP` dispatches and `EventQueue.after_group(run)` (a payload ended inside an area detonates after it). A nested entry that asks for shared rolls inside a non-sharing group shares only for its own duration (a phase-B blast still rolls once).

**Group settlers.** Owners holding work for a group register a settler on it (GridMap's pending light fact). They run after the pre-completion systems, so the light fact is published even when no sensory reducer is attached (no observers yet).

**Late-completing facts.** A zone's own change completes right after its group (its completion reads settled senses). The group lists it in `completes_after`; systems receive the `OpenGroup` in `settle_group`, and the reducer does not settle those observers a second time for it.

**Anchors.** An attached zone has two bindings: losing its anchor ends it inline (a broken trap cannot strike inside its own group), and following its anchor's moves is phase B.

**Occupancy-free facts.** Zone membership, residue and movement-topology facts take the hazard path even when a pending step has bumped occupancy; the step's own fact settles contacts afterwards (anchored zones no longer force a full recompute mid-step).

**Shared staged loop** (§5.6): `resolve_staged_area` in `dnd/spatial/area_reach.py`, used by Fireball and `payload_blast`. Each stage continues only when one of its own propagation barriers is `DESTROYED`; `BaseItem.destruction_lineage_uuid` (recorded at the accepted breakage) feeds `prerequisite_destruction_lineages`. No event scan, no `propagation_revision`.

**Shared roll.** `Damage.get_dice` returns one `Dice` per (source, packet, outcome) inside a sharing group: area effects, zone install/move, cast loops, round step, and multi-target effects without attack rolls.

**Root vs per-application handlers:**

| Handler | Placement | Reason |
| --- | --- | --- |
| Counterspell | root only (E) | one interruption per cast |
| Greater Invisibility check | root only (F); creation lineage = root cast | one check per action |
| Hidden / InvisibilityEffect reveal | per application, idempotent | the first application removes it; the rest no-op |
| Sanctuary self-break, MetamagicAutoRemove | per application, idempotent | caster bookkeeping consumed once |
| Vicious Mockery | per application | consumed by the first ray (authored) |
| Sculpt Spells, Globe, Forcecage, Wet, Divine Health, Resilient Sphere | per application | admission filters must see each target |
| Silence | root | casting under Silence is blocked once |

**Outcome changes for sign-off:**
- reactions, concentration saves, aura refresh, summon departures and anchored zone moves now resolve after every target's effect;
- one roll per area or simultaneous multi-target effect (Chain Lightning and Magic Missile included; attack-roll effects excluded);
- a cast's concentration that ends mid-batch stops re-sustaining later targets (J);
- the Sleep/Color Spray pool refunds vetoed candidates;
- separate arrival / turn-start / turn-end fences;
- Moonbeam cast exposure counts against the fence;
- the Spirit Guardians slow only follows an admitted trigger;
- Thunderwave and 9 other readers use objective positions;
- the concentration check no longer rewrites the damage event's status message (the loss is carried by the release facts);
- a staged area reaches further only through its own destroyed barriers, not any propagation change elsewhere on the map;
- a payload ended inside an area (holder or caster killed by a Fireball) detonates after that area resolved;
- **PB3 (Q7) consequence:** zone turn triggers at EXECUTION run before the turn's duration advance, so Stinking Cloud's Nauseated ends at the creature's turn end ("spends its action that turn") instead of a 1-round duration that would expire in the same turn start;
- **C/Q2 consequence:** the gas trap test "appearance, entry and turn start share one exposure per turn" fails: the trap declares `{APPEAR, ENTER, TURN_START}` as fenced, the same shape as Cloudkill and Black Tentacles, which Q2 names as separate triggers. The test is left failing for the human.

**Deferred.**
- Per-target state off `self.target_entity_uuid` goes to PD1b: every `_apply` reads it, and PD1b's selection carries the targets. P3 keeps the save/restore in `_apply_target_application`, so a phase-B replay sees the root target, never the last one; pools are per-cast (D).
- L12 (Guardian of Faith presentation centre) needs a protocol decision: `SpherePresentationGeometry.center` is a cell, and a Large footprint's centre is a half cell (float centre or a footprint geometry kind). Human.
- Bug G goes to PD1b.
- `requires_paths` / `_paths_dirty` deletion goes to P5.

### 5.9 Residue field per material (D15, 2026-10-17)

Measured: a body response or Fireball's ash deposits tile by tile; each new tile is a full condition lineage
(application 4 versions + membership commit 2) and each accumulation its own tile fact. Stubbing body responses:
Circle of Death 1.15 s → 0.58 s, 1,298 → 542 versions; Fireball 739 → 624 ms.

- **Data on tiles.** Each `Tile` holds its residue after-values per material (`TileResidueState`, the existing wire
  type; `condition_uuid` is the per-cell identity `uuid5(field, cell)`, stable across deposits). `to_world_tile_state`
  reads them; nothing reads residues from tile conditions.
- **One field per material per map** (`ResidueField`, owned by the map, keyed by `residue_id`): deposits, one
  `SpatialHandler` over its hazardous cells (entry damage / fear, unchanged rules), traversal invalidation for new
  hazardous cells, connected-ground queries for fear (`same_residue_ground` reads tile data).
- **One deposit = one call = one fact**: `deposit_residues(cells → ellipses, profile, …)` updates every cell and
  publishes one tiles fact (inert rows; `commit_tile_mechanics` when new hazardous cells appear). Body responses,
  Fireball ash and spilled containers call it once per deposit. No residue condition lineages.
- Object-face residues (`ObjectResidueCondition`) are unchanged.

## 6. Predicted counts (GC)

| Unit | Meaning |
| --- | --- |
| FR | full recompute |
| P | §4 pass for one observer |
| O | the number of phase-B items, each its own group |

- "After P3" assumes P1–P3; global cache wipes remain until P5.
- "Conservative" prices P as FR. Millisecond targets are in §6a (D18); this table keeps the counts.

| Case | Now | After P3 (conservative) | After P5 |
| --- | --- | --- | --- |
| Circle of Death (12 hit, 8 die) | 8×31 = 248 FR (~1.3 s) | 30·(1+O) P | wipes 0 |
| Holy Aura ×8 | ~240 FR | 30 P | — |
| **Fireball classic** | ~816 FR + barrel (2c+7)·V ≈ 750 FR + 1,470 hazard-only; ~25 wipes | 30·(1+O) P (~150 ms + O); wipes remain | 0 wipes |
| Magic Missile / Chain Lightning / Color Spray | deaths·(V+1) + blinds·V | 30·(1+O) P each | — |
| Sleet cast (C≈200) | 202·V = 6,060 FR obscured (~270 s) | 30 P obscured (~1.35 s) | — |
| Sleet drop | ≈6,030 FR (~30 s) | 30 P (~150 ms) | — |
| Ice Storm (C≈49, 4 deaths) | ≈1,654 FR (~13 s at 8 ms) | 30·(1+O) P | — |
| Gust of Wind zone, 6 caster steps | per step (1 + 2ΔC + L)·V | per step: zone-move group ≤30 P | — |
| Wall of Stone (S=10, D=4, E=1, p=3) | S·V + 2V + 3D·V + 2E·p·V ≈ 540 FR | 30 P + escape steps (per-step deltas) | — |
| Round step, 3 ROUNDS zones | 180 FR | 0 solves; ≤30 descriptor updates if duration is projected | — |
| Thunderwave ×4 (10 ft) into Spike Growth | pushes × steps × 8 ENTER cascades | 30 P; the 8 Spike Growth entries resolve inline on their steps | — |
| P-g1 / P-g2 / Darkness–Daylight / summon retirement | measured in P0b | 30 P per group | — |

**P1 residue, stated honestly:** once `requires_paths` is gone, C·V hazard-only
refreshes and C versions remain per terrain install until P2.

**Non-sensory terms**, reported separately:

- versions × per-version cost (the base adds `ActionCostsCommittedEvent`,
  `ActionApplicationCommittedEvent`, `ConditionMembershipCommittedEvent` and
  `EffectApplicationEvent` ×3);
- per-seat publication (handoff 47–350 ms);
- rules work;
- AI knowledge reduction;
- turn-start navigation;
- AI decision;
- Choices: modelled in §14.6 (PD1/PD2).

## 6a. Whole-action targets (D18)

Human, 2026-10-17:

- "of course we need good targets for all the slowdowns we are getting this needs to be smooth and playable";
- "i would say that 100ms is the max for any operations above that is crazy / 50 starts getting acceptable / <20 / <16 is where we would love to be";
- "in general anotehr constraint no more than 100kb for each payload -- it should be more than enough to handle a single sub turn event";
- "for now I would like to ignore gc mangament and reach the point where gc does not trigger or is not meaningfull it is more of an alaarm button for us now".

§6 prices perception only. These targets cover the whole request the player waits on and every update the server sends.

| Tier | Rule |
| --- | --- |
| **Ceiling** | No run of any operation over 100 ms; no seat update or request response over 100,000 B encoded (`encoded_bytes`, `response_bytes`). |
| **Acceptable** | Median ≤50 ms. |
| **Goal** | Median ≤20 ms; ≤16 ms (one frame at 60 fps) is where we want to be. |

§6's Sleet sensory target (≤150 ms, "P4b + D9") is above the ceiling and withdrawn; §6b owns that term.

**How a row is measured.**

- One row per operation of every `gallery_crowd.py` CASES entry; the exit can't be met by leaving rows out.
- 3 runs at one named commit, with no concurrent test or agent load. The median is held to a tier; every run is held to the ceiling.
- Wall clock, GC pauses included.
- Cast rows report the tool's five spans: construction, native, operation, publication, encoding. Request rows (Choices, Preview, Command, AI Advance) report the total; their split comes from the CPU sampler.
- Payload: the largest encoded seat update of the operation (`encoded_bytes`), or the response (`response_bytes`) for requests.
- GC is an alarm: gen-2 collections per operation are counted (`gc.callbacks`, to add to the tool) and reported with the row.

**Now.** ms are median / worst of 3, with native / publication medians where the tool reports them; B is the largest update or response. The figures are provisional: most logs date from 16:34–16:47, before a7a2b9bf0, and the fighter Choices logs from 12:27, all under agent load. Rows marked *1 run* come from one loaded run. Every row is re-timed at one commit once the current agent wave is merged.

| Row (GC case, operation) | Now ms | Largest B | Owners |
| --- | --- | --- | --- |
| Preview, caster | 7 / 8 | 1,956 | goal met; keep |
| Preview, fighter | 5 / 5 | 853 | goal met; keep |
| Choices hit, caster / fighter | 0 / 0 | 512,290 / 125,524 | PD2 (bytes) |
| Choices miss, caster (123 rows, 1,474 targets) | 252 / 261 | 512,290 | PD1b, PD2 |
| Choices miss, fighter | 140 / 148 | 125,524 | PD1b, PD2 |
| Command, fighter attack | 46 / 48 | — | acceptable; P6, P7 |
| Command, caster Fireball | 668 / 685 | — | P6, P7, PV1–PV3; the gap to the direct cast is measured with the sampler |
| Fireball | 323 / 343 (159 / 148) | 1,023,988 | P6, P7, PV1–PV3 |
| Circle of Death | 334 / 359 (156 / 158) | 1,110,472 | P6, P7, PV1–PV3 |
| Ice Storm | 203 / 205 (85 / 101) | 681,267 | P6, P7, PV1–PV3 |
| Sleet Storm cast | 513 / 536 (265 / 226) | 1,690,189 | PV1; P7, PV2, PV3 |
| Sleet Storm concentration drop | 769 / 790 (191 / 538) | 5,169,992 | PV1; P7, PV2, PV3 |
| Cloudkill cast (*1 run*; encoding 318 ms) | 808 | 971,673 | PV1; P7, PV2 (encoding), PV3 |
| Cloudkill concentration drop (*1 run*) | 560 | 7,475,101 | PV1; P7, PV2, PV3 |
| Darkness (*1 run*) | 739 | 801,180 | PV1; P7, PV2, PV3 |
| Daylight (*1 run*) | 661 | 6,093,663 | PV1; P7, PV2, PV3 |
| Gust of Wind cast | 190 / 196 (133 / 37) | 275,229 | P5, P6, PV1; P7, PV2, PV3 |
| Gust of Wind move | 93–102 / 105 (51–63 / 31–37) | 245,183–247,982 | P5, P6, PV1; P7, PV2, PV3 |
| Spirit Guardians cast | 81 / 88 (45 / 26) | 215,288 | P6; P7, PV2, PV3 |
| Spirit Guardians move (3 cells, aura carried) | 233–308 / 605 (123–166 / 99–115) | 532,552–559,829 | P5, P6, PV1; P7, PV2, PV3 |
| AI Advance, turn start | 304 / 345 | — | P7, PV1, PD1b / PD2, PT |
| AI Advance, decision only | 99–101 / 105 | — | PD2, P7 |
| AI Advance, acting (276 versions) | 327 / 351 | — | P6, P7 |

Encoding cost is owned by PV2: it falls with the bytes.

Rows still to measure: magic_missile, chain_lightning, holy_aura, mass_heal, mass_healing_word, delayed_blast_fireball, grease, web, spike_growth, thunderwave_spike_growth, caster_steps, turn_start, turn_undead, gas_vent_plate, portal_plate, wall_of_stone, summon_retirement, round_step_zones. Cases to add: a reaction on a human seat, and a whole AI round (§6b).

**Rules.**

- The exit passes only when every row holds the ceiling, in ms and in KB. A miss blocks the exit until the human decides.
- After each merged batch the integrator re-times every row and records the table in the progress log.
- A row still over the ceiling once its owners have landed gets its residual terms measured (sampler, counts) and reported to the human with a proposed phase. Targets are never silently changed.
- Rows come down by removing work in systems: facts, passes, copies, allocations, bytes.
  - No new cache or memo attributes on entities, blocks, values, conditions or runtime dataclasses.
  - No manager or registry classes, no lazy properties.
  - A value that must be kept is a frozen value owned by the system that computes it, keyed by named revisions, with its invalidation stated in this plan.
- GC tuning, freezing around operations, pooling and disabling the collector are not fixes.

## 6b. Subjective vision as data (PV1–PV3, D19)

Human, 2026-10-17:

- "maybe the whole subjective vision thing needs a fix so that we can get to arrays as quickly as possible";
- "you already know that nothing sees that no need to comptue shit" (a heavy blocker should prune work, not add it);
- "no reason for this stuff t obe sent we can have better handing and partial updateds on for bodies";
- "bro per seat or per observer is a nothingburger because worst case sceanrio is one observer one seat  for each character";
- "we need to handle the per seat scenario per observer but of course when shared we should optimize".

**Evidence (GC, 2026-10-17).**

- **Blocker size changes nothing.** Darkness (~28 cells), Cloudkill (~50) and Sleet Storm (~200) each cause 30 full recomputes over the same 50,535 observer-cell pairs.
  - Heavy obscurement is a per-cell filter over each observer's whole wall FOV (`recompute_observer`, optical stage).
  - The numpy route masks (`get_optical_route_masks`) already hold the answer, and are then walked cell by cell in Python.
  - Volume geometry, hazards, cell contacts, reverse memberships and emit are per-cell Python too.
- **The blue seat (26 observers) receives 1,690,695 B on the cast and 5,177,992 B on the drop.**
  - `observed_changes` is 51 % of the cast. It is derivable (0 mismatches over 3,543 rows), and no player-side runtime reader uses it.
  - Re-sent bodies are 76 % of the drop: 234 re-acquisitions of 20 actors, identical to what the client holds. The `| acquired` term in `capture.py:_capture_actor_admissions` bypasses the known-actor check.
  - 58 of 59 item fields are static per `item_id`.
  - Hazards are re-sent as `false` for every re-added cell, and light sources come back at the revision the client already holds.
- **Readers by cell** are heavy in sensory, entity pathing, projection, audience and the AI knowledge reducer; rules make about 24 such reads.

**First principles.**

- What can stop vision is a finite set: walls and optical boundaries, heavy obscurement, magical darkness, and the light level at the target cell.
- What can see is a finite set: plain sight, darkvision, Devil's Sight and Truesight (each with a range), plus blindsight and tremorsense.
- So subjective vision is a table, not a per-cell procedure. Today's rule (`_visual_route_modes`, `_route_light_levels`) is exactly:

| On the route | Plain sight | Darkvision | Devil's Sight | Truesight | Blindsight / Tremorsense |
| --- | --- | --- | --- | --- | --- |
| Wall / optical boundary | blocks | blocks | blocks | blocks | own reach rule (unchanged) |
| Heavy obscurement | blocks | blocks | blocks | blocks | ignores |
| Magical darkness | blocks | blocks | sees through in range | sees through in range | ignores |

- Light at the target cell: plain sight needs more than darkness; darkvision turns darkness into dim and dim into bright; Devil's Sight and Truesight turn darkness into bright.
- Per cell: 4 eligibility bits (plain, darkvision, Devil's Sight, Truesight). Range and the route's obscurement bits decide each bit. The effective light, or "not seen", is one lookup in a 16 × 5 table.
- A bigger blocker means more zeros, not more work.
- Only checks against specific targets stay per target, over the creatures and objects on visible cells, never over cells: invisibility, hiding, object inclusion, and boundary evidence.

**World grids: one owner each, replacing storage.**

| Grid | Owner and writer | Deleted |
| --- | --- | --- |
| Obscurement: per-owner footprint masks, with combined bits derived in the same write | GridMap, written only at the AreaCondition membership commit; `excluded_owner_uuid` reads the per-owner layer | `_optical_obscurement_by_position` push dict, the `condition.get_optical_obscurement_at` pull branch, `_obscurement_index`, `_optics_blocking` |
| Resolved light level | written where `_resolve_light_contributions` runs; `Tile.resolved_light_level` reads it | the per-tile resolved copy |
| Hazards | the owners' footprints already held by GridMap; per observer, each owner's `is_hazardous_for` is called once and its footprint OR-ed | per-cell hazard dicts |
| Occupancy | unchanged authority (tile membership); contacts iterate the occupants in the window and index the visible mask | — (no occupant grid) |

P4a's obscurement and light items fold into PV1, so that storage migrates once. P4b is closed: measured, not adopted.

**PV1 is split so that it doesn't collide with P7.**

- **PV1a** touches only sensory, GridMap, the new `dnd/core` view module and the rules / discovery readers. It can start now; the Sleet demonstration comes from PV1a.
  - The emitted sensory event keeps its schema: its cell lists are produced from the mask difference, so the cost scales with changed cells.
- **PV1b** comes after P7: the packed value through `SensesSnapshot`, `apply_current_senses`, capture, audience, the AI knowledge reducer and the SDK.

**PV1 — perception as arrays, end to end.**

- **The view function** lives in a `dnd/core` module and takes primitives: origin, the sense ranges, and the grids. numpy stays out of `dnd/types`.
- **The cell sets in snapshots, native events and wire** are one frozen packed value: origin, shape and bytes.
- **`Senses` holds published perception only:** window origin, visible, light and hazard arrays, the `seen` mask in map coordinates, and contacts. `ObserverField`, route modes, volume fields and the light epoch move into `SpatialSensesSystem`, keyed by observer uuid.
- **Rules and discovery** (~30 sites) read through a few pure query functions.
- **One settlement path:** observers whose window box intersects the change box are recomputed. The emit diffs the arrays directly.
- **Deleted:**
  - the hazard-only and scoped paths: `_can_scope`, `_update_scoped`, `_fact_scope`, `_refresh_footprint_scope`, the emitter change log (`light_epoch`, `light_sources_changed_since`, `forget_light_changes_through`) and the contact epoch;
  - the reverse cell indexes;
  - `Senses.apply_sensory_update`;
  - the set forms in `SensesSnapshot`, `capture_senses_snapshot`, `apply_current_senses` (the one shared reducer), the AI's `visible_index` / `seen_index` and `observers_by_known_position`.
- **The protocol changes freely.** The human said to ignore the Godot client: this repo's protocol and SDK are updated in the same change.
- **Gate.** The cases are sleet_storm, darkness_daylight, cloudkill, fireball, gust_of_wind_walk, spirit_guardians_walk and ai_decision.
  - **Spike** (devtools only): per-observer ms, plus equality with today's result on those cases.
  - **Equality** with recordings made at the pre-PV1 commit (an archived arm), with no flag in `dnd/`.
  - **Per-observer budget**, derived from §6a: sight windows cover the hall, so a settlement recomputes all ~30 observers. Their total must stay ≤10 ms (half the 20 ms goal), so each whole `recompute_observer` (view, contacts, hazards, emit) gets ≤0.33 ms, median over all observers on the cases.
  - **No per-cell Python calls** in the view path (counts mode).
  - **Area independence:** Darkness, Cloudkill and Sleet native ms within ±10 % of each other at one commit.

**PV2 — the rest of the wire.**

- `observed_changes` leaves the player `SensoryFact`; the native event keeps it.
- The HUD sends only the sheets that changed (91,468 B for blue when sent whole). Spatial effects are a content id plus packed cells.
- Expected seat bytes per row are recorded beside §6a's table when PV2 lands.
- Object and entity contact changes are packed uuid deltas. The client derives nothing.
- **Multi-observer seats** (human: "handle the per seat scenario per observer but of course when shared we should optimize"): each changed cell, body and item is sent once per seat, and each observer gets a bit list over the seat's shared cells. A one-observer seat is plain per-observer.
- No retained client-side state for cells out of view (human: "a bad idea to keep 2 states"). Cells coming back into view carry their light and hazard values, packed.
- **Combat log** (Fireball: 160,291 B in both seats' updates of 1,024,279 B and 358,941 B):
  - `sub_entries` is deleted (110 nested copies: 104 repeat another top-level event log). The client composes the tree from the node lineage the update already carries, and `target_entry_indices` indexes `children_lineages`. Flattened, the log is 41,504 B.
  - `root` is an index into `events`; the root event (44 KB) is sent twice today.
  - The rendered strings stay server-side (12.6 KB after flattening): no SDK renderer.
  - One data-only projection per seat replaces the three `project_combat_log` calls (`capture.py` ×2, `application.py` / `session.py`).
- **Version identity:** every wire reference to a version (`lineage_uuid`, `parent_event`, `source_event_uuid`, `commit_event_uuid`, `cause_event_uuid`) uses the seat's public occurrence index (`ProjectionState.public_versions`, already `source_index`), across updates. The uuid strings are dropped in the same change: 377 rows in blue's Fireball update, 72 % of them intermediate versions.
- **Gate:** every update ≤100 KB on every row.

**PV3 — bodies and items as patches.**

- There is one observation type: a patch against `ProjectionState.remembered`. First acquisition is a patch against an absent body, so there is no full-body branch.
- The patch is computed in projection, after disclosure, from a before/after of the touched actors.
- `remembered` changes only through `apply_player_fact` on the emitted patch, the same reducer the client runs.
- **Items:** the client can't know items in advance (human). A seat receives an item's full record the first time it sees that `item_uuid`, then only patches. `EquipmentFact` becomes an item patch. The `PlayerActor` / `VisualItem` types change, not just the encoder.
- **Gate:** no body bytes for unchanged re-acquisitions; the D16-C replica test passes.

**P7b — stored versions frozen, capture by reference.**

- The capture deep-copies every retained event (`capture.py:_retained_event` / `_detach_retained_event`; ~16 % of the sampled Fireball op, `smp_fb2`).
- The copy exists because stored versions are mutated after storing:
  - `_store_event` appends children into stored versions (`events.py:2333-2339`, `add_child_event`);
  - `phase_to` mutates the previous version's `combat_log` in place;
  - `conditions.py:2942` sets `combat_log` on a stored EFFECT version;
  - `post` is a shallow `model_copy`, so versions share containers;
  - events hold live objects (condition, values, costs).
- **Work:**
  - child links are read from the queue's lineage index;
  - combat logs are built by copy-update before `post`;
  - no shared mutable containers;
  - live objects are replaced by values where capture reads them;
  - then capture holds stored versions by reference.
- **Gate:** versions frozen at store; no `deepcopy` in capture; the wire is byte-identical.

**PT — turn start** (human: "of course bro it is unacepptable").

- First AI Advance, sampled under load:
  - AI knowledge catch-up ~48 %, folding every event since the AI's last turn: P7's AI item, plus PV1, since its indexes become arrays;
  - AI discovery ~33 %, mostly object-contact checks that build a pydantic object per contact, plus object HP reads: PD1b / PD2;
  - turn-start navigation ~11 %.
- **AI knowledge system (the catch-up's one owner).** `AIKnowledge` starts at cursor 0 and folds the whole history on the assignment's first decision: ~193 ms of the 398 ms sampled first Advance (`smp_ai`, loaded).
  - One AI-knowledge system owns the `AIKnowledge` values, keyed by assignment, and advances them at the EventQueue batch dispatch.
  - A new assignment starts from the same cold composition the seats use. Assignments are created at session setup, in the summon cast, on rebind, and lazily in `_ensure_assignment`.
  - Deleted: the lazy creation branch (unreachable) and the whole-history catch-up.
  - **Integrator decisions (AIK, 2026-10-17):**
    - One function, "advance this assignment's knowledge to the current cursor", called at batch dispatch for every assignment and by each decision or guard read for its own assignment. A read folds only the current batch's pending versions. The movement guard has to learn before a move completes (`tests/ai/test_event_knowledge.py`), so the pull can't be deleted outright.
    - A cold start from live state would be a second, inexact path. The objective part (world, actors, pending conditions, open events) is the same for every assignment: it is one shared fold per session, advanced once per batch. Each assignment folds only its observers' sensory facts, from the observers' birth. Creation is folded from the record at the explicit creation site.
    - Knowledge is keyed by the assignment object: opened at creation, dropped at close, cleared on generation reset.
  - **Gate:** at the first decision, `AIKnowledge` equals today's full replay on the GC cases, or the memory differences are listed for sign-off; the summon-cast row is measured.
- **Navigation:** one path search over a cost grid with a predecessor array. `walkable`, `paths`, `path_costs`, `safe_*` and `collision_blocked` stop being per-cell dicts and sets.
- **Gate:** the turn-start rows within the ceiling.

**PR — area-spell rules work (Fireball, Circle of Death, Ice Storm).**

After PV1a, Fireball's native time is ~200 ms (loaded), of which perception is ~37 ms. CPU sample `smp_fb2` (loaded, 736 ms op):

| Term | ms |
| --- | --- |
| per-target `_apply` | ~195 |
| saving throws (`saving_throw_bonus`, which sets and clears the target on every value of both creatures, plus deep copies; ~1.2 ms per read, P8) | ~60 |
| creature damage | ~45 |
| object damage and destruction (`_apply_destruction`, environment `_on_destroy` builders) | ~75 |
| event post / register over ~560 versions | ~68 |
| first-use pydantic schema builds inside the op (`model_rebuild`) | ~30 |
| enum property reads in hot loops | — |

- **Work:**
  - The target context of a value read is an argument, not state set and cleared on every value.
  - No deep copies on the save path.
  - Per-target damage and destruction do only what the rule needs.
  - Schemas are built at startup.
  - Hot enum reads are taken out of the loops.
  - Each removal is counted.
- **Gate:**
  - native ms of Fireball, Circle of Death and Ice Storm before/after;
  - P6's deterministic transcript (every version's fields, grants, combat logs and seat updates) identical;
  - counts of value context set/clear calls and deep copies on the save path → 0.

**PH — heap: the GC alarm** (human: "reach the point where gc does not trigger or is not meaningfull").

- **Measured (GC Sleet, HEAD 5c3b90e90; scratch `heap_attrib.py`, `heap_fields.py`):**
  - Every Sleet run carries exactly one gen-2 collection of 264–303 ms over ~600K tracked objects.
  - 587,332 tracked objects before the first op. Owners:
    - entity / block registry 351K;
    - player runtime 84K;
    - event store 81K, growing 16–20K per op;
    - unattributed 72K (item presentation states, visual items).
  - Inside the registry:
    - the `.values` of value-holding blocks ~183K: Health 53.6K, HitDice 32.4K, Ability, Skill and Equipment ~17K each, ActionEconomy 15K, Weapon 9K, …;
    - `Senses.paths` 42K lists;
    - `Senses._field` 35K;
    - `Senses.objects` 13.8K;
    - Tile containers ~25K, about 10 mostly empty containers per tile across 1,895 tiles.
- **Why it matters.** A full collection runs when long-lived objects grow by 25 %. At 600K objects and +20–40K per op, it lands every few ops, and each pass over 600K objects costs ~280 ms, which alone breaks the ceiling.
- **Work, each item removing objects rather than tuning the collector:**
  1. Per-op retained growth → ~0:
     - event versions hold no per-version sets or dicts of their own;
     - shared frozen rows (`ObservedChangeRef`, `PerceivedContact`) are not copied (P7b);
     - nothing else retains per-op containers.
  2. Value layer as data: each block's `values` becomes compact records in a system-owned table. Modifiers live in system tables keyed by value, with no per-value dict / set / list graph. Reads stay exact.
  3. Navigation as arrays (PT): `Senses.paths` becomes a predecessor array.
  4. Perception (PV1a / PV1b): no per-observer field graph; audience per-cell sets become arrays.
  5. Tiles: no empty per-tile containers. Absent means empty, and per-cell state lives in GridMap-owned maps.
- **Gate:**
  - 0 gen-2 collections inside any measured op on every GC row, with the default thresholds;
  - tracked objects before the first op and retained per op reported at each re-time;
  - retained per op ≤1K.

**Measurement cases to add:** a reaction that pauses for a human seat (an opportunity attack, Counterspell), and a whole AI round (every native-AI combatant's turn in sequence).

**Order.**

1. Spike (done).
2. PV1a, alongside PW (PV2's non-cell items and PV3).
3. PV1b after PV1a; PV2's cell packing with PV1b.
4. P7b after PW, because both edit `capture.py`.
5. The AI knowledge system after P7 (done); navigation after PV1, because it shares the grids.

## 7. Phases (execution order) and gates

**Order (decided 2026-10-17; the human left it to the plan):**

- **Sensory first:** P1 is the smallest change with the largest measured term (Sleet cast 5,931 FR).
- **PD1a before P3:** P3's shared staged loop consumes the one footprint function.
- **PD1b after P3 and the re-measure:** both rewrite `BaseAction.apply` and the per-target loop. P3 lands groups and per-target state first, then PD1b moves to `apply(scan, selection)`.

| Phase | Scope | Gate |
| --- | --- | --- |
| **P0a** | ✅ Worktree created, environment synced, docs copied. ✅ First counters added (full recompute, each sensory fast path, light-source FOVs, cache clears). ✅ Known failures triaged; stale tests fixed (69 pass). Running: cleanup of the 106 uncollectable test files. To do: GC fixture harness (§9.4); discovery counters (rows, copies, validations, footprints, emitted targets); remaining counters (P by kind, cache misses, facts by type, versions, deferred dispatches). Production comparison uses the archived arm `.runtime/causal-execution/production-229ce/` (no checkout). | fixture loads; counters visible; `--collect-only tests` has 0 errors |
| **PB1** | ✅ **Done 2026-10-17** (A, B: one latest-wins arbitration for activation and footprint moves, `SpatialCondition._begin_footprint_change`; K: monotonic revisions + path cache cleared in `clear()`, light reseeded in `create_rectangle`; tests `test_spatial_conditions.py::test_exclusive_conditions_latest_wins_without_raising`, `test_gridmap_rebuild.py`). Blocker bugs confirmed by verification: crashes (exclusive-surface raise, cloud-overlap raise), stale caches after `clear`/`create_rectangle`, any triaged failure blocking the fixture | failing-first case per bug |
| **P0b** | **Split 2026-10-17 so P1 isn't blocked on measurement: P0b-1 (now) = ordinary + counts for the P1/P2 gate rows (Fireball, Sleet cast/drop, Ice Storm, both Choices rows); P0b-2 (before P3) = the remaining GC, routine and production-arm rows.** Baselines: the saved production fixture (reconcile §2 and the cost-only arm), then every GC row, routine row and discovery row (§1); counts **and** ordinary complete-operation timings | each "Now" within ±15 % or the model corrected and the human told |
| **P1** | **Step 1 done 2026-10-17:** the reducer no longer treats `requires_paths` (movement topology) as a full recompute; support changes still force one through the observer optical revision. Sleet cast FR 5,931 → 90 (264 s → 7.8 s counts mode), drop 5,901 → 60 (31.7 s → 1.5 s); hazard-only residue 5,842 as stated. **Step 2 running:** `SpatialChannel` / `WorldEdgeChannel` everywhere, named `ObserverRevisions`, `SpatialCondition.spatial_channels()` bumped by GridMap at membership commits. **Moved to P2:** `invalidate_spatial_caches` private + AST ban; the remaining outside writers (terrain modifiers, residues, item blocking, walls, entity size/flight) are re-routed there anyway. Channel enum; writer-derived channels; tile mechanics without `requires_paths`; area conditions bump only their channels; `invalidate_spatial_caches` private; AST architecture test banning `_`-prefixed access on values bound from `get_map()` (31 current sites migrate) | Sleet cast FR 6,060 → ~60 (+ C·V hazard-only, stated); ordinary timings for Sleet cast/drop, Ice Storm, Fireball |
| **P2** | Single reducer entry (remove AC:972, 1510; D8); duration as a state fact; §5.5 facts with EFFECT dispatch and 4 reader migrations; light per cause | predicted versions/passes + ordinary timings |
| **PD1a** | **Done 2026-10-17; footprint gate carried to PD1b** (6,364 computed: per-cell aims are still enumerated until PD1b's aim-per-creature rows). Solver: the native ray everywhere. Wire: cylinders report `"ignore_barriers"` (client must accept). **One footprint (§14.3a):** `objective_footprint(shape, aim, caster_pos, source_pos)` in `dnd/core/aoe.py` (11 callers); AoEShape a frozen value without result fields; one propagation primitive; `AreaPropagation` value for cylinders; spell protection untouched at its 5 sites (Globe out of scope); zones take their area from `AreaCondition.area` (76 + 13 declarations); the listed geometry paths, `filter_propagation_positions`, its cache and the dead caches deleted (U1, U2, U4) | (a) per AoE spell × aim (no Globe), discovery hit set == execution affected set, U1/U2 written failing-first; mechanism/corner outcome changes listed; footprints 7,938 measured → ≤580 computed / ≈230 distinct |
| **P3** | §5.2–§5.4 mechanism; handler dispatch enum + phase B + non-handler splits; root/per-application table; isolation (pools per cast in P3; `self.target_entity_uuid` moves to PD1b's selection, see §5.8); single damage roll (sites in §9.2); shared staged loop; objective positions (§5.7); SEN:1848 illumination-gap gate reworked (deferral guarantees a gap > 1). Includes **PB2** group-related bugs: Counterspell/Greater Invisibility per target, twinned validation, pool refunds, fence, parent cancellation, sort-key `getattr`. | every §6 "After P3" row; changed outcomes listed for sign-off |
| **PB3** | Rules deviations confirmed unintended (D6) | failing-first case each |
| **Re-measure** | — | top residual terms with counts and timings |
| **PD1b** | **Rows, legality, selection, switched together (§14.2–§14.5):** the actor scan; `_admission_error` + `rule_error(scan, selection)` replacing 232 `_validate` + 4 discovery-only overrides (Q-W5); `Entity.perform` as the only `apply` entry; spells listed once with castable levels; aim points with hit sets; relocation destinations from the scan; region descriptors; env use via rings; objects from perception; Cleansing Touch and connectors bounded; one `ActionSelection` (§14.4b) through every consumer; the per-cell, variant, name/index paths deleted; bug G fixed by construction; profile hooks on the scan (Q-W6) | (b) discovery and Command agree on every GC row × target × level; (c) player, AI and server lanes green; remaining `_validate` overrides = the named handler-admission list; eventful validations 148,567 measured → 0; emitted targets 209,734 → ≤580 aims + ≈435 creature + ≈350 zone + R; LOS enumeration 378.7 s → 0; ordinary Choices timing reported (§14.6) |
| **PD1c** | **Whole-world scans at execution (§14.8)**; D14 approved | GM1 brute-force equality; AST ban on world iteration in `dnd/`; the redesign's tests |
| **P4a** | *Folded into PV1 (§6b): its obscurement and light storage migrate with the owned grids.* | — |
| **P5** | Scoped invalidation: cache entries keep bounds and drop on intersection; light selection by recorded lit area; path freshness by revisions; maintained barrier set. *Under PV1 these survive outside perception; perception entity caches on `observer_spatial_revisions` stop, because PV1 deletes them.* | global wipes → 0; cache misses before/after; timing |
| **PD2** | **Costs of what is kept (§14.7):**<br>• Command uses the bare admission check, not a full preview;<br>• preview cached as its projection, no JSON-size measurement, no double deep copy;<br>• capture without dump/validate rounds; `_make_action_info` without per-row `BaseCost.model_validate`;<br>• AI row-profile dumps removed;<br>• movement list (D13): copies at `entity.py:6885-6892`, per-call key sorting, shared path tuples, OA exposure intersection once per path tree, per-step hazard checks, swim/climb/fly bounded by remaining movement (U5);<br>• `_prepare_position_preview_cache` keyed by GridMap revisions instead of re-sorting each call;<br>• retained discovery graphs released at the operation boundary (§9.10).<br>*Conditional on the post-PD1 measurement (like P4b), adopted only if R(S−h) > Um+I+F (handoff:194):* owner revisions (external writes routed through owners first), the session cache by input sections, selection staleness on the same keys. | Choices cache hit / miss / Preview / Command ms before/after; copies/serializations per request counted |
| **P6** | Event machinery: COMPLETION handler lookup; per-cell dispatch re-reads; identity computation per version (D4); turn witness set; Fireball latest-version access; residue-fear provenance | versions and dispatch counts before/after |
| **P7** | Seat-independent capture (pure function, frozen value); one fold per seat; AI knowledge reduction consumes settled sensory events once per group.<br>**D16-C**, the mirror fold leaves the live path. Deleted: `AudienceRuntime.latest`, `current_composition`, `committed_log_count`, `exclusive_current` and both of its branches, `PreparedPlayerOperation`, `prepare_current_operation`, `apply_current_operation`, the `prepared_sensory` parameters and the `prepare_sensory_delta` default. Capture and bookkeeping read `ProjectionState.remembered` (actors, content and the last HUD named there). `CaptureCheckpoint`'s own fold is derived from the projection fold, and its reset branch is deleted. The devtools consumers migrate with no `latest` shim. Reconnect and recording work from the journal. A capture error stays fatal. | publication and AI ms before/after; per-seat wire identical; replica test (the fold of emitted updates from initialization == `remembered` == a cold composition), with no production flag |
| **P8** | Value layer: min/max once per read; bounded breakdown cache; stats snapshot on change | passive-perception and resistance evaluation counts before/after |
| **PV1** | Perception as arrays end to end (§6b): owned world grids, one pure view function, one settlement path, packed cell sets through snapshot, event and wire; P4a's obscurement and light items folded in; spike first | §6b PV1 gate |
| **PV2** | The rest of the wire (§6b); after P7 | §6b PV2 gate; every update ≤100 KB |
| **PV3** | Bodies and items as patches (§6b); after P7 | §6b PV3 gate |
| **P7b** | Stored versions frozen, capture by reference (§6b) | versions frozen at store; no deepcopy in capture; wire byte-identical |
| **PR** | Area-spell rules work (§6b): value reads take the target as an argument; no deep copies on saves; per-target damage and destruction; startup schema builds | Fireball / Circle of Death / Ice Storm native before/after; transcript identical |
| **PH** | Heap (§6b): per-op retained growth ~0; value layer as data; tiles without empty containers (paths and perception via PT / PV1) | 0 gen-2 collections inside measured ops; retained per op ≤1K |
| **PT** | Turn start (§6b): the AI knowledge system (one owner, advanced at batch dispatch, cold start); navigation as a cost grid with a predecessor array | turn-start rows within the ceiling; first-decision knowledge equality |
| **PC** | *(other repo; human)* NDClientGodot SDK schema 9 → 11; grouped world boundaries | — |
| **Exit** | Whole-action targets (§6a, D18): every operation of every GC case re-timed after each merged batch | every run of every row ≤100 ms and every seat update ≤100 KB; acceptable and goal tiers reported per row; a miss blocks the exit until the human decides |

**Correctness oracle.**

- At each settlement in tests, the observers picked by window-box intersection
  must produce the same arrays as recomputing every observer. PV1 is also checked
  for equality against recordings made at the pre-PV1 commit (§6b). Memory is excluded.
- Run the existing sensory, light, Fireball, Globe, residue-fear, pending-return
  and player capture suites.
- Rule outcomes are data-driven from P0b. Outcomes changed by decided rules (one
  roll, phase B, fixed order, §5.6/§5.7, bug fixes) are listed for sign-off.

**Lanes.** Counts go in the architecture or live/integration lane; no wall-clock
asserts in the default lane. A phase that doesn't remove its predicted term is
stopped and reported.

## 8. Decisions

| # | Decision | Status |
| --- | --- | --- |
| D0 | Base `d13e6ad` | **Decided** |
| D1 | Accumulated-changes facts with EFFECT dispatch; 4 readers migrated | **Approved** (with the plan, 2026-10-17) |
| D2 | Outside groups, facts settle per fact through the §4 delta | Follows from §5.2; for sensory, superseded by PV1's one settlement path |
| D3 | Duration-only ticks don't re-solve observers | **Approved** |
| D4 | Identity grants per version, per-handler copies, lineage lists | Keep unless P6 shows they're safe to reduce |
| D5 | ~~Discovery in a separate plan~~ **Superseded:** discovery is in scope (§14) | Human 2026-10-17 |
| D6 | All bugs fixed: engine bugs outright; rules deviations checked against the branch's spell plans and SRD; recorded adaptations stay; unclear ones go to the human | **Decided** |
| D6a | One damage roll per area effect | **Decided** |
| D7 / D7a | Groups for area/multi-target resolution; "all damages, then reactions"; cast-level reactions at root | **Decided** |
| D7c | Groups also at the zone/wall/trap/portal/round-step entries of the index (area mechanics beyond casts). Supersedes handoff lines 110 ("no fabricated simultaneous admission") and 140 ("do not freeze every target at cast start") for area resolution. | **Approved** |
| D8 | APPEAR effects needing the field observed first, if any, when the manual reducer calls go | Check in P2 |
| D10 | Fixed order except player-selected order and authored physical order | **Approved** (correctness, not performance) |
| D12 | Available-actions model (§14) | **Decided** (human 2026-10-17) |
| D13 | Movement destination list kept; only its compute overhead fixed | **Decided** |
| D14 | Whole-world scans replaced by bounded owner queries (§14.8, `WHOLE_WORLD_SCAN_REDESIGN_2026-10-17.md`) | **Approved** (human 2026-10-17); Q-W2 perceived preview; Q-W3 delete |
| D15 | Residues: one condition per material for the whole map, updated per deposit (per-cell amounts and contributions), instead of one condition membership per tile | **Decided** (human 2026-10-17: "one condition for material across all map that gets updated … so we have good scaling") |
| D16 | One sensory fold per seat: the projection's and the current state's audience compositions are one (the duplication predates event-stream reduction) | **Decided** (human 2026-10-17: "we obviously do not need to duplicate … or to even keep the separation if it is not needed") |
| D17 | Spells listed once with castable levels; the selection names the level; the AI always casts the base level | **Decided** (human 2026-10-17) |
| D16-C | D16's method: the server mirror fold (`prepare_current_operation` / `apply_current_operation`, the current composition) leaves the live path; bookkeeping reads the outgoing update; the replica check (emitted-update fold == cold composition) becomes a test | **Approved** (human 2026-10-17: "c is ok") |
| D18 | Whole-action targets (§6a) for every operation: 100 ms ceiling, ≤50 ms acceptable, ≤20 / ≤16 ms goal; ≤100 KB per update; GC is an alarm, not managed | **Decided** (human 2026-10-17) |
| D19 | Subjective vision as data (§6b): perception as one table applied as arrays; compact deltas; bodies and items as patches; turn start | **Decided** (human 2026-10-17); human answers: no item catalog, no retained client state, the Godot client ignored, turn start owned, per-observer deltas with shared parts once per seat |
| D11 | Worktree | **Done** |

### 8.1 Verified bugs (verification pass at `d13e6ad`)

Probes for A, B, C and I were run; A and I were re-run by the coordinator in this
worktree. The rest is static reading.

**PB1: before the GC baseline (blockers)**

| Id | Bug | Fix |
| --- | --- | --- |
| A | Exclusive same-layer surface **raises** on different content (AC:354-358, re-raised at :596-598). Reachable: Flaming Sphere trail, Winter's Breath, `patch()`, Grease/Web/Entangle/Spike Growth/Ice Storm cast over each other, oil→fire beside overlapping debris or acid. Probe: Fire on Grease and Fire on Wet both raise. | latest wins and substitutes; never raise (Q1) |
| B | A moving cloud **raises** on any other cloud-layer occupant (`_change_footprint` → GM:1653-1660), inside the caster's TURN_START handler (CONJ:2011, 3593) | latest wins (Q1); moves use activation arbitration |
| K | `GridMap.clear()` keeps `_path_cache`/occupancy revision while resetting other revisions; `create_rectangle` drops non-attached light contributions (GM:6312-6380, 2423-2441) | clear caches; monotonic revisions; reseed like `set_tile` |
| R-stale ✅ done | Base failing tests that are stale: Globe ×4 (fixed dice faces exhausted by damageable walls), Dimension Door ×2 (`spell.dimension_door` id), lifecycle helper ×3 (`CombatLogEntry.data`), world-prop cold init ×4 (`_retained_event` audience API), entity birth ×1, body residue ×1, 2 collection errors (missing `tests.game.*` / `game.runtime_*`) | update expectations; list for sign-off |
| R-door ✅ done | 54 door tests reach across a full cell to an edge-mounted door (stale, Q8) | move actors to a cell touching the edge; list for sign-off |

**PB2: with P3 (group-related)**

| Id | Bug | Fix |
| --- | --- | --- |
| E | Counterspell re-fires per target application (ABJ:939-965, 1063-1067) | ignore `application is not None` |
| F | Greater Invisibility rolls an escalating Stealth check per application; twinned on [self, ally] checks the caster twice (`conditions.py:2829-2846`). The check itself is a recorded BG3 adaptation. | root events only; root lineage as creation lineage |
| G | Twinned Invisibility/Greater Invisibility `_validate` skip `super()`: the 2nd target has no range/visibility/duplicate check (`illusion.py:886-906, 977-997`). Wider pattern: 102 of 174 spell/class `_validate` overrides skip `super()`. | **moved to PD1b:** fixed by construction: base checks live in the non-overridable `_admission_error`, rules in the additive `rule_error` (§14.3b) |
| J | The generic loop never re-checks root cancellation, cast concentration or target liveness. `prepare_concentration` silently creates new concentration mid-batch (ACT:5217-5220). | per-iteration checks |
| N | Spirit Guardians slow leased before admission (CONJ:2363-2366) | admit first |
| Q | `senses.position` used for geometry (Thunderwave and 9 other sites, §5.7) | objective positions |
| D | Sleep/Color Spray consume pool HP for vetoed candidates | refund and continue (Q3) |
| C | First-per-turn fence keyed by target only. Grease/Insect Plague/Incendiary/IceSurface lose the end-of-turn save after entering (SRD says both). | key by (target, arrival group / TURN_START / TURN_END) (Q2) |
| L8 | Moonbeam cast exposure bypasses the fence (EVO:5998-6001) | route through `_admit_trigger(APPEAR)` |
| S | Sort-key `getattr` (BA:118-127) | `resolution_order_key` |

**PB3: rules deviations confirmed unintended**

| Id | Bug | Fix |
| --- | --- | --- |
| I | Overlapping difficult terrain stacks (+1 per zone; probe 1→2→3; SRD says it never stacks) | minimum-cost constraint of 2 |
| L1 | Hypnotic Pattern has no "sees the pattern" filter | `can_see_visual_effects` |
| L2 | Silence lacks the thunder immunity its docstring promises | membership contribution; no sound system (Q6) |
| L4 | Slow has no 6-creature cap | up to 6, lowest HP first (Q4) |
| L9 | Daylight dispels Darkness of any level (SRD: 3rd or lower) | level check |
| L11 | Mass Cure Wounds takes the first 6 by position | up to 6, lowest HP first (Q4) |
| L12 | Guardian of Faith presentation centred on the top-left cell | centre on the footprint |
| P | Admission-time temp-HP diff (`entity.py:3749, 3797`), latent | record only (approved) |
| M | Turn-start saves split across EXECUTION/EFFECT phases | one convention: EXECUTION for every zone turn trigger (Q7, approved) |
| L6 | Web lacks its light obscurement | one-level light reduction, non-stacking (Q5) |

**PD1/PD2: discovery bugs**

| Id | Bug | Fix |
| --- | --- | --- |
| U1 | Caster-origin shapes (cones, lines, Thunderwave) over-report hits in discovery: no propagation filter, which execution applies (`entity.py:6059-6060` vs `core/aoe.py:225-233`) | one footprint function (PD1) |
| U2 | Cylinders (Ice Storm, Flame Strike, Call Lightning) under-report hits: discovery filters by propagation, execution doesn't (`entity.py:6061-6068` vs `core/aoe.py:396-437`) | one footprint function (PD1) |
| U3 | `secondary_targets` mutated in place on shared cached targets (`entity.py:5740-5745`), also on the AI path | fresh rows (PD2) |
| U4 | `_aoe_origin_fov_cache` is never read (dead) (`entity.py:8106-8109`) | delete (PD1) |
| U5 | Swimming discovery runs an unbounded `compute_paths` every call (`entity.py:6850-6865`) | bound by remaining movement (PD2) |

**Not bugs** (verified):

- Holy Aura range/choice (matches the SRD plan).
- Calm Emotions without a save, and Preserve Life without a pool (recorded BG3
  adaptations).
- Entangle/Tentacles without LEAVE (SRD: restrained "until the spell ends").
- Sanctuary area break.
- Banishment of self (RAW-consistent, guarded); see Q9.

**Human decisions (2026-10-17):**

| Q | Decision |
| --- | --- |
| Q1 | **Latest wins.** An incoming exclusive surface or cloud with no authored transition substitutes the incumbent in the conflicting cells; same-content moves displace as activation does; never raise. A full material-transition graph is later work, not this plan. |
| Q2 | **Rules, not a choice:** first entry on a turn, start of turn and end of turn are separate triggers per the SRD (Grease, Insect Plague, Incendiary, Cloudkill, Tentacles, IceSurface). Fence keyed by (target, arrival group / TURN_START / TURN_END). |
| Q3 | **Refund:** vetoed Sleep/Color Spray candidates cost nothing; continue down the list. |
| Q4 | **Slow and Mass Cure Wounds:** no caster choice. Up to 6 creatures, **lowest current HP first** (fixed-order key as tie-break). |
| Q5 | **Web lowers light one level** on its cells (VERY_BRIGHT→BRIGHT→DIM→DARKNESS; never below DARKNESS; non-stacking), instead of a new obscurement tier. Needs a small relative "dim one step" contribution beside the existing caps (`base_tiles.py:399-413, 610-619`); none exists today. |
| Q6 | No sound system: Silence gets thunder immunity only. |
| Q7 | Asked "what is canon and what is BG3". **Canon:** core 5e doesn't order turn-start effects; Xanathar's simultaneous-effects rule lets the turn's creature choose. BG3: not claimed. **Code:** EXECUTION was chosen deliberately on 2026-02-05 (`c58b3a8`: "Fire BEFORE auto-stand at EFFECT") so a creature knocked prone by a turn-start save still auto-stands that turn (`actions_functional.py:136-175`); "until next turn" effects like Dodge are still active during that save, a creature-favourable order consistent with Xanathar. **Recommendation:** EXECUTION for every zone turn trigger, with this reason documented. **Approved (2026-10-17).** |
| Q8 | **Stale tests, not a bug.** The tests place the actor at (2,3) with the door on the east edge of (3,3) (`test_environment_destruction.py:110-114`), i.e. reaching across a full cell; edge-mounted doors correctly refuse that. The 54 tests move their actors to a cell touching the edge (expectation update, listed for sign-off). |
| Q9 | Self-Banishment stays. |
| I | Difficult terrain doesn't stack (minimum-cost 2). |
| Globe | **Out of scope** (late-game spell; fix when a boss needs it): X (acid flask) and H (Globe area trimming) dropped. |
| P | Temp-HP admission diff is latent (nothing grants temp HP inside the damage's own admission today). Recording only, not fixing now. **Approved (2026-10-17).** |

## 9. Open study items

1. **Deferred dispatch details:** liveness revalidation per deferred handler kind;
   which existing handlers return modified events and so must be split like
   concentration.
2. **Single-roll sites:** every AoE `_apply` that rolls damage (index §3). Classify
   each damage-roll-result handler (`wizard.py:252-331`, `hit_effects.py:68`) as
   roll-level or target-level. Zone exposures (one creature per trigger) are
   unaffected.
3. **Client timing:** one reveal and one world boundary per group; schema gap (PC).
4. **GC fixture harness** (`devtools/performance/gallery_crowd.py`, seed recipe vendored at `devtools/performance/gallery_crowd_seed_recipe.json`, no credentials):
   - the real worker runtime (`server.worker.start`) on an extended authored Lantern Gallery recipe: torch-carrying fighters (`hero.fighter_l5_shield_torch`) with starting damage in the blast clusters, spread witnesses, lit hall torches, an oil barrel, then a plate/vent, a portal, undead and a summoner;
   - one case per fresh process; modes ordinary / counts / profile (the shape of the archived `gallery_baseline_v1.py`);
   - measured as construct → apply → operation → both-audience publication → encoding, plus Choices/Preview/Command for discovery;
   - `devtools/player_server_acceptance/performance_spells.py` imports the deleted
     `game/` package and isn't reused.
5. **Movement/AI per step:** AI continuation reads settled perception after each
   step, which holds because Move isn't a group. Measure AI reduction per step in
   P7.
6. ~~Whole-world scans~~ merged into §14.8 (v3.6).
7. ~~Discovery revisions~~ owners named in §14.7 (v3.6).
8. ~~Bounded passes~~ closed: P4b was measured and not adopted (progress log, 2026-10-17); PV1 replaces it.
9. **Actor scan at execution** (PD1b): count every `apply()` entry point (reactions, OA, triggered spells, harness) and decide who builds the scan there without BaseAction importing Entity (§14.3b).
10. **Retained discovery graphs** (handoff:118): release cost at the operation boundary, measured in P0b, owned by PD2.

## 10. Process and risks

**Process:**

- AGENTS.md plan-adherence sub-agent during implementation.
- No agent commits.
- Antislop and antiOOP review of every plan version that adds design (v3.5 reviewed, v3.6 re-reviewed; v3.7 is their fold-in plus human answers).

**Risks:**

- Visible rule changes need sign-off: reactions after all targets' damage (inside
  the spell), one roll, fixed order, §5.6/§5.7 perception and push changes, bug
  fixes.
- Client schema gap (PC); the client must also consume the new discovery rows (region descriptors, aim points with hit sets, levels as a field).
- AI behaviour shifts with discovery: one row per aim point with correct hit sets, and the footprint bugs U1/U2 fixed, so friendly-fire choices change. Listed for sign-off with P0b/PD1 outcomes.
- Also for sign-off: mechanism areas switched to the one propagation primitive (corner cells, PD1a); stone-escape order (§14.8); the Opulent Revival fix; Cleansing Touch's spell picked as a target facet (client protocol, PC).
- PD1b is the largest phase: 232 `_validate` + 4 discovery-only overrides, ~33 `apply`/`pre_validate` callers behind `Entity.perform`, ~30 variant + 22 template-name + 29 facet definitions, the selection through 9 consumer sites, and 94 + 35 test files. Plus Q-W6: 5 profile hooks / 106 `actor: Any` / 48 isinstance.
- All numbers are predictions until P0b.

## 11. Re-based refs

| Item | Location |
| --- | --- |
| Terrain loop | AC:1339-1427 |
| Manual reducer calls | AC:972, 1510; completions AC:616, 731 |
| Tick | AC:964-974 |
| Light recompute | GM:5985-6040 |
| Death | `entity.py:2531-2556`; `base_block.py:572-589` |
| Destruction | `base_item.py:722-782`; GM:3892 |
| Object move | GM:3507-3600 |
| Identity computation | EV:2159-2172, 443-449 |
| Navigation | SEN:136, 1794; `entity.py:5423-5502` |
| Values | `values.py:864-919, 1599-1661` |
| Cache clears | GM:584-641, 4881-4940, 6276-6308 |
| Area bumps | AC:285, 472, 662, 742, 1572 |
| Positionless invalidations | `entity.py:848, 881, 891` |
| Per-entity caches | `entity.py:6103-6113, 6181-6187, 6648-6699` |
| Fireball re-stage | EVO:1039 |
| Choices | `session.py:54-68, 344, 454-455` |
| Per-observer objective inputs | GM:4139-4219, 5383-5450, 5539-5578 |
| Capture | `capture.py:669-755, 811-850, 952-1058` |
| Event machinery | EV:1837-1839, 2260-2322, 2040-2052, 2192-2198; `encounter.py:925-940`; EVO:1029, 1036 |
| Untracked writes | GM:1542, 1663; `base_tiles.py:311`; `entity.py:1951, 1967`; ABJ:2338, 2356 |
| Tile hint | GM:1629 |
| Sort key | BA:110-129 (`getattr` at 118-127) |
| Reducer registration | SEN:677-692 |
| Illumination gap | SEN:1848 |
| Discovery entry | `entity.py:7993-8184` (`get_available_actions`) |
| Discovery collectors | `entity.py` 6335-6497 (entity), 6752-6962 (path/position), 7184-7304 (LOS), 7306-7469 (AoE), 7471-7519 (object), 7562-7991 (use/world) |
| Variants | `actions.py:5359-5438`; `base_actions.py:1847-1893` |
| Discovery validation | `base_actions.py:2098-2137`; witness search 2110-2123; `actions_functional.py:281-331, 490-515, 612, 619, 654-656, 700` |
| Session / worker | `player/session.py:54-68, 334-506, 585`; `player/choice_projection.py:83-134`; `server/worker.py:142-156, 254` |
| AI discovery | `ai/runtime/decision_epoch.py:148-157, 819-845, 948-971` |

## 12. Changes

**v3.14 → v3.15:** PR area-spell rules work (no phase owned it after P6 / P8).

**v3.13 → v3.14:** PH heap phase, from the GC census (the GC alarm).

**v3.12 → v3.13** (the v3.12 antislop and antiOOP reviews, all accepted):

- The combat log is flattened and `root` is an index; no SDK renderer.
- One version identity, the seat's occurrence index.
- P7b freezes stored versions first.
- The AI catch-up has one owner, the AI knowledge system, with a cold start.

**v3.11 → v3.12** (Fireball payload and publication sample):

- PV2 adds the combat log (no repeated child entries; `data` only, rendered by the SDK) and the version rows (indexes).
- P7b: capture by reference.
- PT: the AI catch-up folded at assignment creation.

**v3.10 → v3.11** (v3.9 antislop review):

- §6 Target column, P4b, D9, §9.8 and the bounded-pass risk deleted; P4a folded into PV1; §4 and D2 superseded for sensory.
- §6a gains bytes per row and the Cloudkill / Darkness / Daylight rows; the ceiling is 100,000 B; encoding is owned by PV2.
- PV1 is split into PV1a (now) and PV1b (after P7), with a derived per-observer budget (≤0.33 ms), named cases and an explicit deletion list.
- The P5 items that survive are named.
- The oracle is restated for one path.

**v3.9 → v3.10** (human answers and the v3.9 antiOOP review):

- §6b from first principles: vision as a sense × interceptor table applied as arrays.
- World grids with one owner each, replacing storage.
- `Senses` published only.
- Packed cell sets end to end.
- One observation type for bodies.
- PT for turn start.
- P4a folded into PV1; P4b closed.

**v3.8 → v3.9** (human 2026-10-17 and the v3.8 reviews):

- §6a: one row per GC operation; median and worst run; five spans; 100 KB per update; GC as an alarm; exit blocked by any miss; fixes are system work, not object caches; the 30 % publication share removed.
- §6b: subjective vision as data (PV1–PV3), from the Sleet / Darkness / Cloudkill measurements and the payload study.
- P7 carries the D16-C deletion list and the replica test.

**v3.7 → v3.8** (human 2026-10-17):

- §6a whole-action targets (D18, human tiers): 100 ms ceiling for any operation, ≤50 ms acceptable, ≤20 / ≤16 ms goal; owners per row; an exit row in §7.
- D16 method C approved: the mirror fold leaves the live path; the replica check becomes a test.

**v3 → v3.1:**

- phase A/settle/B;
- D7b withdrawn;
- one roll; all bugs fixed;
- Fireball one group per blast;
- groups not at every `BaseAction.apply`;
- eager settlement outside groups;
- loop rule restored;
- P0 split;
- P4a/P5 unconditional;
- AI, client and P6 items;
- open study items.

**v3.1 → v3.2** (both v3 re-reviews and the human's worktree instruction):

- Worktree created and recorded.
- Group mechanism made concrete: own ContextVar, entry-kind stack, nesting joins,
  phase B after depth 0. Settle via `PreCompletionSystem.settle_group` in the root
  pre-completion; owners keep pending work; group check inside
  `recompute_observer`.
- W narrowed to light publication + subjective pass; objective invalidation and the
  life-state commit stay immediate.
- Handler dispatch as a two-value enum on `BaseHandler`, with replay, a no-mutation
  invariant and non-handler splits; spatial ENTER handled by an entry-kind rule.
- A complete root/per-application table instead of two hand fixes.
- Pools stay on their owners ("group-scoped pools" dropped).
- Sort key moves to `base_block.resolution_order_key` (removes `getattr`);
  player-selected order exempt.
- One shared staged loop for Fireball and `payload_blast`, with integrity-based
  stage results.
- Objective positions for geometry readers; perception-read outcome list (§5.7);
  push-ENTER stop change listed.
- Counts corrected:
  - wipes remain until P5;
  - 30·(1+O);
  - Thunderwave 8 entries;
  - Ice Storm ~13 s;
  - barrel term added;
  - Gust replaces Spirit Guardians for terrain moves;
  - GC instance values;
  - P1 residue stated.
- GC gains P-g1, P-g2, Darkness/Daylight and summon retirement cases.
- Complete-operation timings at the P1/P2 gates; gates for P6–P8.
- No checkout needed for the production comparison.
- D7c and D10 adjusted.
- AST private-access test widened.
- SEN:1848 gap rework assigned to P3.

**v3.2 → v3.3** (human: movement must stay step by step):

- Movement is never a group.
- Forced movement inside a group keeps per-step inline triggers and stops.
- Spatial ENTER/LEAVE handlers are always INLINE; the entry-kind deferral rule is
  removed.
- Push-caused entries and paid retreats moved out of phase B.
- Thunderwave row corrected.

**v3.3 → v3.4** (human answers 2026-10-17): Q1–Q9 decisions; difficult terrain non-stacking; Globe out of scope (H, X dropped); temp HP pending; Q7 canon/code answer with recommendation; Q8 resolved as stale tests.

**v3.4 → v3.5:** available-actions discovery in scope (§14; PD1 after P0b, PD2 after P5); D5 superseded.

**v3.6 → v3.7** (v3.6 re-reviews: antislop 16, antiOOP 14; human answers; P0a measurements):

- Legality: one non-overridable `_admission_error(scan, selection)` + one additive `rule_error`; checks take the candidate as an argument (this, not moving code, is what deletes the per-candidate copies); rules keep full world access (human: "this could block more complicated spells"); 4 discovery-only overrides and `StructuredAction` included; `Entity.perform` is the only `apply` entry.
- Footprint: aim parameter; AoEShape a frozen value; spell protection left at its 5 sites (Globe out of scope); call-local dedup, aim-major order (64-entry FOV LRU); zones' `area_propagation` duplicate removed.
- Scan: target-only `CreatureFacts`; relationship leaf (methods delegate, no 50-caller migration); actor data incl. charges/grants (both Protocols deleted); `contact_ring_cells` named with a GridMap test.
- One `ActionSelection` in `dnd/core/action_types.py`; `get_variant_facets` deleted; `facet_domain(scan, …)`.
- Movement branch kept (D13) — v3.6 wrongly listed it for deletion.
- Counts corrected (232, 22, 29, 11, 76 + 13, 94 + 35); GridMap refs re-based; V/O renamed Vc/Ob; Cleansing Touch and connectors moved to PD1b; owner revisions moved under the conditional gate; Entity cache fates stated.
- Human: D14 approved; relocation destinations = sight ∩ empty ∩ range; unused faction scans deleted; objects are part of perception. Then Q-W2 and Q-W5 approved, Q-W6 required ("any is bad in general") and resolved as no actor parameter, `Entity.get(self.source_entity_uuid)` in overrides (human: "that is what we did everywhere else"), order left to the plan (§7 header).
- P0a measured the godmode Choices miss at 392.7 s instrumented (LOS 378.7 s; 148,567 validations; 209,734 emitted targets; 577 rows): the v3.5 static estimates were low.

**v3.5 → v3.6** (§14 antislop 13 + antiOOP 14 findings, whole-world redesign):

- PD1 split into PD1a (one footprint), PD1b (rows, legality, selection together) and PD1c (whole-world scans, after D14 approval), each with correctness gates.
- Legality is one path: rule bodies move from 221 `_validate` overrides into the non-eventful hooks; G moves to PD1b.
- One `objective_footprint`, one propagation primitive, `AreaPropagation` for cylinders, `footprint_signature()`, zones' area from `aoe_shape`; no new cache.
- Scan types in a leaf, built by one Entity method, passed as data; one perceived-creature reader; one relationship function.
- Selection identity widened to cost source, item, facets; all name/index sites listed.
- Range/LOS lookups corrected (no distance field; creature LOS = `visual`).
- Env use reuses `contact_positions` via rings; connectors added to §14.8; objects by uuid on demand.
- PD2 = costs of kept things; session section cache conditional on measurement; revision owners named; one phase per item.
- §14.6 per-term table of what remains; 580 hit sets; ms target only after P0b.
- Open human questions collected in §14.10.

**v3.5 consistency pass** (human request):

- §14 approved.
- D1/D3/D10 marked approved; D12–D14 added.
- R7 (discovery) added to the root causes.
- Discovery baselines added to §1 and P0b.
- P0a/PB1 progress recorded.
- Discovery bugs U1–U5 added.
- Harness design recorded (§9.4).
- Revision study item added.
- Risks, refs and the review status updated.

## 13. Reviews

- **v1:** antislop (10) and antiOOP (12), all accepted (§12 history).
- **v3:** antislop (8 + ref nits) and antiOOP (10), all accepted into v3.2, with
  one exception. Antislop #1 asked that a §5.2 entry close at its own exit even
  when nested. The antiOOP nesting rule (join; phase B after depth 0) was chosen
  instead, because it keeps one settle per spell and still gives each phase-B item
  a fresh group. Move steps aren't groups at all.
- **v3.2:** no separate re-review was run. v3.3–v3.5 changes are human decisions, plus §14, which is under review now.
- **Bug verification:** done (§8.1).
- **v3.5 §14:** antislop (13) and antiOOP (14), all accepted into v3.6. Where they conflicted, the code decided: `_aoe_origin_fov_cache` and `compute_subjective`/`compute_for_targeting` are dead (antislop); the footprint cache is not a new one (antiOOP; the existing `_propagation_fov_cache` remains).
- **Whole-world redesign:** its own antislop (9 minor) and antiOOP (2 major) reviews, accepted; its `get_target_variants` hook is replaced by the §14.4 `facet_domain`/`with_selection` pair.
- **v3.9 §6b:** antiOOP (10) and antislop (14), all accepted into v3.10 / v3.11, except light-source restore by revision: dropped, because the human rejected keeping a second state.
- **v3.8 §6a / D16-C:** antislop (12) and antiOOP (11), accepted into v3.9, with two changes. A kept value's invalidation is stated in the plan; a separate human approval per value was not adopted, since the human did not ask for it. Request rows stay total-only with a sampler split; the tool is not extended for them.
- **v3.6:** antislop (16) and antiOOP (14) re-reviews, all accepted into v3.7 except: antiOOP #5 (move spell protection into the footprint with provenance) is replaced by antislop #2 (leave it at its 5 sites; Globe is out of scope by human decision); antiOOP #7 (delete four relationship methods, migrate ~50 callers) is narrowed to a leaf function the methods delegate to; antiOOP #8 (106 profile hooks) is a human question (Q-W6); the antiOOP rule "no `Entity.get` in predicates" is dropped after the human's objection (rules keep world access).

## 14. Available actions (discovery) — human-decided model (2026-10-17)

### 14.1 Decisions (human)

| Decision | Detail |
| --- | --- |
| Environment **use** actions stay | Open door, pull lever, loot: reach-bounded and few. Move+use already exists as `AvailableWorldInteraction.contact_positions` (`entity.py:7610-7629`). It is recomputed via rings (§14.2 #4), not added as a second structure. |
| **No object rows; objects are part of perception** | No global object/wall target pools ("you can target any wall in the game"). Objects are "part of the general perception": the client and the AI pick a perceived object (`senses.objects`) by uuid, and it is validated on demand by the same checks (§14.3b). The basic AI policy scores object targets at zero today (`basic.py:530-545, 655-656`), so nothing is lost. |
| AoE: **finite aim points derived from targets** | One aim point per perceived creature, each with its hit set (enemies / allies / self). There is also a legal-region descriptor: the client free-aims any legal point, validated on demand. |
| Spells listed **once with allowed levels** | — |
| **Relocation destinations** (Telekinesis, Dimension Door, EVO:6561/6672) | "Who can be selected … in sight + empty … easy to derive": destinations = sight mask ∩ unoccupied ∩ range, read from the scan. A target is listed when that set is non-empty. No witness search. |
| **Movement destination list kept** | Reachability needs paths, and it matters for AI; its cost is package size. Only its compute overhead is fixed (PD2). |
| **Single space scan per actor** | Solves all spells by lookup. |
| Focus is speed | The schema shape follows the model: "we are not here speaking about schemas". |

### 14.2 The actor scan (PD1b; computed once per discovery call or per performed action)

**Types:** frozen dataclasses in a new leaf `dnd/types/discovery.py` (`ActorScan`, `CreatureFacts`, `ActorScanRecord`), importing neither Entity nor Senses.

**Builder:** `Entity.action_scan(...)`, which produces a per-call local value. It replaces the `_prepare_aoe_caches` contact reads (`entity.py:6194-6215`) and `_visible_hostile_threat_domains`. There is no context class with behaviour and no PrivateAttr cache.

**Use:** the scan is passed as an argument to the admission checks (§14.3b). It is the shared, precomputed input that makes the common checks (range, sight, faction, reach) O(1). It does **not** restrict what a rule may read: a spell's `rule_error` keeps full world access (`Entity.get`, GridMap, occupancy, support/height), as Charm Person's body does today (`enchantment.py:171-186`). Forcecage push-outs, wall placement and Telekinesis objects need exactly that. What is forbidden is a copy of the action, a declaration event, or a mutation.

Contents (each input already has an owner):

1. **Sight:** the caster's `Senses.visible` cell mask (position targets only).
2. **Perceived creatures:**
   - **Target facts:** a target-only `CreatureFacts` (creature type, life state, condition summary, `blocks_external_contact`, faction) from `Entity.creature_facts()`. The AI's multi-observer `project_entity_fact` (`dnd/ai/runtime/subjective_projection.py:170-252`) composes only this.
   - **Observer additions:** the scan record adds this observer's contact (`visual` flag, `spell_utils.py:49-51`) and its relationship.
   - **Relationship:** a pure leaf function `relationship(src_uuid, src_faction, tgt_uuid, tgt_faction)`, used by BA:1673, 1694-1696 and 1795-1797. `Entity.is_ally` (4420), `is_enemy` (4438) and `is_enemy_of` (4456-4461) become one-line calls to it, and the `isinstance(other, Entity)` goes. Their ~50 callers are not migrated (scope).
3. **Navigation:** reachable cells, costs and paths per movement mode, from the already materialized navigation. Non-walking modes are bounded by remaining movement (U5, PD2).
4. **Perceived objects whose contact ring meets R:**
   - Prefilter: a new `GridMap.contact_ring_cells(object_uuid)`. A GridMap test asserts the ring contains every origin `manual_object_contact` admits (GM:2840-2880, including the boundary neighbour cell).
   - Exact check: it stays `manual_object_contact(origin=cell)` on ring ∩ reachable, because contact depends on the requester's knowledge and origin tile.
   - Connectors: they come through the same object reads, not `get_all_connectors()` (`entity.py:7630`).
5. **Threat domains** for OA exposure. These are computed once per collector call today (5485, 6510, 6881, 7042). The per-destination costs (exposure intersection, hazard steps) are PD2.
6. **Reach mask** for the caster's neighbour cells: touch/HAND access via `can_reach_between`, ≤ 24 checks.
7. **Actor data:**
   - slot capacity, restricted grants and free-cast grants;
   - held weapons, spellcasting sources and entitlements;
   - source-item charges (replacing the runtime-checkable `FiniteChargeProvider`, BA:52, 1509, 2302, 2330);
   - `active_encounter_uuid`.

Lookups:

- range = O(1) `grid_distance_feet` from `get_target_origin()` (BA:1338-1354; the origin varies per action, e.g. a source item);
- creature line of sight = the `visual` flag; the cell mask is for position targets only;
- relocation destinations = mask ∩ unoccupied ∩ range;
- filters = record facts; touch = reach mask;
- costs once per (spell, level, cost source); Jump is the only target-dependent cost (`actions.py:3463`).

### 14.3 Rules and their one handling each

#### 14.3a One footprint (PD1a)

**Today: four geometry paths and two propagation primitives.**

The geometry paths:
- `AoEShape.compute_subjective` / `compute_for_targeting` (aoe.py:86-157, 377-420; dead, only aoe.py:387 calls them);
- `set_subjective_footprint` / `_resolve_subjective_entities` (aoe.py:159-200, caller `entity.py:5986`);
- `compute_objective` (aoe.py:202-240, 11 execution callers) and `Cylinder.compute_objective` (aoe.py:422-437);
- `Entity._compute_aoe_propagation_footprint` (`entity.py:6042-6068`, which mutates `computed_origin`).

The primitives:
- discovery and `spatial/mechanisms.py:159` use `filter_propagation_positions` (supercover rays, GM:6154);
- execution and senses use `compute_propagation_fov` (shadowcast, GM:6077).

The two primitives can disagree at corners.

**After:**

- **One non-mutating** `objective_footprint(shape, aim, caster_pos, source_pos) -> frozenset` in `dnd/core/aoe.py`. That is the right layer: aoe imports gridmap, and BA imports aoe.
  - The 11 callers migrate.
  - All the paths above are deleted.
- **AoEShape becomes a frozen value**, no longer a `BaseObject` with `source_entity_uuid` and `context`.
  - Its result fields (`target`, `computed_origin`, `affected_positions`, `affected_entity_uuids`, aoe.py:40-46) are deleted, which also deletes the per-aim copies (BA:1659).
  - Identity = (shape, `footprint_target_key(aim, caster_pos)`): the existing per-subclass key (aoe.py:69/251/278/307) takes the aim as a parameter.
  - Deleted: the isinstance chains (aoe.py:466-500, `_get_aoe_radius_ft` in ACT), the `type`+`model_dump_json` key (`entity.py:6130-6143`), and the `Senses` import in aoe.py.
- **One primitive:** `compute_propagation_fov`.
  - `filter_propagation_positions` and `_propagation_filter_cache` are deleted.
  - `connected_propagation_positions` (GM:6115) stays as the "connected" propagation value.
  - Mechanisms migrate, and their corner changes are listed for sign-off.
- **Cylinders:** "ignore barriers" becomes a value of `AreaPropagation` (`types/spatial_effects.py:10`), dispatched on that field. Execution semantics are kept (fixes U2).
- **Caster-origin shapes** (6 cones, 4 lines, Thunderwave) get the propagation filter execution applies (fixes U1).
- **Spell protection stays at its 5 current sites, untouched** (EVO:974/1175/1325, `spell_payloads.py:87`, AC:1118). Only Globe registers one (ABJ:1149), and Globe is out of scope. Gate (a) fixtures contain no Globe.
- **Zones:**
  - `AreaCondition.area: AoEShape` replaces `zone_shape` / `zone_radius_feet` / `zone_width_feet` / `zone_direction` (76 declarations in 14 files, including the non-spell zones in traits, gas_traps, paladin, divine_rewards and summons).
  - It also replaces `area_propagation` (13 declarations, which overwrite the shape's value at AC:1090) and the string dispatch (AC:1044-1091).
  - The zone stores its aim relative to the anchor, so `move_zone` moves the anchor.
  - Daylight's radius is declared once. Discovery never reads condition classes. The 4 contract-less zones stop enumerating reachable cells.
- **Dedup and cache:**
  - One call-local dict keyed by footprint identity, dropped on return.
  - Iteration is aim-major, so the existing `_propagation_fov_cache` (`FOV_CACHE_ORIGINS = 64`, GM:78) never evicts a live key. No persistent cache is added.
  - Deleted Entity caches: `_aoe_footprint_cache` and its `_aoe_footprint_cache_context` (581); `_aoe_origin_fov_cache` (592-596) and its threaded `fov_cache` parameters (5945, 6045, 6111-6118, 7309, 7576, 8106-8109; U4).
- **Consumers:** discovery, preview, the P3 shared staged loop (`spell_payloads.py:84`, EVO:963) and AC:1096 all call it. There is no second geometry path.

#### 14.3b Legality: one path (PD1b)

**Today: three rule paths.**
- 232 eventful `_validate` overrides (44 in EVO), with bespoke rules such as Charm Person (LOS + humanoid, `enchantment.py:171-186`) and Revivify (`necromancy.py:2808-2820`).
- 4 discovery-only `validate_requirements_for_discovery` overrides that Command never runs: `rage.py:586`, `sorcerer.py:1489`, `environment_interactables.py:691`, `traits.py:1239`.
- Overridable hooks that read mutable instance fields (`self.target_entity_uuid`, `end_position`, `extra_target_positions`, `get_all_targets()`; BA:1360-1500). These force the per-candidate copies, the shared-template mutation `shape_template.target = position` (`entity.py:6158-6160`), and skip-`super()` bugs such as G (20 `position_placement_error`, 11 `selection_preview_error`, 3 `targeting_error`, 3 `physical_access_error` overrides).

**After:**

- **One non-overridable** `_admission_error(scan, selection)` holds the base checks: range, sight/`visual`, reach, source item, source condition, entitlement, base placement. It then calls **one additive** `rule_error(scan, selection)`, whose base returns None and which subclasses override without `super()`.
- **Every check reads targets, positions and vertices only from `selection`.** No check reads `self.target_entity_uuid`, `end_position` or `extra_target_positions`. This is what deletes the per-candidate copy: discovery validates against the registered template itself (`self`), with the candidate passed as an argument. Today the copy exists only to carry the candidate (`template.model_copy(deep=True, update={"target_entity_uuid": …})`, `entity.py:5875`).
- **Conversion per override** is mechanical: read the target from `selection` instead of `self`, and return the message instead of `declaration_event.cancel(...)`. World reads stay.
- **What moves into `rule_error`:** all 232 override bodies, the 4 discovery-only overrides and the existing hook overrides. The only overrides kept are for handler-based admission, listed by name. The PD1b gate counts the rest.
- **One caller set:** BA:2098 and its callers (`entity.py:5879, 6307, 6889, 7266, 7494, 7686, 7903, 7957`), preview, Command and execution all call `_admission_error`.
- **Deleted:** `StructuredAction._validate` (BA:2621, no subclass in `dnd/`).
- **AST test:** it bans overriding the base checks. Bug G is fixed by construction.
- **Execution owner:**
  - `Entity.perform(action, selection, parent_event=None)` in `entity.py` builds the scan for the declared targets and calls `action.apply(scan, selection, parent_event)`. Every direct `.apply(` caller already imports `dnd.entity` and holds the actor: `controller.py:192`, `actions_functional.py:487/807`, `reactions.py:70/127`, `divine.py:222/232/237`, `barbarian.py:1122`, `traits.py:649`, EVO:4134, `necromancy.py:1185/1211`, ACT:342, `spell_summon_actions.py:1442`, `enchantment.py:1906`, `wall_constructions.py:554`, `environment_interactables.py:348`.
  - `apply` and `pre_validate` (≈33 callers) take the scan.
  - An AST test allows `.apply(` only in `Entity.perform` and `super().apply` overrides.
  - The `apply_from_control` PrivateAttr save/restore (BA:2351-2359) becomes the selection's controller uuid.
  - The convolution loop's `self.target_entity_uuid = …` (BA:2201) goes with P3's per-target isolation.
- **Protocols deleted:** `FiniteChargeProvider` (BA:52) and `RestrictedActionGrantProvider` (BA:1847-1867, `action_types.py:161`). Charges and grants are scan data, which also deletes the `entity: Any` hooks (9 sites). Where a check in a spell or class needs the actor, it uses `Entity.get(self.source_entity_uuid)`, as Q-W6 does.
- **Profile hooks** (5 base hooks at BA:1057-1116 taking `actor: Any`, 106 occurrences with overrides, 48 `isinstance(actor, Entity)` checks, called per row at `entity.py:5717-5720`): they lose the actor parameter and resolve `Entity.get(self.source_entity_uuid)` like the rest of the codebase (Q-W6).

| Rule | Handling |
| --- | --- |
| Per-target facts (creature type 9, target conditions 8, life state 2, `blocks_external_contact`) | record facts |
| Physical reach vs optical LOS (~21 touch, 12 physical-access, 4 touch-contact) | reach mask |
| Source item origin / firing sector (7 sites) | once per spell |
| Source state, resources | once per (spell, level, cost source) |
| Allocation count grows with level (Chain Lightning) | per-level field |
| Placement / support / height / wall vertices (~15–20 spells) | region descriptor (§14.4); on-demand placement rule |
| Relocation destinations | mask ∩ unoccupied ∩ range (§14.1) |
| Objects (24 `CREATURE_OR_OBJECT` sites, Chain Lightning objects) | perceived object by uuid, same checks on demand. Continual Flame (touch, owned items, EVO:4479-4481) stays a reach-bounded row. |
| Handler-based admission | preview / command only |

### 14.4 What is deleted (no old path; PD1b)

- **Variants and facets:**
  - Deleted: `get_discovery_variants` copies (~30 overrides), the 22 `get_discovery_template_name` overrides, `get_variant_facets` (29 definitions; callers `entity.py:5699, 7621`), `_parse_spell_variant_template_name`, and `_resolve_executable_template` with its name scan and `getattr(template, "_create_variant")` (`actions_functional.py:304-331`).
  - Each owning class instead has `facet_domain(scan, level, target_record | None)` and `with_selection(selection)`; the generic pipeline calls only these.
  - Domains depend on level (`available_forms`, `summoning.py:57-66`), on legality (held weapon slot, `transmutation.py:2198-2209`), or on the target (Cleansing Touch: the spells on that ally, computed on demand at preview). This replaces the redesign's `get_target_variants`.
- **Per-cell candidate enumeration:**
  - LOS/position rows (`entity.py:7184-7304`);
  - the 4 contract-less zone templates, which leave `_collect_path_actions`' movement branch (6837-6961). The branch itself stays for Move (D13) and is optimized in PD2;
  - AoE per-cell candidates and per-target preview enrichment (`entity.py:7306-7469, 6114`), plus `discover_player_actions`' per-target `preview_aoe_target` (`session.py:369-394`);
  - the continuation-witness and path-witness search (BA:2109-2123), replaced by §14.1 relocation destinations;
  - next-vertex enumeration (`actions_functional.py:490-515, 654-656`);
  - wall form variants.
- **Object candidate pools:** `entity.py:5922-5935, 5885-5893`, global object rows `7471-7519`, and Chain Lightning object secondaries. Secondaries are picked on demand by uuid, which removes the U3 in-place mutation (`entity.py:5740-5745`) and the index rebasing (handoff:119).
- **Per-candidate deep copies, declaration events and per-target cost checks:** `entity.py:5875, 5882, 7262, 7269, 7489, 7495, 7898, 7904, 7952, 7958`.
- **World-interaction contact queries** (object × every move cell, `entity.py:7610-7640`): replaced by rings ∩ reachable (§14.2 #4). `getattr(item, 'stack_count')` (7605) goes with them.
- **Whole-world scans in discovery** (moved here from §14.8):
  - Cleansing Touch: one row; the targets come from the existing perceived-ally + 3×3 touch pool; the spell is a target-dependent facet. Rows for unseen allies' spells no longer leak.
  - Connectors: through perceived objects.
- **Entity caches:** `_aoe_preview_cache*` (586-590), `_aoe_contact_alive` (591), `_visible_position_cache` (607, duplicates the sight mask) and `_aoe_nearby_candidates_cache` (610).
- **Selection by name / index:** replaced by §14.4b.

**14.4b Selection.** One frozen `ActionSelection` in `dnd/core/action_types.py`. Its fields:
- registered template uuid;
- `cast_at_level`;
- `cost_source: Slot | FreeCast(grant id) | Restricted(grant id)`;
- source item uuid;
- facets: `tuple[ActionVariantFacet]`;
- target uuids, positions or vertices;
- controller uuid.

It replaces:
- the index-based `player/commands.py:17` type;
- `instantiate` (BA:1817), `_create_variant` / `generate_variants` (ACT:5359, 5467) and `_bind_executable_action`;
- the split cost-source fields (`cast_cost_grant_id` / `cast_cost_label`, ACT:4803-4804; `_restricted_action_grant`, BA:1016);
- both name separators (`__grant_`, BA:89, 1868-1894; `__item_`, `actions_functional.py:503, 563-574`, `entity.py:7620`);
- the name facets (`__cage_form`, `wall_constructions.py:920`; `__delivery`, EVO:6752; Cleansing Touch `[condition_uuid]`, `paladin.py:1429-1438`).

`cast_at_level` belongs on the executable instance built by `with_selection`; costs come from `_get_costs_for_level` (ACT:5502).

These sites move together:
- `action_dispatch.py:59-62` and `server/worker.py:120-132`;
- `player/commands.py:17-22` and `sdk/python/src/dnd_player/contracts.py:51`;
- `player/session.py:397-442, 486-521`; `choices.py:118`;
- AI `execution.py:181-187`;
- `encounter.py:1665` `execute_by_index`;
- `actions_functional.py:281-331, 612, 619, 700`.

Test fallout is 94 test files calling `get_available_actions` and 35 using `execute_by_index`, adapted or deleted under the same rule as P0a. The client protocol change is in PC.

**Region descriptors** are a projection of the existing `position_discovery: PositionDiscoveryContract` (BA:151-199, 1009), `position_selection` (`action_types.py:64`), `get_range` and `aoe_shape`. There is no per-spell descriptor class.

### 14.11 PD1b execution design (2026-10-17)

**Core API.** One coordinator lands this first, as a single commit with the base implementations and no overrides converted yet.

- **Leaf `dnd/types/discovery.py`** (frozen dataclasses, no Entity/Senses import):
  - `CreatureFacts`: uuid, position, creature type, life state, condition names, `blocks_external_contact`, faction, size.
  - `ScanRecord`: facts, `visual`, `Relationship`, where `Relationship` is a StrEnum of SELF / ALLY / ENEMY.
  - `ObjectRecord`.
  - `ActorScan`: actor uuid and position, the visible mask, `creatures: Mapping[UUID, ScanRecord]`, `objects`, reachable costs, reach cells, threat domains, slot capacity, restricted and free-cast grants, source-item charges, `active_encounter_uuid`.
  - A pure `relationship(src_uuid, src_faction, tgt_uuid, tgt_faction)`.
- **`dnd/core/action_types.py`:** frozen `ActionSelection` with these fields:
  - `template_uuid`;
  - `cast_at_level`;
  - `cost_source: CostSource` (SLOT / FREE_CAST(id) / RESTRICTED(id));
  - `source_item_uuid`;
  - `facets`;
  - `target_uuids`;
  - `positions`;
  - `controller_uuid`.
- **`BaseAction`:**
  - `_admission_error(scan, selection)` holds the base checks and is not overridable; an AST test bans overriding it.
  - `rule_error(scan, selection) -> str | None` is the one additive per-action rule (base None).
  - `facet_domain(scan, level, target_record)` and `with_selection(selection) -> BaseAction`.
  - `apply(scan, selection, parent_event=None)`; base `_validate` calls `_admission_error`.
- **`Entity`:** `action_scan(...)`, `creature_facts()`, and `perform(action, selection, parent_event=None)` as the only `apply` entry, with an AST test.

**Correction (2026-10-17, coordinator, listed for sign-off): the executable instance keeps `apply(parent_event)`.**
§14.3b had `apply(scan, selection, parent_event)` with "≈33 callers". It missed the tests: 159 test files make 673
direct `.apply()` calls on executable instances. The intent is kept without that churn:
- an executable instance is its own selection (`current_selection()` from its fields, which only `with_selection`
  and `instantiate` set);
- the base `_validate` asks the source block for its scan (`BaseBlock.action_scan()`, defined by Entity) and calls
  `_admission_error(scan, self.current_selection())`: one legality path, shared with discovery;
- discovery calls `_admission_error(scan, candidate)` on the registered template itself, with no copy and no event;
- `Entity.perform(action, selection, parent_event)` = `action.with_selection(selection).apply(parent_event)` is the
  only `.apply(` caller in `dnd/` (AST test over `dnd/`; tests keep building instances).

**PD1b exit items (owned by the coordinator, gate (c) fails while they are open):**
1. Physical access joins `_admission_error` and the `physical_access_error` override chain is deleted: Continual Flame, connector traversal and Multiattack declare their access as data the base reads.
2. Per-target isolation: each per-target application is its own `with_selection` instance; `_apply_target_application` no longer mutates and restores `self.target_entity_uuid`.
3. Execution scans carry no navigation (`action_scan(with_navigation=False)`); the `discovery.action_scan` counter is checked on the caster-step and Gust/Spirit Guardians walk rows, and no non-creature apply source reaches `_validate`.

**Open in the fan-out: physical access.** Three `physical_access_error` overrides change the base check instead of
adding to it (Continual Flame admits carried items without reach; connector traversal and Multiattack replace it).
`rule_error` is additive, so the base reach check joins `_admission_error` only once those three are expressed as
data the base reads (e.g. the access the action declares for the selected target), not as overrides.

**Open in the fan-out: target counts.** 9 `get_all_targets` overrides cap or dedupe selected targets (Bless/Bane,
Hold Person upcast, Eyebite...). Base admission now checks the selection as named, so "at most N" and "distinct"
become `rule_error` messages instead of silent trimming.

**Fan-out.** Five sub-agents run on disjoint file groups. Each converts the files' `_validate`, discovery-only and hook overrides into `rule_error`, plus profile hooks without an actor parameter, variants to `facet_domain`, and `apply()` callers to `Entity.perform`. Each runs its files' suites.

| Group | Files | Override sites |
| --- | --- | --- |
| 1 | evocation | 90 |
| 2 | transmutation, illusion, divination | 65 |
| 3 | enchantment, necromancy | 68 |
| 4 | conjuration, abjuration, summoning | 73 |
| 5 | actions, classes, items, monsters, walls, spell_payloads, traits | ~100 |

**Then the coordinator:**
- the discovery rows rewrite (`entity.py` collectors: one row per action with levels, aim points with hit sets, region descriptors, rings, relocation destinations, perception objects);
- the deletions in §14.4;
- the consumers: session, worker, AI, capture, SDK;
- test migration (94 + 35 files);
- gates (b) and (c).


### 14.5 Consumers

- **Session/worker** (`dnd/player/session.py`, `choice_projection.py`, `server/worker.py`): rows as above, selection as §14.4b.
- **AI** (`dnd/ai/runtime/decision_epoch.py`, `action_semantics.py`, `execution.py`) reads exactly the new data: creature targets, aim hit sets, paths, costs and OA exposure (`ai/policies/basic.py:537, 707, 919-921`).
  - The `include_aoe_preview` per-cell rows are gone; there is one row per aim point.
  - Objects come from perception (§14.1).
- **Godot client:** consumes the new rows and the selection (PC, other repo).

### 14.6 Counts (GC caster: Vc≈500 visible cells, C=29 perceived creatures, Ob≈126 objects, R≈150 reachable cells, 47 spells)

**First measurement (P0a, 2026-10-17; counts mode, instrumented, not timing-qualified).** Godmode caster, Choices cache miss = **392.7 s**:

| Term | Measured |
| --- | --- |
| LOS collector | 378.7 s |
| Entity rows | 5.2 s |
| Path rows | 3.0 s |
| AoE rows | 2.2 s |
| Rows | 577 |
| Eventful validations | 148,567 |
| Emitted targets | 209,734 |
| AoE aims and footprints | 7,938 |
| Response | 2.55 MB |

Cache hit 0.2 ms; Preview 3.6 ms; Command (Fireball) 6.9 s.

The earlier static estimates (≈276 rows, ≈25–30k validations, ≈45,000 emitted targets) were low. P0b re-bases the "Now" column with ordinary timings.

| Term | Now (measured) | After PD1 | Phase |
| --- | --- | --- | --- |
| Rows built (`_make_action_info`) | 577 | ≈63 (levels and facets are fields) | PD1b |
| Eventful validations | 148,567 | 0 (`_admission_error` is non-eventful) | PD1b |
| Emitted targets | 209,734 | ≤580 AoE aim points + ≈435 creature + ≈350 zone + R | PD1b |
| AoE footprints | 7,938 | ≤580 computed, ≈230 distinct | PD1a |
| LOS/wall enumeration | 378.7 s of 392.7 s | 0 | PD1b |
| Enemy weapon actor | measured in P0b | attacks × perceived enemies; ≈240 ring lookups | PD1b |

What remains after PD1, measured in P0b:

| Term | Ref | Owner |
| --- | --- | --- |
| `_make_action_info`: `BaseCost.model_validate` + 4 profile callbacks per row | `entity.py:5731` | PD2 (and Q-W6) |
| `capture_choices` dump/validate per row and target, double deep copy | `choice_projection.py:87-134` | PD2 |
| Preview deep copy | `entity.py:6122` | PD2 |
| Navigation materialization when dirty (every turn start) | `entity.py:5423-5502` | measured; P5 path freshness |
| `_prepare_position_preview_cache` sorting Ob and collision cells per call | `entity.py:6640-6699` | PD2 |
| Per-step hazard checks per path | `entity.py:7102-7105` | PD2 |
| Propagation FOVs per distinct aim | ≈230 | PD1a |
| Encoding | `worker.py:254` | PD2 |
| Retained discovery graphs released at the operation boundary | handoff:118 | PD2 |

No ms target is set before P0b measures these terms.

### 14.7 PD2 detail (costs of what is kept)

**Unconditional:**

- **Command** re-runs a full preview to read `can_confirm` (`session.py:494`); it becomes the bare `_admission_error`.
- **Preview:** `model_dump_json` only to measure size, plus two deep copies (`session.py:435-442`). The projection is cached instead.
- **Capture:** dump + validate per row and per target, plus a double deep copy (`choice_projection.py:87-134`). This goes away with fresh native rows.
- **Cache hit:** re-encodes compact choices (`worker.py:254`).
- **AI:** dumps row profiles every epoch (`decision_epoch.py:819-845`).
- **Movement list (D13):**
  - copies at `entity.py:6885-6892`;
  - its cache key sorts all path costs on every call (`entity.py:7021-7050`);
  - path tuples are shared;
  - exposure intersection once per path tree;
  - hazard steps;
  - the U5 bound;
  - kept caches `_fast_move_target_cache` (597) and `_position_preview_cache` (602), keyed by GridMap revisions (`entity.py:6685-6699`).

**Conditional on the post-PD1 measurement (like P4b).** Adopted only if R(S−h) > Um+I+F (handoff:194):

- **Revisions on their owners**, following the `observation_revision` pattern (AC:73): ActionEconomy, Equipment, Inventory, SpellcastingBlock, Entity (`registered_actions` and the conditions container), Health, and Senses (contacts).
  - Before any of them, route the external writes through owner methods: 11 ActionEconomy writes (e.g. `conditions.py:2426`, `transmutation.py:378`) and the Health writes (`entity.py:2505/2538/2761`, `traits.py:1629/1648/1660`).
  - `SpellProtectionRegistry` register/unregister (ABJ:1149/1163) bumps `propagation_revision`.
- **Session cache by sections:**

| Section | Key |
| --- | --- |
| Creature rows | actor (position, economy, spellcasting, equipment, conditions, registration revisions) + per perceived creature (uuid, health rev, condition rev), read at request time + force_attack |
| AoE hit sets | `observer_spatial_revisions` (GM:522) + global `grid.propagation_revision` |
| Movement | path revision |
| Env use | position + path revision + object state (doors, levers) |
| Handlers | handler state |

- **Selection staleness checks** (`worker.py:123-125`, `session.py:403`) move to the same keys.

### 14.8 Whole-world scans at execution (PD1c; **D14 approved** by the human 2026-10-17; design `WHOLE_WORLD_SCAN_REDESIGN_2026-10-17.md`)

**One objective GridMap query:** `get_entities_in_bounds(bounds)` and `get_entities_within(center, radius_feet)`.

- **Walk:** one walk over the existing chunk index `_contact_candidate_cells` (GM:2650-2661).
- **Metric:** the same as range admission.
- **Membership:** tile membership ⇔ `is_deployed`, so callers drop `is_deployed`.
- **Cost:** O(chunks + o_r log o_r). No other proximity helper is added.

The discovery-side scans (Cleansing Touch, connectors) are in PD1b (§14.4).

| Site | Today | After |
| --- | --- | --- |
| Revivify (`necromancy.py:2741-2805`) | world scan per level | `get_entities_within(origin, 30)` + companion/ally/life-state filters + caster mask (dead bodies aren't contacts) |
| Holy Aura count (ABJ:3752-3770) | `len(Entity.get_all_entities())` leaked as `num_projectiles` | declared `BaseAction.any_number_of_targets: bool` (rejected together with `allow_same_target`); count = admitted recipients |
| Forcecage displacement (`wall_constructions.py:881-902`) | world scan per visible centre | box query on the chosen centre; predicate and `str(uuid)` order kept; the preview checks only perceived creatures, execution real occupancy (Q-W2) |
| Stone escapes (`wall_constructions.py:509-548`) | world scan, registry order | shell-bbox query; order = `resolution_order_key` (sign-off) |
| Charm Monster advantage (`enchantment.py:2636-2644`) | world scan | target's encounter roster via `get_alive_combatants()`; the new import `dnd.spells.enchantment → dnd.encounter` is acyclic (`dnd.encounter` reaches `dnd.spells.content_metadata` only through `dnd.actions`, never enchantment) |
| Turning (`divine.py:275-289`), Preserve Life (`cleric.py:120-131`), Sunder (`divine_intervention.py:133-141`), Opulent Revival (:205-236) | world scans | `within(.., 30/30/50/60)`; Turning keeps the **target's** "can see you" check |
| `get_entities_by_faction` / `get_alive_by_faction` (`entity.py:4500-4522`) | world scans with no `dnd/` caller | deleted (human, Q-W3) |

- **Bug (D6, sign-off):** Opulent Revival can revive a suspended dead companion off-grid. Grid membership excludes it.
- **Tests (redesign §4):**
  - `tests/engine/test_bounded_recipient_discovery.py`: CT1–3, RV1, HA1;
  - FC1, WS1, CM1, TU1, PL1/SU1/OR1 in the existing suites;
  - GM1 brute-force equality;
  - an AST ban on `get_all_entities` / `_entity_registry` iteration in `dnd/`, with the listed exceptions.
- **Superseded parts of the redesign doc:** §3 `get_target_variants` and §2.1 "Kept: `get_variant_facets`" are replaced by §14.4.

### 14.9 Evidence

| Source | Finding |
| --- | --- |
| Production rework plan | Gallery Choices ≈191 ms ordinary after schema 8; deferred AoE preview kept |
| Held experiment | Wall/LOS enumeration 77.4 s of 90.2 s instrumented. The tile-storage (−17 %) and wall-interval (−8.5 %) wins came almost entirely from that enumeration, so they aren't needed once it's gone. The whole-request shell memo was rejected (155 MB) and must not be revived. |
| P0a GC measurement | Choices miss 392.7 s instrumented, LOS collector 378.7 s (§14.6) |
| This study | Three read-only maps (engine core, placement, consumers) at `d13e6ad`; v3.5 reviews (antislop 13, antiOOP 14); v3.6 re-reviews (antislop 16, antiOOP 14); whole-world redesign with its own reviews |

### 14.10 Questions for the human

| Q | Question | Status |
| --- | --- | --- |
| D14 | Whole-world scan redesign | **Approved** (2026-10-17) |
| Q-W1 | Relocation destinations | **Decided:** sight ∩ empty ∩ range from the scan (§14.1) |
| Q-W2 | Forcecage placement checks every deployed creature, ignoring `subjective`. It refuses ("cannot displace a partially enclosed creature") when any straddling creature, seen or not, has no free reachable cell, and free cells are judged on real occupancy. A refusal therefore reveals an unseen creature; when every straddler can be pushed out, the preview just passes. | **Decided (human 2026-10-17):** preview on perceived contacts; execution refuses on real occupancy |
| Q-W3 | Unused faction scans | **Decided:** delete |
| Q-W4 | AI object attacks | **Decided:** objects are part of perception (§14.1) |
| Q-W5 | Rule bodies of 232 `_validate` + 4 discovery-only overrides move into `rule_error(scan, selection)` behind one non-overridable `_admission_error`; `Entity.perform` becomes the only `apply` entry | **Decided (human 2026-10-17): yes** |
| Q-W6 | The 5 base profile hooks (`get_outcome_profile`, `get_fixed_healing`, `get_self_setup_profile`, `get_target_effect_profile`, `get_world_effect_profile`) take `actor: Any` (106 occurrences with overrides), and overrides use `isinstance(actor, Entity)` 48 times; `_make_action_info` passes the Entity per row (`entity.py:5717-5720`) | **Required in PD1b** (human: "any is bad in general"; "that is what we did everywhere else"): the hooks lose the actor parameter. Every caller passes exactly `Entity.get(self.source_entity_uuid)` (discovery `entity.py:5717-5737`; ACT:5549; Multiattack sub-attacks built with the same source, `traits.py:587-604`; the summon override, `spell_summon_actions.py:833`). Base hooks return None and never resolve it. Overrides (95 of 114 read the actor, mostly via shared helpers) call `Entity.get(self.source_entity_uuid)`, and the shared helpers in ACT take a typed `Entity`. All `Any` and the 48 `isinstance` checks are deleted. Nothing goes into the scan. |
| Order | Run P1–P3 before PD1? | **Decided** (human: "whatever the order what make most sense"): §7 order, sensory first, PD1a before P3, PD1b after P3 |
