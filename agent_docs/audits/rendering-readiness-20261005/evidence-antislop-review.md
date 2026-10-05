# Retained evidence follow-up — independent anti-slop review

2026-10-05. Bounded source review; no production edits by reviewer.

## Findings and disposition

The follow-up correctly snapshots the existing six owner maps: condition, spatial, construction, concentration, item attachment and deposit clocks. `retained_trace` calls no registration, reducer or sampler and infers no application/removal date. Dates and membership are copied from the actual maps supplied to graphical playback. Serializing immediately after registration gives a detached per-head evidence snapshot; it is not a second runtime lifetime store.

This is a snapshot of the bound head's retained schedule, including known future within-head milestones. It is **not** a state-inspection payload safe to show wholesale to the player at that head's start. The surrounding head already records presentation start and duration. Future narrative/UI code must observe the same cursor/disclosure cuts rather than display all known scheduled removals early.

AST comparison with HEAD confirms unchanged function bodies for `scene_actors`, `available_clips`, `concentration_media_draw_commands`, `frame_trace` and `draw_trace`. Their relocation separates evidence/selection from graphical dependencies without changing selection, clocks, pixels or draw ordering.

The expanded motion trace usefully preserves existing body contexts, frame keys, recovery start, geometry parameters and world/contact/residue records. Residue serialization retains logical asset identity while omitting the large asset record. No new presentation interpreter was introduced.

## Required small correction

The retained-pose exclusion initially removed `ConditionAppearance.layers[*].media`, but not `ConditionAppearance.live_copies.layers[*][1][*].media`. Live copies use the same ResolvedConditionLayer type. An absence/return pose retaining them can therefore still dump the media catalog and local AssetSpec paths. Extend the same exclusion to this nested location, including both `actor.condition` and `appearance_override` branches. This does not require changing runtime pose models.

Otherwise approve this bounded evidence instrumentation. It does not claim a portable client schema, fully instrumented movement state commits, all-family semantic export, or visual acceptance. The parent reports ECS/DAG approval separately; that is not substituted for the concrete serialization finding above.

## Correction review — approved

The nested exclusion now reaches `live_copies.layers[*][1][*].media` through both retained pose appearances. The paired-pose regression constructs ordinary and live-copy layers from actual catalog media, serializes both absence and return snapshots, and checks logical asset identity survives while media/images_by_facing are absent. The required correction is closed.

**APPROVE this bounded instrumentation checkpoint.** The parent reports five passing evidence tests and earlier 19 passing headless/condition/Hypnotic tests, clean game typing and 3,611 collected game tests. Collection is not a full-suite pass; this review does not claim one. No remaining blocker was found in the reviewed snapshot/extraction changes. The scope limitations above remain.
