# Fireball ledger (GC caster, oil barrel, ~30 observers)

Measured at integration head fa74e5101 / 489d06d2e on 2026-10-17. Ordinary mode, three runs. The gallery runs one full collection before each op, outside the timed span, so the op is charged only for its own collections.

Tools, all in scratchpad `residuals/`:

- `stage_sampler.py`: assigns each CPU sample to the innermost stage on its stack.
- `alloc_sites.py`: tracemalloc by engine allocation site.
- the gallery's own `gc` row field.

## The row

| Measure | Value |
| --- | --- |
| total | 246–267 ms |
| native | 116–134 ms |
| operation | 6–10 ms |
| publication | 119–122 ms |
| encoding | 4 ms |
| event versions | 564 |
| largest seat update | 402,176 B |
| young survivors | ~60K objects |
| gen-2 inside the op | 0 |
| one full pass at this heap size | ~185 ms (paid whenever one fires; the heap is ~500K tracked objects) |

## Stages: CPU time and objects kept at op end

| Stage | ms (3 runs) | Objects kept (site) | Owner and next exact change |
| --- | --- | --- | --- |
| Publication: projection and seat fold | 65–73 | 1,613 (`audience.py:501` per-cell previous-cell dict); 600 (`reduction.py:94` tile `model_copy`); 444 (`projection.py:1647`) | **PV1b**: packed cells in the fold (built, not merged: move publication 2× slower, cause open). Tile states as frozen values, no per-tile `model_copy`. |
| Publication: capture | 49–53 | 3,212 (`capture.py:690` `deepcopy` of retained events); 1,926 (`capture.py:626` `_event_header` copies grants into `set`s) | **P7b**: stored versions frozen (child links from the lineage index; combat logs by copy-update), then capture by reference. `_event_header` keeps the frozensets (one-line). |
| Perception settlement | 45–57 | 10,982 (`sensory.py:594` one SensoryUpdateEvent per observer per settlement); 1,638 (`sensory.py:590` ObservedChangeRef); 726 (`sensory.py:1057` `_holders` sets) | **PV1b** packs the event's cells; **PV1a-2 next**: one settlement per step, 2-D batching. |
| Event machinery (store, post, phase, perceivers, grants) | 24–33 | 1,824 + 746 (`events.py:695/699` `post` `model_copy` per version); 940 (`events.py:2293` one grants dict per version); 477 (`events.py:2172` `publish_committed_phase` `model_copy`); 1,545 (`encounter.py:91` perceivers re-stringified per version); 1,736 + 617 (`encounter.py:101/110` grants dicts) | **P7b**: no per-version copies. Perceivers and grants once per distinct input, ids stringified once. |
| Value reads | 16–33 | 1,684 + 1,530 (`values.py:706/1331` `combine_values` builds new values per read); ~1.4K (`values.py:1758–1784` `ModifiableValue.create`) | **PH-2**: values as records; a combined read returns a reading, not a new value graph (design settled, ~1.5–2 sessions). |
| Object damage and destruction (barrel, ash) | 8–16 | — | Authored rule (spill, ignite). Re-sample before changing. |
| Targets and footprint | 4–8 | — | Done (PD1a / PD1b). |
| Creature damage and saves | ~4 | — | PR done (saves 1.7 → 0.9 ms per read; set/clear walks 25,260 → 0). |
| Residues | ~4 | — | Done (D15). |
| Publication tile states | (inside publication) | 2,227 (`base_tiles.py:357` a fresh `WorldTileState` per tile per publication) | **unowned → P7b-adjacent**: a tile's state is a frozen value, rebuilt only when the tile changes. |
| Encoding | 4 | — | Falls with bytes (PW, PV1b). |

## What is already removed (merged)

- **Perception.** ~6,000 full recomputes per area spell → 30 (P1/P3). Arrays per observer (PV1a). Scoped wipes → 0 (P5).
- **Events.** Per-cell handler re-reads and completion lookups (P6). Identity-grant copies 16,480 objects / 13.7 MB → 1,326 / 0.2 MB (grants).
- **Publication.** The server mirror (P7). Body and item patches, `observed_changes` off the wire, flattened combat log, occurrence-index identity (PW: 1.02 MB → 0.40 MB).
- **Rules and values.** Frozen value-read context (PR). Schema builds out of ops (PS).

## Gate status

| Gate | Target | Fireball now |
| --- | --- | --- |
| Ceiling | ≤100 ms | **missed**: ~250 ms |
| Payload | ≤100,000 B | **missed**: 402,176 B |
| Gen-2 passes inside the op | 0 | 0 in these runs, but depends on what earlier ops left |
