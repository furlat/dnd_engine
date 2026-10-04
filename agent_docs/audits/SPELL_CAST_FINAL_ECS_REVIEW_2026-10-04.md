# Spell casting final ECS/evidence review — 2026-10-04

**Final outcome: approved. No remaining ECS/data, gallery-provenance, or test
reconciliation blocker within the authorized spell-casting scope.** Earlier
checkpoints below are historical; the final closure at the end supersedes their
pending status.

Reviewed the feature trace, changed tests, completed focused logs, private
`merge_gallery.py` / `coverage_receipt.py`, and representative actual part-run
traces. No production source was edited and no tests or renders were launched
by this reviewer.

## Test correction review

- `final-affected-checks.log`: 57 passed across the palette, body-action and
  True Strike files. Current tests retain actual pixel/alpha checks, palette
  isolation under both load orders and seeks, native child weapon timing,
  equipment and outcome checks. Matching original Magic2 frames replace the
  obsolete single-frame charge-art expectation.
- `final-current-selection-checks.log`: 41 passed across the five corrected
  selection/contract files. Preparation frame and Shield motion expectations
  follow the approved assignments; interception ordering checks remain.
- The CodexFX comparison now preserves delivery/result/equipment/recovery
  contracts while checking the independently authored current cast. Its
  separate reimport test still requires the authored recipe bytes to survive.
- False Life samples the actual retained local application boundary and still
  checks immediately before and exactly at it. The absolute lifetime is checked
  against that boundary with floating-point tolerance; the visibility boundary
  itself was not relaxed.
- Cone of Cold already had `holdUntilContact: true` in the task's before snapshot.
  The Finger test now permits this existing hold and still forbids Finger's
  delayed-launch clock on other recipes. This is not a new production exception.

## Initial evidence findings (closed by the correction below)

1. **Coverage must identify the actual executed identity.** In the reviewed
   `coverage_receipt.py` lines 24–28, any canonical-owner cast can satisfy a
   variant/action-alias row. Retained facts are neither mandatory nor joined to
   the selected primitive by event UUID. This can report execution of a repeat
   or variant using only its parent's cast. Match the exact variant `effect_id`
   or alias `behavior_id`, require the corresponding committed retained event,
   and link it to the executed primitive. Canonical-owner coverage may document
   an explicitly selected derived route separately.
2. **True Strike needs its causal link.** Selecting any attack with a weaponGlow
   is insufficient. The real trace's attack has a `parent_lineage` containing
   the True Strike spell fact, with an intermediate event lacking a fact. Keep
   full event/lineage links so the receipt proves that child relationship.
3. **Movement heads are valid trace entries.** Unconditional access to
   `composition['nodes']` / `['body_actions']` fails on movement compositions.
   The actual `control-blindness` trace demonstrates this. Extract presentation
   primitives from choreography heads while preserving all causal evidence.

Concrete reviewed trace examples support a bounded correction: Produce Flame's
initial cast and hurl have the same recipe owner but distinct event UUIDs and
behavior identities; Blindness's body cue shares its UUID with the exact
`control.blinded` spell fact; Hellish Rebuke's executed cast maps to a retained
`kind: action` fact naming `reaction.spell.hellish_rebuke`. Ice Knife's disabled
burst has its own effect fact and executed cast node within the actual owner
lineage, without an extra body gesture.

## Merge/provenance review

The merge uses completed standard recorder outputs, refuses missing/duplicate
case IDs and recorded failures/gaps, copies case artifacts, and retains each
origin manifest plus both run descriptors. Its source-snapshot relative path
resolves to the persistent archive. All 48 recorded source-snapshot hashes match
the current workspace files at this checkpoint. The two current top-level coverage arrays
are equal (795 declaration rows); retaining one is valid for these inputs,
preferably with an equality check. These declarations are not execution proof.

The proposed 298 recordings / 150 identities remain target counts until the
final manifest and corrected executed-coverage receipt exist and are checked.
Full-suite completion and reconciliation also remain required. No complete
gallery acceptance or all-frame visual inspection is claimed here.

## Coverage ownership correction — independently verified

The revised private coverage script closes all three findings above. Ordinary
cast/body primitives now join the retained event by exact UUID. Derived rows
require the exact action/reaction behavior or variant effect identity; canonical
coverage explicitly resolves only declared derived owners. True Strike uses the
actual attack-to-spell lineage ancestry, retaining intermediate events without
facts. Movement heads are excluded from cast-primitive extraction.

Independently checked all 246 primitive proofs in the supplied partial receipt
against 213 original case traces: every selected native/executed event is a
non-canceled completion; ordinary UUID joins, derived identities, and the True
Strike ancestry chain agree. No mismatch was found. The supplied partial report
still records 117/150 identities, 215 recordings, and eight gaps; it predates the
Shield correction and is explicitly partial. Inspection of the actual Shield
trace confirms its body cue UUID matches the committed `condition` fact carrying
`condition.spell.shield`, so the new exact condition branch is supported.

The merge now checks equality of the two source coverage declarations. Its
existing refusal to accept failed/gapped cases remains. Refreshing the two old
summon scenario archives through their existing producer is an input-provenance
correction; retain the original failed clips/inputs and record which successful
replacement outputs the final merge selects. No production workaround is needed
or approved by this evidence review.

**Coverage ownership logic is approved.** Final acceptance remains open for the
completed manifest, corrected final coverage totals, explicit summon replacement
provenance, and full-suite reconciliation.

## Final persistent gallery — independently verified

Reviewed the completed archive at
`/home/tommaso/Dev/neurodragon_art/reviews/spell-casting-20261004/acceptance/runs/20261004-all-spell-casts/`.

- The manifest contains 298 unique recordings, all passed, with 5,560 passing
  recorder checks, no failed checks, and zero gaps. Every standard input, trace,
  video and poster exists. Every final input/trace matches its declared source
  run byte-for-byte.
- The final `spell-coverage.json` is marked non-partial and accounts for exactly
  the 126 canonical plus 24 derived assignment identities. All 150 have executed
  evidence. Independently verified all 335 linked primitive proofs against all
  298 traces: committed completion, exact ordinary UUID, exact variant/alias
  identity, and True Strike ancestry checks have no mismatch.
- The four explicit replacements are Wolf and Fey Jaguar, each in caster and
  opponent views. Their manifests preserve links and all eight original gaps.
  Original input hashes match the refresh receipt, and old inputs, traces,
  videos and posters remain present. The final four replacement inputs, traces,
  videos and posters match the refresh run byte-for-byte.
- Replacement scenario parameters are unchanged. The originals contain the
  documented null removal-state behavior IDs; refreshed Wolf trait removals and
  Fey summon-control removal contain their full existing identities. These are
  newly recorded inputs from the existing scenarios, not repaired historical
  facts or a renderer workaround.
- All snapshotted production code, authored data, authoring tool and tests still
  match their recorded hashes. The only 48-file snapshot mismatch is ASSETS.md
  line endings and one trailing blank line; its normalized text has no substantive
  change.

A nonblocking gallery-label issue was reported: refreshed caster titles repeat
the caster suffix and opponent metadata includes an extra caster tag. Actual
perspective identity and scenario evidence are correct.

**Final ECS/data/provenance findings are closed.** This approval does not claim
manual viewing of every encoded frame. Only full client-suite completion and
failure reconciliation remain pending here; the ongoing suite and its Silence
diagnosis are not treated as resolved by this receipt.

## Full-suite reconciliation and final closure

The complete original client run ended with **3,524 passed and 34 failed**, for
3,558 cases. Independently parsed its exact failed node IDs and checked them
against `test-reconciliation.json`: all 34 appear exactly once and map to a
passing run of their complete current test file. The six complete-file reruns
report **57 + 41 + 9 + 3 + 37 + 14 = 161 passed**, with no failure summary.
No original failed case remains unaccounted for. This is a reconciled full run,
not a claim that the original log was entirely green.

The later test corrections retain their contracts:

- Hold keeps explicit gesture/layer capability checks plus independent paralysis
  facts. Magic Missile keeps volley order, staggering and outcome checks with
  the reviewed frame-7 release.
- Silence samples the middle of the intended source frame to avoid absolute
  float subtraction landing just before a boundary. It retains exact frame,
  application/sustain, repeated pixels, depth, removal fade and backward-seek
  checks; no production timing tolerance or renderer change was introduced.
- Rebake uses a complete 128px source cell and deterministic noise input, checking
  every resulting RGBA pixel, source/output geometry, unchanged original and
  selected files, and untouched recipe bytes.
- Summon release and preparation constants independently match all eight
  measured Special1 hand paths at frames 11 and 6. The separate dismiss action
  remains at frame 8 with its before/at-release membership checks intact.
- Support media checks the current matching Magic2 source while preserving
  duration/registration/no-damage checks. Teleport still relocates once without
  restarting its body clip, now checked at the approved frame 11.

Independently recomputed the 41 original production/data/authoring hashes from
`source-snapshot-initial-manifest.json`: all match current files, corroborating
the production-stability receipt. The refreshed 74-file source/test/document
snapshot matched the workspace immediately before this review-receipt update.
Final architecture checks report **82 passed**; scoped typing reports **zero
errors and zero warnings**.

The normalized final gallery observer tags identify their actual observer once;
the duplicate caster-title suffix is removed. Opponent titles still retain the
caster phrase before their opponent suffix, a cosmetic label detail without
an evidence or ownership impact.
The artifact-integrity receipt matches the current manifest and unchanged
coverage hashes; manifest SHA256 is
`5503c81628e1bfea46c21aea2a7b957cf98887613eba7165ee08417c1f16f484`.
The previously verified 298 recordings, 5,560 passing checks, zero gaps and
150/150 exact executed identities remain accepted. No new test, render,
production edit, or external communication was performed by this reviewer.

**All review findings are closed.** Archive this final receipt with the other
completed source/evidence documents; no implementation or validation blocker
remains within this review's scope.
