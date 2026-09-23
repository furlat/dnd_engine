# Destruction implementation — 2026-09-21

Status: **shared lifecycle, current-family migration and first multi-cell prop
unit implemented and validated**. Bulk interiors adoption and
new fixture-media approval remain separate outstanding parts of the plan.
Authority: [reviewed lifecycle plan](DESTRUCTION_LIFECYCLE_PLAN_2026-09-21.md)
and [coverage ledger](DESTRUCTION_COVERAGE_2026-09-21.md).

## Observable contract

- Requested behavior: selected physical objects retain identity when destroyed;
  their authored destroyed state governs behavior, geometry and appearance.
- Boundary: ordinary native actions/damage and recorded subjective events.
- Input: real nonlethal/lethal attacks, uses, consumption and discovery histories.
- Output: one destruction transition with causal consequences, valid persistent
  aftermath, correct terminal consumption and faithful saved replay.

The user clarified that destruction needs its own native event which cascades
physical changes. ItemDestructionEvent is the owning transition; spatial, light,
condition and spill facts are children, not substitutes for it. Gameplay source
and damage context remain native; no renderer instructions enter that event.

## Work and evidence

- Shared ItemIntegrity and authored ItemDestructionProfile added; persistent
  breakage separated from terminal retire().
- Existing physical content now uses this lifecycle. Final focused native content
  run: 317 tests passed in 31.91s; device/concentration/Web/targeting: 64 passed.
  These runs include the dedicated destruction event, not the earlier prototype.
- Seven ground hardware counterparts and their composition with existing
  mechanisms: 13 behavioral histories plus 15 direct-item tests passed in 5.54s.
  Jaw release, held plate peer ownership, released gas persistence, hidden spike
  discovery, hatch retirement and canceled installation are covered.
- Native production Pyright: zero errors and warnings. Full engine regression
  and broader game replay validation are in progress.
- Initial presentation slice: five door/hardware/device cases pass, preserving
  contact identity, supplied finite frame timing, settled/seek pixels and both
  observers. Full owned selection and old saved-input fixtures remain in progress.
- A new oil lineage test initially expected both oil and a made-up Burning Oil
  name after ignition. Reading the existing interaction confirmed that ignition
  replaces oil with Fire Surface; the test now requires that actual behavior.
- No new visual approval or completed full-catalog integration claimed yet.

## September 22 review and broader validation

- Full engine run: 1,346 passed; one failure was the old exact 179-entry catalog
  assertion after the ten new authored identities. The test still constructs
  every public entry; the stale numeric ceiling was removed. The affected
  semantics module then passed in the architecture follow-up run.
- Architecture exploratory run: 81 passed, five failures. One current item
  inventory expectation omitted the ten new IDs; its family coverage is now
  updated. The other four are the previously documented CR-0 frozen-source/count
  checks and retired server `dnd.core.senses` import. No source digest refresh or
  retired server resurrection was made for this feature.
- After initial-state corrections, the event/door/current item-architecture
  selection passes all 255 tests in 28.05s.
- Full owned presentation/replay selection: 126 passed in 89.32s; scoped typing
  is clean. Genuine old saved native door/device archives retain their visual
  behavior through passive compatibility, without re-recording them.
- Independent implementation review found two concrete inconsistencies: initial
  wrecks retained intact flags/positive HP; terminal no-profile destruction
  could project both the explicit new event and its legacy disposal child as
  two breaks. Shared initial-state normalization and explicit-event preference
  at the legacy projection seam fix those cases. Both have actual native tests.
- Five existing representative cases are being captured with new same-ID native
  histories: clear/jammed door, ready/deployed blade and maintained Web device;
  both observers, all four cameras.

## Multi-cell furniture and owned terrain

The finite furniture unit received independent anti-slop and ECS review before
implementation, then cross-review of the actual code. A placement retains one
canonical anchor and resolved covered supports. Existing Tile bands, spatial
events, light deltas and sensory subscriptions serve every covered cell.
Ordinary attack, pickup and manual Use share legal contact with the actual
footprint, including walls and diagonal obstructions. Remote linked controls
retain their existing path. Rejected placement/rotation/relocation leaves the
previous world intact. Supporting Tiles cannot be replaced underneath an item,
including through the rectangle authoring helper.

Two authored profiles exercise the contract: a two-cell wooden bed and one-cell
wooden table. Both use ordinary WorldItem, Health and the shared destruction
profile. Broken bed terrain belongs to one internal condition and its linked
ordinary AreaCondition; committed placement updates its covered cells. Removal
releases only its own cost modifiers, preserving overlapping oil or other areas.
This is not a second map or an object per debris fragment.

Evidence to date:

- 94 focused multi-cell/terrain/world-authoring tests pass, including actual
  far-end attacks, tail-only visibility, light updates and atomic rejection.
- 36 furniture/ground-hardware/direct-builder cases pass, including real walking
  costs, overlapping oil, repeated removal and same-region rotation/relocation.
- Three new saved-input tests pass after engine reset: both observers retain
  same-ID destruction, an observer seeing only the nonanchor cell notices true
  removal, and late discovery carries settled state without a past break.

Native placement and public game replay carry the full footprint. The separate
AI observation schema still exposes one actual observed contact rather than
the complete footprint. It has not been silently treated as full AI support.

Cold room construction now has an explicit deferred-behavior path for these
profiles. It publishes the existing WorldInitialized fact first, then the same
ordinary condition installer used by live creation settles the committed wreck
footprint. No placement or historical destruction is invented. Two new cold
cases, live debris cases and the complete world-initialization module pass
**38 tests in 5.66s**. Both intact and already-destroyed bodies replay correctly
after engine reset; removal returns the affected cells to their remaining
terrain costs. Independent ECS review approved the actual implementation.

## Supplied prop media and real review histories

Eight native IDs now use the existing finite environment-bank renderer: the
storage chest alias, three chest styles, crate, oil barrel, bed and table.
Ten accepted source selections supply twenty intact/break banks (5.1 MiB).
Chest closed/open entries use their exact reconstructed source pairs; the old
static chest selection was removed so one binding owns the body. Existing 146
environment bank rows and door/trap mappings were retained unchanged.

State selection, finite collapse, settled frame, contact flash and reverse seek
reuse the current renderer. Native descriptions, HP, blocking and debris costs
remain in native profiles. The offline importer only packages explicitly
selected media, pivots and timing; it does not author gameplay or hash sources.

- [Current door/device/hardware gallery](http://127.0.0.1:8767/runs/20260921T221449Z-5770b8/index.html):
  10/10 clips pass.
- [Props and actual chest contents](http://127.0.0.1:8767/runs/20260921T222920Z-12c92c/index.html):
  20/20 clips pass. Ten native experiments each have two subjective histories
  and four camera views. Inputs are saved for passive replay.
- Boundary-rendering and final prop cases: 101 passed in 34.46s. Tests retain
  actual frame-zero continuity, destruction timing, settled/late state and seek.
- Root inspected bed/chest intact and settled frames in all four views.

Chests spill a real healing potion through their existing inventory lifecycle.
The public sequence contains its floor placement. **There is no installed floor
potion sprite**, so the potion is not visibly drawn in these clips; no inventory
icon was substituted for world art. Oil's native spill likewise does not imply
that a floor-effect media binding has been authored.

The new prop path exposed an existing very-bright-light crash: multipliers above
one generated invalid pygame fill colors. The shared bank treatment now clamps
RGB multiplication while preserving alpha, with ordinary-light output unchanged.
The real boundary-rendering case and color/alpha checks cover that repair.

## Remaining adoption

This completes the finite destruction/multi-cell proving unit, not all interiors.
The wider 117-subject source set still needs its explicit native profiles and
bindings. The bed/table and crate/barrel source selections cover only their
named subjects. Mounted/tabletop aftermath, support-dependent content, windows
and house assembly retain their separate plan boundaries. No multi-Z, salvage,
repair or general structural-collapse system was introduced.
The separate `environment.arcane_device` healing fixture still needs its own
explicit durability/appearance disposition; the two migrated spell-device
bodies do not establish one for it by association.

## Asset handoff

The user assigned task 01a0b501-8a27-7413-ba24-4a36e5b140d2 the asset work.
It delivered `output/environment-sprites/fixture-destruction/HANDOFF.md` in its
worktree, with 48 candidate banks / 192 color-and-depth sheets. Forty-six banks
cover lever/torch/ground hardware; two propose boulder/barricade appearances.
These are **user-unapproved candidates**, not installed media. Existing approved
doors, blade/crusher, cannons, chest and decor remain unchanged.

The user rejected the first active spike collapse's small triangular fragments.
The artist replaced only the four active plain/coated/bloodied spike banks with
solid long broken shafts; the former versions are superseded. Updated handoff,
index and archive carry that correction. None of those candidate versions were
imported here. READY and ACTIVE entry banks must be selected from the recorded
physical pre-destruction state, already retained by ItemDestructionEvent.

Candidate review: [fixture destruction, both entry states](http://127.0.0.1:8778/fixture-destruction/?asset=spikes-plain&entry=both&review=solid-shafts-v2).

## Final validation record

Source: `/mnt/c/users/tommaso/documents/dev/dnd_engine`, branch
`codex/recovery-design`. Prepared uv environment:
`/home/tommaso/.cache/dnd-engine/venv`.

- `python -m pytest -q tests/engine tests/architecture/test_content_recovery_cri_direct_items.py --tb=short`:
  **1,377 passed in 144.50s**. This supersedes the earlier engine run with its
  stale catalog-count failure. It includes the completed multi-cell support
  replacement fix, before the final cold-initialization extension.
- `pyright dnd game devtools/animation_review devtools/import_environment_props.py`:
  **0 errors, 0 warnings**. Checker enumeration through `/mnt/c` emitted a slow
  file-enumeration notice; no game runtime or checker policy was changed.
- Affected boundary-test annotations were corrected to their actual yield and
  return types; its 86 tests pass and all eleven prop/media modules typecheck.
- `git diff --check` across affected source/test/document paths is clean.
- Cold furniture extension: **38 passed in 5.66s**, scoped typing clean and
  independent review approved. This closes the cold setup limitation recorded
  during the first multi-cell review.
- Full `python -m pytest -q tests/game --tb=short`: **1,954 passed in 974.47s**
  (16m14s). This is the full presentation/replay/clip-extractor suite, including
  rendering and encoding; it is not an engine-turn performance measurement.

The exploratory all-architecture run's four previously documented historical
CR-0/retired-server failures are not represented as passing by the maintained
registry result. No source-hash baseline was regenerated.
