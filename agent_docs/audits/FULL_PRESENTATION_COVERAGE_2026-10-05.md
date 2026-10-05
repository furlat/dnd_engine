# Full presentation coverage and repair design

2026-10-05. Covers the entire current game presentation, not only spells. This is source/design coverage; current pixel and boundary-time validation is explicitly outstanding. It is not implementation acceptance.

## Coverage denominator

The [reproducible full inventory](rendering-readiness-20261005/full_inventory.py) expands the earlier spell inventory into:

- **1,367 declared/selected content rows across 24 families**, each with binding and historical evidence status: [CSV](rendering-readiness-20261005/all-content-coverage.csv), [JSON](rendering-readiness-20261005/all-content-coverage.json).
- **All 53 AnimationData fields**, including consumer references; all 53 values are now materialized in the effective catalog: [field ledger](rendering-readiness-20261005/catalog-field-coverage.json). Source references are candidate attribute references; similarly named attributes are not automatically semantic uses.
- **All 126 top-level game Python modules** with descriptions, dependencies, functions and records: [source index](rendering-readiness-20261005/module-source-index.json). This index establishes the review denominator, not a line-by-line correctness certificate.
- **82 public/bound/source records** from player facts, choreography, world transitions, playback, native world-state facts and perceived senses: [record field index](rendering-readiness-20261005/record-field-index.json).
- **873 declared review cases** indexed by scenario and tags: [case index](rendering-readiness-20261005/declared-case-index.json). Declaration is not execution evidence.
- All 27 public fact kinds, damage stages, observations, world updates, cancellation metadata, initial state and factless admitted nodes. These are enumerated in the [readiness audit](RENDERING_SCHEMA_READINESS_2026-10-05.md).

The selected content rows include 93 action identities, five attack recipes, shove, 160 condition recipes, all selected rigs, 13 world animation bindings, devices, portals, spatial media, deposits, doors, traps, props and wrecks. Shared recipes do not imply every action/rig/outcome combination has been visually verified.

## End-to-end ownership

`session/engine operation → private capture → observer projection → public sequence → causal index/reduction → presentation grouping → binding and state-commit scheduling → retained lifetimes → body/media/world sampling → graphics or narrative`.

Native handlers remain gameplay owners. The presentation must consume their committed, permitted results rather than call handlers or recreate attack, surface, movement, saving-throw or initiative rules. Preserve native resolution/application identities and order. Public factless outcomes are valid inputs.

Existing private replay (`replay.py`, `presentation.py`) is not the future client protocol. Public player sequences (`player_facts.py`, `player_reduction.py`) remain the shared input. Compatibility upgrading stays at decode boundaries (`recording_compat.py`), not scattered through renderers.

## Full behavior matrix

Each row states the authored owner, current Python responsibility, repair/design obligation and mandatory evidence. Detailed geometry and lifetime branches remain in the readiness audit rather than being flattened away here.

| Domain | Authored data / existing Python | Required contract and repair | Required evidence |
|---|---|---|---|
| Ordinary actions | body_action recipes/bindings/deliveries; body_action.py, choreography | Resolve aliases once; preserve outcome/interaction ownership; do not route every action through spell casts | Item use, equipment, class action, failed action, body-only action |
| Melee/unarmed/off-hand | attack recipes with precedence and rig/item selectors; attack.py | Same attack outcome path for creatures/objects; exact item UUID and weapon set; no duplicate off-hand executor | Hit/miss/crit, unarmed, off-hand, fixed/modular rig, object target |
| Ranged/thrown | attack projectile profile, measured release and offsets | Preserve release socket/time, world trajectory and interception; material treatment must be explicit | Bow, thrown, intercepted projectile, camera rotation, elevation |
| Attack materials | attackVfx selectors + layer materialization | Current `_attack_layers` declares tint while loader uses source-hue rotation or multiplication. Resolve one explicit color treatment and key caches by it; verify palette swap correction visually | Elemental/non-elemental slash, absent fixed-rig slot, different palettes |
| Spells | effective drafts, gesture/media/material/area recipes | Preserve semantics, application identities, measured sockets and phase ownership; each spell's selection reviewed | Existing full spell matrix plus outcome and disclosure variants |
| Voluntary movement | movement contexts, rig mappings, motion tracks; bind_motion/sample_motion | Keep disclosed steps, mode, connector, cadence and reaction holds; no inferred hidden path | Walk corners, flight, jump, crawl, elevation, interruption |
| Forced movement/shove/fall | forced context/profile and shove recipes | Attempt separate from displacement; actual distance/path/drop and landing authoritative; contact timing from presentation | Zero/partial/full displacement, ledge fall, landing damage, prone |
| Portals/absence | portal/absence recipes and retained state | Independently nullable endpoints, departure and arrival clocks; no remote visibility grant | Departure-only, arrival-only, full transfer, return, missing endpoint |
| Opportunity/other reactions | interruption policies, body recipes; presentation_group/interruption | Preserve independent roots/native order; group only actual trigger references; paused incoming sample can use a different clock from reaction | Successful/failed reaction, interrupted attempt, completed child, unmatched reaction root |
| Damage/heal/temp HP | contexts; combat.py, feedback.py, choreography | Request versus result, exact resolution/application, zero/blocked effects; share occurrence timing with text without equating text with number sprites | Multiple damage types, repeated targets, temp HP absorption, blocked heal |
| Saves/lifecycle | death/save/life contexts | Save result distinct from optional dodge art; prone-to-death does not stand up; corpse/disintegration/departure distinct | Save succeeds with damage, dying/stable/dead/revive, prone death |
| Conditions/item effects | condition recipes/media, item attachments and lifetime maps | Original owner/clock, last-owner removal, suppression, consumption, quiet reacquisition; head playlist does not rotate body VFX | Multiple markers, duplicate owners, suppression expiry, drop/pickup/transfer |
| Summon/control changes | lifecycle media, manifestation material; entity_lifecycle | Birth/terminal departure/control loss consume existing facts; no new summon rules in renderer | Creation, despawn, hostile control loss, unknown source |
| Spatial handlers | backend spatial modules produce facts/sensory/world updates | Inventory outputs rather than clone enter/leave/turn/damage/ignition dispatch into recipes | On-entry/turn damage, save/prone, suppression, moved field |
| Tile state | WorldTileState and WorldUpdate, floor/app composition | Terrain/light/movement costs/elevation/slope/condition labels/residue are separate state facets; names alone cannot establish cause | Cold scene, updated tile, reacquisition, stairs/support |
| Surface/deposit state | deposit bindings, residue histories, surface_reveal_delay | Persistent received contributions and landing reveal; new surface mechanics excluded; no inferential chemistry | Existing deposit, new landing, changed residue value, object/wall-face residue |
| World connectors | WorldConnectorState, movement and world projection | Connector state and boundary geometry stay explicit; movement and presentation cannot infer unseen endpoints | Traversal, boundary change, partial disclosure |
| Props/doors/traps | environment/device banks and transition frames | State transition distinct from interaction attempt; formation/contact/clearance commits; activation can recur without changed state | Open/close, engage, press, activation, projectile trap, destruction/wreck |
| Constructions/walls | construction/spatial layers | Section/owner retirement and partial disclosure; physical state commits follow measured formation/clearance | Partial destruction, suppression, expiry, shell/flat geometry |
| Sensory/world commits | observation dependencies, state schedule | Exact disclosed causes, not child-only assumption; visible-state change distinct from unseen operation | Newly seen gear/HP, hidden-source damage, light/obscuration at formation |
| Idle and retained scene | scene/body_history/lifetime samplers | Initial state has no fabricated application; decorative loops run without action heads | Pause, idle, seek, return to retained head |
| Text and labels | existing feedback plus proposed authored descriptions | Narrative based on public evidence/semantic occurrences, not draw-command scraping; local strings and templates selected once | Unknown names, denied source, mechanical detail, deterministic replay |
| Final composition | registration/depth/area/volume/blend/floor | Preserve world XYZ, ownership, support and boundary cuts; no tile-footprint masking substitute | Four cameras, elevation, partial visibility, blended loops |
| Live/replay/export | encounter_play, player decode/reduction, recording tools | One input/clock contract for both outputs; stale caches and archival versions explicit | Live versus saved public replay, pause/seek, headless transcript |

## World-state facets cannot disappear into a generic VFX record

WorldTransition currently has ten fields: is_open, is_engaged, trap_state, pressed, activation, creation, removal, destruction, hit_flash and spatial_motion. They represent different transitions and are not the complete world-state denominator. Tiles, connectors, senses and object snapshots may change without one of these finite cues.

Direct tile condition names are observational labels; do not use string matching to invent mechanical identity. Spatial effects already carry stronger identities/geometry. Text can say the observed tile is affected by a named condition when that is what is disclosed; it cannot claim who applied it, when, or what damage it caused without matching evidence.

## Repairs prioritized by responsibility

1. **Evidence ownership:** exact event/version/application links for binding and state commits; public non-fact channels and initial state included.
2. **Timing:** explicitly record measured anchors, causal floors and retained clocks. Unify duplicated policy only after comparing current boundaries; retain family samplers.
3. **Authoring:** make actual color treatment authoritative; resolve action aliases and record material/socket policy; classify source constants as asset constraints, content policy or operator math.
4. **Lifecycle:** distinguish all observation/ownership transitions and stable occurrence identity. Existing lifetime maps remain owners.
5. **Verification:** traces must include all bound families and commit provenance. Gallery/check counts cannot prove timing, disclosure or narrative correctness.
6. **Narrative:** describe permitted operation versus observed state through shared semantic records and explicit template selection; no hidden rules or draw-command inference.

These are design repairs to be implemented only under the revised implementation plan. Newly found source debt is not automatically a confirmed player-visible regression.

## What full coverage means here

Full scope and enumerable ownership are mandatory now. Full runtime/pixel acceptance is a later, separate gate. Every current item must end up with a reviewed mapping, explicit state-only treatment, accepted historical limitation, or concrete repair and verification case. No generic fallback, a zero-gap inventory, or a large video count can mark an unverified item accepted.

The two independent review receipts are linked after revision in the implementation plan. They review both the breadth of this inventory and whether the proposed solution respects the actual owners. They do not certify unseen pixels.

Independent second-pass approvals: [anti-slop](rendering-readiness-20261005/antislop-full-review.md) and [ECS](rendering-readiness-20261005/ecs-full-review.md). Both approve source-scope coverage and the rewritten work plan, not completed runtime or pixel verification.
