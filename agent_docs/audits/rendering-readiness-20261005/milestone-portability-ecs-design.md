# Finite milestone view and portable export — bounded ECS recommendation

2026-10-05. Read-only inspection of current bound owners, causal binder equations, narrative traversal and AnimationData. This is an implementation recommendation, not certification that a diagnostic view replaces the remaining causal migration.

## Smallest useful shared view

A pure projection of existing bound scalar fields is justified. It must not own, recompute or mutate their schedule. Keep it downstream of choreography, attacks and retained lifetime registration. Narrative and developer trace may consume the view; samplers continue to read their existing owners until a separately reviewed equivalent replacement exists.

A milestone needs:

- owner: finite family tag, native event/instance UUID, optional application ID, track ID or state/leg ordinal;
- name: finite literal describing the real source field (release, contact, hp_commit, body_end, recovery_start, complete, state_commit, snapshot_reconciliation, application, activation, consumption, removal, return, partial_retirement);
- at_ms in **one declared coordinate system** (head-relative for bound records; absolute presentation time for retained records must be explicitly normalized);
- evidence: existing exact native/version refs where available;
- role: actual publication, visual anchor, reconciliation, or sampled lifecycle phase. A visual anchor is not automatically a factual occurrence.

The enclosing trace supplies generation and observer; a stand-alone export must include them. Content/recipe ID is attribution, not identity. Two targets or two same-target applications must not collide: use existing ApplicationTimeline.source.application_id, and retain existing stable ordinal when no application ID exists. Ground delivery is explicitly its own owner kind, not an invented creature target.

## Exact source mapping

| Family | Existing scalar sources | Important distinction |
|---|---|---|
| Cast | ActionNode.start_ms + CastTimeline.release_ms/body_end_ms/recovery_start_ms/complete_ms | Cast release is not every recipient contact |
| Cast application | application start/travel/contact/HP dates on each ApplicationTimeline; use cast_deliveries for ground variant | A/B/A owns three applications even with repeated target |
| Attack | ActionNode.start_ms + AttackTimeline.release_ms?, contact_ms, body_end_ms, complete_ms; DamageTiming.hp_ms separately | Melee may have no projectile release; do not fill it with contact |
| Body action | BodyActionCue.start_ms/effect_ms/body_end_ms/join_ms/complete_ms | Existing fields already include their local positioning; do not add start twice |
| Equipment | cue start plus EquipmentTimeline's actual anchors | Appearance and final state commitments differ |
| Standalone damage/heal/life | existing cue DamageTiming, HealCue and LifeCue fields | Requested/applied result and cosmetic tail are not interchangeable |
| Bound state | StateCommitEvidence.at_ms + visit offset, state ordinal | Native batch stays atomic; multiple source versions may share a date |
| Motion | MotionLeg start/end; MotionStateProvenance state_index/at_ms/origin | Root/prefix reconciliation must remain marked non-occurrence |
| Nested/discarded group | MotionGroupSource.offset_ms + its StateCommitEvidence dates | Does not create a second occurrence when the same group is also visited |
| Retained conditions/items/slots | existing applied/activated/consumed/removed/returned dates and source owner | None means not witnessed; it is not zero |
| Spatial/construction/deposit | owner-specific application/commit/removal/destruction/partial-cell/release dates | Parent collapse, section hit, sight loss and cell retirement differ |

For passive loops, frozen samples, two-frame crossfades, particles and trailing emissions: expose the selected **sampler contract and inputs**, not an infinite chain of milestone events. Decorative end cannot become the completion join of unrelated actions.

## Dependency view: only actual relations

A typed passive edge can represent `offset_from` or `not_before`/join only when the producing binder knows the relation. The projection must not derive causal edges by comparing timestamps or assuming all descendants share a parent contact. Existing exact sources include:

- AreaReachFact prerequisite_destruction_lineages and previous reach;
- SensoryFact.observed_changes/cause_event_uuid and the current observed-commit mapping;
- ActionReaction.triggered_lineage_uuid;
- explicit formation/removal owners matched to WorldUpdates;
- a selected forced movement travel-end or portal settled anchor supplied to `_child_timing`.

Initially expose a resolved relation only where its scalar source refs are available. A missing source remains explicit unresolved evidence; never synthesize a parent edge or use max(empty)=0. Keep unknown evidence distinct from authoring errors. State final timestamps already produced by the binder remain authoritative.

The current binder computes causal constraints before collecting StateCommitEvidence. That evidence records *what/when*, not every *why*. A downstream view cannot honestly reconstruct the full dependency graph. If full dependency export is required, append passive edge evidence at the existing binder equation sites. Do not re-evaluate those equations in the view. Validate cycles/producers only on the relation subset that is actually exported and label subset coverage; do not claim a complete scheduler proof.

## Equations safe to share now

**Safe:** one traversal/normalization of existing bound anchors into head-relative milestones, currently repeated in narrative and trace readers. `walk_bound_timelines` is already the traversal owner; extend/reuse it rather than create a second timeline walker. Offset addition is exact and has no policy. Multiple references to the same actual native milestone can deduplicate using their owner/name/application key, but conflicting dates must be reported rather than silently choosing max.

**Not established as safely equivalent:** generic extraction of max-joins. `_child_timing` treats movement parent completion, injury state, displacement travel end, portal settlement and sequence ordering differently. Formation/clearance joins identify world owners; sensory joins identify observed source relations. They happen to use max, but replacing them with one policy helper risks erasing the very distinctions under review. Keep these family equations until concrete before/after boundary fixtures prove equivalence. A trivial max wrapper adds no value.

**Do not extract as mechanics:** narrative `outcome_date` computes when a summary is safe to disclose. It is a consumer policy, not the schedule governing gameplay/rendering. It must not feed back into binder dates.

## Portable catalog requirements

AnimationData is a local assembled catalog, not an export DTO. Its Path-valued `media_root`, `resources`, ProjectileStorage and any raster-derived geometry must not be serialized wholesale. Use a versioned explicit export record with existing authored family models and an explicit logical resource table.

1. Preserve all existing family discriminators, ordered recipe/profile precedence, rig/action qualifiers, optional versus absent values and source aliases. Do not add a new behavior registry.
2. Resource keys remain the existing logical identifiers. Export a relocatable package-relative URI plus media metadata/hash where needed; reject absolute Windows/Linux filesystem paths. Package mapping is an offline boundary, not a runtime lookup of the engine filesystem. Exclude local `media_root`.
3. Preserve source sheet/pivot/frame/fps/direction/registration geometry and effective palette treatment, including noise resource ID. Emit the resolved swap/source decision used by loader/cache; legacy tint labels must not misdescribe actual behavior.
4. Declare units: time ms, grid coordinates in cells, elevations in steps (5 feet where current code uses that conversion), angles radians or degrees per authored field, RGBA integer convention. Keep authoritative native feet values where already carried; never silently relabel units.
5. Reject nonfinite numbers. JSON object map keys must be strings; tuples become arrays deliberately. UUIDs are strings, enums their public values. No Python classes, callbacks, MappingProxyType wrappers, sets, surfaces or NumPy arrays in the portable contract.
6. Rig body contexts/socket measurements, actual creature-rig mapping, field geometry and sampler operator tags remain required data. Unsupported visual capabilities stay explicit. No cast-ID conditionals are introduced to cover missing exported parameters.
7. `context_source_json` holds currently unused source data; do not advertise it as executable portable support. Either keep a clearly marked archival payload or leave it out of the executable schema. Enumerate implemented operators explicitly.
8. Validate field/reference coverage against the existing catalog-field inventory; round-trip supported authored records and normalized bound milestone samples with strict extra-field rejection. Repeated application IDs, reaction association, atomic WorldUpdate references and retained owners must survive. This validates format, not TS execution (which remains out of scope).

## Review gate

Approve a small read-only finite milestone projection and explicit portable export boundary under these constraints. Do not approve a newly generalized scheduler from this inspection: no equivalent replacement of the family causal equations has yet been demonstrated. The implementation must name which duplicated consumers it replaces, retain exact dates and expose missing relation evidence honestly.
