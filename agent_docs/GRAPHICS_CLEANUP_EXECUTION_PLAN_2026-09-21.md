# Unified graphics cleanup and bug-fix plan

Date: 2026-09-21. Branch: `codex/recovery-design`.
Status: independently reviewed, implemented and validated within this scope.
Exact test runs, visual evidence and remaining preexisting limits are recorded
in the [implementation result](GRAPHICS_CLEANUP_IMPLEMENTATION_2026-09-21.md).
Preceding evidence: [full system review](GRAPHICS_SYSTEM_REVIEW_2026-09-21.md).

This replaces that review's preliminary cleanup order. It incorporates the
user's correction: Fire Bolt may adopt the shared targeting representation and
implementation, provided its approved rendered behavior is preserved. Its old
JSON and historical execution quirks are not the acceptance target.

## Intended result

Ordinary new spells select existing meaningful presentation capabilities through
authored data. Every effective choice has a clear owner. Shared functions resolve
attachments, delivery, contact, consequences and historical state. Pygame draws
the result; native gameplay supplies the recorded facts. Future NeuroClient work
can reuse the records and their explicit execution semantics.

The work is complete when the demonstrated defects are fixed, the active test
suite collects and passes, known terrain cases have been adjudicated, and the
affected approved references survive the representation changes. A successful
handful of videos, unchanged recipe bytes or a zero-gap report alone is not done.

## Design boundaries

| Owner | Responsibility |
| --- | --- |
| Native ECS and event progression | Outcomes, costs, handlers, conditions, spatial geometry, origin/range, life state, item state and concentration ownership. |
| Subjective projection and recorded facts | Exactly the permitted causal information, observations and state, including initialization. Complete lineages remain the presentation unit. |
| Authored presentation | Body/media selection, contact timing, attachments, pivots, phase scales/rotation, palettes and finite/persistent appearance. |
| Shared binding and sampling | Resolve those records against historical facts; coordinate existing capabilities on the owning lineage's clocks. |
| Pygame adapter | Load selected media, project, transform and composite. No gameplay decisions. |
| Offline media intake | Translate packaging, copy selected media and update its registration/storage. No implicit changes to spell behavior. |

The latest subjective state can continue advancing while historical playback runs
at its own authored pace. Neither that separation nor parent/child ownership is
being redesigned. No new native event, entity flag, handler hierarchy, expression
language, animation-manager hierarchy or additional event registry is justified
by the confirmed defects.

## 1. Authoring changes: what is missing and what already exists

The local `dnd.spellStudioDrafts` format already extends original NeuroStudio.
Extending it for a concrete new capability is legitimate. Adding fields to hide
a consumer bug or making every implementation detail configurable is not.

| Subject | Decision for this cleanup |
| --- | --- |
| Actor attachment basis | Make root/body/ground meaning explicit and actually honored. Add `rigRoot` alongside existing `body` and `tileCenter` where the existing root placement must be represented. Use existing source sockets for measured hand positions; do not measure new keypoints just for cleanup. |
| Actual-path inset | Promote the existing `axisPx` idea to target anchors as well. `forwardPx` is along the authored facing; `axisPx` is along the resolved source-to-target chord. Do not overload one with the other based on anchor basis. |
| Image registration | Keep scalar `anchor`, optional per-facing pivots and existing sprite override. Their meaning must be the image point placed on the resolved attachment. The presence of an eight-row table must not secretly switch the attachment algorithm. Convert selected legacy compensation into authored placement. No additional registration-mode enum is currently justified. |
| Units and transform order | Document source-cell points, reference-pixel offsets, normalized image pivots, actor scale, visual horizontal scale, world support height and camera zoom separately. Document which values participate in the travel clock. |
| Phase scale, rotation and time mapping | Already implemented fields: preserve them. Fireball travel can rotate while its explosion does not. No additional spell-specific orientation fields. |
| Downed body presentation | Add optional state-selected body pose/entry/recovery data to the local lifecycle presentation, using existing body-animation values and rig clips. Current lifecycle contexts contain feedback only; DYING/STABLE do not have a held downed pose. Recorded `LifeFact`, not a fabricated Unconscious condition, owns this selection. |
| Conditions and contact clocks | Existing membership, rest-pose attachments, body transitions and contact definitions remain. Reuse their shared sampling mechanics; preserve actual damage commit offsets rather than forcing all HP changes to projectile arrival. |
| Finite cast and movement media | Existing `media`, attachments, phase mapping, motion fit/contact, movement-rate and condition selectors already express selected behavior. Document and exercise them; no second timeline language. |
| Areas and maintained fields | Existing recorded footprint/geometry, deployment and lifetime/media bindings remain authoritative. Do not infer mechanical reach from transparent pixels. |
| Body releases and floor state | Existing native material/receiving regions plus selected presentation responses remain the owners. No new spell-by-spell blood code. |
| Selected media source | Record the selected asset/phase delivery and its source in the existing offline intake/binding ownership. Selection must be explicit before import; importer invocation order is not authoring. |
| Native replay fields | No new fields required. Restore compatibility for the two demonstrated historically absent optional facts without manufacturing values. |

### A small format revision, not a replacement language

Use a local `dnd.spellStudioDrafts` version increment for the attachment-semantic
change. Keep the existing Studio record structure. Version 1 and original
NeuroStudio v6 inputs must retain their documented old meaning during conversion;
do not silently give an old `tileCenter` or `forwardPx` a different meaning.

Convert legacy records at the existing authoring-load/import boundary into the
same passive records used by current authoring. Selected local recipes should
be written in the new explicit form after their conversions are checked.
Unchanged imported references remain source/history, not a competing editable
owner. Historical interpretation belongs at that boundary, not in a second
per-frame executor. Keep conversion functions narrow and deterministic.
Compatibility here covers executable selected records and retained supported
reference cases. It does not promise to implement every dormant combination in
the original NeuroStudio schema. Populated unsupported tracks stay explicitly
reported until a separately required capability supplies their consumer.

For each new field document its owner, units, omission/default behavior,
precedence and one existing case requiring it. Update the Pydantic records,
selected JSON and `PRESENTATION_CONTRACT.md` together. Reuse current loader and
semantic tests; no duplicated hand-maintained schema registry, TS runtime,
external materializer or automated asset/source audit is needed by the game.

Old spell-format conversion and old event-record compatibility are different
boundaries. A recipe format revision must not invalidate saved subjective events.

## 2. Fire Bolt: preserve the result through explicit geometry

The selected Fire Bolt uses a 128-pixel canvas, bottom pivot, phase scale 1 and
legacy compensation `(0,-64)`. The compensation is added to endpoints with each
actor's scale before path insets, then removed from the projected draw point.
The image's placement completes the cancellation. Its modular rig root padding
is 41 pixels, giving an effective visual center `41 - 64 = -23` pixels above
support before actor scale and the path inset.

The ordinary modular torso is at `(64,60)`, or `60 - 128 + 41 = -27` pixels.
Blindly selecting that point moves the spell. A `+4` body lift would reproduce
the modular vertical base but is not a general multi-rig conversion. Moreover,
Fire Bolt's `-16` target offset follows the actual adjusted chord, not the nearest
authored facing. Height changes and noncanonical directions expose the difference.

The candidate explicit conversion is therefore:

- Preserve root-relative placement using `basis: rigRoot` and lift `-64` on
  source and target, including the existing per-facing source override.
- Preserve source path inset `axisPx: 24` and target path inset `axisPx: -16`;
  clear the formerly overloaded target `forwardPx`.
- Register the selected sprite by its center through the existing pivot override.
- Keep casting pose, release, preparation, travel speed/minimum, frame rates,
  curvature/orientation, colors, impact and damage timing unchanged.

These are derived values, not new aesthetic tuning. The implementation must
prove the complete conversion before selecting it. Do not reduce acceptance to
the modular rig at unit scale or to the endpoint coordinates before rasterization.

A disposable planning probe has already checked the coordinate conversion:
10,368 rendered projectile-layer comparisons across eight rigs, three scale
pairs, three position/height cases, standing and the rigs' authored `Die` rest
points, three samples in each phase, four cameras and two zooms. It found zero
pixel/destination/blend differences and zero release/anchor/completion timing
differences. Evidence:
`.runtime/graphics-audit-20260921/probe_fire_bolt_attachment_conversion.py` and
`fire-bolt-attachment-conversion.log` in that directory.

The probe uses current implicit root behavior and overloaded target forward
inset as proxies for the proposed explicit fields. It proves the numerical
conversion, not the as-yet-unimplemented new resolver, complete actor/world
composition or device correction. Those remain implementation acceptance work.

The common resolver must distinguish attachment position from image padding and
resolve source/target scale, support, pose displacement and path inset in a stated
order. A finite cast track and a projectile targeting the same body attachment
must obtain it from the same shared body-placement calculation. Device emission
continues to use the recorded item's measured muzzle. Distinct timing and display
coordinate spaces remain explicit: camera rotation must not retime gameplay
presentation, and image dimensions must not become the native range metric.

One related source-item case needs its own assertion: the old Fire Bolt canvas
compensation is currently also added after the device muzzle override. Removing
it should make a device shot start at the actual muzzle. That is a correction to
an inherited device placement problem, not a reason to offset every cannon or
retune the approved mage spell. Existing approved cannon spells have zero such
compensation. Verify their launch arc and contact unchanged.

### Equivalence evidence

Use the same retained event inputs before and after. Cover preparation, release,
mid-flight, contact and settled impact; all four cameras; canonical and oblique
shots; unequal actor scales; raised/lowered contacts; rig differences and sleeping
recipients. Check actual composed image positions/pivots, selected rows/rotation,
contact and completion clocks, pose displacement and depth/occlusion.

Use representative saved gallery clips, numerical geometry checks and ad hoc
before/after frames. No universal baseline project or pixel-diff test framework.
Where a changed rounding order produces different pixels, inspect and account
for it rather than declaring raw coordinate equality sufficient. Keep the old
selected output available until the conversion satisfies these observations.

## 3. Work sequence and acceptance

### A. Make the existing checks and references trustworthy

Keep a reference to the committed plus current working state and affected saved
inputs. Label known approved results, unreviewed captures and known defects in
the existing implementation/review records. Do not regenerate every clip.

Repair the 52 classified stale test cases by their actual semantic contracts:
selected door silhouettes, native door state, deliberate authored attachment
changes, death-specific causal children, historically valid legacy fixtures,
residue coexistence and complete initialization values. The audit contains the
case-by-case evidence. Keep their substantive HP, chronology, identity, masking,
disclosure and replay assertions. No blanket snapshot/count updates.

Restore collection of active assertions in the five import-blocked modules.
`test_spellcasting.py` must retain its native tests; only one current import is
solely for the old server catalog consumer. Preserve catalog/event identity via
the active boundary. Extract native encounter/controller assertions from the
mixed server modules. Explicitly retire obsolete HTTP/session consumers outside
the active test lane with a recorded disposition. Do not rebuild the retired
server, skip whole mixed modules or disguise failures with `importorskip`.

Acceptance: an ordinary documented active game/engine command collects without
an ad hoc five-file ignore list. Every retired assertion has an explained scope;
every still-relevant assertion has a current home.

### B. Restore saved-input and media-selection stability

**Native recordings:** admit historically absent `temporary_hit_points_grant`
and `resolved_speed_feet` as unknown/`None` at the existing recording boundary.
Keep required causal identity and disclosure strict. No generic acceptance of
every defaulted model field. Missing speed must preserve historical timing rather
than become zero or a manufactured 30 feet; missing grant must not invent an owner.

Replay the actual Thunderwave, invisibility, device volley and mixed-residue
archive reproductions through decode, projection and reduction. Also replay
their retained public inputs directly with an empty engine runtime. Preserve
initialization events, complete lineages, equipment/active sets and private-data
exclusion. No recapture required to repair an old archive.

**Media intake:** make the selected cantrip bundle and Poison Spray replacement
explicit inputs to the offline import. Preserve unrelated asset entries and
storage. Rerunning an older full-bundle command must not silently downgrade the
selected travel+impact asset. Retain the selected recipe, registration, palette
and phase semantics through reimport into a temporary output root.

Prefer the existing bindings/source metadata and a small explicit CLI selection;
add a small manifest field only if that information has no current owner. Do not
introduce a dependency/build orchestrator, source hash, startup scan or recipe
generator. Inspect the other current importers for the same demonstrated whole-
catalog replacement pattern; share only genuinely repeated packaging operations.

Acceptance: actual old native/public recordings work; ordinary reimport followed
by selected-media updates and repeated selected import produce the same effective
current assets. An unselected historical package cannot replace selected content
silently. Enabled phases remain compilable and authored behavior remains unchanged.

### C. Implement the explicit attachment contract and migrate Fire Bolt

Apply sections 1–2 at `animation_types.py`, the existing authoring load boundary,
the shared attachment/registration functions and the affected selected recipes.
Unify the common body/socket arithmetic used by cast media and projectile media.
Keep small functions and passive records; introduce no manager or callback graph.

Migrate all selected records whose meaning changes, while retaining the same
effective values for unaffected recipes. Test the existing imported reference
conversion too. Source basis must not be ignored, scalar versus directional
pivots must not change the algorithm, and actual-chord offsets must not become
facing offsets. Preserve the existing reference travel-clock convention.

Acceptance: Fire Bolt's mage output passes the equivalence evidence above;
shared torso spells still hit the same body point; resting targets still move
only the recipient contact; cannon shots start at the muzzle; Fireball's ground
impact remains unrotated; Magic Missile retains tangent-following A/B/A delivery.
No spell-ID branch, universal pixel offset or one-camera compensation is added.

### D. Close damage/life integration through the existing owner

Fix both the rejection in `compile_cast` and the terminal-death-only assumptions
later in cast sampling. Removing the guard by itself does not fix the contract.
Use the existing recorded damage and life facts and shared lifecycle/body rules.
One owning application commits its disclosed HP/life result at its authored
damage/lifecycle point relative to contact; nested reactions own their own
consequences. Preserve existing impact delay and HP callback timing, including
the current floating-number-frame convention. Preserve downing HP normalization already
recorded by the engine. Do not infer life state from HP or call DYING a death.

There is an additional presentation gap here: native downing installs capability
modifiers directly, not an Unconscious condition instance, and the current
lifecycle context has feedback but no downed pose. Extend local lifecycle
authoring with optional state-keyed body presentation (for example
`lifeState.bodyPoses.dying` / `.stable` with `bodyPose`, `applicationBody` and
`removalBody`, reusing existing body-animation fields). Both states may select
the existing fall/rest clip and reverse recovery. The implementation should
reuse the existing finite body/rig sampling, not condition membership or a new
animation engine. Entering STABLE from DYING with the same pose must not replay
the fall. Actual death has its own authoritative state and existing presentation;
it must not stand the actor up to fall again. Revival clears the downed owner;
other still-present pose owners, such as Sleep, remain effective.

This selection is the only additional lifecycle authoring needed by the
demonstrated case. Keep the original feedback rows and native modifier/event
semantics unchanged. Do not add per-spell flags or new native data.

Use real event histories for alive-to-dying, initially dying/stable recipients,
terminal death and repeated applications crossing a state boundary. Check legal
native outcomes, ordered contacts, held downed/dead pose and no duplicate damage
or life animation. Retain Sleep's fall/hold/wake behavior and actual death priority.

Acceptance: the existing 4-HP Fire Bolt reproduction has a cast and correct final
state, without the obsolete gap; subsequent histories and scrubbing preserve
their received state. Downing/rest/recovery uses the authored state selection,
including DYING-to-STABLE continuity, later death and healing/revival. Standing
reference spells, melee, reactions, blood and sleep/waking retain their original
timing and output. No per-spell `supportsDying` flag.

### E. Complete native origin adoption across the relevant spell catalog

Inventory remaining direct caster sensory-distance checks and classify them as
primary target validation, secondary chain/area/aura distance or unrelated rules.
Change primary target-range checks to the existing `get_target_origin` /
`get_target_distance` / effective-range owner, including discovery and execution.
Do not perform a text replacement across all distance calls.

Acceptance includes the five-foot operator/cannon/target reproduction for Hold
Person and Chill Touch, plus currently authored affected spells such as Ice Knife
where inspection establishes the same primary-range bypass. Test ordinary mage
range, device range override, sector boundaries and operator perception alongside
real execution/costs. Preserve eligibility, concentration owner/capacity, source
attribution and legitimately separate secondary distances. No new native field
or per-cannon spell implementation is required.

### F. Resolve remaining visual and contract debt

The six terrain expected failures need a bounded investigation using their
existing jump and forced-movement scenes. In particular, a test requiring more
than 100 visible body pixels is not by itself proof of incorrect occlusion.
Inspect the actual contact/height, foreground geometry and composed frames.
Correct demonstrated errors in the common depth/compositor owner; preserve
legitimate foreground hiding and replace invalid readability thresholds with
the established geometric requirement. Remove xfail markers only after the
intended behavior is established and passes. No flight or terrain-system rewrite.

Correct the Fire Bolt contract to describe the actual result and, after migration,
its explicit representation. Update current schema fields/precedence and the
existing coverage view. Keep selected binding, executable capability, observed
run and approved output distinct. Enable no currently dormant recovery/area-sprite
tracks merely because they parse; keep accepted potion source-media omissions.
Coverage should report a selected unsupported capability instead of silently
pretending it renders. Keep its stdout usable JSON without Pygame's greeting.

Reduce misleading current-status duplication in `RECOVERY_PLAN.md`: retain a
short current state and links to the implementation/audit records. Preserve the
user's corrections and prior decisions; archive chronology rather than silently
rewriting history. Do not mix this with an unrelated documentation reorganization.

## 4. Verification and completion

Run focused tests for each changed owner, then the active game/engine suite once
after the integrated changes. Include the currently manual native device tests
affected by origin/concentration/health behavior, active-package typechecking and
the dependency/DAG checks. Broaden or repeat only for new failures or changes.
Report the exact command, counts, exclusions and remaining defects honestly.

Use a bounded visual matrix assembled from existing saved inputs:

| Shared capability | Reference cases |
| --- | --- |
| Attachments and orientation | Fire Bolt, Poison Spray, Ray of Frost/Ice Knife and tangent Magic Missile; oblique/raised/unequal-scale/resting contacts. |
| Device versus actor source | Mage/cannon Fireball, Sleep/Web and one source-muzzle placement assertion. |
| Consequence ownership | Downing/death, repeated A/B/A applications, reaction attack during movement and Sleep waking. |
| Local and maintained media | One support/buff, one direct/local spell and an existing area deployment/removal. |
| Environment/depth | New smooth-door open/closed silhouettes, a trap injury with residue, jump and forced movement over existing raised terrain. |

Each affected visible reference uses four cameras and the existing observer
perspectives. Numerical/unit checks can cover a broader parameter matrix cheaply;
do not render every permutation of every spell. Save traces for a changed case,
not a new instrumentation stream. Keep native gameplay and frame/capture timing
separate if a performance regression actually appears.

Completion requires:

1. The four reproduced runtime/import/replay defects are fixed through their
   existing owners, including projectile downing and catalog-wide origin adoption.
2. Fire Bolt uses the common explicit attachment implementation with preserved
   approved mage output and documented device correction.
3. Authoring extensions have complete execution semantics and version conversion;
   ordinary new content requires no importer-generated behavior or spell branch.
4. Active tests collect normally and pass, and all six terrain cases have a
   supported disposition. No unexplained failures or silently carried exclusions.
5. Relevant saved inputs still replay independently of engine execution and
   retain permitted state/causality; affected visual references remain available.
6. Current documentation and coverage describe what actually executes. Human
   review status is accurate; automated captures are not called human-approved.

If investigation discovers a genuinely different gameplay decision, describe
the concrete case rather than inventing a rule. Ordinary implementation choices
and independent work in the remaining units can continue under the agreed plan.

## 5. Independent review

Anti-slop and anti-OOP/ECS reviewers are required by `AGENTS.md` and participate
in this plan. Their scope is correctness, ownership, preservation of observed
behavior, unnecessary abstractions/fields and verification quality. Their
agreement does not replace native event or actual image evidence.

Both reviews are complete. The anti-slop reviewer approved the plan and supplied
the Fire Bolt conversion probe, with the restriction to supported legacy
records now stated in section 1. The anti-OOP/ECS reviewer approved with two
corrections now included in D: downed body appearance is genuinely missing and
requires presentation data; existing HP commit offsets must remain relative to
contact rather than being flattened to arrival. Neither review requires new
native fields, a generalized animation system or a broad optimization project.
