# Recovering the approved blood distribution

Status: implemented and independently reviewed after rejection of the modest
tuning. [The 28-clip review gallery](http://127.0.0.1:8767/runs/20260920T001053Z-bfa9ce/index.html)
is ready for user visual review.

## Requested result and evidence

The user rejected gallery `20260919T235102Z-e50471`: blood stayed close to the
victim and looked static, unlike the inspected two-goblin scene. The art task
relayed the user's clarification: that original scene is the high-gore reference;
the desired game result is moderately high, not necessarily its full volume.

The exact reference is `http://127.0.0.1:8778/blood-fluid/?review=hit-accumulation`.
The art task verified its source against its approved snapshots. Default A lot
has 96 independently timed droplets; their endpoints span approximately 2.7 by
1.6 tiles, with persistent irregular lobes extending farther. The integrated
compact replacement has 28 droplets fitted repeatedly into tiny ellipses. The
latest 35% radius increase retained essentially the same small receiving area.
Asset freshness, passing tests and reviewers agreeing with that narrow proposal
did not establish the requested visual result.

## Bounded correction

1. Reuse the original 56-droplet High preset as the moderately high candidate.
   The art task exports its four seeds into the existing normalized landing
   schema, preserving distribution, lifetimes, delays and floor kernels. Use a
   single enclosing native region per physical family, not a full cloud emitted
   separately into each of several small regions. Inspect the result at actual
   gameplay scale before calling it accepted.
2. Ordinary blood gets broader authored family geometry through its existing
   passive body-response profile. Piercing stays more directional, slashing
   wider, blunt more local. Existing propagation, support admission and player
   visibility still select recorded receiving cells. This intentionally changes
   ordinary blood's receiving tiles; native state remains authoritative.
3. Preserve bone/corrosive/dread native layouts and their existing presentation
   templates for this correction. Their receiving tiles are whole-tile gameplay
   conditions; enlarging an art container would also enlarge hazard reach. An
   authored per-material template override is sufficient in the existing JSON;
   no renderer material switch or additional sampler is needed.
4. Restore the original readable airborne tangent tails through authored media
   values. Preserve fixed historical wound sources, target landing geometry,
   actual arrival reveal and absolute-time replay. Blood still accumulates one
   unit per tile per real qualifying injury, capped at five. Do not simulate
   particle entities in the backend or let pixels select native conditions.

Native ellipses describe coarse receiving coverage; organic marks need not fill
every pixel. This slice does not claim exact reproduction of the original field:
the existing normalized renderer retargets from the historical wound and scales
kernel offsets with accumulation. The original kept some satellite offsets
fixed. No new kernel-growth vocabulary is necessary to evaluate this correction.

## Validation boundary

Input: real discovered attacks over ordinary turns, saved from both actors.
Output: serialized receiving state and four-camera footage showing airborne
spread, visible marks on neighboring tiles, and growth after repeated hits.

Add one visual behavior regression that the compact implementation fails:
ordinary blood has visible floor marks across multiple neighboring cells, with
greater visible coverage after five hits. Retain native door/height admission,
later observation, seekable landing, saturation and hazard-entry tests. Recapture
the selected native inputs because their geometry changes. Inspect first hit,
flight and five-hit aftermath, with the original high reference alongside them.
Keep the old gallery as evidence; do not replace visual judgment with test counts.

## Independent reviews

Anti-slop and anti-OOP/ECS reviewers independently identified the shared-global
layout/template trap: widening all materials would silently enlarge harmful
cells. Both recommend ordinary-blood-specific authored data through the shared
processor, preserving other profiles. Neither requested another handler, event,
clock, schema hierarchy or pixel-based gameplay collision system. Final code
review and visual results remain to be recorded.

## Implemented data and measured comparison

The art handoff preserves the original High56 goals, delays, lifetimes, sizes
and 375–390 floor kernels per seed. One fixed normalization basis is used across
all four seeds: center `(.5, 0)`, radii `(2.5, 1.7)`. A smaller proposed basis
would clip an outlier; squeezing that basis into the initially proposed native
sizes would again reduce the artwork too far. The resulting native blood data:

| Family | Center | Radii | Unobstructed candidate cells at angle zero |
| --- | --- | --- | --- |
| Piercing | `(.45, 0)` | `(2.25, 1.45)` | 18 |
| Slashing | `(.42, 0)` | `(2.1, 1.6)` | 20 |
| Blunt | `(0, 0)` | `(1.5, 1.5)` | 9 |

These are receiving containers, not counts of visibly blood-covered tiles.
Recorded piercing replay actually has visible pixels on six cells after one
hit and seven after five; substantial marks (32+ alpha pixels in a full-size
projected tile) appear on four/five cells. Slashing has six/nine visible cells,
three/six with substantial marks. This distinction is why hazardous materials
retain their compact geometry. No claim is made that every pixel inside the
receiving container is coated.

At camera zero and scale one, summed projected floor alpha coverage grows from
1,186 to 4,512 pixels for piercing and 1,090 to 3,818 for slashing. Hits six and
seven preserve the fifth-hit field exactly. These are measurements of two real
saved histories, not mandatory dimensions or per-frame runtime diagnostics.

The existing media loader now accepts per-material template/tail/frame values.
Only blood selects the new templates, 35ms tails, 3–12px limits, 2px snapping and
26-frame track. The last possible critical particle lasts about 1.002 seconds,
inside that 1.083-second track. The unchanged global compact data still supplies
all other substances. No sampler or floor-painter code was changed.

Both final reviewers approved the ownership and implementation; the anti-slop
reviewer independently ran the two new cross-tile image regressions. The art
author inspected first-flight, first-floor and accumulated four-camera images,
finding a plausible moderately-high result below the original96 reference.
That is a still-image assessment; the full gameplay footage remains the review
artifact for motion and user taste.

## Validation results

The focused native/replay/media run had 102 passing tests and one overly exact
floating-point comparison (`1.55` versus `1.5499999999999998` after converting
tile-local geometry back to world coordinates). It now compares geometry with
numeric tolerance. The whole native body-residue module, fear-entry scenarios
and weapon-motion review tests subsequently passed: 60 tests, 9.34 seconds.
The affected production modules typecheck with zero errors. The two new pixel
regressions also passed independently in the anti-slop review.

Initial captures passed 6/6 for ordinary piercing and repeated piercing/slashing,
then 22/22 for criticals, other weapon families, north/reverse direction, doors,
raised support and ledge. The second matrix has zero reported media gaps.
All are real discovered attacks; the final combined gallery only replays saved
player packets. Both participants retain independent subjective recordings.

Inspected four-camera output shows irregular outward spray and floor growth.
Open-door aftermath reaches through the boundary, closed-door aftermath stays
on admitted floor, raised-floor marks stay at their support height, and ledge
marks stop at the admitted support. This does not introduce cross-height flight
or wall splats. The authored same-support rule is unchanged.

Final combined saved-only replay: **28/28 clips passed**, 3,260 four-camera
frames, zero reported media gaps. Cases cover ordinary/critical physical
families, direction, open/closed doors, raised/ledge supports and seven-hit
piercing/slashing accumulation. Every card is one of the two native observer
perspectives. Earlier rejected galleries remain intact for comparison.

## Follow-up: the example creatures must match their materials

User correction: bone examples should use skeletons, preferably the premade
Undead pack; toxic examples can use orcs for now. Use existing Skeleton Archer
materialization and packaged rig for bone catalog rows, including the separate
actor in the mixed-material case. Import selected original Orc01 sheets from
the owned Orcs/Goblins pack and bind them to native Orc identity. An explicit
review `creature_identity` selects that real creature; the existing corrosive
response is composed on this fixture before deployment/capture. Label its
existing acid behavior clearly. Do not alter canonical Orc biology, invent new
poison rules or add a permanent monster factory for an example selection.

Anti-slop and anti-OOP/ECS reviewers approved this bounded approach. Both
verified Orc has no existing body handler and Skeleton Archer already has its
bone response. Validate recorded creature identity, body-release/floor facts,
and real single/repeated-hit clips from both observers and all four cameras.

Implemented: bone catalog entries select the existing packaged Skeleton Archer;
the mixed case also materializes that real creature. Orc01 uses 14 exact original
body/shadow sheets (15 frames × eight directions) through a normal rig binding.
The review Orc carries the native Orc identity and its explicitly composed
corrosive response. No renderer exception or canonical creature change.

Validation: 25 body/residue replay tests pass, including seven real hits against
each requested creature, retained identity, release material and floor state
from both observers. Changed Python modules typecheck clean. The
[14-clip material gallery](http://127.0.0.1:8767/runs/20260920T002005Z-c8c90f/index.html)
passes across 2,938 four-camera frames, zero media gaps. Premade skeleton and orc
poses/injury output were visually inspected. This unit changes the selected
creatures; counterpart footprint/amount behavior is unchanged.
