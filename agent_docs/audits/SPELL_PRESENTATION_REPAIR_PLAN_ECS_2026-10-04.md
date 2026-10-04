# Spell presentation repair — independent ECS/DAG plan review

Date: 2026-10-04. Scope: the complete categorized repair plan, current shared
authoring/timing owners, and the unfinished formation candidate. Read-only source
review; no production changes, tests, renders or external conversations. The
original 298 recordings remain archival evidence.

## Decision

The proposed architecture is appropriate. Reuse of `BodyClip`, `BodyContext`,
`ActionFrameAnchor`, rig `pose_sockets`, authored media phases and existing
spatial/construction bindings keeps ownership passive and preserves the import
DAG. The ordered evidence gates and explicit distinction between diagnosed,
patched and accepted work are necessary. No second animation registry, gameplay
system, event vocabulary or per-spell executor is justified.

One bounded clarification is required in the two-date section before nonzero
formation milestones are enabled: **materialize both the witnessed artwork start
and the resolved effective state-commit date into existing retained presentation
records, after causal joins.** `formationCommitMs` is an authored minimum offset;
it cannot also stand in for the final date when sibling materials or an indivisible
multi-source observation delay admission further. Draw consumers must use the
resolved dates, not independently calculate `applied_ms + formationCommitMs`.
Missing witnessed creation must retain sustain/cold-acquisition behavior rather
than derive a supposed historical start from a later observation.

With that clarification, I approve the plan's ECS/data boundaries. This is not
acceptance of the current formation implementation or of corrected visuals.

## Existing-owner checks

- Motion defaults belong to the existing clip metadata/rig document and are
  resolved offline into concrete Studio sockets and timing. Exact fixed-rig
  `BodyContext` overrides and native sockets remain authoritative. Keep source
  attachment lifetime on the delivery, as the plan now specifies; a gesture can
  serve both detached emission and a persistent hand-held effect.
- Keep `ActionFrameAnchor` for body frames, validating against each actual clip.
  VFX phase anchors need their own phase-bounded numeric frame value because
  `BodyFrame` is limited to 0–14. The shared conversion must consume the existing
  FPS, time-map, fit/duration and playback-rate semantics actually used by its
  consumer. Reject an unavailable or ambiguous required milestone rather than
  silently treating a body frame or raw FPS division as equivalent.
- `animation_data._root_body_rig` can materialize root defaults without importing
  authoring tools into runtime. Lifetime registration already imports choreography;
  choreography must not import those registrars in return. Retained dates are
  data, not another frame-pump scheduler.
- Spatial fields and physical constructions both require the two-date contract.
  Delaying a sensory row alone cannot prevent an earlier `OBJECT_PLACED`/world
  update from admitting collision. Preserve each received update whole and carry
  its causal maximum to associated actor observations.
- Palette selection stays on the exact uncanceled owning branch before the
  common palette resolver. Existing condition identities, instant-death facts and
  damage reentry remain authoritative; cosmetic media cannot manufacture native
  damage, blood deposition, a new sleep rule or another teleport.

## Current implementation findings — must close before enabling milestones

These are findings in the partial candidate, not objections to the approved
high-level ownership model. No authored `formationCommitMs` values are currently
enabled in `game/data`; default-zero behavior is not evidence for the new path.

1. **Future disclosure can enter pre-commit artwork.**
   `game/spatial_media_draw.py:63` reintroduces an entire retained future effect
   when any position is currently visible. Its later volume path accepts that
   effect's `visible_volume_positions` and `upper_volume_surfaces`; the field
   compositor treats those as already granted sight, including surfaces without
   a currently visible ground tile. `game/construction_media.py:84` similarly
   admits complete future section/dome geometry after an any-visible-cell test.
   Final volume composition does not supply a missing current visibility grant.
   Formation may draw only its independently witnessed shape on currently
   disclosed supports/surfaces. Clip/filter the retained presentation data by
   the current grant before these consumers, or decline unsupported partial
   visibility; do not borrow the delayed observation's grant.

2. **Nominal and effective commit dates are currently conflated.**
   Both draw paths stop their pending-art window at `applied_ms +` their local
   binding offset. Choreography can instead delay the state until a larger
   sibling/material or multi-source date. That leaves an interval with neither
   pending artwork nor admitted state. `game/spatial_media_lifetime.py:125` also
   falls back to `at - binding.formationCommitMs`, which is not necessarily the
   witnessed start after those joins. Retain the exact compiled dates as stated
   in the required clarification above.

3. **A source's revised milestone must exist even without a state node.**
   `game/choreography.py:1424` first records creation's delivery date. The final
   formation pass updates milestones while iterating `state_nodes`, but a
   `SpatialEffectStateFact` is normally not retained there: the timed-fact filter
   at line 1281 excludes it, and any corresponding world-update node replaces
   its fact with `None`. Thus the later `CREATED` branch at line 1504 cannot by
   itself revise all source creation milestones. A sensory update containing
   that owner is delayed directly, but another update/actor observation referring
   to the same source without repeating `spatial_effects_changed` can retain the
   old date. `_observed_commit` now takes the maximum of resolved sources, which
   is correct only after every relevant source has its final milestone. Seed
   exact creation-source lineage dates from `formation_commits`, then propagate
   received causal joins before folding updates and actor observations. Preserve
   native source ordering and whole updates; no fabricated sensory event is needed.

## Acceptance boundary

The plan already requires the appropriate narrow evidence: measured reusable
motion sockets/keypoints; actual four-camera emission pixels; cloud/light and
physical-construction pre-commit, commit and clearance; a multi-source observation
with different source dates; related actor disclosure; partial visibility; cold
acquisition/reacquisition; and identical forward/backward seek. Include a source
whose creation has no world-update state node and a pending-art interval extended
by another source. These cases directly exercise the three candidate findings.

The earlier 142 focused passes predate this formation work. Body/media anchor
metadata, enabled asset milestones, new source review and fresh bounded visual
evidence are still outstanding. No full repair or visual acceptance is claimed.

## Amendment — final plan clarification review, 2026-10-04

Reviewed the amended plan. The requested clarification is closed: it explicitly
retains witnessed artwork start and resolved effective commit after causal joins,
uses current per-cell/surface grants, seeds exact creation-source lineage dates
without requiring a state node, and keeps nonzero offsets disabled until the
three implementation findings close. Mapped media-clock semantics and cold
acquisition remain explicit; no new registry, event or dependency cycle is added.

The 24-row gallery table covers every ledger ID and requires exact inspection
moments, preserved original evidence and visible open limitations. The assignment
audit now requires the complete loaded inventory, derived/weapon exceptions and
motion-specific effect meaning beside the main VFX, rather than variety quotas
or generic rationales. Reproducible authoring must preserve explicit palettes.

**Final plan approval: no remaining ECS/DAG plan blocker.** This amendment does
not close the three partial-implementation findings or claim visual acceptance.
Only the plan and this receipt were reviewed/updated; no production edits, tests,
renders or external-chat communication were performed.
