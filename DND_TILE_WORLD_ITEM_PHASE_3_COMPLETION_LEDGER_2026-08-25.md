# Phase 3 Slice 3.5 completion ledger

Status: `PHASE_3_ACCEPTED`

This ledger records the accepted Phase 3 result. No production or test file was
changed in Slice 3.5 except the two authorized constant deletions below. The
candidate described by the unchanged implementation manifest was independently
approved for correctness and anti-slop, and the final ledger bytes are bound to
the combined Phase 3 handoff / Phase 4 implementation-plan review described at
the end of this document.

## Governing hashes

| Authority | SHA-256 |
|---|---|
| Completion plan | `fd0600201666d86ca8a9bab669fd736f0a50e14729f64a8415c0339abd6faedc` |
| Completion plan substantive revision | `22e45a4b0a27dfa8952d534d08e9beef3922b28594b4bc6ab9314be9d652000b` |
| Slice 3.4 architecture amendment | `56b374fc9c0579d535220c98147aa67031dd415ea37c911669348bc89f3c9454` |
| Slice 3.4 amendment substantive revision | `8fefd782f976ba890858fd3acac30e82f597aa57e056a439776a0a690d5ad2cc` |
| Accepted Slice 3.3 manifest | `2e1ed59f9615bc4c97863cb46cbfa9328d35d145f080f48b90b44656c852a296` |
| Slice 3.3 master migration plan | `50411e5575e6336ca0301acf032797cdf1d5ea885df5ccd37d6619f593e7a193` |
| Ordered-side Phase 3 guidance | `ed3b4afbe88ab4278c27429b3c9b1727a8ccdc144c3019ab5dcef00ca1715cd0` |
| Active-runtime scope amendment | `f10e2fbbcb6ba8732d078f0c4f2f5276716eb51e32c083068f3cae93c9ba52d6` |
| Active-runtime ledger | `63e25aac3f0136daa8d43b860c328fe8b7b9f26529f65792b123dc77293c059a` |
| Slice 3.3 repair plan | `5b8c50f6cbbd8100380fb5fc091e9b4389406d024256063d03632af6445b937e` |
| Slice 3.3 implementation ledger | `cefc0700bdadcce62d419a20f5c8261c10e9c4ae3c10d8e7fef9badcffbe6cc1` |

## Authorized Slice 3.5 edit

Applied with `apply_patch`:

- `dnd/maps/arena_layout.py`: deleted unused `DOOR_DIRECTIONS` and
  `WALL_DIRECTIONS`; retained the standard directional barrier constructor,
  current ordered barrier builders, sensory hint/collision names, and bounded
  propagation behavior.

No excluded file, governing plan, production core, or test was edited in this
slice. The accepted Slice 3.4 candidate changes remain the previously reviewed
15-file envelope, including the one-line architecture amendment.

## Accepted Slice 3.3 hash comparison

The 44 accepted Slice 3.3 members were checked from their current raw bytes
before finalization. There were zero mismatches outside the authorized
Slice 3.4/3.5 envelope. The 11 intended divergences were:

| Member | Accepted hash | Final hash | Reason |
|---|---|---|---|
| `dnd/content/items/environment_item_builders.py` | `75203dd1d9007a19c32d8473f389cdad97adad2962f76690c5f63881a65741c4` | `a099dba1b891f25e2cc2c5914ca7db95f3345bfadb3d1922e63fcd2d53cd7619` | Slice 3.4 direct cliff/WallTorch builders |
| `dnd/content/items/item_catalog.py` | `bdfe041535dbe03e89790d4070aa5047508f62bee422b950b7f908c9058ebba2` | `bce7cd163d2fa8ecdea77fe1bdd91ed2202835f784ced6a42f2ee4b37c621f04` | Slice 3.4 cliff identity |
| `dnd/content/scenarios/battlefield_builders.py` | `b3e74a5e045993e77dee36e2797d63ab4965cbabaa0154f35c13f6e838743414` | `aa4d7a28259b73e0aa2e333bd8bfb0f6ac50ffb57253c8b058cd9802e85be6e7` | Slice 3.4 authored rows |
| `dnd/content/scenarios/battlefield_definitions.py` | `1076e91cab7b973bc6ded57393e0b074b3e2216f453fc99767d546d504112303` | `9da232343bcb626c24a6e960706017e91057fc8ffc44262cbb5e6843899dc710` | Slice 3.4 placement schema |
| `dnd/items/environment.py` | `ba97c570ca881b78337331debff0293bb91e16ee2ca528449fd690d7286b38b2` | `64a7a5a106539f2dde73df9e2de7f07f4fe7c997fad77871b656b873dc9bc398` | Slice 3.4 concrete cliff |
| `dnd/maps/arena_layout.py` | `99bf92c92c5bdb8402a69f993f898e80b42c3adbf0955758d0cd0b18947bccd1` | `778a01701a047fa0886c9ce181de39783ce2f75083890df5ffaf661260671706` | Slice 3.4 mount facts and Slice 3.5 dead-constant deletion |
| `tests/architecture/test_content_ledger_boundary.py` | `dd574bbd87c5ec45606ae2d4c92811bed709f7592a138307d714b3a4c34dc5be` | `16b45ddb4f7517fbafb8bd9f87cbc74cd954c347b276ee2ae75655d0308f6bdf` | Approved count 145 to 146 amendment |
| `tests/engine/test_elevation_proving_battlefield.py` | `b4b485a302651655288c09d99d80e2e9a47baec0849b16a3c6b8a4426f79a167` | `333f3924d843c3ff0562dd98dafd5d3135a26049a956f7f824a7a640ca4fdd5b` | Slice 3.4 proving cliff |
| `tests/engine/test_items_inventory_equipment.py` | `d127ac258aa2e6c077644ce60313b9ebceff43b5855a1fda20146d12d2162dde` | `f4dfcd45a0b83fc9ee2e8729a0b56925bd9842687e1ab00ff86af5c0a8af1a2b` | Slice 3.4 WallTorch lifecycle proof |
| `tests/engine/test_tile_surface_contract.py` | `568d92bcb8e254f794dc669102a3cf9f7f3231a86748d4fb3f6b4a8a1e5bec4d` | `552193064ee7ba4f5d929639f9f881b058870d86d4048631e0bdf29e36dbe335` | Slice 3.4 boundary-height/rebuild proof |
| `tests/manual/test_72_battlefield_deployment_catalog.py` | `8f713e99e02fe274f18faecb3a0fe846fd978ebe1947d977337e0559f9b86138` | `51f19e39bb4aec848d7ce9e6083130c862dd9a3dd01265fd304f777ddb439c67` | Slice 3.4 public boundary query proof |

The other 33 accepted members matched exactly.

## Validation commands and results

All commands used `./.venv/bin/pytest` and `-p no:cacheprovider` where
applicable.

1. `./.venv/bin/python -m compileall -q` over the 15 approved Slice 3.4/3.5
   active Python files: exit `0`.
2. Scoped `git diff --check` over the deterministic 59-member active union:
   exit `0` (Git emitted only its existing LF/CRLF conversion warnings).
3. Exact new/extended Slice 3.4 selector matrix: `10 passed in 8.69s`.
4. Placement/ordered-edge/elevation/movement/path/forced-movement lane over
   `test_grid_pathfinding.py`, `test_world_edge_identity_and_elevation.py`,
   `test_elevation_proving_battlefield.py`,
   `test_elevation_performance_contract.py`, `test_move_settlement.py`,
   `test_elevated_jump_transaction.py`, and
   `test_action_cost_and_position_commit.py`: `135 passed in 31.76s`.
5. FOV/light/senses/propagation/AoE/condition lane over
   `test_senses_light_stealth.py`, `test_spatial_effects.py`,
   `test_direct_spatial_effect_materialization.py`, and
   `test_condition_lifecycle.py`: `119 passed in 29.39s`.
6. Item/action/content/bootstrap/event/replay/WallTorch/spatial lane over
   `test_items_inventory_equipment.py`, `test_action_discovery.py`,
   `test_direct_scenario_deployment.py`, `test_event_lifecycle.py`,
   `test_event_wire_visibility_contract.py`, `test_objective_state.py`,
   `test_runtime_reset.py`, `test_37_authored_encounter_mechanics.py`, and
   `test_72_battlefield_deployment_catalog.py`: `170 passed in 72.19s`.
7. Frozen 14-module capability command from Section 7.7: `321 passed in
   63.72s`.
8. Complete spell family command `tests/engine/test_spell_families.py`:
   `62 passed in 28.64s`.
9. Complete architecture command `tests/architecture`: `41 passed in
   20.58s`.
10. Complete active in-process command from Section 7.7: `614 passed in
    176.07s`.
11. Exact active collect-only command: exit `0`, `614 tests collected in
    9.58s`; sorted unique normalized node-set SHA-256:
    `774c745d442d5db6b8bfb2878309b4eae118e08d264ae4a12370f2a21db05641`.
12. Structured locality/timing command over the existing diagnostics,
    bounded-observer, fixed-radius, directional-preflight, light-radius,
    channel-cache, composition, action-discovery, and path-edge selectors:
    `17 passed in 26.74s`.

No test failure or repair occurred in this Slice 3.5 run. A preliminary shell
probe found that the bare `python` command is unavailable; all validation was
rerun with the repository's `./.venv/bin/python` and completed successfully.

## Section 14 zero-reference audit

The audit searched the exact 59-path active union. It explicitly excluded
deprecated/server/editor/SDK/generated paths, inactive
`dnd/items/environment_content.py`, and excluded legacy tests. Results:

| Gate | Active matches | Classification |
|---|---:|---|
| Tile border/intrinsic/derived authorities and `allows_direction(s)` | 6 | Only historical wording/output labels in `tests/manual/test_08_world_model_and_movement.py`; no gameplay API reference |
| BaseItem directional blockers, neutral BaseBlock hooks, object-border maps/recompute/setters | 0 | Clear |
| Authored `blocked_directions` and duplicate topology evaluators | 0 | Clear |
| `DoorObject` and object-owned `is_perceivable_by` | 0 | Clear |
| `WorldTileState` directional-open tuples | 0 | `WorldTileState` itself remains, but has no directional-open tuple |
| Authoritative `SpatialChangeEvent.directional_*` maps | 0 | Clear; directional sensory hints remain separate and approved |
| No-argument global barrier discovery/cache | 0 | `get_barrier_positions` remains only as an explicit-footprint bounded query |

Retained approved names were classified, not edited: directional positions 10,
directional neighbors 10, directional channels changed 6, directional
collision blocked 34, and `place_standard_directional_barrier` 2. The only
remaining `WALL_DIRECTIONS` references are three imports/assertions in excluded
`tests/manual/test_directional_environment_legacy_contract.py`; that excluded
legacy test was not edited. There are no remaining active `DOOR_DIRECTIONS` or
`WALL_DIRECTIONS` references.

## Final candidate artifact

The deterministic membership is the sorted unique union of 41 retained Slice
3.1 paths, 44 accepted Slice 3.3 paths, and approved Slice 3.4/3.5 additions:
59 members total, 33 production and 26 tests. The manifest excludes both
final artifacts and all governance/excluded/unrelated files.

- Manifest: `DND_TILE_WORLD_ITEM_PHASE_3_IMPLEMENTATION_MANIFEST_2026-08-25.json`
- Manifest SHA-256: `08c756ee62b953dd7326de9d5d06345eb3b948743b5d328559da8df6b40027f0`
- Manifest verification: valid JSON, sorted/deduplicated, 59 members, zero
  current-byte hash mismatches.
- Ledger: `DND_TILE_WORLD_ITEM_PHASE_3_COMPLETION_LEDGER_2026-08-25.md`

The implementation manifest remains byte-for-byte unchanged as the reviewed
candidate membership record. This ledger is the acceptance record for that
candidate.

## Independent acceptance record

The pre-acceptance candidate was bound to:

- implementation manifest SHA-256
  `08c756ee62b953dd7326de9d5d06345eb3b948743b5d328559da8df6b40027f0`;
- pre-acceptance completion-ledger SHA-256
  `93485e9e77c6d88d1f7d048ea3fcb17ca3e7e2be0ec0ee11cc0a87b13ca2ad08`;
  and
- completion-plan SHA-256
  `fd0600201666d86ca8a9bab669fd736f0a50e14729f64a8415c0339abd6faedc`.

The independent correctness review reverified every manifest member, reran the
complete 614-node active in-process lane successfully, and approved the exact
candidate with no remaining correctness finding. The independent anti-slop
review reverified all 59 member hashes, the active scope, deletion gates,
public-test posture, and the exact focused proof; it approved the same exact
candidate with no MUST-FIX finding.

No code, test, manifest, or plan byte changed between those reviews and this
acceptance edit. The only change is this ledger's status and review record. Two
independent reviewers must validate these final ledger bytes together with the
exact Phase 4 Entity-occupancy implementation plan before implementation of
Phase 4 begins. Their external exact-byte verdicts complete this non-circular
handoff; they are not written into this file after approval.
