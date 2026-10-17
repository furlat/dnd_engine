# Codebase study notes — 2026-10-16

Orientation notes from a read-only study of `feature/speedupsensory` at
`229ce025f3ff` (dirty: `RECOVERY_PLAN.md` plus untracked docs). Code was the
source of truth; doc claims that disagree with code are listed in §9. The human
pointed at [ENGINE_PERFORMANCE_HANDOFF_2026-10-16.md](ENGINE_PERFORMANCE_HANDOFF_2026-10-16.md)
as the evidence base for the performance problem; its measured tables are not
repeated here beyond what is needed to connect them to source.

No production code, tests or benchmarks were changed. One scratch probe
(Fireball into a cluster, open bright arena) was run before the handoff was
supplied; its numbers are in §6.1 and are a toy workload, not the gallery fixture.

## 1. What is live

| Area | Live source | Notes |
| --- | --- | --- |
| Engine | `dnd/` (~164k lines) | `entity.py` 8.1k, `core/gridmap.py` 6.4k, `actions.py` 5.7k, `core/events.py` 5.7k, `blocks/sensory.py` 2.2k. |
| Server | `server/` (~2.3k lines) | FastAPI host + pooled worker subprocesses. |
| SDKs | `sdk/python`, `sdk/player-typescript`, `sdk/protocol` | Player schema **9**. |
| Player boundary | `dnd/player/` | capture → projection → per-seat reduction. |
| Agent sandbox | `monty_sandbox/` | MCP server, Monty REPL, drives the real server via SDK only. |
| Perf harnesses | `devtools/player_server_acceptance/` | cProfile + `dnd/action_timing.py` recorders. |
| Godot client | `/mnt/c/Users/tommaso/Documents/Dev/NDClientGodot` | `play.tscn`/`play.gd` is the live player. |

Dead or leftover: `dnd/runtime/**` (only `.pyc`, nothing imports it),
`tests/{product,runtime,scenario_lab,transition_sequences}` (only `.pyc`),
`game/` (gone; still referenced, see §9), `*_obsolete/`, `deprecated/`.
`agent_docs/CLAUDE.md` describes an older layout (`examples/`, `claude_docs/`, CLI).

## 2. Process and execution model

- One uvicorn process, one asyncio loop. `Service` holds one `Host` per game
  and a worker pool (default 4 workers, `server/config.py:17-19`).
- Each game leases one `python -m server.worker` subprocess for its lifetime.
  The engine is single-threaded, synchronous and process-global (EventQueue
  class attributes, `get_map()` singleton, `spatial_senses_system` singleton,
  registries). That is why worlds are isolated per process.
- `Host.run` is serial: one request in flight per game (`server/host.py:368-446`).
- Publication boundary = one human command or one AI decision
  (`encounter.advance_one_controller_action_boundary`, `dnd/encounter.py:1343`,
  wrapped in `EventQueue.batch_on_event_callbacks`). Each boundary is a
  host↔worker round trip plus capture/projection for every seat.
- There is **no engine-side parallelism**. "Parallel execution of spells" today
  means sequential resolution in one thread; concurrency exists only in client
  presentation (overlapping component windows inside one group, §8).

## 3. Event core (`dnd/core/events.py`)

- `Event` is a pydantic model; each `post()`/`phase_to()` makes a new version
  (new uuid, same `lineage_uuid`) and registers it. Phases:
  DECLARATION → EXECUTION → EFFECT → COMPLETION (or CANCEL).
- `EventQueue.register` (`:1807`) → `_store_event` → handler dispatch.
  Handlers never run at COMPLETION.
- `_store_event` (`:2112`) on **every version**: copies observer grant sets,
  calls `_identified_entity_observer_computer` (installed by Encounter,
  `encounter.py:97`: grid subscribers at participant position + `senses.entities`
  membership), merges parent grants, appends to 7 indexes, runs per-event
  callbacks, then sequence and batch callbacks.
- `phase_to(COMPLETION)` (`:441`) runs **pre-completion systems first**
  (`run_pre_completion_callbacks`, `:1765`), then recomputes located grants,
  generates the combat log, perceivers and revealed sets, then posts.
- Pre-completion systems are the hook where derived state is settled *inside*
  the causal event: `SpatialSensesSystem` (sensory), summoning system,
  restraint callback. GridMap also settles light *before* completion
  (`_recompute_lights_before_spatial_completion`, `gridmap.py:3175`).
- Alternative publication paths exist: `preflight`/`publish_preflighted`
  (pure validators), `publish_committed_phase` (already-committed facts; handlers
  see a deep copy and cannot veto), `publish_completed_fact`,
  `register_completion_sequence` (many completions, one sequence notification).
- `batch_on_event_callbacks` only delays observers registered via
  `add_on_event_batch_callback`; the only registrants are in `server_obsolete/`. Handlers,
  pre-completion systems and per-event callbacks are never deferred by it.

## 4. Sensory reducer (`dnd/blocks/sensory.py`, `SpatialSensesSystem`)

Runs as a pre-completion system for `DEATH`, `CONDITION_APPLICATION/REMOVAL`,
`LIFE_STATE_CHANGE`, `TURN_START` and all `SPATIAL_*` types (`:646-665`).

Candidate observers (`candidate_observer_uuids`, `:1565`): subscribers at the
event's cells (`grid.get_subscribers_at`), reverse indexes by entity/object, and
— when the hint has `requires_paths` — every observer whose visible/path/safe-path
footprint contains the cell (`observers_by_known_position`).

Per candidate, `__call__` (`:1634`) chooses:

| Input | Path | Cost |
| --- | --- | --- |
| `SPATIAL_LIGHT_SOURCES_CHANGED` | descriptor refresh | cheap |
| `SPATIAL_LIGHT_CHANGED`, field current | `_update_light` (`:1867`) | changed cells + contacts there |
| Another creature `SPATIAL_ENTITY_ENTERED`, field current | `_update_entity_contact` (`:2010`) | one contact |
| Own turn start / own condition / own entry / tile residue / tile change **without** `requires_fov`/`requires_paths`, field current | hazards-only refresh | local |
| Everything else: `SPATIAL_PERCEIVABILITY_CHANGED` (deaths, hide, invisibility), object placed/removed/changed, tile change with `requires_paths`, `SPATIAL_EFFECT_CHANGED`, self-movement, stale field | **`recompute_observer` (`:708`)** | full |

`recompute_observer` = capability inputs → geometric FOV (revision-cached) →
per-cell optical filtering (obscurement routes walk a supercover line per cell
when obscurements exist) → nonvisual FOV → boundary snapshot → boundary
evidence → contact scan over every visible occupied cell → known-object contacts
→ boundary contacts → `replace_perception` → volume geometry → re-subscribe cells
→ volume light → hazards → reverse-index footprint. Then the caller diffs full
before/after snapshots (`emit_sensory_update_delta`, `:454`) and emits a
`SensoryUpdateEvent` only if something changed. Unchanged results still pay the
whole solve.

Field freshness is a per-observer 4-tuple of revisions
(optical, illumination, propagation, occupancy) bumped by `GridMap` for
observers dependent on the touched cells (`gridmap.py:522-545`). Any bump in the
wrong channel pushes the observer off the fast paths.

Navigation (Dijkstra) is not run by the reducer; it sets `_paths_dirty` and
`materialize_navigation` runs at discovery/turn/movement boundaries
(`entity.py:5438`, `:8020`).

## 5. Lighting (`dnd/core/gridmap.py`)

- `recompute_lights_at_positions` (`:5967`) loops **all** light sources,
  range-tests each, recomputes in-range ones fully (`_compute_light_tiles`),
  and publishes **one committed four-phase event per source**
  (`_fire_light_batch_events` → `_fire_committed_spatial_event`). Each of those
  completions runs the sensory reducer again.
- When the parent spatial event has `requires_light_recompute`, its candidate
  observers are deferred on the light children and refreshed once at the
  parent's completion (`sensory.py:1638-1643`). Observers outside that set still
  react per light child.
- Light suppression tokens (`set_block_light_suppressed`, `:5628`) are used by
  death, world presence and dousing; each change goes through the same per-source
  publication.

## 6. Cascade anatomy (source-traced)

**Death.** `Entity._commit_life_state` (`entity.py:2492`) →
`invalidate_occupancy_paths` (bumps occupancy revision for observers of that
cell) → light suppression (if it carries light) →
`_notify_perceivability_changed` (`base_block.py:567`, full four-phase event) →
reducer: subscribers of the cell + everyone who had the victim as contact →
**full recompute each**. `LifeStateChangeEvent` (target only) and `DeathEvent`
(observers still holding the victim; usually none by then) follow.
Targets resolve sequentially, so an AoE with D deaths and O observers costs
≈ D × O full recomputes.

**Terrain field (Sleet / Ice Storm / debris).** `AreaCondition._apply`
(`spatial/area_conditions.py:1504`) → `_apply_terrain_positions` (`:1358`): per
cell, add a modifier, `invalidate_spatial_caches({"movement"}, {cell})` and
`publish_tile_mechanics_changed` → one four-phase `SPATIAL_TILE_CHANGED` per
cell, hint `requires_paths=True` (`gridmap.py:1615-1631`). Because the hint
carries `requires_paths`, the reducer's cheap `tile_refresh` path is excluded.
Every observer whose visible/path footprint covers the cell gets a **full
recompute per cell**. The same `_apply` then calls `spatial_senses_system(effect)`
once more by hand. Sleet also installs HEAVY optical obscurement, which makes
each recompute walk obscurement routes per cell. Removal mirrors this through
`_remove_terrain_positions` (`:1401`) unless a `_removal_publication` buffer is
active. Saved production evidence for the gallery fixture:
Sleet cast 197 `spatial_tile_changed` terminals, 853 versions, only 14 sensory
terminals, **53.3 s native**; drop 810 versions, 6.1 s.

**Destruction.** `SpatialChangeEvent.object_removed` sets `requires_fov` /
`requires_paths` / `requires_light_recompute` for blocking objects → per-source
light events + full recompute for subscribers; debris is a separate
`DestructionDebris` → `AreaCondition` field, which then hits the terrain-field
path above. A large room full of breakables multiplies both.

**Corpse lights.** Death bumps the occupancy revision before suppressing the
corpse's attached lights. The light children then fail `_can_update_light`
(`sensory.py:1843`, needs unchanged occupancy or an ENTITY_ENTERED parent) and
fall to full recomputes too. Per kill with no lights: ≈3 reducer calls
(perceivability, life state, death), plus one per attached light.

**Zone creation reduces twice.** `AreaCondition._apply` calls
`spatial_senses_system(effect)` by hand (`area_conditions.py:1528`); `activate`
then completes the same `SpatialEffectChangeEvent` (`_complete_change`, `:623`,
`:741`), which runs the pre-completion reducer again. `SPATIAL_EFFECT_CHANGED`
has no fast path, so both are full recomputes for the candidates. Whether the
second pass is ever needed was not established.

### 6.0 Spell execution order (`core/base_actions.py`, `spells/evocation.py`)

- `BaseAction.apply` (`:2260`) → `_apply_action` (`:2273`): costs, declaration,
  validation, cost commit, EXECUTION, area target resolution once (`:2416`,
  sorted), EFFECT, `_apply_target_applications`, `_finalize_aoe`, concentration
  cleanup, COMPLETION.
- `_apply_target_batch` (`:2111`): one copied execution event per target with an
  `ApplicationMembership(index)`; `_apply` then COMPLETION **before the next
  target starts**. Target k's save → damage → death → every sensory reduction
  finishes before target k+1 rolls. Nothing is batched.
- Fireball (`evocation.py:920-1038`) grows in stages: each stage publishes an
  `AreaReachEvent`, applies new recipients one by one, ignites surface contacts,
  and runs another stage if `grid.propagation_revision` changed (a barrier broke).
  `_finalize_aoe` deposits Ashen residue last (one CONDITION_APPLICATION per
  cell, cheap hazard path).
- Fireball rolls its damage inside each target's `_apply` (`evocation.py:1107-1111`),
  so each target gets its own roll. This is a rules-fidelity observation, not a
  performance item.
- Multi-projectile spells (Magic Missile `:557`, Scorching Ray `:701`, Eldritch
  Blast `:2782`) are one application per projectile in the same sequential loop.
  "Simultaneous" exists only in naming/metadata (`ApplicationMembership`,
  `missile_volley`).
- Nested movement (steps, Thunderwave pushes) runs zone damage, deaths and their
  reductions inside the step's EFFECT phase, before the step's own completion.
- `SensesUpdateHint.entity_died` is read (`sensory.py:1621`) but never written.
- The only real deferral is `_paths_dirty`. `GridMap.disable_events`, the
  `_removal_publication` buffer and `commit_object_removals(publish=False)` exist
  for atomicity, but each retained change is still published as its own event.

### 6.1 Toy probe (open bright 25×25 arena, before the handoff was supplied)

Scratch script: `/tmp/claude-1000/-mnt-c-Users-tommaso-Documents-Dev-dnd-engine/ab518066-b09e-4d5f-b4c8-5b2d938240f6/scratchpad/fireball_probe.py`.
All targets killed; witnesses static.

| Targets | Observers | Full recomputes | Sensory events | Wall |
| --- | --- | --- | --- | --- |
| 1 | 8 | 9 | 6 | 60 ms |
| 8 | 15 | 100 | 84 | 157 ms |
| 20 | 29 | 401 | 376 | 517 ms |

Every sensory event had reason `perceivability`. The 49 ashen tile
conditions (196 versions) did not trigger full recomputes here. Bright map, no
torches, no breakables: this isolates the death term only.

### 6.2 First-principles inventory

Human direction (2026-10-16): times must drop by a lot. The faults are
first-principles ones. One change cascades through the sensory system several
times instead of once, and the same sensory computation is repeated for every
observer.

**A. One logical change, several sensory passes**

| Change | Passes today | Source |
| --- | --- | --- |
| One creature dies | perceivability (four-phase event) + life state + death + one per corpse light; the light ones are full recomputes because occupancy was bumped first | `entity.py:2492-2517`, `base_block.py:567`, `sensory.py:1843` |
| N targets in one AoE | N independent passes over the same observers, interleaved with the target loop | `base_actions.py:2111-2151` |
| Zone appears | manual `spatial_senses_system(effect)` + its own completion | `area_conditions.py:1528`, `:623`, `:741` |
| Terrain field over C cells | C four-phase tile events, each a full recompute for every covering observer (`requires_paths` blocks the cheap tile path) | `area_conditions.py:1358`, `gridmap.py:1615`, `sensory.py:1714-1728` |
| Light-affecting change | one committed event + pass per in-range source | `gridmap.py:5967-6022` |
| Breakable destroyed | object removal + per-source light + debris field (→ terrain row) + Fireball re-stage on propagation change | `events.py` `object_removed`, `evocation.py:1030` |
| Creature moves with a light | light child refresh, then the ENTERED refresh, which often finds nothing new | Sept 12 sensory study; `sensory.py:1674-1688` |
| Every event version | identity-observer computation at store (×4 phases), again at completion | `events.py:2137`, `:443` |

**B. Objective work repeated per observer inside `recompute_observer`**

| Work | Why it is shared | Source |
| --- | --- | --- |
| Boundary snapshot: copy wall/door side layers for the observer's region, resolve every provider (`BaseBlock.get` + `get_boundary_structure`) | same physical walls for everyone; handoff v10 saw 11,304 providers resolved, 0 reused | `gridmap.py:4116` |
| Optical obscurement snapshot rebuilt from per-cell condition queries | same storm/fog cells for everyone | `gridmap.py:5360` |
| Per visible cell, a supercover line walk unioning obscurements | the line is origin-dependent, but every observer re-reads the same cells; under Sleet this is R² × R per observer, per solve | `sensory.py:819-866`, `gridmap.py:5410` |
| Tile light level reads and light-route tables | objective illumination | `sensory.py:840-843` |
| Emitter descriptors (`observe_light_sources`) | same emitters | `sensory.py:1812`, `gridmap.py:5516` |
| Hazard cells and effect indexing | which cells carry hazards is objective; only the filter/DC check is per observer | `sensory.py:1098` |
| Passive perception recomputed per subject inside `_resolve_contact` | one scalar per observer per solve | `sensory.py:1484-1487` (probe: 362 calls for 100 solves) |

**C. What is genuinely per observer**

Origin and range of sight (FOV is cached by origin and radius), sense modes and
their ranges, visual access, passive perception vs each subject's stealth,
invisibility bypass, hazard filter/DC, and the observer's own memory (`seen`,
previous contacts). Everything else in a solve is shared world data.

## 7. Existing performance work (from the handoff, not re-run)

Four worktrees hold attempts; the causal one has active dirty work to protect.
Production gallery fixture: `NDClientGodot/.runtime/gallery-sorcerer-20261015-seed3-door`
(godmode sorcerer at (36,7), 47 spells, aim (42,10)). Key production numbers:
Fireball 718 ms native, Ice Storm 2.45 s, Sleet cast 53.3 s, Sleet drop 6.1 s.
Best later arms: Sleet cast ~1.36–1.5 s, Ice Storm ~0.4 s, Fireball ~0.69 s,
still above the 100 ms / 40 ms goals. Discovery (Choices) separately ~24–33 s on
wall-heavy variants. Constraints carried by the handoff: keep ECS owners, no new
universal world/interpreter/manager, single execution path, coarse fork/join only
for substantial independent work.

## 8. Godot client consequences

- Groups (one per lineage) play strictly serially; overlap exists only inside
  a group and in retained components.
- Commit times are forced monotonic in source order. Any commit touching
  tiles/objects/senses/connectors is a **world boundary** that pauses the clock;
  only one boundary is prepared/admitted at a time. Same-timestamp commits merge;
  staggered ones (per-target deaths, per-cell field changes, light changes) become
  N serial boundaries, each with prepare → admit → publish and atlas jobs per
  changed source and per visibility-flipped row.
- So engine-side per-cell/per-death granularity also multiplies client holds.

## 9. Doc vs code discrepancies

- Player schema is **9** in code and SDKs; `RECOVERY_PLAN.md`,
  `sdk/protocol/README.md:178` and `server/README.md:121` say 8.
- `AGENTS.md` links `HISTORY_BEFORE_ME.md` at repo root; it lives in
  `agent_docs/`.
- `devtools/player_server_acceptance/performance_spells.py` imports
  `game.combat_demo` and `tests.game.*`, which no longer exist.
- `tests/architecture/test_dependency_boundaries.py:1006` imports `game.app`.
- `tests/paused_server/` is documented as broken and is not skipped.
- `agent_docs/CLAUDE.md` refers to `examples/`, `claude_docs/` and a CLI that
  are gone.
- NDClientGodot README says `run.cmd` opens `demo.tscn`; it opens `play.tscn`.

## 10. Human answers and remaining questions

- **Latency target:** cut times by a lot. The faults are first-principles ones
  (multi-pass cascades, per-observer repetition, global invalidation for local
  changes). Don't litigate which boundary the timing is measured at.
- **Fixture:** no existing fixture is mandated. Spells must be thrown in big rooms
  with many creatures, many lights and many destructible objects, so every bad
  path fires at once.
  - The closest existing map is the Lantern Gallery
    (`battlefield_catalog.py:357`, 73×39, dark): 33 wall torches, ~100 breakable
    props, 246 wall pieces.
  - Its handoff fixture has only 6 creatures, so a stress variant needs a dense
    roster (clustered in the blast plus spread witnesses) and two audiences.
- **Still open:** which base the next step builds on — production, or the
  causal-execution worktree.
