# Q4: where keyed world changes are produced (study with measurements, 2026-10-18)

**Setup.** Measured on `codex/event-native-deltas` at 63c4a07f1, gallery G1 (amber 4 observers, blue 26), three runs on a loaded machine. Probes are in the integrator's scratchpad `q4/`.

## Decision (integrator): (W)

The writers record the keyed change, and completion fills in only those keys' after-values. Capture diffing against the session fold (C) is kept only as a test oracle. The settlement-level option (S) is rejected.

## 1. What already carries its keyed change

- **Already keyed on the native event:**
  - TILE_CHANGED partial fields;
  - LIGHT_CHANGED `light_level_map`;
  - `TileElevationChangeEvent`;
  - `WorldModifiedEvent` before/after (tiles, `default_light`, connectors);
  - tile conditions (name, uuid);
  - objects, object residues and contents, as after-values by uuid.
- **Not keyed: only TILES_CHANGED.** It comes from two writers, residues.py ~186–286 and area_conditions.py ~1405/~1447, and publishes complete rows re-snapshotted at completion (gridmap.py ~3637–3640).
- **Whole rows have one reader:** `world_facts.apply_world_fact`, called by each seat's fold, the capture targets and the AI fold (knowledge_reduction.py ~218–220). `sensory_fold.py` ~64–68 folds spatial-effect and light-source rows, not tile rows (a correction to the plan).

## 2. Where `_world_update`'s time goes (ms per op, both seats)

| Op | Sensory-driven | World-driven | Member cells ± | Composed entered / left | Composed entering mock |
| --- | --- | --- | --- | --- | --- |
| Fireball | 8.8–10.9 | 5.1–5.6 | 9,702 | 0 / 2 | 0 |
| Sleet cast | 19.5–29.6 | 2.9–4.6 | 25,623 | 0 / 940 | 0 |
| Sleet drop | 25.6–33.4 | 0.4–0.5 | 21,663 | 677 / 0 | 0.9 (73 objects) |
| Darkness | 11.0–11.7 | 0 | 11,937 | 0 / 375 | 0 |
| Daylight | 14.8–20.2 | 2.2–3.2 | 11,950 | 377 / 0 | 0.4–0.5 |
| Wall of Stone | 10.0–13.5 | 0.7–1.0 | 9,033 | 0 / 370 | 0 |
| SG walk step | 1.1–2.3 | 0.7–1.1 | 10–27 | 3–7 / 0–5 | ≤0.2 |

85–98 % of the time is sensory-driven: per member event, every object at every member cell added or removed is re-observed. The decided rules (composed entering cells, nothing on leaving) remove all of it. The world-driven part is what Q4 affects; `_tile_changes` itself is ≤0.7 ms of it.

## 3. The candidates

- **(W) The writer records the keyed change.**
  - **Exactness, by simulation** (wrappers on `Tile.record_residue`, `Tile.forget_residue` and the terrain write, folded and compared with the completion rows): 652 of 653 rows exact.
    - Fireball 140/141, Ice Storm 91/91, Magic Missile 27/27, Sleet cast and drop 197/197.
    - The one mismatch is a `resolved_light` value that the whole row carried 34 versions before its own LIGHT_CHANGED fact; (W) attributes it correctly.
  - **Ordering:** no row changed between declaration and completion in 7 cases, but values are read at completion.
  - **CPU:** native −0.3 to −7.0 ms per op (Fireball −2.1 to −2.8, Sleet cast −3.9 to −7.0); each fold +0.1 to +0.4 ms.
  - **Native TILES_CHANGED payload, whole rows → keyed:** Fireball 117 → 27 KB, Sleet 92 → 6.9, Ice Storm 65 → 11, Magic Missile 22 → 6.4. Wire bytes are the same as under (C).
  - **Architecture:** the owning writer records the change as frozen types in `dnd/types` (`WorldTileChanges` exists). No new import edges.
  - **Size:** ≈150–200 lines, plus 3 test references to `tile_states`. Gate: AI knowledge equal.
- **(C) Capture diffs the after-rows against the session fold.**
  - Exact to the fold, but light can be attributed early.
  - +0.2 to +1.1 ms per op, and the native whole rows stay.
  - Needs the session fold (E3a) before E2. ≈60–80 lines.
- **(S) The settlement emits world changes.** Rejected:
  - WORLD_MODIFIED, item-location and item-resource events never reach the settlement (`EVENT_TYPES`, sensory.py ~988–1007);
  - inert facts emit nothing;
  - group settlements merge facts, breaking one update per occurrence;
  - it works per member, not per seat: composing there inverts the DAG, member entering cells are 18–58× the composed ones, and each observer would hold its own copy;
  - it still needs (W) or (C) underneath;
  - dropping tile cells from the settlement gained nothing measurable.

## 4. Side finding: skipping inert tile facts in the settlement

An inert tile fact (blood or ash amounts) pulls every observer in range into a settlement that publishes nothing. Skipping it using the event's existing hint:

- Magic Missile: settlement 9.5–9.7 → 4.4–4.5 ms, native 22.5 → 15.5–16.5 ms, digest and wire identical;
- Fireball, Chain Lightning, Ice Storm: no change;
- Sleet and Wall of Stone: not verifiable (their runs differ from themselves).

Open edge: `_reason_for(events[-1])` can change when the inert fact was the last event.
