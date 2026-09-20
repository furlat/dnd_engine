# Investigation of the ten remaining game-test failures

**Completed:** all ten ordinary failures are repaired. Final verification is
**1,190 game tests passed, 6 existing expected failures**, plus **11 gallery/HTTP
tests passed**. The investigation below explains the repairs; implementation and
verification details follow at the end.

The user rejected leaving failing tests behind after the graphics cleanup.
Reproducing them at the starting checkpoint established their age, not their
acceptability. This study checks their assumptions against the approved behavior
and follows execution beyond the first failed assertion.

Scope: the ten failures reported in
[the cleanup result](GRAPHICS_CLEANUP_RESULT_2026-09-20.md). The investigation
below was read-only. The subsequent authorized test repair is recorded at the end.

## Result

All ten reproduce: the three affected modules report **10 failed, 11 passed in
14.26 seconds**. Five obsolete expectations account for them; additional probes
did not establish a production defect in these cases. At the study checkpoint the
tests remained red pending repair, not as an accepted baseline.

| Cases | Failed expectation | Contract and observed result |
| --- | --- | --- |
| 2 hidden-blood cases | One ground draw using the old blood sprite | Approved geometry reaches nine disclosed tiles; donor and hidden trap remain concealed. |
| 4 bloodied-trap cases | Increase total blood but leave its geometric contribution unchanged | Injury increases both values; lowering retains them. |
| 2 forced-movement cases | Damage's immediate parent must be movement entry | A ready trap first activates; that state event owns damage. Entry remains its causal ancestor. |
| 1 retained-event case | Native and copied models equal, including registration policy | One detached event disables registration. Other encoded fields and causal identities match. |
| 1 sensory case | Frozen contact must be copied to another object | Mutable snapshot dictionaries are independent; immutable contacts can be shared. |

## Blood footprint and hidden information

`test_known_blood_ground_renders_without_revealing_donor_or_hidden_spikes` in
`tests/game/test_bloodied_spike_presentation.py` fails for immediate visibility
and later first sight. Lines 67–69 require one draw at `(5, 3)` and the retired
`residue.blood.<facing>` asset.

The [approved distribution correction](BLOOD_REFERENCE_CORRECTION_2026-09-20.md)
explicitly broadened ordinary blood's native receiving geometry while preserving
support admission and subjective disclosure. These scenarios disclose nine cells
at x=4..6, y=2..4. Every camera renders them through `particles.region.blood`.
The donor remains absent from the receiving player state; no hidden trap or shaft
overlay is drawn. This failure is not evidence of an information leak.

Repair: assert the independently expected footprint and its agreement with
recorded, disclosed receiving tiles. Retain all four cameras, initial cleanliness,
donor concealment and hidden-trap assertions. Check the selected geometric
material. Do not weaken the test to “some blood exists” or restore a single decal.

## Accumulation, contact and shaft frames

`test_bloodied_spike_pixels_follow_contact_and_existing_deployment_frames` fails
for plain/poison-damage traps and walker/operator perspectives. Line 198 changes
only expected `amount`; expected `contributions` still describe the previous
amount. This creates an inconsistent expected state.

Probes across all four cases establish:

- Initial entry: all nine receiving tiles remain clean until injury contact at
  416.67 ms, then receive their recorded residue state.
- Lowering retains both the aggregate and geometric contribution.
- Occupied raising: both are 2 units at 249 ms and 3 at 250 ms, the lever contact
  and injury time. Condition identity and contribution shape persist.
- At contact, floor pixels still match the previous two-hit field. New marks
  appear through particle arrivals; settled pixels differ. Backward seeking
  reproduces the earlier pixels.
- **128 subsequent shaft-raster checks passed**, including four cameras,
  raising/lowering, retained poison-coating pixels and backward sampling. These
  are diagnostic checks past the failing assertion, not a repaired pytest run.

Repair: use the recorded residue after-value and explicitly check its meaning:
preserved condition identity/geometry, unchanged amount on lowering, and one-unit
aggregate/contribution growth on injury. Keep the contact, frame, coating, pixel
and seek assertions. Do not manufacture expected values with the same reducer
being tested.

The existing `public_history`/`selected` helpers already return the saved player
lineage. Read its `world_updates[*].tiles` after-values by tile position; no new
extraction framework is needed. Lowering may have no tile delta and should retain
the before-value. Occupied raising must have the recorded change as well as the
independent one-unit and identity assertions.

## Forced movement and complete trap ancestry

`test_actual_spike_entries_keep_separate_damage_and_reached_contacts` in
`tests/game/test_damage_animation.py` fails for 40 HP and 4 HP. Line 125 requires
`SpatialChangeEvent` as the immediate parent of damage.

`SpikeTrap.set_trap_state` and the entry handler in
`dnd/spatial/environmental_conditions.py` implement the intended distinction:

```text
First entry: shove → forced movement → entry → trap activation → damage
Raised trap: shove → forced movement → entry → damage
```

The activation event also represents a lever raising spikes under an occupant.
Removing it or reparenting damage would damage the causal model to satisfy a test.
Actual complete-lineage choreography binds without presentation gaps:

| Initial HP | Reached contact | Damage | Result |
| --- | --- | --- | --- |
| 40 | (2, 11), at 956.35 ms | 5 | 35 HP, alive |
| 35 | (2, 12), at 1253.33 ms | 7 | 28 HP, alive |
| 4 | (2, 11), at 1253.33 ms | 5 | -1 HP, dead; path ends here |

The paths have different travel timing; each injury occurs at its own actual
arrival. Sampled contact agrees with the reached cell. Existing native history
tests already follow the complete ancestry in
`tests/game/test_forced_movement_history.py` around line 83.

**Four existing focused tests passed**: both native spike histories, reached-cell
damage playback, and lethal completion/idle preservation. The latter verifies
corpse position in all four cameras.

Repair: follow `parent_lineage` to the matching actor-entry ancestor, using the
existing history-test approach. Preserve hit count, cell, cumulative HP and
life-state checks. Do not flatten ancestry or infer contact from the trap anchor.

## Passive replay and sensory ownership

The two failures in `tests/game/test_presentation_boundary.py` are
`test_three_intervals_are_complete_passive_and_replay_after_reset` and
`test_pure_reduction_removes_before_after_values_and_copies_payloads`.

Of nine admitted door-demo events, only one differs between native and retained
models: the actor-owned startup `SpatialChangeEvent` at index 15 changes
`use_register=True` to `False`, explicitly applied by `_retained_event` in
`game/presentation.py:581`. Every other encoded field, observer grant and causal
identity matches; private attributes match too. The other eight copies retain
their original flags. Registration policy is not a game-state difference.

All nine retained records survive exact encode/decode/encode equality through
`game/event_record.py`. After full native reset, serialized replay produces
closed/open/closed doors, 4,096 tiles and 43/44/43 visible cells. Final senses equal
the live engine's final senses. EventQueue and BaseObject registries remain empty
through decode and reduction. `PASSIVE_EVENT_REPLAY`, rather than a blanket
false-flag rule, protects that construction boundary.

`PerceivedContact` (`dnd/types/senses.py:41`) is frozen with immutable values.
Ordinary field mutation is rejected. The reducer creates independent contact
dictionaries: clearing input dictionaries leaves reduced contacts intact;
clearing reduced dictionaries leaves the previous snapshot intact. The `is not`
assertion demands an unnecessary allocation, not stronger isolation. Both test
bodies pass their remaining assertions when only the failing assertion is omitted
in a diagnostic run.

Repair: compare complete encoded payloads with the registration-policy difference
accounted for explicitly. Retain causal identity checks and exercise passive
decode/replay after reset. Replace the contact identity assertion with mutable
container isolation checks. Do not change lifecycle policy or add deep copies.

## Bounded repair sequence

1. Correct these five expectations in the three affected test files, preserving
   the observable contracts above. No runtime change is justified by this study.
2. Run all three affected modules and the native/playback spike checks. Any new
   discrepancy requires its own investigation before changing its expectation.
3. Run the broader game suite and existing separate gallery/server lane. Report
   actual remaining failures, if any. Do not carry knowingly failing ordinary
   tests forward under a “pre-existing” label.

No visual-regression framework, replay abstraction, asset audit, hash check or
renderer bookkeeping belongs to this repair.

Independent anti-slop and ECS reviews support this scope. Anti-slop examined
blood concealment, accumulation and subsequent raster assertions. ECS examined
serialized facts, passive registries and state ownership. Its explicit constraint:
do not require every retained event's registration flag to be false, and do not
alter production construction to satisfy that assumption.

Diagnostic logs are `/tmp/dnd-test-failure-study.log` and
`/tmp/dnd-trap-lineage-study.log`; the evidence needed to interpret them is above.
The latter contains three selected tests; the fourth playback test passed in a
separate direct run (2.83 seconds). These are session diagnostics, not new tooling.

## Authorized repair

The user subsequently requested the actual repairs and appropriate feature
coverage. Only the three affected test files changed in this repair; no runtime
code, recipes or media changed, and no tests were skipped or marked expected
failure to obtain a passing result.

| Boundary | Preserved and strengthened coverage |
| --- | --- |
| Hidden residue, immediate/later first sight | Real saved subjective events; independently expected receiving footprint; no donor or hidden trap; all four cameras; actual blood pixels against an otherwise identical state with residue removed. Holding FOV fixed prevents a visibility change from falsely proving blood rendered. |
| Plain/poison traps, walker/operator | Recorded tile after-values; every receiving tile clean before initial contact; one accumulated unit and matching geometric contribution; persistent condition identity and shape; lowering preserves blood; occupied raising adds it at contact. |
| Shaft and floor presentation | Actual application rasters for raised/lowered shafts and visible poison coating across four cameras; floor pixels preserve prior marks at contact, grow on landing and seek backward with the same trap frame/FOV in the comparison; no requirement that every receiving cell contains visible particles. |
| Forced movement through traps | Complete native ancestry to the affected actor's entry, separate reached-cell damage, cumulative HP and lethal result. Existing integrated playback tests also verify the corpse stays at its final reached position across completion and idle in four cameras. |
| Passive replay | Entire recorded payload comparison, with only registration disabling allowed; causal identities; JSON encode/decode after native reset; door, light and sensory results; empty registries after decoding and reduction. |
| Sensory isolation | Incoming dictionaries, resulting entity/object dictionaries and prior snapshot stay independent under mutation; immutable contact values may be shared. |

Floor checks pass sampled state and reveal values through the application draw
function, rather than duplicating the separate texture-sampler tests. This does
not claim exhaustive coverage of every feature combination or replace the
deferred visual comparison tooling.

Independent anti-slop review requested the hidden-blood raster check; that was
added without conflating first-sight FOV changes with blood pixels. ECS review
implemented and verified the passive replay/isolation changes. Anti-slop review
also approved the final application-raster comparisons at contact/settled/seek.

### Verification after repair

- Initial focused runs: **45 passed, 2 existing expected failures** for blood,
  damage, forced movement and residue geometry; **4 passed** for the replay
  boundary. After strengthening application-raster assertions, the final blood
  module rerun passed **11 tests**.
- The initial monolithic game run was terminated with exit 143 before a summary.
  It is not counted as complete. The same complete selection was rerun in three
  smaller filename batches, all of which exited successfully:
  - `test_[a-d]*.py`, excluding the separate gallery files: **703 passed**,
    179.59 seconds.
  - `test_[e-m]*.py`: **159 passed, 6 expected failures**, 123.04 seconds.
  - `test_[n-z]*.py`: **328 passed**, 107.48 seconds.
- Separate `test_animation_review.py` and `test_animation_review_server.py`:
  **11 passed**, 152.52 seconds, including generated videos, saved-input replay,
  paired doorway perspectives and HTTP seeking.
- Total unique final tests: **1,201 passed, 6 existing expected failures**.
  No ordinary failures remain in `tests/game`.

The expected failures are the two forced-movement stair-occlusion cases and four
jump terrain-occlusion cases (uphill/downhill, airborne rear cameras 0/1). They
remain real, separately tracked renderer defects; this test-contract repair did
not change their markers or claim to fix them.

Completed run logs are retained in `.runtime/graphics-cleanup/test-repair-a-d.log`,
`test-repair-e-m.log`, `test-repair-n-z.log` and `test-repair-gallery.log`.
