# Movement state provenance: narrow ECS recommendation

2026-10-05. Source review of current choreography.py `_bind_jump`, `bind_motion`, `sample_motion`, and player_reduction.py. No production edits. This resolves the annotation question, not movement redesign.

## Distinguish derivation from occurrence

`MotionTimeline.states` are published snapshots, not an event queue. Some states are the result of applying a branch; some adopt a nested compositor's result; some reconstruct a prefix; final state re-folds the entire root. Every such snapshot may depend on already displayed facts. Giving each state's complete input set a fresh occurrence timestamp would duplicate attacks, damage and conditions.

The smallest safe addition is one **passive per-state provenance row**, aligned by state ordinal (times can tie), containing:

- state ordinal and existing at_ms;
- finite derivation tag: `branch_fold`, `nested_group_result`, `jump_launch`, `landing_prefix`, `root_reconciliation`;
- exact ordered native inputs for direct folds: nodes/version rows and observation/world event identities, using the same fields as StateCommitEvidence;
- references to contributing bound groups: native root UUID and actual offset within movement, not copied cue/state trees.

This is trace evidence, not a new reducer or scheduler. If avoiding another public record is preferable, use these fields on a specifically named motion provenance record, rather than pretending a generic StateCommitEvidence is already an occurrence contract. The finite tag documents an existing binder operation; no callback or executable string is attached to it.

The base `MotionTimeline.before` is implicit. Native input lists preserve order. Group references preserve their existing local clocks; snapshot publication time does not overwrite those clocks. Source identities are deduplicated only for semantic occurrence selection later, **not by deleting repeated reducer inputs from the audit**.

## Exact call-site mapping

| Current branch | Snapshot published | Provenance | Occurrence rule |
|---|---|---|---|
| `bind_motion`: opaque/non-Step child, including `group.movements` | `group.after` at existing elapsed after group and optional disclosed dwell | nested_group_result; reference bound group and its actual start offset | Group's own witnessed events retain their own dates. No extra movement event for adopting its result. |
| Step belongs to another subject | direct `reduce_lineage(working, branch)` at unchanged elapsed | branch_fold; exact branch inputs | Does not create a leg for the current actor. Facts may be meaningful even with no cue. |
| Ordinary/rejected Step after reaction/contact groups | direct branch fold at leg/reaction end | branch_fold plus any nested groups already contributing to working | Step outcome is native. Previously shown reaction outcomes are not replayed at step completion. |
| End of normal movement | `reduce_lineage(working, lineage)` at existing elapsed | root_reconciliation with full exact root inputs | This may contain genuinely root-only state, but repeated child inputs are reconciliation, not fresh occurrences. Never blindly emit all root descendants here. |
| Jump preflight | `working = group.after`; launch_state captures this | Preserve contributing preflight group refs and accumulated prior direct branch folds | Preflight reactions are played before arc; their earlier dates remain authoritative. |
| Jump takeoff | `reduce_nodes(launch_state, (takeoff,), versions, (), ())` | Exact takeoff input; no invented observations/world update | Takeoff's state is published only at the existing launch snapshot, after anticipation. |
| Jump departures | `group.after` after binding with rebased cursor; transitions separately offset | Add departure-group references at the existing launch-transition offset | Do not create a new midair pause or replace group transition clocks with the later launch snapshot date. |
| Committed jump launch | launch_state appended after takeoff anticipation | jump_launch aggregation of the above contributors | Snapshot publication and each nested cue date differ. Shared native facts are not new cast/damage occurrences. |
| Landing with a positive-duration group | prefix state rebuilt from target and `source_index < first landing version`, then appended | landing_prefix with the exact selected node/observation/world inputs and versions | Prefix reconstruction is not a replay of everything that happened before landing. Landing group owns its outcomes. |
| Jump completion | `final = reduce_lineage(target, lineage)` published after landing/later nested movement | root_reconciliation with whole-root inputs | Again, preserve root-only terminal state without narrating all previous consequences twice. |

For jump launch, tracking **only the last departure group** is insufficient: its `before` includes previous preflight/branch results. Track provenance alongside `working` and copy that provenance when `launch_state=working`, then append takeoff/departure contributors. This is metadata propagation only; do not re-run reduction or diff state to guess causal owners.

## Existing authored adjustments must not be misrepresented

Jump preflight deliberately replaces the mover's occupancy layer with the original launch occupancy while binding opportunity attacks. Departure binding deliberately resets only reducer_cursor into the enclosing root interval. These are presentation composition operations, not native gameplay changes. The jump_launch derivation tag documents this existing operation; it must not narrate "lands" or "takes off" merely because this intermediate replacement happened.

For an interrupted jump, earlier Steps may mechanically have committed while the rendered body is held at the launch pose. Provenance must retain those public facts separately from the visual placement policy. Do not fix that mismatch by deleting evidence or inventing a new movement fact during this instrumentation task.

## Hidden intervals

The existing binder advances an authored dwell for loss/reacquisition and never reconstructs hidden travel distance. That dwell has no new evidence. The resulting snapshot references the disclosed branch or group that changed contact, but the annotation cannot infer an unseen start/end leg. Initial `stage_actors` and reference acquisition from observations are staging, not movement occurrence. If included in trace, label them as baseline evidence; keep baseline separate from emitted action semantics.

## Acceptance requirements for the annotation

1. Exact state dates, resulting states, legs and reaction offsets remain unchanged.
2. Repeated root folding remains inspectable but produces no duplicate occurrences by default.
3. Nested displacement has one graphical owner and one native semantic edge.
4. Takeoff anticipation does not retime departure world transitions or preflight damage.
5. Hidden dwell contributes no fabricated endpoints, distance or action label.
6. Prefix/final reconciliation has enough evidence to explain a state with zero body duration.
7. Same-time snapshots use ordinal plus retained source ordering; timestamp alone is not identity.

This design is approved for read-only provenance instrumentation. A later narrative implementation must explicitly resolve authoritative occurrence placement; these annotations alone are not that policy.

## First implementation review

Current implementation adds passive MotionReductionSource, MotionGroupSource and MotionStateProvenance on the existing MotionTimeline. Metadata is appended next to existing snapshot publication; no observed timing/reducer change. State ordinal distinguishes same-time states. The direct branch and final root folds preserve exact node/observation/world identities and version rows. Jump `launch_sources` correctly snapshots `working_sources` only when launch_state is assigned from working, then adds takeoff and departure contributors; unused later folds are not incorrectly attached to launch.

**One required provenance correction:** MotionGroupSource currently holds only root UUID and offset. Zero-duration groups are not retained as MotionReaction, and jump departure groups are not retained as MotionReaction regardless of duration. Those references therefore cannot be resolved to exact bound commit evidence through walk_bound_timelines. Their result contributes state, but the exported annotation has no exact contributing input/commit record.

Add the compact native reduction input evidence to the group source, and if timed intermediate commitment is claimed, its StateCommitEvidence tuple. Alternatively retain an evidence-only index of these groups. Do not retain duplicate entire BoundChoreography trees for this purpose. The source branch is available at each call site; do not infer it afterward from final state. Positive-duration retained groups may use the same passive representation for uniformity.

Landing zero-duration groups are not adopted directly into a motion state in the existing implementation; final whole-root reduction explains the final snapshot. Their contact cues remain separately retained. That is not an extra missing state-provenance row, although trace/semantic coverage of the cues remains separate.

Review disposition: behavior/timing placement accepted; exact provenance needs the discarded-group correction before claiming this lane complete.

## Corrected implementation approval

MotionGroupSource now carries its exact MotionReductionSource inputs and existing StateCommitEvidence tuple, including for zero-duration opaque/contact groups and all jump departure groups. The previously unresolved references are now self-contained evidence without retaining duplicate graphics/group trees. Call sites use the actual branch passed to the compositor. Approved the corrected provenance checkpoint. No runtime timing changes observed.
