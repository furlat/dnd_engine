# Doors and trap destruction integration

The user authorizes integrating `DOORS-AND-TRAPS-PRODUCTION-HANDOFF.md` while
away. The prior trap/portal/material chunk is complete. Upright portals and the
broader prefab/wall inventory remain deferred. This document owns the new chunk.

## Requested behavior and observable boundary

Actual door interactions play the supplied smooth opening/closing bank and keep
its matching endpoint. Actual attacks damage and destroy doors and blade/crusher
hardware. Destruction leaves the appropriate persistent remains; clear passages
are traversable, while an explicitly authored jammed outcome retains its stated
channels. Broken mechanisms cannot strike again; their independent plates may
still control other targets. All presentation reconstructs from recorded public
events, including initial world disclosure, after the engine is reset.

## Evidence from the live tree

- DirectionalDoor already has boundary placement, native open/close, occupied
  closure checks and held-control retries. It inherits the ordinary item damage
  path but currently defaults to no Health and untargetable. Material is hardcoded
  wood, extent two steps, and rendering is a binary generic frame/leaf.
- Blade/crusher behavior is FiniteTrap, a spatial condition. AttackObject targets
  ordinary items. A native probe confirms an item-anchored spatial condition is
  already removed when its hardware item is destroyed. Reuse that lifecycle.
- A second probe reproduces destruction during activation's EFFECT callback:
  the condition is removed but fire continues applying its payload. Recheck the
  actual mechanism admission before unapplied consequences; do not roll back
  damage or other effects that have already completed.
- Existing destruction events disclose an observed object and replacement. The
  current remnant is an inert center item, suitable for cannons but insufficient
  for a boundary door whose remnant can still block movement.
- Indoor opening has geometry depth for all 24 poses/both swings. Recovered doors
  and destruction banks lack matching depth; supplemental original-geometry
  exports are requested from the asset task. Intact trap masks are invalid for
  destruction. Open-door destruction entries are also requested to avoid a
  cosmetic snap to closed.

## Native changes

1. Use authored passive door profiles for the ten recovered families and six
   indoor designs. Retain stable item identity, physical material, mechanism,
   legal swing, extent and explicit closed channels. Keep the existing ten-foot
   envelope unless a native authoring contract establishes a different height;
   do not derive dimensions from sprite bounds. Different styles share providers.
2. Persist the selected swing so closing and later observers use the same bank.
   Lift mechanisms remain lifts. Keep existing use actions and control links.
   Make supported doors attackable with ordinary Health and explicitly authored
   simple HP; avoid introducing an unrelated resistance/balance system.
3. Extend the existing passive remnant description only enough to retain authored
   placement capability and structural channels. An inert boundary remnant keeps
   boundary direction/base/orientation; center cannon remains keep their existing
   behavior. Clear and jammed outcomes have distinct identities and explicit
   channels. Decorative side fragments never imply an intact door leaf.
4. Compose blade/crusher hardware from ordinary damageable items and the existing
   WORLD_OBJECT-anchored FiniteTrap. Preserve the exact mechanism relationship;
   no new health or readiness authority in the spatial condition. Hardware removal
   removes that condition, while plate ownership/control links stay independent.
   Preserve existing hazard discovery; do not disclose a concealed mechanism via
   a newly listed object. Public relationships are limited to actually disclosed
   participants. Use the existing native content/constructor registration path.
5. Recheck liveness after interception callbacks and before still-unapplied trap
   payloads. Verify destroyed hardware cannot rearm or accept later plate pulses.

## Presentation and delivered data

- Register every delivered family explicitly. Keep metadata in small checked-in
  JSON and rasters demand-loaded; no runtime file audits, hashes or source scans.
- Reuse finite world transitions and the existing object-destruction fact. Extend
  the shared authored bank vocabulary for sample times, pivots, persistent
  endpoints and depth registration, instead of one executor per door family.
- Indoor opening uses 24 samples over 0.8 seconds. Recovered doors retain their
  declared 12-frame/16-fps timing. Trap destruction uses the actual 14 nonuniform
  sample times ending at 5.958333 seconds, not a guessed frame rate.
- Register each bank's own cell/pivot/scale. Indoor destruction uses 384-pixel
  cells/pivot 192,272; intact indoor art uses 256/pivot128,208. Recovered desert
  C7/C9 are 320/pivot160,241.92. Apply boundary mounting exactly once and keep
  floor base height independent of image size.
- Use geometry depth with the existing fixture painter partition to keep walls,
  actors, leaf and preserved arch correctly ordered. Never paste intact masks
  over a destruction bank or use an always-front leaf.
- Native destruction commits at damage contact. Settled open doors require their
  matching open-entry bank; closed doors and ready/deployed mechanisms use their
  corresponding entries. A mechanism destroyed within activation binds at the
  recorded activation contact. Arbitrary interruption midway through a door's
  opening is outside the supplied art and this implementation; no speculative
  transition scheduler or delayed mechanical disable is added.
- Preserve last destruction frame after seek/reload, with no return to an intact
  frame. Trap wreck art keeps the arch, and contributes no invented tile blocker.

## Validation and review delivery

Read HOW_TO_TEST.md before adding tests. Exercise real commands and observable
outputs: open/close both ways; occupied close; material/placement/profile identity;
nonlethal/lethal attacks; clear and jammed traversal; elevated door placement;
hardware destruction during activation; later plate pulses; plate controlling a
second surviving mechanism; public JSON replay after engine reset; hidden and
visible observers; persistent wreck after fresh disclosure and seeking.

Produce paired saved-event clips with four-camera mosaics. Include walls adjoining
the door, actors on both sides and walking through, closing and breaking closed
and open doors, deployed/concealed trap break entries, subsequent harmless plate
activation and passage through the broken arch. Cover all explicit families in
catalog/data checks and representative mechanisms in longer gameplay narratives;
provide short visual variants so the user can inspect all delivered appearances.
Keep approved unrelated spell, portal and blood behavior unchanged.

Anti-slop reviewer: graphics_antislop. Anti-OOP/ECS reviewer: graphics_ecs_review.
Both review this bounded plan before edits and review the final native/public
contract. Art intake by gore_antislop is independent of backend implementation.
Record review amendments, actual checks, gallery links and remaining art limits
below; automated capture success is not human visual approval.

## Review decisions

Both reviewers approved the bounded plan. Geometry review requires keeping the
source ground pivot distinct from each pose's boundary mounting pivot. Padding
adds to the same mount during destruction. The depth decoder needs the projected
offset between source origin and native boundary origin; it must also partition
overlapping wall commands when there is no actor in front of the doorway.

Native review confirmed existing item anchoring performs trap cleanup, so no new
trap-item class/cleanup registry is needed. Hardware perception delegates to the
existing mechanism's discovery result; the public anchor is disclosed only with
its object. Wrecks retain a small factual prior-state record (door open/swing or
mechanism mode), allowing fresh disclosure to select the same last frame.

Use the current two-step native envelope as an explicit gameplay choice, with
simple wood18/metal27 HP. Those numbers are content defaults, not measurements
or inferred balance from artwork. Existing object damage rules remain the owner.
Extend plates only for an authored tuple of activation targets to exercise the
requested surviving connection. Single held-control behavior is unchanged; mixed
held/pulse control batches and a general signal network are outside this chunk.

## Implementation and validation record

The native implementation has **16 authored door profiles and 12 trap hardware
profiles**, using the existing constructor registry. Door profiles select native
material, mechanism and swing; the two-step envelope and wood18/metal27 HP remain
explicit content defaults. The old generic `build_directional_door()` retains its
existing health/targeting defaults. Newly authored doors are damageable.

Hardware is an ordinary item with Health plus its WORLD_OBJECT-anchored mechanism.
Discovery delegates to the existing condition; a public `anchor_item_uuid` appears
only when its object is disclosed. Destruction snapshots physical configuration
before removal and leaves an inert remnant with the same placement. Removal stops
still-unapplied trap consequences, without reversing completed damage. A pressure
plate can send a finite tuple of pulses, and keeps working with surviving targets.
The single held-control behavior is unchanged.

Presentation has one passive `environment_art.json` catalog, pure finite pose
selection, and a small Pygame raster adapter. Matching geometry depth partitions
against actors and adjoining walls. Source pose offsets, boundary mounting pivots
and source ground origins are separate authored values; screen rounding does not
enter depth coordinates. Runtime loading does not audit files or compute hashes.
The native backend contains no frame, duration or sprite fields.

Independent native/anti-slop review approved the resulting ownership and cleanup.
The native selection passes **123 tests**, including 48 new cases; selected native
and presentation implementation typechecks are clean. Saved public replay checks
exercise both observers after engine reset, every indoor open/close frame, actual
damage contact, exact destruction sample times, backward seeking and fresh
initialization containing only a persistent wreck. Gallery and final renderer
regression results are recorded below when their runs complete.

### Final evidence

- [Complete review: 146/146 observer clips](http://127.0.0.1:8767/runs/20260921T012108Z-a7b4d4/index.html),
  comprising 118 door views and 28 trap views, 24,503 four-camera frames, no
  reported presentation gaps. The page references the original saved inputs and
  trace files; it selects the corrected rerenders of the four offset door families.
- Native selection: **123 passed**. Broader gameplay/presentation selection:
  **202 passed**, including the recorder's real export/replay cases. New scenario
  and renderer checks: **48 verified** (28 native history/replay + 20 presentation).
  After the initialization correction, player projection and cold presentation
  boundaries pass another **19 checks**. These selections overlap; do not add them
  into a claimed whole-repository total. Selected implementation and test
  typechecks and diff whitespace checks pass.
- The old CR-I architecture module's five failures were historical source/row
  assertions, not gameplay contracts. Its SHA checks, source scans, frozen counts
  and nested test-collection audit were removed. Current initialized declaration,
  constructor, behavior and visible-item contracts remain: **5 module tests and
  36 related tests pass**. Historical ledgers were left as documentation.
- Intake now contains **146 banks**, including all **122 supplementary depth
  exports**. Exact first/final raster comparisons check recovered open-entry art
  against the existing open pose and wreck, with no runtime audit or source hash.
  Source `geometry.projections[].ground_origin_px` supplies per-pose depth origins;
  image mounting pivots remain unchanged.

Actual defects corrected during integration were local and reproducible:
destruction binding referenced another branch's locals; the gallery producer used
a positional call to a keyword-only scenario; initialization omitted native world
edit/elevation facts; and four recovered banks applied the workshop pose offset
in the wrong direction. The workshop maps source rows to physical edges, so a
known physical edge selects `source = physical - offset`. Saved-input comparison
showed the corrected gate fitting all four views; no speculative aperture clipping
was introduced. The raised fixture itself now authors terrain with real events,
and tests assert received support, not merely native object placement.

Visual inspection covered indoor and recovered opening/closing, open and closed
breakage, the corrected lift gate, trap collapse and subsequent plate use, plus
raised passage. This supports the integration; it is not a claim that the human
has approved every new clip. Broader thin-wall/prefab composition, unrelated wall
styles and upright portals remain outside this chunk.
