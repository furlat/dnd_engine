# Production-gap plan ECS / event / DAG review — 2026-10-04

**Initial plan checkpoint: bounded approach is sound; two concrete clarifications
were required before closing plan approval. The final source checkpoint below
supersedes these pending findings.** These concern existing disclosure admission and
ring dispatch. No new event framework, native collision rule, condition owner,
or spell executor is needed. This is a read-only plan/source review, not approval
of an unimplemented consumer. No tests or artwork captures were run.

Reviewed plan SHA256: `d65fa80ef76df6b072f391bc5dae5abd67a9673eb8f129e5597d2d13a2486540`.
Reviewed incoming `production-gaps-20261004-v1` HANDOFF.md SHA256:
`1d61668b9c4402db717df8d70c11d273929648281467ef4b768f049832f9a9e2`.
Source: [HANDOFF.md](/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/production-gap-delivery-2026-10-04/HANDOFF.md). The separate dome-size investigation is
withdrawn and outside this review.

## Required concrete clarifications

1. **Wind must admit the exact interception contact, not only the wall owner.**
   [player_projection.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/player_projection.py:281) currently preserves
   `projectile_deflection_position` when the intercepted owner occurs anywhere in
   current or declaration `spatial_effects`. This proves owner disclosure but not
   disclosure of the contact cell. A partly seen wall can have its interception
   outside the observed portion. The new local gust must require the contact in
   received wall coverage and witnessed cells at the relevant event/declaration
   boundary, using the existing projection inputs. Tangent selection uses only
   that received owner's geometry. An absent or private point must not trigger a
   renderer-side collision search, invented contact or lookup of the live native
   condition. Preserve Shield's separate existing exact-condition attribution.
   Add the partly seen-owner/hidden-contact case to the plan's existing Wind
   disclosure check; a wholly absent owner alone does not exercise this boundary.

2. **The Thorns ring must bypass, rather than enter, the segment-only procedural
   branch.** [wall_assembly_media.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/wall_assembly_media.py:110) selects
   any registration with `thorns`, then discards non-`WallSegment` paths with
   `continue`. A native 10-foot ring would pass dimensions and still never reach
   the existing ring bank. Narrow this dispatch to a procedural Thorns
   `WallSegment`; let `WallRing` reach the existing registered ring sampler.
   Preserve [assembly_media_limitation](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/wall_assembly_media.py:76)'s
   complete-received-shell and no-suppression checks. Whole-ring RGBA cannot be
   admitted on partial visibility, and this work does not authorize a clipping
   framework or revived XYZ. The plan should say this explicitly rather than
   “allow ... through the procedural straight-wall branch.”

## Existing ownership and minimal consumers

Wind already has the required native result. [Attack](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/actions.py:2348)
asks the existing [GridMap.missile_interceptor](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/gridmap.py:1856),
which chooses the nearest admitted owner/contact. It retains
`intercepted_by_condition_uuid` and `projectile_deflection_position` on the
ordinary Attack result and changes the outcome to MISS. [WindWallZone](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/wall_fields.py:159)
uses current contribution admission and the existing `wall_path_contact` law;
no second intersection system or extra hit/miss event is justified.

The client currently retains those passive fields on
[AttackFact](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/player_facts.py:97), but [bind_attack](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/attack.py:311)
still sends the ordinary projectile to the original recipient. Extend the
existing `AttackProjectileTimeline` with bounded passive termination data and
consume it in `sample_attack`, `project_attack_projectile` and
`attack_projectile_contact`. Keep the original release socket, trajectory and
clock; stop at the retained interception and sample height at the same original
trajectory fraction. Merely swapping the target endpoint would change the curve,
height interpolation or speed and is not equivalent to stopping that trajectory.
Ordinary unblocked attacks remain unchanged. The one finite gust belongs to the
same Attack UUID and begins at its interception presentation time, not at native
recording wall-clock time or original target arrival. Its retirement must join
that existing finite action/media path, with no maintained spatial owner.

The existing [condition_reaction.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/condition_reaction.py:104) consumer
handles actor-attached conditions such as Shield. Wind is a spatial owner, so it
must not be fabricated as an actor condition to enter that branch. Resolve the
exact received spatial owner and its authored response data on the existing
attack/choreography path. A closed typed response/material record can select
raster bank versus original continuous mesh source; the accepted
[directed_surface.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/directed_surface.py) rasterizer and registered
media sampler remain the rendering primitives. Pure source geometry/material
sampling may live beside the existing Wind sampler, with leaf data ownership;
no upward native-to-game import or late import is needed. Do not add a dispatcher
keyed on the spell's display name.

Thorns requires only the accepted native geometry correction in
[WallOfThorns.wall_geometry](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/wall_fields.py:262): ring height20→10
feet. Its centreline radius10, thickness5, owner, damage, duration and movement
stay on the existing native condition. The incoming human height clarification
is explicit; it does not alter dome size. Existing ring source windows0–62,
63–126 and128–159, camera mapping[0,3,2,1] and owner application/removal times
remain sufficient once dispatch is corrected. The procedural straight path
continues using its existing geometry, contacts and shared surface compositor.

Cone's three coarse depth bands fit a small optional typed per-view/facing
sort-offset extension to the existing `StudioMediaTrack` and
`StationaryMediaCue.depth_offset_cells` path. Keep it as painter registration,
not a mutation of ground apex, world hit geometry or actual recipient order.
No native change is needed for headings. Call Lightning's complete strike fits
one existing ground-anchored finite track per admitted selected point, with
recipient material responses only for the real received applications. Its
release+31.25ms contact must feed the existing cast/damage timing; multiple
recipients must not duplicate the full strike, and an empty selected point still
has its one visual strike. Existing repeat-action and concentration ownership
remain authoritative.

## Acceptance boundary

The plan's selected-resource importer/storage reuse, original source preservation,
finite lifecycle checks, paired-observer review, four-camera gallery and later
independent implementation review are appropriate. No additional systems or
mechanics are requested by this receipt. After the two clarifications above are
made, the bounded plan has no identified ECS/event/import-DAG design blocker.
Actual source delivery hashes, private installation and final tests/gallery still
belong to implementation acceptance. No external chat was read or contacted.


## Amended plan and implemented source checkpoint

**Approved within this bounded ECS / event / DAG source review.** No remaining
source blocker was found after the explicit corrections below. The amended plan
SHA256 is `ade59da93d24ff8c3b9840697a2a5ed3048b06b1b1c5cae803a40c4d992222da`. The current human instruction permits Cone's
nearest eight-direction bank with a small residual screen rotation, preserving
native arbitrary aim. It supersedes the earlier handoff restriction on this
specific Cone adaptation. It does not change Wind's continuous native tangent
requirement or authorize a dome-size investigation.

This pass reviewed the actual current sixteen-file source/plan snapshot retained
in `SPELL_GAP_ECS_REVIEW_2026-10-04.json`, canonical digest
`9dfe1754183acca63ff7a3d1cf93c4dbb3c517d66548ca98ef869ab71b983dd9`. Original plan findings and their source pins above remain
historical evidence. This approval does not assert that broader test or gallery
work still underway has already passed.

### Findings closed

- Wind projection now requires the actual contact cell in both the exact received
  owner's `positions` and the same snapshot's `visible` cells. Remembered hidden
  positions alone no longer admit a live interception. Current and declaration
  snapshots preserve the existing witnessed-event boundary; the client never
  asks the live map or condition for a hidden contact.
- The retained `AttackFact` remains the only interception result. Its existing
  native owner UUID and XZ point supply the passive `ProjectileInterception` on
  the existing attack timeline. The projectile keeps the original trajectory
  parameter multiplied by the admitted fraction, original bolt length and
  interpolated height. A bounded release-socket registration correction reaches
  the exact retained wall point; the same corrected sampler supplies the logical
  sample and each camera projection. This is explicitly a presentation adjustment,
  not a newly simulated deflection. Installed ranged profiles are straight;
  no new Bezier scenario or collision policy is introduced.
- The original WindHit cross consists of two transparent quads. Both now render
  through separate existing rasterizer passes, preserving the rear plane when
  a nearer texel is transparent. The five original instances, finite0.70s
  envelopes/stagger, delivered transforms/material and existing palette composer
  are retained. The gust belongs to the same Attack UUID, starts at that attack's
  admitted interception time, and clears finitely on the existing action clock.
- A further Cone residual-angle defect was found and corrected during this pass:
  `project_world(direction)` includes map-center translation in camera quarters1–3.
  The final code subtracts `project_world((0,0))` from the projected endpoint before
  taking its angle. Exact headings therefore retain their original banks; oblique
  aims receive only their residual rotation. The selected native direction,
  recipients, saves and damage are untouched.
- Thorns' procedural branch is now restricted to `WallSegment`, allowing the
  existing `WallRing` bank path to run. The native ring is10ft high, radius10ft and
  width5ft; existing damage, duration, movement and ownership remain. The original
  full-shell and suppression guards still refuse an unsupported partial ring.
  Flat procedural Thorns and original ring phase/camera registration remain.

### Composition and source-of-truth assessment

The native-to-client boundary stays unchanged apart from the requested Thorns
height: the engine chooses targets, outcomes and Wind intersections; projection
admits observations; retained data drives presentation. No extra event, action,
condition or spatial owner is fabricated for a local gust. No repeated Wind
passage damage or guessed miss trajectory was added.

Cone's optional `StudioMediaTrack.sortDepthByFacing` changes only the existing
painter key. Ground apex and native 60-foot geometry remain independent of the
three coarse volume depth bands and caster hand fit. Source-oriented bank
selection plus the human-requested residual rotation is data-directed, with no
spell-name dispatch or native aiming restriction. The single Call V5 media track
is ground-anchored once per selected point; its31.25ms contact and actual recipient
responses use the existing finite cast/application clocks. Its four camera assets
and the existing electric hands/contacts create no new cloud or condition.

The import direction is consistent: native leaf geometry values feed
`game.attack`; choreography drawing imports the attack sampler and the Wind
material sampler; the latter imports existing numeric/raster/painter leaves and
has no dependency back on attack or choreography. `cast_media` uses passive
native geometry and established registration/projection. The nine reviewed
Python files contain no function-local imports. No reflection escape, new
content registry, alternate executor or parallel lifetime manager was introduced.
The JSON source-resource selection remains in the existing installed resource
map, not a runtime file scan. The Wind component's authored model is passive
validated source data; its cached sampler does not own gameplay state.

### Evidence and remaining completion work

This reviewer read source and the assigned native-boundary test scenarios but
ran no tests or recordings and edited only audit receipts. The intake producer's
saved `tests-final.log` reports6 passes and its typing log reports zero errors;
the root's saved `.runtime/spell-gap-20261004/typing.log` also reports zero errors.
These are attributed producer evidence, not fresh independent test claims.
The assigned test/gallery lane must still close the native all-camera, oblique
Cone, hidden Wind contact, repeat/empty Call and actual ring lifecycle cases.
A later final evidence/source-delta review is required if source changes again.
Full-ring partial visibility, coarse Cone depth bands and the expressly accepted
Cone residual-image adaptation remain disclosed limits, not missing native rules.
No source, artwork or test implementation was changed by this review; no external
chat was read or contacted.


### Final contact-clock correction included

Approved the subsequent bounded Cone material correction and updated the same
source snapshot. `StudioBodyMaterialTrack.clock` is a passive closed literal
(`release` / `contact`) with existing `release` behavior as default. Cone alone
opts into `contact`. The existing cast-material sampler uses each already-bound
application's `travel_end_ms` and actual outcome gate; negative ages produce no
material. `finite_body_material_end` uses that same per-application start and
finite envelope for both existing cast compilation paths, so the head cannot
retire while a late recipient's frost is still active. Start offsets are applied
once by the shared material sampler, and no separate hit clock or event is added.
The old default-release necrotic material behavior remains. This closes the
before-contact frost risk in source; the assigned test lane owns the requested
precontact/retirement validation. No tests were run by this reviewer.


## G4 circular-source amendment and cold filtering checkpoint

**Plan amendment approved; circular implementation review follows when saved.**
The amended plan SHA256 is
`bc429dcdb7b3872b5446834d0e62061d89c287981cffe3958dd1246bebfaec5d`.
The original `ThornsModules.gd` explicitly has `circular=true`: module indices0–15
use the original uncentered source offsets, circumference33.941125504, centreline
radius4.242640688 native units, circular vertex transform and curved normal
transform. Existing Thorns component data already suffices. Extending the current
sampler is an authorized source-path integration, not new artwork, a geometric
clipping framework or a native rule. The received module filter must keep original
module indices for interior variants and transforms; filtering must not renumber
visible pieces. The existing owner dates, local occupants, committed damage pulses,
finite retirement, suppression spheres and XYZ painter remain the consumers.
The whole-ring RGBA complete-shell guard remains for its fallback only. Earlier
bank-only/partial-ring limitation statements in this receipt describe the initial
implementation and are superseded by this explicit amendment once verified.

The cold-material correction imports only `repeated_texture` from the existing
`directed_surface` numeric module. Read-only AST traversal found an11-module game
import closure from `directed_surface` and no path back to `condition_draw`.
Its fract UVs are clamped to half-texel bounds before the existing bilinear sampler,
which prevents repeat-edge blending and implements the source's LINEAR plus
CLAMP_TO_EDGE law. Original silhouette alpha remains unchanged. No extra material
owner, sampling clock or rendering pipeline was added. Reviewed
`game/condition_draw.py` SHA256:
`f06fa1306466ff36d45b9a4dce3a9f27323c3dbfe24982d67bf0b382643a5b57`.
No tests or production edits were performed for this checkpoint.


## Circular Thorns implementation — source review closed

**Approved in the bounded source review.** Read both final modules against the
original `ThornsModules.gd`, SHA256
`7b9050cc3971bb28a119b22143770635757524f245169344f950ca88e6d3d6b5`.
The fixed16 original slots keep their native uncentered offsets. `vine_mesh`
uses each surviving original module index for interior variation and shift;
only triangle-buffer offsets use local concatenation indices. Filtering therefore
does not reseed or move the remaining modules. No new module model or authored
resource was created.

The source circular law is retained after the existing living displacement:
`theta = x / 33.941125504 * 2*pi`, radius `4.242640688 + z`, and the matching
curved XZ normal transform. The existing normal-scale, growth, dissolve-before-depth,
retirement, original textures, palette and finite two-second living clock are
shared with the straight path. Ring distance replaces segment distance solely
when choosing the existing nearby visual occupants; actual contact pulses still
come from retained native damage dates. The owner UUID and start/removal dates
remain unchanged.

`wall_assembly_media` admits original circular slots by their physical shell
sections intersecting the received ring shell. Unreceived slots are never built;
the code does not promote a partial observation to a full-ring image. Existing
received suppression positions retain geometric registration, while the existing
`ExcludedSphere` values mask the same shared `SurfaceVolume`. The registered
whole-ring fallback still has its complete-shell/no-suppression guard when no
procedural Thorns source exists. No native collision or visibility calculation
was replaced, and source geometry was not reconstructed from the revoked XYZ
payload. Root's real-observer recording and the assigned test lane remain the
visual/evidence acceptance boundary.

The additional `WallSegment` / `WallRing` typing correction moves `frozen=True`
from each model's existing `ConfigDict` into its class header. The immutable
Pydantic contract, fields and validators are unchanged; static typing can now
recognize their existing hashability in the bounded surface cache. It adds no
mutable cache key adapter, reflection, value wrapper or dependency edge.

Final reviewed delta pins:

- `game/thorns_surface.py`:
  `a55e06bfac99f7529bff2f86ef69ecbca3d426b8079fcf6a32b5c6e102788585`.
- `game/wall_assembly_media.py`:
  `1972bc005f15bb9185cb20a58cd43e7b33d991cd79b503eea96aa38349f79009`.
- `dnd/core/presentation_geometry.py`:
  `a10ca4d4006230f273c754e95b5077b805afecdc52b556b3bf4d2bc90adb4ba3`.

No source blocker remains in this amended G4 or cold-sampler delta. The combined
sixteen-file manifest above is updated. No tests, recordings or production edits
were performed by this reviewer; test and gallery results must be attributed to
their actual producer. Later source changes need an explicit delta review.


## Final bounded source and scenario review — G1–G4 closed

**Approved within this ECS / event / DAG review; no unresolved source blocker.**
This final checkpoint supersedes the temporary frozen-header/cache paragraph
above. The final nineteen-file source, plan and test manifest is retained in
[SPELL_GAP_ECS_REVIEW_2026-10-04.json](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/SPELL_GAP_ECS_REVIEW_2026-10-04.json),
canonical SHA256 `015505988090b2b82bcada645363c60f994b52350b20181cc18c4922fc45261d`. The approved amended plan remains
`bc429dcdb7b3872b5446834d0e62061d89c287981cffe3958dd1246bebfaec5d`.

Only two entries changed from the prior sixteen-file review:

- `game/thorns_surface.py` is now
  `902e56b3d0c28a473fd81e420f8da742cbf35bef526ce374a7bb13e52c54ff00`.
  `vine_surface` receives primitive centre coordinates, an optional straight
  tangent and source length. Circular uses `None` for tangent and the original
  sixteen source slots; straight passes the same normalized tangent, midpoint
  and length as before. These are numeric sampler inputs, not a new geometry
  model, cache wrapper or mutable gameplay state. Source transforms, normals,
  variants, clocks, owner and suppression admission remain as reviewed above.
- `dnd/core/presentation_geometry.py` is now
  `2a19b41f3c1d67b7c810775accb95a659b992e1fa515de3106755b20dd266438`,
  exactly matching the pre-gap final-source snapshot. Both attempted class-header
  changes are fully reverted. There is no native geometry-model change in this
  cache correction.

`game/wall_assembly_media.py` remains
`1972bc005f15bb9185cb20a58cd43e7b33d991cd79b503eea96aa38349f79009`. Its circular path preserves original
section indices, builds only sections admitted from the received shell, and
passes the existing exclusion spheres to the same XYZ painter. There is no
whole-ring disclosure promotion or additional native collision query. The
whole-RGBA fallback still requires complete shell coverage. The same original
`ThornsModules.gd` hash and equations recorded above were checked again; the
primitive-key change introduces no import edge, event or executor.

### Authored native scenarios and assertions

Read the complete final
[production_gap_scenarios.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/game/production_gap_scenarios.py)
and
[test_production_gap_delivery.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/game/test_production_gap_delivery.py),
plus the bounded repeat hunk in
[area_spell_scenarios.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/game/area_spell_scenarios.py).
The scenarios create real encounters, discover legal actions, execute them,
retain observer-specific bytes and reduce those bytes through the ordinary
presentation path. Fixed dice/save support controls outcomes without fabricating
spell events. Cleanup restores the runtime and random state. Call's moved repeat
uses the available Move action before discovering its real repeat target; default
existing area scenarios retain their previous behavior.

The eighteen final cases cover eight Cone headings plus oblique aim, unchanged
native full/half save damage, caster ground apex, four-view residual registration,
separate painter depths, frost absent before contact and after retirement, and
preserved current-pose alpha. Call checks initial/repeat delivery, actual caster
movement, an empty selected point, real recipients and concentration removal.
Wind checks cardinal/diagonal/oblique native interceptions and an unblocked bow,
unchanged target HP on interception, retained exact endpoint in four cameras,
same-owner finite gust timing and deterministic repeat sampling. Ring assertions
use naturally partial native observations, formation/loop/real removal, empty
coverage rejection and stable original module variants after filtering.

The ring suppression assertion directly checks the existing received exclusion
volume; it is not represented as a new native moving-Antimagic scenario. The
native ring history proves ordinary lifetime/removal and partial observation.
The numeric original-slot comparison protects source identity rather than a new
rule. No fixture widens received shell cells merely to make the ring visible.
No new rule, duplicate owner, event pipeline or test-only runtime fallback was
found in these files.

### Final attributed evidence and limits

This reviewer inspected, but did not execute, the saved producer evidence:

- `.runtime/spell-gap-20261004/dnd-production-gap-delivery-closed.log`:
  eighteen final gap cases passed.
- `.runtime/spell-gap-20261004/dnd-production-gap-delivery-final.log`:
  forty-one earlier combined cases passed (seventeen gap plus twenty-four
  existing area cases, as identified by the producing lane). The eighteen-case
  final run replaces the seventeen-case gap portion; these are not claimed as
  fifty-nine distinct tests.
- `.runtime/spell-gap-20261004/typing-closed.log`: final scoped typing reports
  zero errors and warnings. Earlier saved gap architecture and attack/projection
  regression logs report thirty-seven and seventy-six passes respectively.
- `.runtime/spell-gap-20261004/acceptance-summary.json`: the producer records
  eight final clips, 148 checks and zero presentation gaps, in two retained runs.
  This is recorded gallery evidence, not a claim that this reviewer manually
  inspected every frame. Exact evidence hashes are in the receipt JSON.

The source-of-truth boundary is unchanged: native rules choose outcomes and
interceptions, observed facts admit disclosure, and existing timelines/material
samplers render the received result. Coarse Cone depth bands, the human-approved
small residual bank rotation, and the established source/palette composition
limits remain explicit. The withdrawn dome-size investigation stays outside
scope. No tests, recordings, artwork or production source were changed by this
review; only this receipt and its digest were updated. No external chat was read
or contacted. Further production changes require a bounded delta review.
