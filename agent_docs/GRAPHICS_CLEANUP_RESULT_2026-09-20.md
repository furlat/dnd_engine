# Graphics cleanup implementation

Branch: `codex/recovery-design`. Starting checkpoint: `39d1f6c21b` (`pre-cleanup`).
This implements the ownership, registration, portable-contract and coverage units
of [the approved plan](GRAPHICS_CLEANUP_PLAN_2026-09-20.md).

## Observable contract

- Requested behavior: make authoring ownership understandable and expose actual
  presentation support while retaining the approved composed output.
- Boundaries: offline media import/bake, loaded presentation data, saved-event
  replay, and the existing review gallery.
- Inputs: unchanged authored selections and delivered media; the same saved
  player event sequences before and after registration cleanup.
- Expected output: preserved pictures/timing, imports that do not rewrite
  choreography, and honest metadata/observed coverage without native data leaks.

## Delivered

1. **Authoring ownership.** Recovery, ice and CodexFX importers now update media
   and packaging while preserving selected recipes and unrelated bindings.
   Fireball no longer gets sockets through another draft's list position; ice
   spells are no longer reconstructed from Guiding Bolt. These choices live in
   the explicit existing recipes. Ordinary recovery import requires the selected
   color revision, so it cannot silently restore the earlier white-heavy art.
2. **Palette ownership.** Casting layers declare their offline palette input and
   output sheet. The baker writes PNGs only. Target flash treatment, frame,
   duration and child effects stay authored. Chill keeps its distinct full
   casting palette and dark/noisy target treatment. Existing selected images
   were retained, not regenerated into the repository.
3. **Portable data.** Local bundles identify `dnd.spellStudioDrafts` version 1;
   the original NeuroStudio v6 reference remains available. Ice Knife's typed
   child recipe lives in the authored document's `effectDrafts`, not generated
   media bindings. [The contract](../game/data/PRESENTATION_CONTRACT.md) records
   extension semantics, file ownership, coordinate units, the existing resolved
   equipment ledger, and algorithms a later TS adapter must reproduce.
4. **Registration.** One shared calculation owns attachment compensation and
   image-center placement. It preserves legacy Studio canvas registration and
   measured directional pivots, phase scale, actor scale and residual rotation.
   Compiled travel duration, ground/body attachment choices, wall masks and
   reaction/movement rules are unchanged. This is not a new animation framework
   or an anatomical retuning pass.
5. **Coverage.** The initialized view reads actual loaded maps and owner-side
   capability declarations. The explicit developer command additionally lists
   native event categories, retained models and registered spells as distinct
   inventories. The static gallery joins selected support with actual received
   facts and bound lineage evidence, including movement reactions. Parent
   ownership follows stable lineage IDs, not emitting phase-version IDs.
   Missing generic action bindings produce a diagnostic only for eligible,
   disclosed actors. No hidden native capture is read to fill report gaps.
6. **Obsolete ownership paths.** Removed recipe generation from ordinary imports,
   palette passes that retuned behavior, and CodexFX output/source hash bookkeeping.
   Updated active bundle instructions. The optional original NeuroClient source
   converter remains a reference-import tool; gameplay does not run it.

The coverage panel keeps binding selection, observed execution, replay checks
and human visual approval separate. Accepted source strips are limited to the
existing approved potion recipes and aliases, not every future action.

## Verification

- All **15 loaded recipes** retained their previous effective fields; the only
  added layer field is an offline bake input. All **8 rebaked casting sheets**
  matched the shipped selected pixels exactly in a temporary output directory.
- Both real recovery/ice deliveries reimported into a temporary directory with
  unchanged recipe values and packaging metadata. The real external CodexFX
  converter also retained recipes and existing media metadata/bindings.
- **129 focused tests passed** for placement, timing, rig scale, camera direction,
  height, volleys, area projection and drawing. Changed modules typecheck cleanly.
- The final ownership, palette and coverage batch passed **42 tests**. The three
  older graphics test modules passed **24 tests** after correcting the stale
  expectations described below.
- Coverage/condition/body-action checks and review/HTTP integration passed,
  including nine real-event integration clips. New tests also establish that a
  future unsupported source strip does not inherit the accepted potion omission.
- The same **8 saved-input clips** passed before and after, totaling **874
  four-camera frames**, with no presentation gaps. Encoded video files and
  posters were directly byte-equal; no hash or pixel-comparison framework was
  added. The selection covers Ray of Frost, split Eldritch beams, Fireball at an
  east wall, a height-changing Fire Bolt and repeated Magic Missiles.

[Before registration cleanup](http://127.0.0.1:8767/runs/20260920T111831Z-674986/index.html)
· [After cleanup / coverage panel](http://127.0.0.1:8767/runs/20260920T112243Z-9abde2/index.html).
These are preservation captures, not a claim of new human approval.

The broader game-suite run (excluding the separately checked gallery/server
modules) reported **1176 passed, 14 failed, 6 expected failures**. All fourteen
failures were reproduced using `game` code/data from the user's starting
checkpoint, unchanged native code and the same tests. Logs are retained in
`.runtime/graphics-cleanup/game-suite.log` and `checkpoint-failures.log`.

Four failures belonged to obsolete graphics expectations: the old delayed flash,
full vital equality despite the approved palette change, a source-output SHA
audit, and a handwritten catalog list omitting Misty Step. The audit was removed;
the other three assertions now preserve the current approved contracts and pass.
The remaining ten failures concern six blood/trap presentation cases, two trap
spatial-event assumptions, retained-event equality and immutable contact sharing.
Their reproduction establishes that this cleanup did not introduce them; it
neither proves those features correct nor authorizes speculative mechanics edits.

The user rejected leaving those failures unresolved. The subsequent
[failure study](TEST_FAILURE_STUDY_2026-09-20.md) traces all ten beyond their first
failed assertions and records the completed test repairs. It found stale footprint,
accumulation, immediate-parent and object-equality assumptions; it also checked
actual concealment, contact timing and passive replay. The repaired game suite
reports **1,190 passed, 6 existing expected failures** across three completed
batches; the gallery/HTTP lane reports **11 passed**. All ten ordinary failures
are resolved. The expected failures remain explicit terrain-occlusion defects
in jumping/forced movement, not failures newly reclassified by this repair.

## Deliberate remaining scope

The coverage command currently exposes 101 catalog spells without a selected
cast draft and five partial condition recipes. Child/state presentation is
separate from having a cast animation. Condition equipment/appearance tracks
and broader delivery vocabulary still need explicit feature work; no placeholder
recipes were created to make the report green. Choosing those capability gaps
is the remaining feature-selection part of work unit 6, not unfinished importer
or placement migration.

The current on-demand JSON report is saved at
`.runtime/graphics-cleanup/presentation-coverage.json`; regenerate it with
`uv run --no-sync python -m devtools.presentation_coverage` rather than maintaining
another handwritten content inventory.

Independent anti-slop and ECS reviews cover the implementation. Visual pixel
regression tooling stays deferred for ad hoc use; nothing was added to game
startup or the per-frame loop to audit assets or collect coverage.
