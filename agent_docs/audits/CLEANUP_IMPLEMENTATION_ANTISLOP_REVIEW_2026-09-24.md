# Cleanup implementation plan — anti-slop and correctness review

Reviewed document: `agent_docs/RENDERING_ASSET_CLEANUP_IMPLEMENTATION_PLAN_2026-09-24.md`.
Reviewer: independent `cleanup_antislop` agent. Date: 24 September 2026.
Initial scope: plan review only. The implementation follow-up below records the
later authorized production work and its separately bounded review.

## Round 1

**Verdict: approve the structure; two bounded acceptance clarifications required before final approval.**

The plan preserves the existing architecture instead of treating the audit as a
reason to rebuild it. The rendering units have concrete owners, dependencies and
observable gates. Archive preservation, forward asset separation and production
packing are separated from deferred Git history work. Checkpoints are internal
validation boundaries, not instructions to stop repeatedly for user permission.

I independently read the current public/native codec, projection, passive capture,
interruption binding, importer and reporting code, their relevant tests, the
source contract, the testing guide and both consolidated audits. I inspected all
three retained native gzip fixtures using only Python's standard library. Every
Action/Spell row involved in their missing additive fields is noncanceled:

| Fixture | Action rows | Spell rows | Canceled Action/Spell rows |
| --- | ---: | ---: | ---: |
| Legacy device destruction | 4 | 6 | 0 |
| Legacy door destruction | 4 | 0 | 0 |
| Legacy Web destruction | 4 | 4 | 0 |

This supports the plan's bounded completion-only archive repair. It does not
justify inventing old cancellation/payment semantics.

### Required clarification 1 — state the legacy re-encoding acceptance explicitly

U1b correctly says admission defaults are not historical facts and warns that
`model_fields_set` alone is not provenance. Its gate should also explicitly say
that a supported old decode → native re-encode → decode must not promote an
absent new receipt/targeting field into a supposedly recorded false/default
fact. Otherwise a repair can satisfy the public completion assertions while
`encode_event` silently materializes defaults into the next native archive.

Current evidence: `game/event_record.py:encode_event` dumps all model defaults;
`decode_event` uses current native models. `player_projection.py` emits an
`ActionCancellation` only for canceled action events. The relevant current
fixtures never need that cancellation fact, but archive re-encoding remains a
real existing boundary. `test_presentation_boundary.py` already asserts live
source/capture equality and passive decode/re-encode equality.

Add a tiny focused compatibility case beside the existing recording tests:
actual legacy completion input, explicit modern false/true receipts retained,
original missing receipt remains unasserted on re-encoding, and passive registry
behavior is unchanged. Leave the exact omission-preservation choice to the
bounded codec probe already in U1b; do not mandate a new metadata model, widen
native rules, or invent general legacy cancellation support.

### Required clarification 2 — retain the known missing modular-art boundary

The completed inventory identifies a real existing coverage gap: 216 of 281
mechanically supported equipment selections share missing modular categories;
81 categories/1,134 requested bindings are absent, including the Barbarian's
Head17. A1/A2's clean-install and final reachability gates must distinguish:

- an accidentally omitted asset that was present and retained by this release;
- a supported content request whose art was already absent from the baseline.

The first is a packaging defect and must fail the release gate. The second stays
an explicit known content limitation outside this cleanup, with the preserved
inventory reference. Do not claim all declared content renders, quietly substitute
another appearance, or turn implementation into an unrequested asset-generation
project. Representative installation smoke and exact selected-frame reachability
remain appropriate proofs.

### Small execution detail

Section 15 provides the uv prefix but leaves the broad lane/gallery exclusions
and Pyright invocation implicit. Add the literal existing commands (including the
two excluded gallery modules and `gallery` / `paused_lifecycle_clip` expression)
so the final comparison cannot accidentally select a different test population.
Keep exclusions explicit slow-lane separation, not permanent failure waivers.

## Source-grounded preservation checks

- R1 is correctly separated from old archives: the union-wide public validator
  damages ordinary JSON admission. Fix it without relaxing strict placement or
  forcing every fact through broad tuple coercion.
- R2 validation must protect selected storage as well as recipes. The existing
  import test explicitly expects the historical Fireball layer form; the plan
  correctly refuses to preserve that obsolete owner as a regression oracle.
- U3 retains passive draw values and avoids making diagnostics a semantic
  transport. The material-order grouping must remain intact during migration.
- U4 names all three existing implicit composition selectors and preserves the
  different XY, XYZ and fixture-depth spaces. It keeps effective scale distinct
  from authored `.5` and camera zoom.
- U5 puts finite media joins before recovery, matching the existing direct-cast
  ordering, while preserving nonblocking contact emissions and causal anchors.
- U6 is correctly an intentional visual correction with its own geometric oracle;
  it must not be hidden inside the otherwise pixel-preserving registration move.
- U7 repairs actual bound-portal reporting in the existing inventory traversal.
  It does not equate received, selected, bound or visually approved.
- A2/A3 use the exact inventory and preserve the real conditional/preload reads.
  Staging into an empty installation is essential so leftover source files do
  not conceal missing packaged dependencies.
- Optional resizing/compression, unintegrated spells and hypothetical 3D
  transparency capability remain outside primary completion.

## Round 2 — final revalidation

**Verdict: approved. No remaining blocking anti-slop/correctness findings.**

I reread the entire revised 781-line plan, including the changes from the other
reviews, rather than reviewing only a summary of the edits.

- U1b now explicitly protects native decode → re-encode → decode absence
  semantics, explicit modern true/false values and live/captured equality. It
  leaves the concrete solution to a bounded codec probe and does not introduce
  hypothetical legacy cancellation infrastructure.
- A1 distinguishes omitted retained payloads from the baseline's missing modular
  art. It preserves the known limitation without substituting appearances,
  claiming complete content coverage or adding asset generation to the scope.
- Section 15 contains the literal selected-game and whole-game Pyright commands,
  the exact gallery exclusions, baseline population and separate slow-lane result.
- The additional active-world-catalog typing and diagnostic-evidence-off gate
  strengthen the existing boundary without creating a universal model. Schema
  meaning/version changes now happen together in U4.
- Raw XY pages retain matching color/coordinate rectangles, and public normalized
  bindings remain with the code release; private installation cannot overwrite
  those authored documents.
- Exact output preservation remains distinct from the intended wall-cap fix.
  Optional compression/derivatives and historical Git cleanup do not become new
  prerequisites, and internal checkpoints do not require repeated user prompting.

Approval applies to this implementation plan. It does not assert that any
proposed production change, package, timing result, test or pixel comparison has
already passed. The implementation still must satisfy the named gates, including
actual archive bytes, preserved recorded outcomes, targeted regressions and the
integrated closure run. No production code, artwork or broad test suite was
changed/run during this review.

## Implementation follow-up

Independent review scope: root-owned U2 selected-media import boundaries, U3
diagnostic independence, U4/U5 composition and timing changes, and A1 private
installation. I read the current producers/consumers and focused tests. This is
not independent approval of my own U1 codec, U6 wall-cap or U7 fixture work;
another reviewer owns those checks. The integrated suite and fresh production
installation remain the root agent's closure work.

Two concrete defects were found and corrected with the root agent's approval:

1. **Packed import selection did not understand archive addresses.**
   `devtools/media_delivery.py` still indexed every surface component's `pattern`.
   Current packed Color Spray therefore raised `KeyError` on actual reimport.
   The existing metadata traversal now also reads `archive.file`, for both a
   single packet and per-facing components. Four small tests cover retaining a
   selected packed delivery versus refreshing the importer's own source. The
   existing actual control reimport reproduced the failure before the repair.
   Control and spell import modules afterward: **27 passed in 20.70 seconds**.
   No new owner registry, media scan or source checksum was introduced.

2. **XYZ/ownership resize indices differed from the color scaler.**
   Color already used Pygame-ce/SDL's fixed-point center sampler. XYZ/ownership
   used floor-based sampling, so e.g. 3→1 selected color column 1 but metadata
   column 0. `registered_media.py` now applies the same 16-bit integer-center
   indices to both metadata arrays. Colors, source assets, pivots and output
   dimensions are unchanged. A one-off comparison of all source widths 1..100
   and output widths 1..120 matched actual Pygame in all **12,000 pairs**.
   Portable JSON cases include odd dimensions, up/down scaling and tie cases.
   The contract records this exact rule for a later TS adapter.

The second repair is an explicit correctness change, separate from pixel-equal
packing. Forty native Fireball scene samples (wall/open door × four cameras ×
five zooms) retained identical raw color packets and destinations. At 1× the
composites are identical; resized composites change 70–957 pixels per sample as
their corrected ownership/depth affects clipping and ordering. Both four-camera
0.5× old/new/difference sheets were inspected: boundaries and apertures remain
intact, with small changes along sampled edges rather than a color/size retune.
Evidence is retained at:

- `.runtime/cleanup-implementation-20260924/u7-paired-sampling.txt`
- `.runtime/cleanup-implementation-20260924/u7-paired-sampling/wall-east.png`
- `.runtime/cleanup-implementation-20260924/u7-paired-sampling/open-door.png`

The focused presentation-contract, XYZ, registration and 104-case scene
occlusion lane passed **165 tests in 34.27 seconds**. Scoped Pyright for
`game/registered_media.py` and `devtools/media_delivery.py` reports zero errors.

No additional blocking defect was identified in the reviewed implementation:

- Selected media remains separate from recipes and palette authoring; the
  reimport guards consume existing loaded addresses rather than inventing
  runtime ownership or inferring behavior from assets.
- Typed draw roles, actor/object ownership, cells and device poses replace
  semantic reads from diagnostic tuple positions. Remaining tuple slicing only
  annotates diagnostics. Body clipping, fixture ordering and device occupancy
  use their named fields; source component order remains separate.
- Composition choice is explicit at local intake. Original formats normalize
  there; active sampling does not pick volume mode from an optional sidecar.
  Physical size and zoom are separated by source calibration, while timing
  joins retain causal contact and existing nonblocking emissions.
- The private-art command is an explicit offline tool. Normal install trusts a
  previous matching receipt and file size, preflights pending files only, and
  leaves unlisted local work intact. Deep byte checks remain explicit export or
  `check --hashes` work. Its allowed paths cannot overwrite public authoring or
  code. CLI tests cover missing companions, same-size release updates, receipt
  reuse, repair, pointers, symlinks and public-path rejection.

Remaining limits are stated rather than converted into new cleanup work: the
current painter is not a per-pixel fragment renderer for mutually intersecting
translucent volumes; preexisting missing modular categories remain content
gaps; a local installer/release check does not verify remote publication or old
Git history. No broad test suite or historical repository rewrite was performed
by this reviewer.

### Saved-input closure: completed action receipt coverage

The final gallery exposed a gap in U1's enumerated completion families. Inspection
of the original September 11 native recordings showed that the failing Attack
and Jump rows were all **completion, canceled=false**, including both lethal
opportunity reactions. These were not undocumented canceled actions and did not
need payment reconstruction or replacement captures.

The receipt omission rule now derives from the exact existing
`action_economy_spent` field in the finite registered event schemas. This covers
Action, Attack, Spell, Movement, Jump, Shove and CounterspellReaction uniformly;
equipment events are ordinary Events and do not carry that field. Spell-only
additive declaration fields remain separately named. Admission still requires
explicit noncanceled completion, and re-encoding preserves missing evidence.
No cost, status message or presumed engine phase is converted into payment.

`tests/game/fixtures/legacy-completed-actions.json` preserves four actual recorded
rows from the affected inputs. Focused tests cover their causal identity and
roundtrip omission, plus live defaults, explicit false/true and canceled rejection
across all seven action schemas: **35 passed in 4.09 seconds**. Scoped codec
Pyright is clean. Read-only decode → encode → decode → public projection succeeds
on all three original full histories without registration:

- equipment melee/ranged: six complete lineages, 16 public nodes;
- walk killed: one complete lineage, 16 public nodes;
- jump killed: one complete lineage, 16 public nodes.

The root agent is rerendering those same saved inputs. Originals were not edited
or regenerated. This note reports implementation validation, not independent
approval of my U1 change.

### Shield contact validation boundary

The integrated run exposed three Shield interception failures (melee, ranged,
Magic Missile). A focused run in the Linux production installation reproduced
them: the new stationary sampler validator required a ground attachment, but
the existing condition-reaction producer supplies a resolved body-height contact.
The cue already contains immutable world position, elevation and absolute scale;
the sampler has never needed to resolve its attachment again.

With root approval, only that redundant ground-only restriction was removed.
The authored `target_body` track, body lift, contact direction, position, scale
and clock were retained. Actual unsupported transform/XYZ restrictions remain.
Other producers were inspected: relocation cues resolve disclosed departure or
arrival supports; spatial responses resolve received centers/contact tiles; motion
emissions resolve their historical movement contact. No producer needed changing.

`tests/game/test_condition_interception.py`: **3 passed in 4.08 seconds** against
the Linux production installation. The existing tests cover both subjective
views, actual interception lineage, body gesture preceding contact, maintained
responses without duplicate gestures, and unchanged nonblocking contact tails.
Scoped `game/stationary_media.py` typing is clean. This correction changes which
valid cues are admitted, not their sampled output.

### Offline palette originals versus production outputs

Production-only testing reproduced two palette rebake failures and seven selected
palette checks that still tried to load archive-only `Magic2/Attack5.png`. The
renderer uses the selected colored sheets, all of which were present. Restoring
the uncolored original to production would confuse authoring inputs with runtime
dependencies.

With root approval, `bake_spell_palettes` now accepts an explicit `source_root`
(`--source-root`) using the original `game/assets/...` paths. Defaults retain
existing authoring-install behavior. `--output-root` exposes its existing
separate-output option for review without replacing selected sheets. No recipe
or resource binding is rewritten. `PRIVATE_ART.md` documents this boundary.

The default tests use small isolated archive sources with black/white luminance
extremes and known full, partial and zero alpha. Exact authored palette endpoint
colors and alpha are asserted independently of the recoloring implementation;
geometry, source bytes, selected output bytes and recipe bytes stay unchanged.
Production tests continue checking selected spell colors, nonempty transparent
coverage and complete body-bank geometry. Source-alpha preservation is tested
at the baker boundary rather than requiring raw authoring inputs in production.

Both palette/import modules passed **38 tests in 12.21 seconds** on the Linux
production-only installation. A separate actual-source check rebaked all three
current bundles into a review directory: CodexFX has no active palette outputs,
recovery has seven and ice has three. All **ten** generated 1920×1024 sheets are
bitwise RGBA-identical to selected production; their alpha arrays also equal the
preserved original sources. Evidence:
`.runtime/cleanup-implementation-20260924/palette-rebake/comparison.txt`.
No original media was added to production and no selected asset was changed.

## Final bounded acceptance reread

**No new runtime or authoring-ownership blocker found.** I reread the plan's
required ownership/portability gates and the current status, asset instructions,
selected catalog schemas and generated environment mappings. Runtime code and
media were not edited for this reread; no further test suite was started.
Root is still closing the integrated test ledger, installation and final release
record. This review does not turn those pending gates into completed evidence.

The large `environment_art.json` diff is generated addressing, not a new behavior
system. Measurements of the actual current document:

| Measure | Value |
| --- | ---: |
| Previous / current bank count | 208 / 208 |
| Previous bytes / lines | 281,975 / 13,465 |
| Current bytes / lines | 5,482,308 / 218,974 |
| Color frame rectangles | 13,904 |
| Depth frame rectangles | 8,568 |
| Static frame rectangles | 48 |
| Distinct page paths | 638 |
| Distinct `(path, rectangle)` addresses | 22,520 |

Every frame-address record is distinct; no duplicated banks or duplicated region
addresses explain the growth. The same page path naturally repeats for its
individual cells: repeated path values total 1,583,364 bytes, versus 44,328 bytes
for unique path strings. Current `EnvironmentBankSource` supports a single regular
sheet or explicit `ImageRegionSource` sequences. It has no compact page-run form
that can substitute for these multi-page mappings without extending the adapter.

Whitespace alone could reduce the same parsed JSON to 39,198 lines / 3,190,164
bytes by placing each region on one line, or 2,563,912 bytes if fully minified.
That is optional presentation of generated data, not a correctness repair. Root
chose to retain the generated format. No serializer or new page-run representation
is needed to accept the present implementation.

The status document accurately separates implemented units from integrated
closure, and the public index currently contains zero `game/assets` files.
Private remote publication, original external vendor packs and historical Git
scrubbing remain explicitly outside the completed local migration. The retained
portable contract describes JSON values and the actual sampler algorithms rather
than pretending the original NeuroStudio validator already admits every extension.
Independent rendering time and complete recorded lineages remain intact.

One plan evidence item was not found in the records reviewed here: A3's
same-environment cold selected-frame load time and peak/retained decoded memory
after packing. Pixel/value equivalence and catalog-intake timing are different
proofs. Root was notified to link an existing measurement or record a bounded
representative load/cache measurement before claiming that gate closed. This is
an evidence limit, not evidence of a new performance defect or a reason to invent
a new benchmark framework. The final status/RECOVERY closure text and exact
release totals are being updated by root after its remaining checks.
