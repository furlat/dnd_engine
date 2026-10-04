# Disintegrate native implementation — 2026-10-04

Status: implemented within the assigned packet-3 native boundary. Independent root review is required; this is an implementation receipt, not self-approval. No rendering, artwork, new spell, roster, plane, or general airborne-system work is included.

## Requested behavior and observable boundary

The approved spell implementation plan's packet-3 row and accepted Disintegrate outcome supplement require a real cast to produce DEX-negated 10d6+40 force damage (+3d6 per higher slot), actual admitted lethal dust, destruction of nonmagical possessions with magical UUIDs preserved even inside destroyed containers, native object/force-creation removal and bounded ten-foot object cuts, and rejection of ordinary revival of disintegrated remains.

Input is an ordinary `Disintegrate.apply()` command against an existing creature or visible placed object. Output is authoritative HP/life/item/placement state and the existing typed event stream. Tests never assert artwork or call a second effect executor.

## Native implementation

- `transmutation.Disintegrate` retains normal targeting, costs and save handling. An EFFECT veto stops the creature branch. Flat forty is included in the existing damage bonus/roll, and the one `receive_damage` request retains its real rolls, damage specification and `EffectOrigin`.
- `TakeDamageEvent.zero_hp_disposition` is a request. The existing post-mitigation normal-HP boundary triggers admitted death only when this packet actually reduces normal HP to zero. Temporary HP, resistance, cancellation and the existing normal-HP survival cap remain authoritative. Player death-save actors become dead for this explicit outcome.
- `RemainsDisposition` is a passive leaf enum stored in Health/HealthConfig and retained by birth, life-state and death facts. `DeathEvent` publishes exact destroyed/preserved possession UUIDs only after declaration/execution admission. Inventory membership and existing equipment slots establish possession; nested Inventory contents are traversed deepest first. Existing item retirement and floor-placement admissions run before commitment. Magical children are extracted before a nonmagical container retires. No source-UUID sweep substitutes for membership.
- Generic DEATH EFFECT occurs after commitment and now uses the existing `publish_committed_phase` path, so an observer cannot retrospectively turn committed death/dust into a canceled fact. Declaration/execution still admit or veto death. Existing concentration/death handlers retain their phase and run once. The late-observer regression covers this distinction.
- `Entity.revive` rejects disintegrated remains; ordinary dead bodies still revive. Configured/recorded dust preserves the same restriction.
- Whole object/gear retirement publishes `ItemDestructionEvent` with a dust disposition and exact destroyed UUID. A separately targeted container spills its untargeted contents through admitted floor placement; it does not orphan its storage contents. A creature's consumed possessions instead follow the explicit nonmagical/magical rule above.
- `ObjectSectionVolume` is one passive, grid-aligned ten-foot cube resolved from the existing admitted object contact. Partial `ItemDestructionEvent` retains the volume, previous placement, same surviving item state and resulting placement. `SpatialChangeEvent` retains the same volume and exact removed bands. Only object bands change; terrain and supports remain.
- `BaseItem.removed_local_bands` is the item's retained local geometry. `WorldPlacementSpec`/`WorldObjectPlacement` resolve it into world bands through the existing placement boundary. Relocation, rotation and remove/place do not rebuild the removed bands. The world placement retains its canonical identity/anchor even when its anchor's lower band is gone. Repeated cuts can retire the final remaining volume.
- Existing wall section/zone owners retain cuts in `WallAssemblyPresentationGeometry.removed_sections`. The existing shell/crossing operators consume these apertures. A 20-foot stone panel keeps its original item/zone UUID and untouched blocking. Ice leaves the existing FrigidAir owner only over actually destroyed positions, including a partial dome. Wall of Force removal remains whole-owner and publishes one explicit destruction fact containing every removed section UUID.
- The only new architecture allowance is the exact passive `presentation_geometry -> effect_types` value-composition edge. No late imports, new registry, private scheduler, spell-name dispatcher, or import cycle was added.

## Verification

Environment: source on `/mnt/c/.../dnd_engine`, cached uv environment `/home/tommaso/.cache/dnd-engine/venv`, `uv run --no-sync python -m pytest -q --tb=short --assert=plain`.

- `/tmp/dnd-disintegrate-final.log`: **42 passed** in 31.89s — all 21 new Disintegrate public cases plus 21 architecture/DAG checks.
- `/tmp/dnd-disintegrate-death-final.log`: **133 passed** in 35.67s — Disintegrate, existing lifecycle, summon retirement, summoning lifecycle, and maintained Disintegrate tests after the committed-DEATH-EFFECT change.
- `/tmp/dnd-disintegrate-wall-final.log`: **52 passed** in 13.20s — new Disintegrate cases and the entire existing remaining-wall suite after aperture/FrigidAir correction.
- `/tmp/dnd-disintegrate-type-final.log`: **0 errors, 0 warnings** across all 13 affected native source files and the three affected test files.
- Original `/tmp/dnd-disintegrate-native-regressions.log` is retained: 142 passed and one partial-Ice-dome failure. The failure exposed inherited area-footprint recomputation widening the FrigidAir remnant; explicit retained `section_positions` now bounds that same existing owner and the full wall file rerun passes.
- Earlier failed logs remain: first fixture over-specified `EffectOrigin.source_id` for directly instantiated/unregistered spells (corrected to compare with the actual committed spell origin); a wall fixture attempted an unsupported mutable static-value field (replaced with real initial slot configuration); and the maintained range test expected an obsolete message substring. The range case now asserts range rejection and unchanged sixth-level slot rather than an incidental wording.

Counts above overlap and are not summed. No full-suite, gallery, pixel or frontend acceptance is claimed.

## Review boundary and retained work

The exact APIs to consume later are `DeathEvent.remains_disposition/destroyed_item_uuids/preserved_item_uuids`, `LifeStateChangeEvent.remains_disposition`, and `ItemDestructionEvent.remains_disposition/affected_volume/destroyed_item_uuids/preserved_item_uuids/resulting_placement`. Partial surviving bodies must use the recorded affected volume and remaining placement; cast intent alone never authorizes a dust outcome.

Large-object targeting uses the current native contact and a bounded native cube; no additional target UI or terrain excavation was introduced. Wall sections remain grounded. Presentation/projection binding remains with the parent implementation lane and is outside this native receipt.

The shared files include concurrent approved packet work; the hashes below identify the review snapshot, not an assertion that every existing modification in those files belongs to this lane.

Snapshot aggregate SHA256 (ordered `path + NUL + file_sha256 + newline`): `1324051282f9c0869482d50ca0d26733b2b5c48e2639f7a956641317374c14a2`.

| File | SHA256 |
| --- | --- |
| `dnd/core/life_types.py` | `2bf7ea8776842791d69a9ca9afcacaa57c42f9fae26c43cc4cf74c87f76d5f0d` |
| `dnd/core/effect_types.py` | `003b984729417818bc16c9c9da706676108e5c92eb0b450211d2caec6de8af0b` |
| `dnd/core/events.py` | `16b8d11c7e9e532c4bcc667b86e82bbfc1935f90c4fbfe2cf94bcb22e623369d` |
| `dnd/core/base_block.py` | `eaf7c768b4dc068c55be29d0e885b33060fb424db67dab302fd9784128359c04` |
| `dnd/core/gridmap.py` | `4b44955725053d097c3eba768db88008071da7a42354e209f52268ffbd003d90` |
| `dnd/core/presentation_geometry.py` | `2a19b41f3c1d67b7c810775accb95a659b992e1fa515de3106755b20dd266438` |
| `dnd/core/wall_geometry.py` | `67b5a9b6e7149508b70336bfde72b04eddf3f96c2271add3fc5806ece76e36d2` |
| `dnd/blocks/health.py` | `366736611a498a1b4789739fd0737b683872135cecfb2aecadfc618e182a1f59` |
| `dnd/blocks/base_item.py` | `7f3a47023875fd6fbf82b485ff7612851a955e7e68e0c03eb551f8b203d8c8a7` |
| `dnd/entity.py` | `4186122bea0ce5590b59f69a761f7aa5c3637f17e5f0bc3122634d47c3dcb988` |
| `dnd/types/world_placement.py` | `0dcd032f8a859984c1bd671bc43361b5e0b03042a62048573474cdd5d38c21e4` |
| `dnd/spells/transmutation.py` | `89c222f2df6df9c98d5031194d539cd79d526148a57def6cb9e7208a6e557dd6` |
| `dnd/spells/wall_constructions.py` | `d2410b914dc3344bdf830f1ce33ca31ea6b030ba4a03771ee82cdfda813eac92` |
| `tests/engine/test_disintegrate_outcomes.py` | `1a844d90b450a7c5523e84bfe8b6d98d29d0d5fe452a18e61f08db63257b4a40` |
| `tests/manual/test_129_disintegrate.py` | `f7f43e040e8fab705deada2513112253d2456586032c663fba017a9073c2af3e` |
| `tests/architecture/test_dependency_boundaries.py` | `508c612b5a885bd20587a625197d2a411b67454f373f6aac79aa2c35f75d687e` |
