# Poison Spray: bounded delivery correction

**Later user correction:** Fire Bolt’s normalization described below was rejected. Its original authored projectile record is restored, with both standing reference videos byte-identical to the earlier approved output. See [Sleep and Fire Bolt correction](SLEEP_POSE_CONTACT_2026-09-20.md). Other spell placement changes are unchanged.

The user rejected the current `20260920T191252Z-4269df` gallery's direction,
apparent backside emission and long drifting cloud. The earlier size/contact
checks did not establish that the whole animation communicated the spell.

## Actual rule and observed defect

`PoisonSpray` targets one enemy within 10 feet, with line of sight and a
Constitution save that negates damage. It creates no area, persistent field or
damage to creatures along the visual path. These native rules remain unchanged.

The new export preserves particle size but bakes a long free flight into the
image. Its emitter stops about 0.5125 seconds after start (the End animation has
an additional 0.2-second key), and particles live up to 1.3 seconds. The source
centroid travels hundreds of pixels beyond close recipients. Playing its whole
tail after the measured contact reproduces that overshoot.

The fixed release socket is applied as authored. In the adjacent diagonal case,
camera 2 projects the forward palm just past the target's body anchor. The
remaining screen distance is 9.54 pixels and the entire baked stream rotates
109.2 degrees. A short, foreshortened journey becomes a long sideways stream.
The Godot author independently confirmed that the source banks themselves are
correctly labelled and there is no source emitter translation.

## Repair proposal

1. The Godot author produces a compact local version of the same smoky puff and
   a local arrival/dissipation phase, using the same palette and pixel scale.
   The export contains local particle motion, not the whole world journey.
2. Use the existing sprite-projectile recipe and executor for the one observed
   recipient. Its existing source sockets, body target, height projection,
   travel interval and impact phase own placement. Keep the current release and
   400-ms arrival. No new spell renderer, geometry framework or backend effect.
3. Keep the isolated casting-hand layer. Correct its sockets only if actual
   visual comparison demonstrates a separate registration error.
4. Remove the superseded Poison distance/contact tables and their newly added
   sampler/schema extension if no remaining recipe uses them. Keep ordinary
   authored timing and the shared finite-media sampler for other spells.
5. Keep import as media/registration copying; author the recipe separately.
   Remove superseded unreferenced Poison pages after replacement is verified.

## Verification boundary

Replay the same eight saved subjective inputs: close/far, axis/diagonal, caster
and perceiver, all four cameras. Inspect onset, approach, contact and the entire
tail. The cloud must leave the hand, stay compact, reach the body, and dissipate
there without appearing to sweep more tiles. Native events and damage outcomes
must be unchanged, including successful saves. Add meaningful rendered
registration/trajectory checks at these phases; a single contact-pixel test is
insufficient. Recheck existing direct/touch and projectile timing regressions.

## Independent review

Anti-slop reviewer: `/root/graphics_antislop` — approved before editing.
Anti-OOP/ECS reviewer: `/root/graphics_ecs_review` — approved before editing.
The Godot author owns media and independently checks source motion.

Both reviewers identified the existing ordinary travel policy as the correct
clock owner: 400-ms minimum plus speed 1000 reference pixels/second covers this
10-foot matrix. `targetLocal` has different semantics and is not used. Existing
tangent bank selection handles the short projected direction without rotating
the original grid bank through a large angle. Full-cell pages fit the existing
sprite renderer; no sparse-offset extension is needed. A direct eight-facing
inspection of the actual Attack5 release frame confirms the existing source
sockets are at the outstretched palms; no socket edits are justified.

Support/healing integration is parked while this reported defect is corrected.
Its read-only study found healing HP timing, source-only cast binding and
condition-layer pair truncation to address later. True Strike's child attack
needs the existing native admission binding; no replacement attack model.

## Implementation and evidence

Selected media: `poison-local-v1` from the Godot task's
`output/weapon-vfx/poison-local-fix/delivery`. Same source smoke, particle size
and literal palette; local velocity 0.6–0.9, lifetime 0.55 seconds, emission
shuts down directly at tick 42. The 58 travel frames and 86 impact frames are
consecutive observations from one 144-Hz simulation, with the same 256px cell
and center pivot. The existing normal-blend projectile renderer plays them.

The independently authored recipe moves its unchanged palm sockets from the
finite-media track to the existing projectile contract. Native Poison Spray and
its event data are unchanged. `MediaContactPoint`, `contactFramesByFacing`,
runtime distance interpolation and its duplicate placement distance are removed.
Ordinary media time maps remain for their actual consumers. The media-only
importer copies phase pages without rewriting recipes or unrelated assets.
The new 24 PNG pages total 2,848,368 bytes; eight unreferenced range-v3 pages
totaling 12,957,263 bytes were removed. Source deliveries remain with their author.

The [new gallery](http://127.0.0.1:8767/runs/20260920T194623Z-83d5aa/index.html)
passes all eight clips. Each input is byte-identical to its previous recording;
release, arrival, damage reaction, HP, flash and floating-number timestamps also
match. Only the excessive decorative tail is shorter. Root inspected onset,
contact and dissipation, including adjacent diagonal camera 2. The short chord
remains correctly foreshortened, without a long stream rotating out of it.

**90 focused tests passed in 15.27 seconds; selected Pyright: zero errors.**
Checks include real native saves and damage, compact rendered pixels throughout
the journey and decay across five placements, three heights, two zooms and four
cameras, exact palm/body registration, seek parity and direct/touch/area/projectile
regressions. Height variations are renderer placement probes, not newly captured
native eligibility scenarios. Human approval of the new motion remains separate.

Final independent ECS review found no blocking regression and reran the 36
direct-media tests successfully. The Godot author separately inspected the
adjacent-diagonal four-camera sequence: the roaming tail is gone and camera 2's
overlap stays local. That specific visual confirmation does not stand in for
human approval of every clip.

## Rejected contact height and common target correction

The user rejected the new gallery's low target contact. Earlier tests verified
agreement with the existing `(64,72)` body anchor but did not establish that it
was the intended torso point. Ray of Frost and Ice Knife still had a separate
`liftY=-12` correction: those spells therefore hit `(64,60)` while Poison did
not. This was an integration/authoring inconsistency.

The modular rig now owns the common `(64,60)` torso point. Ray and Ice Knife's
compensating lifts are removed, preserving their modular contacts. Poison,
Acid Splash, Guiding Bolt and Eldritch Blast use that same point without their
own vertical corrections. Packaged rigs retain their own authored anatomical
points; the removed ice correction no longer arbitrarily lifts those points.
Target-body media also consumes the common anchor, so Shocking Grasp and the
target-local Chill Touch are included in the combined visual review. Ground
effects retain their separately authored ground registration.

The unchanged eight Poison inputs replay successfully in
`20260920T201431Z-9de474`; root inspected arrival pixels in all four cameras.
This is an intermediate repair capture, not a substitute for the requested
combined gallery. Fire Bolt's legacy canvas/forward-offset placement is under
separate pixel audit before claiming all incoming spells share the same point.

That audit demonstrated Fire Bolt's actual drawn core varied around the target
with camera direction; checking its abstract endpoint missed the legacy canvas
compensation. Its authored sprite now registers the actual center `(64,64)`;
the recipe selects the same body target and existing measured Attack5 hand
sockets. No art or renderer branch changed. This legitimately changes travel
duration where the actual palm-to-body distance differs from the old insets;
speed, release, minimum duration and phase policies are unchanged. The shared
target check now passes for seven spells in all four cameras at ordinary and
scaled/elevated contacts. Before/after pixel montages were inspected by root and
the independent reviewer. The main task owns this placement repair; new artwork
was not needed.

The complete catalog review also found Magic Missile still using the old
canvas and target insets. Its recipe now registers the 256px canvas center,
selects the common rig-body point and explicitly authors its Special1 source
base with the old 64-reference-pixel padding removed (`-16 - 64 = -80`). The
existing axis inset follows the corrected source/target chord, so exact old
launch coordinates and arrivals are not claimed. Root inspected old/new launch
and actual arrival images. Original spread, stagger, speed, palette, projectile
media and native multi-target mechanics remain. No new renderer path or art was
needed. The independent ECS reviewer checked this normalization and the tests.

Actual-draw contact coverage now includes eight incoming spells, both modular
and packaged goblin targets, two scale/elevation configurations and four cameras
per case. Legacy Studio numeric geometry tests explicitly load their original
imported recipe; production tests exercise current selected data. This preserves
import compatibility without claiming the obsolete insets describe current art.
