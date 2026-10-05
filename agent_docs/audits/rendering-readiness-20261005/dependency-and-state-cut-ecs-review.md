# Timing dependencies and narrative state cuts — independent ECS review

Date: 2026-10-05. Scope: source-only review of current `presentation_timing.py`,
`presentation_text.py`, `choreography.py`, and `player_reduction.py`. No production
edits, runtime probes, or new visual acceptance in this review.

## Disposition

The milestone view is a valid read-only projection. It is **not yet dependency
annotation coverage for plan D**. Its values come from existing producers, but it
cannot explain which producer constrained another. Do not infer this from equal
numbers, descendant structure, or narrative's conservative maximum date.

The narrative snapshot change is directionally correct and avoids querying live
or final state. One concrete selection defect remains before approval: outer
motion folds can win over the exact nested commit they contain.

## Narrative state-cut finding

`presentation_text.py:299–324` populates both maps with `setdefault` while
`walk_bound_timelines` yields the outer motion before its reactions. A normal
movement step in `choreography.py:2558–2620` first binds an attack/arrival group,
then folds the entire step branch again. `_motion_reduction_source(branch)`
contains every descendant UUID: `player_reduction.lineage_branch` traverses all
children. Therefore the outer `branch_fold` first assigns the final step snapshot
and the preceding outer snapshot to the nested group's events. Later iteration of
the group's exact `StateCommitEvidence` cannot replace those entries.

This is not a timestamp tie issue. It occurs even with different dates. An entry
for a reaction can use a name/condition state after later arrival effects, or
compare a condition update against the state before the whole step rather than
before that update. `fact_text` uses the previous snapshot for condition-state
comparisons as well as object/name fallback, so this matters beyond cosmetic names.

Small repair: collect exact BoundChoreography commit/state pairs first, then fill
only missing identities from admitted motion folds. Keep before/after as one pair
so precedence cannot select the two halves from different owners. Do not fix with
latest/final state or a nearest-date lookup. The retained native version identity
must remain the identity of the evidence being described.

Groups omitted from the drawable reaction tree remain a separate limit: a
`MotionGroupSource` has exact commit evidence but no corresponding intermediate
state snapshots. For those sources, the outer aggregate is a fallback, not the
exact nested cut. Do not describe it as the event's own commit. If precise
condition-change narration is needed there, retain the existing group's passive
commit/state pairs while the group is available; do not replay the reducer in the
text adapter and do not retain its graphics tree just to name an item.

Required regression distinctions: movement reaction then later arrival change;
two updates to the same condition inside one step; zero-duration arrival/departure
group; jump departure group absent from `motion.reactions`; equal-date distinct
native versions. Existing dates need not change to fix snapshot ownership.

## Smallest useful dependency annotation

Keep equations in their current family binders. Add passive evidence **where the
equation executes**, carried by its existing bound owner, then normalize it in
`presentation_timing`. The view must not discover or solve edges.

A compact record needs these fields (names illustrative, not a new registry):

- target reference: existing owner/event UUID, named anchor, application ID when
  relevant; include a local stage ordinal for successive updates of one anchor;
- source references: tuple of exact producer owner/event UUID, anchor, and optional
  application or spatial/section owner UUID; references must distinguish event
  UUID from lineage UUID explicitly;
- operation: `offset` or `maximum` (assignment is offset zero);
- the actual input values in milliseconds, authored offset where used, and the
  resolved output value;
- finite reason naming the existing equation, e.g. formation, clearance,
  observed-source, spatial-cause, destruction-prerequisite, displacement-arrival,
  portal-settled, ordered-group, reaction-alignment;
- target event/observation/world identities when the output admits public state.

A stage ordinal prevents a false self-cycle when an anchor is repeatedly floored:
`commit[1] = max(commit[0], formation)` then
`commit[2] = max(commit[1], observed_source)`. Do not model these as two producers
for the same unqualified final anchor. Original state batch ordinal/version rows
continue to carry ordering; do not replace them with floating-point date sorting.

An absent disclosed producer is not anchor zero. Keep unresolved reference data
explicit or omit that unavailable relation with a recorded coverage limitation.
The graph can validate declared references, conflicting producers and cycles; it
cannot certify unannotated branches. Source values recorded here are evidence of
the executed calculation, not a second schedule to execute in the renderer.

## Exact initial producer sites

| Existing equation | Inputs/reference identity | Owner of annotation |
|---|---|---|
| Formation at `choreography.py:1524–1536`: start + maximum authored `formationCommitMs` | Spatial owner or concrete section UUID, selected spatial/construction binding, formation start | Choreography binder |
| Clearance at 1513–1523: removal start + maximum `removalCommitMs` | Removal transition owner, concrete child construction owners/bindings | Choreography binder |
| World batch floor at 1607 | Original event admission; all matched placed/removed object and construction-owner anchors | Choreography binder; keep atomic WorldUpdate intact |
| Spatial causal floor at 1560–1577, 1613 | Exact ancestor/cause event identified through retained lineage; preserve each contributing source, not only max value | Choreography binder |
| Observed-source floor at 1616 and observation retime at 1626 | `observed_changes.source_event_uuid` to current lineage mapping, or observation's exact source event | Choreography binder |
| AreaReach destruction prerequisite floor | Exact `prerequisite_destruction_lineages` resolved to actual destruction producers | Existing visit branch |
| `_child_timing`: movement max(parent completion, start), displacement assignment, portal/sequence maxima | Parent/action UUID; selected displacement or portal owner; actual previous ordered group | Existing child-timing caller/helper |
| `join_reactions`: delay=max(0, reaction effect−incoming effect); reaction offset=incoming effect+delay−reaction effect | Incoming and each reaction UUID, measured effect anchors | Existing reaction join binder |

The first five form a bounded initial state-admission annotation lane. They do
not alone finish plan D: release/contact, child timing, reaction alignment and
family-specific timing must be represented or explicitly mapped to their existing
producer contracts. Lifetime readouts likewise do not define their causal edges.

## Sharing policy without extra machinery

The normalization traversal already removes duplicated consumer arithmetic. No
new generic maximum scheduler is justified here. The spatial floor, sensory
floor, reaction alignment and ordered-child assignments have different ownership
and missing-source semantics; identical use of `max` does not make their policies
equivalent. Retain these functions until a specific duplicated policy is proven.

Passive timing records must live below the binders and their read-only view in
the import DAG (existing passive type owner is preferable). `choreography` must
not import `presentation_timing`, which already imports `choreography`. No new
engine dependencies, per-spell dispatcher, executable expression language,
callbacks, or registry are needed. Text and trace consume the same records; family
samplers continue consuming the existing bound owners and dates.

## Authorized initial producer implementation (subsequent work)

Implemented the bounded initial lane at the parent's request. This section is an
implementation handoff, **not independent approval of my own edits**.

- `game/timing_evidence.py`: passive reference/operand/calculation-stage records;
  validator checks operand count, finite clocks, arithmetic, duplicate producers,
  backward producer references and matching referenced values/identities. Strict
  schema rejects extra fields; exported clock annotations use `FiniteFloat`.
- `game/choreography.py`: records the existing formation and clearance calculations,
  atomic world floors, spatial ancestry floors, observed-source floors, direct
  sensory-owner floors and observation retiming. Authored offsets retain their
  catalog field path. Calculations retain their original equations and native
  reducer ordering. No producer evidence is read by playback to calculate dates.
- `BoundChoreography.timing_evidence` and `MotionGroupSource.timing_evidence` keep
  those passive records with the existing owners, including discarded/zero-duration
  groups. Existing `before` and `states` fields remain intact.
- `game/presentation_timing.py`: `presentation_dependencies` normalizes the recorded
  clocks and preserves owner/local producer identity; it validates before export.
  It deduplicates the same nested group's evidence reached by two existing paths.
  Presentation milestones also reject nonfinite outputs and use strict fields.
- Existing evidence tests now replay a real Stone Wall history from caster and
  recipient perspectives. They verify objects absent/present immediately before
  and at the atomic commit, formation/removal dependencies, unchanged native final
  state, JSON roundtrip/unknown-field rejection, and rejection of a corrupt cyclic
  producer reference. One shared real history fixture avoids repeating simulation.

**Coverage still missing for D:** producer-side annotations for cast/attack release,
application contacts/HP, body/equipment joins, ordered action children,
displacement/portal arrival, reaction alignment and interruption, AreaReach
prerequisite destruction, movement leg/dwell/departure joins, and retained lifetime
causal edges. Existing milestone/provenance views still expose their measured
outputs, but are not substitutes for those producer-side annotations. The current
validator certifies only explicitly linked local stages. Inputs with no local
producer index are existing bound/measured anchors, not fabricated graph edges or
proof of the entire binder DAG. No repeated family scheduling policy was extracted:
none was demonstrated equivalent in this lane.

Validation before the final schema-only hardening: 11 focused tests passed in
50.12s; scoped pyright zero errors. Final focused rerun and final scoped typing
are reported separately below when complete. No image/render acceptance claimed.

Final focused validation: **11 passed in 51.02s**, including strict JSON nested
field rejection and the two observer boundary cases. Final scoped pyright:
**0 errors / 0 warnings** for choreography, presentation_timing and timing_evidence.
Fresh-process `import game.presentation_timing` did not load Pygame. An intermediate
rerun failed only because the new assertion expected a model-specific Pydantic
error code; dataclass rejection worked and the test now checks the rejected field.
