# Spell presentation repair — model-switch checkpoint

The user requested a checkpoint so they can switch the executing model to Astra.
The active objective is still to finish every issue in
[the approved repair plan](SPELL_PRESENTATION_REPAIR_PLAN_2026-10-04.md), then
deliver the issue-indexed native gallery. This checkpoint is not final acceptance.
Do not restart the task, substitute another plan, or rerender the archival 298 clips.

## Current changes

### Shared motion authoring

- `BodyClip.anchors` uses the existing `ActionFrameAnchor` type. Root defaults
  live in `RigTables.CLIP_ANCHORS` and are materialized by `animation_data.py`.
  Established release frames remain Special1=11, Attack4=9, Attack5=7,
  Attack6=6, Attack1=6. Their preparation defaults remain 8/6/4/3/3 respectively;
  recovery anchors are 13/11/11/9/10. Existing motion/contact-sheet evidence
  was inspected; fixed-rig contexts and native sockets are preserved.
- `devtools/author_spell_casts.py` now materializes named preparation/release
  defaults rather than subtracting three in each spell. Explicit overrides need
  `anchor_override_reason`. Preparation sockets are required only when the
  projectile preparation actually consumes them; blank unused frames are allowed.
- Typed `layer_overrides` preserve intentional exact palette materials. Existing
  variant selectors and unrelated delivery/condition/injury/death fields survive.
- `AuthoredProjectilePhase.anchors` uses phase-bounded `MediaFrameAnchor`.
  `animation.media_phase_anchor_ms` resolves the consumer's supplied FPS/map/fit
  clock, including repeated/reversed crossings and rejection of held ambiguity.
  **Asset milestones and the consumer authoring pass are not finished.**

### Semantic assignment candidates

The complete 126-owner JSON now records each spell's specific manifestation,
gesture meaning, motion-specific effect meaning, competition and progression.
The existing author command applied these selections to ordinary production
recipes. These candidates still require complete semantic/pixel acceptance.

- Touch buffs/restorations and directed ally transfers now use restrained
  Attack5; Shield uses the labeled Attack5/Effect1 off-hand parry.
- All six walls keep Attack4. Wind/Fire use Effect1; Force uses Effect5;
  Stone/Thorns use Effect2; Ice uses Effect3. Extra stacked contours were removed.
- Proven Lightning Bolt/Chain Lightning/Sunbeam remain Attack5, now with only
  Magic2+Effect1. Guiding Bolt/Scorching Ray/Disintegrate/Harm likewise use one
  small flare. Blight is the sole Attack5/Effect3 skull.
- Special1/Effect3's column is restored for Circle of Death, Antimagic Field
  and Mass Heal; it is not the skull. Sunburst retains a body-local accent.
- Guardian of Faith and Heroes' Feast return to invocation; their placement
  on ground alone does not justify a destructive earth strike. Spike Growth
  gains the growth-related upward accent; Grease remains restrained.
- The original assignment Markdown table intentionally remains archival.
  The adjacent JSON is the repair candidate; regenerate a current table after
  acceptance without erasing the before-evidence.

### Shared formation candidate

No nonzero `formationCommitMs` has been enabled in shipped binding data yet.

- Spatial and construction lifetimes now retain actual `committed_ms` from
  compiled state admission independently of witnessed `applied_ms`.
  No subtraction from nominal offsets guesses historical creation.
- Choreography seeds uncanceled creation-source lineage milestones independently
  of retained state nodes, then propagates sensory joins in explicit source order.
  Received updates remain whole; related actor observations follow their source.
- Pending spatial samples intersect current disclosure, discard future volume
  grants, and filter later protection-cell additions through the same grant.
- Pending constructions use the existing genuine-coordinate `SurfaceVolume`
  admission. Pending Force neighbors cannot be consumed by a committed segment's
  coalescing path. Future objects do not enter sampled state/propagation.
- Pending whole-bank sphere billboards decline partial disclosure; positive
  formation-only bindings now qualify for retained lifetimes.
- Source review found the protection-cell, Force-neighbor and whole-bank bypasses;
  these are patched, but the final patch set needs another review and actual
  pre-commit/commit/seek/hidden-interior evidence before enabling offsets.
- **Removal clearance joins remain to be completed/audited under T4.**

### Other candidate

Dimension Door's existing binding now has `transitMs: 0`. Its ingress/egress
strides and single native relocation are unchanged. Corrected clip is outstanding.

## Verification at this checkpoint

- Author command after application: dry run reports `changed: []` in
  `.runtime/projectile-regression-20261004/author-checkpoint.log`.
- Existing rig and authoring round-trip suites: **14 passed in 11.35 seconds**
  in `checkpoint-rig-tests.log` in the same directory.
- The shortened hypothetical clip fixture initially failed the new anchor-domain
  validator before reaching its intended recipe-release check. Its helper now
  clears original default anchors when constructing that hypothetical clip;
  the actual release-rejection assertion remains unchanged and passes.
- Changed Python files passed `python3 -m py_compile` after the final checkpoint
  edits. Run scoped typing/new milestone tests next; syntax validation is not
  comprehensive acceptance.
- A broader shared test batch was stopped for this model-switch checkpoint.
  Its partial log is `shared-repair-tests.log`; it is **not a complete result**.
  The known rig fixture failure is closed by the 14-test run. Construction,
  maintained-media, nature and curse validation remain to be run to completion.
- The earlier 142 passes in `current-focused.log` predate this formation work.
  Do not present them as approval of the new shared state timing.
- No new videos or refreshed native captures were exported during this step.
  Only the existing preview server on port 8768 remains running; owned test
  processes were stopped. No GPU/art production jobs were launched.

## Next work, in order

1. Finish meaningful public-boundary regressions for motion/material idempotence,
   mapped media milestones, actual pending cloud/construction grants, no-state-node
   creation sources, multi-source effective dates, cold acquisition and seek.
   Follow `HOW_TO_TEST.md`; do not freeze private helper call sequences.
2. Re-review the shared formation source with the independent ECS reviewer.
   Author measured visible/contact/formed/clear milestones on existing media;
   materialize concrete binding offsets only after the shared paths are verified.
3. Finish full semantic assignment review beside main Godot VFX, including
   derived palettes/results, fixed-rig overrides and repeated casts. Verify all
   ten formerly white owners against actual material pixels, not just JSON.
4. Verify/complete the remaining issue-ledger candidates: Sunburst geometry,
   Sunbeam join, retained Produce Flame, Fear pixels, Hold connection and measured
   anatomy registration, fresh Hypnotic ownership/rotation, Eyebite sleep/wake,
   Scorching injury, Power Word feedback and portal emergence. Keep all 24 IDs.
5. Export corrected native four-camera evidence with the ordinary gallery/feed
   and per-issue exact clip/frame links. Reuse existing inputs except clearly
   justified fresh native cases; preserve the original 298 media/inputs.
6. Complete appropriate tests/architecture/typing and final independent source,
   semantic and actual-pixel reviews. Close every reported issue before claiming
   completion; open status is progress bookkeeping, not acceptable final delivery.

No new spell rules, events, art, combat systems or external-chat communication
are authorized by this checkpoint. All dirty files from prior approved work must
be preserved; do not blanket-revert the large existing working tree.

## Resumed October 5 — implementation progress (not final acceptance)

- Implemented `removalCommitMs` in existing spatial/construction bindings. Exact
  removal sources and whole received updates now join clearance dates; retained
  removal artwork keeps its original start. Destruction-owned removals use their
  existing destruction path, not dismissal timing.
- Force's observed sequence can contain only section placements, without a
  disclosed field creation. Exact `OBJECT_PLACED` events now supply section
  formation starts and commit milestones. No event is synthesized.
- Original Stone banks have no XYZ samples. Pending whole-bank artwork requires
  the entire footprint already disclosed; partial pending banks are withheld.
  Existing suppression still requires genuine coordinates.
- New tests: sphere formation/clearance/seek (5 tests total, passing), mapped
  media keypoints (4 passing), physical Stone/Force formation and retirement
  (2 passing in 69.59s). Source review by the existing ECS reviewer approved
  this bounded delta pending final visual evidence. Full affected typing reports
  zero errors/warnings. Geometry/palette suites: 140 passed in 46.48s. Nature,
  curse and maintained media initial resumed batch: 47 passed in 25.32s.
- Inspected real registered formation frames. Enabled Fog Cloud, Darkness,
  Stinking Cloud and Cloudkill at source frame 32 / 1000ms, when the cloud has
  filled its silhouette. Their 630ms uniform removal clears state at its end.
  Stone/Ice original banks use frame27 / 843.75ms; Force uses its existing850ms
  material formation. Construction removal uses the existing850ms clear end.
  These data selections still need final in-game evidence and affected tests.
- Actual saved Fireball and Sleep frames were redrawn: Fireball has a continuous
  outer edge and Sleep's soft floor fringe is intact. Final gallery not exported.
- Personally viewed Special1, Attack4, Attack5, Attack6 contact sheets. Independent
  semantic review confirms choices broadly match the user's analysis; JSON now
  records concrete competition risks for broad ground rings/pillars and early
  invocation orbits, rather than treating matching color as sufficient. Removed
  A/B/A scenario language from Magic Missile semantics and unsupported anatomy
  claims from Hold Monster; Shillelagh describes weapon infusion.
- New evidence/logs/scripts are under `.runtime/projectile-regression-20261004`.
  The physical destruction non-interference test was still running when this
  progress section was written; inspect its log/process before launching repeats.

## October 5 completion evidence

See [the current repair receipt](audits/SPELL_PRESENTATION_REPAIR_ACCEPTANCE_2026-10-05.md)
for the final implementation trace, exact test logs, independent reviews and
persistent50-clip/24-issue gallery. This supersedes the earlier next-work list.
The full native archive remains untouched. Source formation/clearance blockers,
split Daylight sensory timing, missing original Attack4 sheets, real Hold scale
fixtures, Sleet clear timing and Power Word impact timing were resolved during
actual source/pixel review. No backend mechanics or external chats were changed.
