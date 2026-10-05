# Producer timing evidence — independent anti-slop review

2026-10-05. Source-only review of `game/timing_evidence.py`, choreography formation/clearance/world/sensory instrumentation, `presentation_timing.presentation_dependencies`, trace and text export integration, and declared focused tests. No production edits or test execution by this reviewer.

## Verdict

The bounded design is sound: passive arithmetic/provenance beside the existing calculation, a validating export view, no second scheduler or date mutation. One exact reference-kind correction is required. This receipt concerns only annotated formation/clearance and dependent world/sensory floors; it does not certify full plan D or unrelated timing lanes.

## Required correction

The removal instrumentation always declares `TimingReference('spatial', identity, 'clearance')` and spatial start operands. However `recorded_transitions` also contains **object-section** removal records: the SpatialFact.OBJECT_REMOVED branch creates `WorldTransition(fact.object_uuid, 'removal', ...)` around choreography line 1055. That object's formation correctly uses kind `object`, while its clearance is exported as kind `spatial`. A typed consumer would look in the wrong owner domain even though its timestamp is correct. Classify clearance/start references using the actual removal owner (object identity versus field identity). Keep the existing arithmetic unchanged. Add an assertion on section-removal reference kind to the current native construction test.

## Checked boundaries

- The old formation/removal equations still use start + maximum authored offset; the change carries `(value, authored_field)` pairs alongside the same values. Authored field strings are provenance labels, not an executable path language.
- World floors, spatial-cause ancestry and sensory-observation floors preserve their existing max operations and input selections. Evidence records do not drive reduction or overwrite clocks.
- `producer_index` is local to the owner tuple. The validator checks prior existence/order, typed reference/value correspondence and arithmetic. No global dependency registry was introduced.
- Inputs with no producer index remain explicitly external/measured/already-bound anchors; validation does **not** prove those external anchors' causal graph or completeness. This limitation is accurately documented.
- `_observed_commit` requires all known observed-source lineage dates before returning a result; the instrumentation's lookup uses the same admitted sources and does not invent a missing date.
- MotionGroupSource carries the nested group's evidence unchanged. Export normalizes result and input base timestamps by the same offset and preserves authored relative offsets. Producer indices therefore remain owner-local and valid.
- Export deduplicates identical owner/evidence bundles; it does not combine distinct native applications or solve a new ordering. Repeated native refs represented as several calculation stages stay distinct by local index.
- `presentation_dependencies` validates before exporting; trace and text use the same view. `FiniteFloat` plus explicit finite checks and extra-forbid records make malformed portable evidence fail rather than silently pass through.
- Validation of arithmetic is appropriate here; it is not a second scheduling formula used by playback. The source of playback dates remains choreography.

## Scope/evidence limits, not blockers for this lane

Selected release/contact/body/socket equations and all retained lifetime schedules are outside this first producer-evidence subset. The validator cannot claim a complete presentation DAG from these rows. No blanket coverage claim is present in the new module docstrings.

The focused tests visibly cover construction formation/clearance admission in both observers, JSON round trips, forbidden extra fields and corrupt producer rejection. Runtime pass results must come from the implementing agent's run; this reviewer makes no such claim. After correcting reference kind, source review finds no additional bounded blocker.

## Cast/attack producer extension review

Source re-review of `timing_evidence.py`, completed cast/attack additions in `animation.py`/`attack.py`, normalized export and initial choreography fixes: **approved for this bounded evidence subset; no blocking defect found.** AreaReach joins were still being developed during this review and are explicitly outside this verdict.

- Object clearance now uses object kind for known object identities. Construction contributors are preserved as object UUIDs alongside authored parameter provenance, closing the earlier reference-kind finding.
- Cast reference identities remain strings because detached CastInput already supports string compiler identities; attack/native owner identity remains UUID. The discriminated reference union records that existing distinction instead of coercing synthetic strings into native event UUIDs.
- Application membership survives on per-application launch/contact/damage/HP refs. Repeated A/B/A targets are not collapsed by target identity in the exported rows. The existing arc arrival-by-target behavior was not redesigned by this instrumentation.
- Release frame/FPS/playback measurements remain alongside the actual computed millisecond offset. Contact distance names specify pixels or cells; length carries feet; speeds/durations retain their declared field-unit names. All resulting clocks and offsets are milliseconds.
- Projectile prepare uses the existing release/prepare-end maximum only when preparation may delay launch. Ground delivery supplies the existing ground contact to its applications, rather than recording a separate invented trajectory for each victim.
- Direct/contact-speed/cell-delay/arc branches record each existing arithmetic stage; they do not install a second formula that controls playback. Capped travel is recorded as its computed duration with source measurements. Validation proves the offset/max/min equation, not independent recomputation of distance/cap/curve policy.
- Damage callback evidence preserves immediate lethal/terminal HP and the surviving body's authored callback frame. HP reentry records the original minimum against actually overlapping subsequent same-target damage starts. Flash/number clocks remain their existing owners, not falsely certified by the HP row.
- Export adds owner scope (`choreography`, `cast`, `attack`) so local producer indices from separate tuples cannot be mistaken for one graph. Owner offset applies uniformly to result and base-input timestamps; relative offsets and measurement scalars are not translated. Interrupted full action evidence is excluded rather than asserting completion.
- `record_timing` appends an already computed result and returns a passive reference. It does not calculate a playback date. `validate_timing_evidence` verifies finite values, arithmetic and local DAG ordering; it cannot claim to validate unnamed external anchors or a complete scheduler graph.

No production edits or fresh test runs were performed in this review. Broader schema round-trip and numerical/runtime pass results belong to the implementing agents. This is not full plan D acceptance and not a reason to block the correctly bounded cast/attack evidence work on unrelated remaining families.
